import os
import sys


_USAGE_TEMPLATE = """Usage: {program} [OPTIONS]

Roam - a procedurally generated 2D survival game.

Options:
  --text        Force text / TUI mode instead of the graphical frontend. Text
                mode is selected automatically when no display is available,
                so this is only needed to override a working display.
  --selftest    Start up, load assets/schemas/config, then exit without opening
                a window. Used to verify a packaged build.
  -h, --help    Show this message and exit.
"""

# Flags main() acts on. --web is accepted but deliberately left out of the usage
# text: it is broken end to end (see issue #550), and the supported way to play
# in a browser is web/serve.py, documented in README.md.
_KNOWN_FLAGS = frozenset({"--text", "--web", "--selftest", "--help", "-h"})


def _programName(argv):
    """Name to print in usage / error output — 'roam.py' from source, 'Roam.exe'
    or 'Roam' from a packaged build."""
    return os.path.basename(argv[0]) if argv and argv[0] else "roam.py"


def _usage(argv):
    return _USAGE_TEMPLATE.format(program=_programName(argv))


def _wantsHelp(argv):
    return "--help" in argv[1:] or "-h" in argv[1:]


def _unknownArguments(argv):
    """Return the arguments main() does not recognise, in the order given."""
    unknown = []
    for argument in argv[1:]:
        if argument in _KNOWN_FLAGS:
            continue
        # macOS passes a process serial number to a launched .app bundle; it is
        # not ours to reject.
        if argument.startswith("-psn_"):
            continue
        unknown.append(argument)
    return unknown


# ---------------------------------------------------------------------------
# Early display probe — must run before any import that pulls in the logger.
# config.py and bootstrap.py both import gameLogging.logger at module level,
# which configures log output (stderr vs file) at import time. We set LOG_FILE
# here so headless auto-detection redirects logs to a file before the logger
# is ever initialised, preventing log lines from corrupting the TUI display.
# ---------------------------------------------------------------------------
def _earlyDetectTextMode():
    if "--text" in sys.argv or "--web" in sys.argv:
        return True
    try:
        import pygame as _pg

        _pg.display.init()
        driver = _pg.display.get_driver()
        _pg.display.quit()
        return driver in ("dummy", "offscreen")
    except Exception:
        return True


if _wantsHelp(sys.argv):
    # Printing usage must not initialise a display or create a log file.
    pass
elif _earlyDetectTextMode() and os.environ.get("LOG_FILE") is None:
    os.environ["LOG_FILE"] = "roam.log"

# ---------------------------------------------------------------------------
# Remaining imports (logger is now configured with the correct destination)
# ---------------------------------------------------------------------------
import json

try:
    import pygame
    from rendering.pygameFrontend import createFrontend

    _PYGAME_AVAILABLE = True
except ImportError:
    pygame = None
    _PYGAME_AVAILABLE = False

    def createFrontend(config):
        raise RuntimeError("pygame is not available in this environment")


from appPaths import prepareWorkingDirectory
from bootstrap import createContainer
from config.config import Config
from config.keyBindings import KeyBindings
from inventory.inventory import Inventory
from gameLogging.logger import getLogger
from lib.trace_client import TraceClient
from player.player import Player
from rendering.renderer import Renderer
from rendering.inputSource import InputSource
from rendering.clock import Clock
from rendering.textFrontend import createTextFrontend
from screen.configScreen import ConfigScreen
from screen.controlsScreen import ControlsScreen
from screen.codexScreen import CodexScreen
from screen.chestScreen import ChestScreen
from screen.inventoryScreen import InventoryScreen
from screen.mainMenuScreen import MainMenuScreen
from screen.optionsScreen import OptionsScreen
from screen.saveSelectionScreen import SaveSelectionScreen
from screen.screenType import ScreenType
from screen.statsScreen import StatsScreen
from stats.stats import Stats
from ui.status import Status
from screen.worldScreen import WorldScreen
from usageReporting import createTraceClient, showFirstRunNotice, versionTags
from world.tickCounter import TickCounter

_logger = getLogger(__name__)


