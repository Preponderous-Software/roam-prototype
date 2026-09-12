# @author Daniel McCoy Stephenson
# @since August 6th, 2022
import os
import shutil
import sys

from appPaths import getBundleDirectory
from gameLogging.logger import getLogger
from rendering.displayInfo import getScreenSize

_logger = getLogger(__name__)

# Anonymous usage reporting (see src/usageReporting.py). The three
# usageReporting* settings below are read from config.yml with these defaults,
# so an installation whose user config predates them still reports until the
# player sets usageReportingEnabled: false. The key identifies the program
# "roam" to the trace service and is not a secret.
USAGE_REPORTING_ENDPOINT_DEFAULT = "https://trace.danielstephenson.dev"
USAGE_REPORTING_KEY_DEFAULT = "G8sLnYKFvDhXETxGBQHio6XoLWavuBAjrrvoeoHit2M"


class Config:
    @staticmethod
    def getVersion():
        # The build's version string, read from the bundled version.txt (which
        # is the repository root from source and the PyInstaller bundle when
        # frozen). Returns "unknown" if the file is missing.
        versionPath = os.path.join(getBundleDirectory(), "version.txt")
        try:
            with open(versionPath, "r", encoding="utf-8") as versionFile:
                return versionFile.read().strip()
        except OSError:
            return "unknown"

    @staticmethod
    def getUserDataDirectory():
        # Writable per-user directory for config and screenshots. On Windows
        # this is %APPDATA%\Roam and on macOS ~/Library/Application Support/Roam,
        # so writes succeed even when the game is installed to a read-only
        # location (Program Files, /Applications). Other platforms use the
        # repository/bundle root (the current from-source behavior). (Saves have
        # their own getSavesBaseDirectory, which resolves the same way.)
        if os.name == "nt":
            appData = os.environ.get("APPDATA")
            if appData:
                return os.path.join(appData, "Roam")
        elif sys.platform == "darwin":
            return os.path.join(
                os.path.expanduser("~"), "Library", "Application Support", "Roam"
            )
        return getBundleDirectory()

    @staticmethod
    def getBundledConfigFilePath():
        # The config.yml shipped with the app (read-only when frozen). Uses
        # os.path (not pathlib) so it stays correct under os.name monkeypatching
        # in cross-platform tests.
        return os.path.join(getBundleDirectory(), "config.yml")

    @staticmethod
    def getConfigFilePath():
        # The user's read/write config file, in the writable user-data
        # directory. From source this resolves to the repository root, matching
        # the previous behavior.
        return os.path.join(Config.getUserDataDirectory(), "config.yml")

    @staticmethod
    def ensureUserConfigExists():
        # On first run, seed the writable user config from the bundled defaults
        # so shipped settings are preserved and the file is writable. No-op when
        # the user config and the bundled config are the same file (from source)
        # or the user config already exists.
        userConfig = Config.getConfigFilePath()
        bundled = Config.getBundledConfigFilePath()
        if str(userConfig) == str(bundled) or os.path.exists(userConfig):
            return
        if os.path.exists(bundled):
            os.makedirs(os.path.dirname(userConfig), exist_ok=True)
            shutil.copyfile(bundled, userConfig)

    @staticmethod
    def getSavesBaseDirectory():
        # ROAM_SAVE_DIR env var overrides everything — used in Docker deployments
        # to point at a mounted volume (e.g. /data).
        envDir = os.environ.get("ROAM_SAVE_DIR")
        if envDir:
            return envDir
        # On Windows store under %APPDATA%; on macOS under ~/Library/Application
        # Support/Roam/saves; everywhere else use the repo-relative "saves" dir.
        if os.name == "nt":
            appData = os.environ.get("APPDATA")
            if appData:
                return os.path.join(appData, "Roam", "saves")
        elif sys.platform == "darwin":
            return os.path.join(Config.getUserDataDirectory(), "saves")
        return "saves"

    @staticmethod
    def getDefaultSaveDirectory():
        # The default save slot, used when config.yml does not pin
        # pathToSaveDirectory explicitly.
        return os.path.join(Config.getSavesBaseDirectory(), "defaultsavefile")

    @staticmethod
    def parseConfigValue(value):
        value = value.strip()
        if value == "":
            return None
        lowerValue = value.lower()
        if lowerValue == "true":
            return True
        if lowerValue == "false":
            return False
        if lowerValue == "none" or lowerValue == "null":
            return None
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            return value[1:-1]
        if value.startswith("[") and value.endswith("]"):
            listText = value[1:-1].strip()
            if listText == "":
                return []
            return [
                Config.parseConfigValue(item.strip()) for item in listText.split(",")
            ]
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            return value

    @classmethod
    def readConfigFile(cls):
        configValues = {}
        configFilePath = cls.getConfigFilePath()
        if not os.path.exists(configFilePath):
            return configValues
        try:
            with open(configFilePath, "r", encoding="utf-8") as configFile:
                for line in configFile:
                    strippedLine = line.strip()
                    if strippedLine == "" or strippedLine.startswith("#"):
                        continue
                    keyAndValue = strippedLine.split(":", 1)
                    if len(keyAndValue) != 2:
                        continue
                    key = keyAndValue[0].strip()
                    value = cls.removeInlineComment(keyAndValue[1]).strip()
                    configValues[key] = cls.parseConfigValue(value)
        except (OSError, UnicodeDecodeError):
            return configValues
        return configValues

    @staticmethod
    def removeInlineComment(value):
        quoteCharacter = None

        def isEscapedQuote(index):
            backslashCount = 0
            currentIndex = index - 1
            while currentIndex >= 0 and value[currentIndex] == "\\":
                backslashCount += 1
                currentIndex -= 1
            return backslashCount % 2 == 1

        for i, character in enumerate(value):
            if character in ('"', "'") and not isEscapedQuote(i):
                if quoteCharacter is None:
                    quoteCharacter = character
                elif quoteCharacter == character:
                    quoteCharacter = None
            elif character == "#" and quoteCharacter is None:
                return value[:i]
        return value

    @staticmethod
    def getBoolValue(configValues, key, default):
        value = configValues.get(key)
        if isinstance(value, bool):
            return value
        return default

    @staticmethod
    def getIntValue(configValues, key, default):
        value = configValues.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        return default

    @staticmethod
    def getFloatValue(configValues, key, default):
        value = configValues.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        return default

    @staticmethod
    def getStringValue(configValues, key, default):
        value = configValues.get(key)
        if isinstance(value, str) and value.strip() != "":
            return value
        return default

    @staticmethod
    def getColorValue(configValues, key, default):
        value = configValues.get(key)
        if not isinstance(value, (list, tuple)):
            return default
        if len(value) != len(default):
            return default

        colorValues = []
        for colorValue in value:
            if isinstance(colorValue, bool) or not isinstance(colorValue, int):
                return default
            if colorValue < 0 or colorValue > 255:
                return default
            colorValues.append(colorValue)
        return tuple(colorValues)

    MIN_WINDOW_SIZE = 400

    def __init__(self):
        self.ensureUserConfigExists()
        configValues = self.readConfigFile()
        # Config is constructed before the frontend creates the window, so the
        # default window size is computed from the OS screen size via the
        # frontend-adjacent displayInfo helper (which keeps the pygame display
        # query out of this backend-neutral module — epic #433 / #463).
        screenWidth, screenHeight = getScreenSize()
        displayDimensionDefault = screenHeight * 0.90

        # Resolve effective display dimensions: manual displayWidth /
        # displayHeight take priority, then savedWindowWidth /
        # savedWindowHeight, then the computed default.
        savedW = configValues.get("savedWindowWidth")
        savedH = configValues.get("savedWindowHeight")
        if (
            isinstance(savedW, (int, float))
            and not isinstance(savedW, bool)
            and isinstance(savedH, (int, float))
            and not isinstance(savedH, bool)
        ):
            savedW = float(savedW)
            savedH = float(savedH)
            savedW = max(savedW, self.MIN_WINDOW_SIZE)
            savedH = max(savedH, self.MIN_WINDOW_SIZE)
            if savedW <= screenWidth and savedH <= screenHeight:
                displayDimensionDefaultW = savedW
                displayDimensionDefaultH = savedH
            else:
                displayDimensionDefaultW = displayDimensionDefault
                displayDimensionDefaultH = displayDimensionDefault
        else:
            displayDimensionDefaultW = displayDimensionDefault
            displayDimensionDefaultH = displayDimensionDefault

        # static (cannot be changed in game)
        self.displayWidth = self.getFloatValue(
            configValues, "displayWidth", displayDimensionDefaultW
        )
        self.displayHeight = self.getFloatValue(
            configValues, "displayHeight", displayDimensionDefaultH
        )
        self.black = self.getColorValue(configValues, "black", (0, 0, 0))
        self.white = self.getColorValue(configValues, "white", (255, 255, 255))
        self.playerMovementEnergyCost = self.getFloatValue(
            configValues, "playerMovementEnergyCost", 0.2
        )
        self.playerInteractionEnergyCost = self.getFloatValue(
            configValues, "playerInteractionEnergyCost", 0.05
        )
        self.runSpeedFactor = self.getFloatValue(configValues, "runSpeedFactor", 2)
        self.energyDepletionRate = self.getFloatValue(
            configValues, "energyDepletionRate", 0.01
        )
        self.playerInteractionDistanceLimit = self.getIntValue(
            configValues, "playerInteractionDistanceLimit", 5
        )
        self.ticksPerSecond = self.getIntValue(configValues, "ticksPerSecond", 30)
        self.gridSize = self.getIntValue(configValues, "gridSize", 17)
        self.worldBorder = self.getIntValue(
            configValues, "worldBorder", 0
        )  # 0 = no border
        self.excrementDecayTicks = self.getIntValue(
            configValues, "excrementDecayTicks", 30 * 60 * 2
        )  # 2 minutes at 30 tps
        self.cropGrowthTicks = self.getIntValue(
            configValues, "cropGrowthTicks", 1800
        )  # 1 minute per stage at 30 tps
        self.pathToSaveDirectory = self.getStringValue(
            configValues, "pathToSaveDirectory", Config.getDefaultSaveDirectory()
        )
        self.webHttpPort = self.getIntValue(configValues, "webHttpPort", 8080)
        self.webWsPort = self.getIntValue(configValues, "webWsPort", 8765)
        # Read-only REST API for external client tools (issue #231). Opt-in and
        # on a distinct port from the web frontend's webHttpPort above.
        self.restEnabled = self.getBoolValue(configValues, "restEnabled", False)
        self.restPort = self.getIntValue(configValues, "restPort", 8090)

        # dynamic (can be changed in game)
        self.debug = self.getBoolValue(configValues, "debug", True)
        self.fullscreen = self.getBoolValue(configValues, "fullscreen", False)
        self.autoEatFoodInInventory = self.getBoolValue(
            configValues, "autoEatFoodInInventory", True
        )
        self.removeDeadEntities = self.getBoolValue(
            configValues, "removeDeadEntities", True
        )
        self.showMiniMap = self.getBoolValue(configValues, "showMiniMap", True)
        self.cameraFollowPlayer = self.getBoolValue(
            configValues, "cameraFollowPlayer", True
        )
        self.limitTps = self.getBoolValue(configValues, "limitTps", True)
        self.dayNightCycleEnabled = self.getBoolValue(
            configValues, "dayNightCycleEnabled", True
        )
        self.dayNightCycleLengthTicks = self.getIntValue(
            configValues,
            "dayNightCycleLengthTicks",
            self.ticksPerSecond * 30 * 60,
        )  # 30 minutes at the configured ticksPerSecond
        self.pushableStone = self.getBoolValue(configValues, "pushableStone", True)
        self.checkForUpdates = self.getBoolValue(configValues, "checkForUpdates", True)
        self.npcEnabled = self.getBoolValue(configValues, "npcEnabled", True)
        self.npcCount = self.getIntValue(configValues, "npcCount", 1)
        self.npcMode = self.getStringValue(configValues, "npcMode", "npc")
        self.npcSimulationRadius = self.getIntValue(
            configValues, "npcSimulationRadius", 1
        )
        # Anonymous usage reporting (on by default; opt out with
        # usageReportingEnabled: false). usageReportingAcknowledged records
        # whether the setting is present in the file at all, which is how the
        # one-time first-run notice knows it has already been shown.
        self.usageReportingEnabled = self.getBoolValue(
            configValues, "usageReportingEnabled", True
        )
        self.usageReportingEndpoint = self.getStringValue(
            configValues, "usageReportingEndpoint", USAGE_REPORTING_ENDPOINT_DEFAULT
        )
        self.usageReportingKey = self.getStringValue(
            configValues, "usageReportingKey", USAGE_REPORTING_KEY_DEFAULT
        )
        self.usageReportingAcknowledged = "usageReportingEnabled" in configValues

        _logger.debug(
            "config loaded",
            displayWidth=self.displayWidth,
            displayHeight=self.displayHeight,
            ticksPerSecond=self.ticksPerSecond,
            gridSize=self.gridSize,
            worldBorder=self.worldBorder,
            fullscreen=self.fullscreen,
            debug=self.debug,
        )

    def getRoomsDirectory(self):
        """Return the directory holding per-room JSON files: the single source
        of truth for the `<saveDir>/rooms` location."""
        return self.pathToSaveDirectory + "/rooms"

    def getRoomFilePath(self, x, y, z=0):
        """Return the path to a room's JSON save file. Surface rooms (z=0) use
        the legacy room_x_y.json filename so existing saves load unchanged.
        Underground rooms use room_x_y_z.json."""
        base = self.getRoomsDirectory() + "/room_" + str(x) + "_" + str(y)
        if z == 0:
            return base + ".json"
        return base + "_" + str(z) + ".json"

    def _writeKeyValues(self, savedValues, errorMessage):
        configFilePath = self.getConfigFilePath()
        lines = []
        if os.path.exists(configFilePath):
            try:
                with open(configFilePath, "r", encoding="utf-8") as configFile:
                    lines = configFile.read().splitlines()
            except (OSError, UnicodeDecodeError):
                lines = []

        updatedKeys = set()
        newLines = []
        for line in lines:
            stripped = line.strip()
            if stripped == "" or stripped.startswith("#"):
                newLines.append(line)
                continue
            parts = stripped.split(":", 1)
            if len(parts) == 2:
                key = parts[0].strip()
                if key in savedValues:
                    newLines.append(key + ": " + savedValues[key])
                    updatedKeys.add(key)
                    continue
            newLines.append(line)

        for key, value in savedValues.items():
            if key not in updatedKeys:
                newLines.append(key + ": " + value)

        try:
            with open(configFilePath, "w", encoding="utf-8") as configFile:
                configFile.write("\n".join(newLines) + "\n")
        except OSError as e:
            _logger.warning(
                errorMessage,
                error=str(e),
                path=str(configFilePath),
            )

    def acknowledgeUsageReporting(self):
        # Persist usageReportingEnabled so the first-run notice is shown once:
        # its presence in the file is the marker. Writes the current value, so
        # a player who already opted out stays opted out.
        self._writeKeyValues(
            {
                "usageReportingEnabled": "true"
                if self.usageReportingEnabled
                else "false"
            },
            "failed to save usage reporting setting to config file",
        )
        self.usageReportingAcknowledged = True

    def saveWindowSize(self, width, height):
        width = max(int(width), self.MIN_WINDOW_SIZE)
        height = max(int(height), self.MIN_WINDOW_SIZE)
        savedValues = {
            "savedWindowWidth": str(width),
            "savedWindowHeight": str(height),
        }
        self._writeKeyValues(savedValues, "failed to save window size to config file")