# @author Daniel McCoy Stephenson
# @since August 8th, 2022
class Roam:
    def __init__(self, config: Config, textMode=False, frontend=None, traceClient=None):
        self.config = config
        self.textMode = textMode
        # Usage reporting is main()'s decision (settings, browser build, env);
        # a Roam built without a client — the Pyodide entry point, tests —
        # reports nothing.
        self.traceClient = (
            traceClient if traceClient is not None else TraceClient.disabled()
        )
        # The frontend owns the display + input lifecycle; the game depends only
        # on the Renderer/InputSource/Clock it provides (epic #433). Selecting a
        # different frontend swaps the whole backend with no game-logic change.
        if frontend is not None:
            self.frontend = frontend
        else:
            self.frontend = (
                createTextFrontend(config) if textMode else createFrontend(config)
            )
        self._initializeDependencies()
        _logger.info("game initialized", savePath=config.pathToSaveDirectory)

    def restart(self):
        """Reset all state for a new game session.

        Rebuilds the display via the frontend with the current config
        dimensions and clears cached singleton instances so all services are
        freshly constructed via the DI container.
        """
        self.frontend.reset()
        self._initializeDependencies()

    def _initializeDependencies(self):
        """Wire up the DI container and resolve all services and screens."""
        self.running = True
        self.frontend.setCaption("Roam" + " (" + self.config.pathToSaveDirectory + ")")

        # Create the DI container and register runtime dependencies.
        self.container = createContainer(self.config)
        self.tickCounter = self.container.resolve(TickCounter)
        # Screens/HUD auto-wire the backend-neutral Renderer (epic #433). The
        # room pipeline migrated off the raw Graphik, so the frontend no longer
        # needs to expose one — the text frontend has none.
        self.renderer = self.frontend.getRenderer()
        self.container.registerInstance(Renderer, self.renderer)
        # The input seam (epic #433, Phase 4): register the InputSource so
        # screens can read events/key state through it instead of pygame.
        self.inputSource = self.frontend.getInputSource()
        self.container.registerInstance(InputSource, self.inputSource)
        # Frame pacing through the Clock seam (#463) so worldScreen's game loop
        # no longer references pygame.time directly.
        self.clock = self.frontend.getClock()
        self.container.registerInstance(Clock, self.clock)
        self.status = self.container.resolve(Status)
        self.stats = self.container.resolve(Stats)
        self.player = self.container.resolve(Player)

        # Register KeyBindings: load overrides from config.yml.
        keyBindings = KeyBindings()
        keyBindings.loadFromConfig(Config.readConfigFile())
        self.container.registerInstance(KeyBindings, keyBindings)

        # Register the player inventory so InventoryScreen can auto-wire.
        self.container.registerInstance(Inventory, self.player.getInventory())

        # Resolve screens that can be fully auto-wired.
        self.worldScreen = self.container.resolve(WorldScreen)
        self.optionsScreen = self.container.resolve(OptionsScreen)
        self.mainMenuScreen = self.container.resolve(MainMenuScreen)
        self.statsScreen = self.container.resolve(StatsScreen)
        self.inventoryScreen = self.container.resolve(InventoryScreen)
        self.chestScreen = self.container.resolve(ChestScreen)
        self.configScreen = self.container.resolve(ConfigScreen)
        self.controlsScreen = self.container.resolve(ControlsScreen)
        self.codexScreen = self.container.resolve(CodexScreen)

        # SaveSelectionScreen needs a callback that cannot be auto-wired.
        self.container.register(
            SaveSelectionScreen,
            lambda: SaveSelectionScreen(
                self.container.resolve(Renderer),
                self.container.resolve(InputSource),
                self.container.resolve(Config),
                self.initializeWorldScreen,
            ),
        )
        self.saveSelectionScreen = self.container.resolve(SaveSelectionScreen)
        self.currentScreen = self.mainMenuScreen

    def initializeWorldScreen(self):
        self.worldScreen.initialize()
        # A save was opened (new or existing): the one usage action reported
        # besides startup. Version only — never the save name or path.
        self.traceClient.report("world-loaded", tags=versionTags())

    def quitApplication(self):
        if self.renderer.supportsImageLoading():
            w, h = self.renderer.getDisplaySize()
            self.config.saveWindowSize(w, h)
            # HUD layout is only mutable by mouse drag, which text mode has no
            # source of, so a text session must not write back offsets that
            # load() clamped to the much smaller terminal-equivalent display.
            self.worldScreen.hudDragManager.save(self.config)
        self.frontend.quit()
        quit()

    def run(self):
        while True:
            result = self.currentScreen.run()
            if result == ScreenType.MAIN_MENU_SCREEN:
                # Preserve current window dimensions so the restart
                # does not shrink a maximized/resized window.
                if self.renderer.supportsImageLoading():
                    w, h = self.renderer.getDisplaySize()
                    self.config.displayWidth = w
                    self.config.displayHeight = h
                    self.config.saveWindowSize(w, h)
                    # See quitApplication(): text mode never persists layout.
                    self.worldScreen.hudDragManager.save(self.config)
                _logger.info("returning to main menu")
                return "restart"
            if result == ScreenType.WORLD_SCREEN:
                self.currentScreen = self.worldScreen
            elif result == ScreenType.OPTIONS_SCREEN:
                self.currentScreen = self.optionsScreen
            elif result == ScreenType.STATS_SCREEN:
                self.currentScreen = self.statsScreen
            elif result == ScreenType.INVENTORY_SCREEN:
                self.currentScreen = self.inventoryScreen
                self.inventoryScreen.setInventory(self.player.getInventory())
            elif result == ScreenType.CHEST_SCREEN:
                self.currentScreen = self.chestScreen
                self.chestScreen.setInventory(self.player.getInventory())
                self.chestScreen.setChest(self.worldScreen.getActiveChest())
                self.chestScreen.setOnClose(self.worldScreen.saveActiveChestRoom)
            elif result == ScreenType.CONFIG_SCREEN:
                self.currentScreen = self.configScreen
            elif result == ScreenType.CONTROLS_SCREEN:
                self.currentScreen = self.controlsScreen
            elif result == ScreenType.CODEX_SCREEN:
                if self.currentScreen == self.optionsScreen:
                    self.codexScreen.setReturnScreen(ScreenType.OPTIONS_SCREEN)
                else:
                    self.codexScreen.setReturnScreen(ScreenType.WORLD_SCREEN)
                self.currentScreen = self.codexScreen
            elif result == ScreenType.SAVE_SELECTION_SCREEN:
                self.currentScreen = self.saveSelectionScreen
            elif result == ScreenType.NONE:
                _logger.info("shutting down")
                self.quitApplication()
                return
            else:
                _logger.error("unrecognized screen", screen=result)
                self.quitApplication()
                return
            _logger.info("screen transition", screen=str(result))


def runSelfTest():
    # Verify a frozen build can locate its bundled data (assets, schemas,
    # config). CI runs the packaged executable with --selftest to confirm the
    # bundle is complete without launching the interactive game loop.
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    try:
        pygame.init()
        pygame.image.load("assets/images/player_down.png")
        with open("schemas/tick.json") as f:
            json.load(f)
        Config()  # reads config.yml
        _logger.info("selftest passed")
        print("Roam selftest: OK")
        return 0
    except Exception as exc:
        _logger.error("selftest failed", error=str(exc))
        print("Roam selftest: FAILED -", exc)
        return 1


def _shouldUseTextMode(argv):
    """Return True when the text/TUI frontend should be used.

    --text forces text mode. Without it, try to initialise the pygame display
    subsystem; if SDL selects a headless driver (dummy / offscreen) or fails
    entirely, fall back to text mode so the game runs without a display server.
    """
    if "--text" in argv:
        return True
    try:
        pygame.display.init()
        driver = pygame.display.get_driver()
        pygame.display.quit()
        if driver in ("dummy", "offscreen"):
            _logger.info("no display detected; using text mode", driver=driver)
            return True
        return False
    except pygame.error as exc:
        _logger.info("display unavailable; using text mode", error=str(exc))
        return True


def main(argv):
    # Argument handling comes before Config(), so usage is still available when
    # configuration cannot be loaded.
    if _wantsHelp(argv):
        print(_usage(argv), end="")
        return 0

    unknown = _unknownArguments(argv)
    if unknown:
        program = _programName(argv)
        for argument in unknown:
            print(f"{program}: unrecognized argument: {argument}", file=sys.stderr)
        print(_usage(argv), end="", file=sys.stderr)
        return 2

    # Frozen executables start in an arbitrary working directory; make relative
    # asset/schema paths resolve against the bundle. No-op when run from source.
    prepareWorkingDirectory()

    if "--selftest" in argv:
        return runSelfTest()

    config = Config()

    # Anonymous usage reporting (src/usageReporting.py): a disabled client when
    # opted out, in the browser build, or under ROAM_USAGE_REPORTING=0, so
    # nothing below can block or raise on the network. The first-run notice is
    # logged once, before the frontend takes over the terminal in text mode.
    traceClient = createTraceClient(config)
    showFirstRunNotice(config)
    traceClient.report("startup", tags=versionTags())

    if "--web" in argv:
        from rendering.webFrontend import WebFrontend

        def _sessionGameLoop(session):
            # Route each browser session to its own save directory so multiple
            # players don't clobber each other's worlds.
            sessionConfig = config
            if hasattr(session, "sessionId") and session.sessionId:
                import os as _os

                sessionConfig = config.__class__.__new__(config.__class__)
                sessionConfig.__dict__.update(config.__dict__)
                sessionConfig.pathToSaveDirectory = _os.path.join(
                    config.__class__.getSavesBaseDirectory(),
                    session.sessionId,
                    "defaultsavefile",
                )
            roam = Roam(sessionConfig, frontend=session, traceClient=traceClient)
            # Web sessions have a fixed per-session save path — skip the main
            # menu's save selection screen and go straight to the world.
            roam.initializeWorldScreen()
            roam.currentScreen = roam.worldScreen
            try:
                while True:
                    result = roam.run()
                    if result != "restart":
                        break
                    roam.restart()
            except KeyboardInterrupt:
                pass

        try:
            WebFrontend(wsPort=config.webWsPort, httpPort=config.webHttpPort).serve(
                _sessionGameLoop
            )
        finally:
            traceClient.close()
        return 0

    roam = Roam(config, textMode=_shouldUseTextMode(argv), traceClient=traceClient)
    try:
        while True:
            result = roam.run()
            if result != "restart":
                break
            roam.restart()
    except KeyboardInterrupt:
        # Ctrl+C: exit cleanly rather than dumping a traceback.
        _logger.info("interrupted; shutting down")
    finally:
        # Always restore the frontend (e.g. put the terminal back to normal mode
        # in text mode), even on an interrupt or unexpected error.
        roam.frontend.quit()
        traceClient.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
