import os
import re
import select
import signal
import subprocess
import sys
import time

# Repo root: tests/integration/ -> tests/ -> <repo>. The game loads assets and
# resolves the saves directory relative to this, so the child runs here.
REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
)

_ANSI = re.compile(
    r"\x1b(?:"
    r"\[[0-9;?]*[A-Za-z]"  # CSI  ESC [ ... final-byte
    r"|\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC  ESC ] ... BEL-or-ST
    r")"
)

DEFAULT_BOOT_TIMEOUT = 10.0
BOOT_TIMEOUT_ENV_VAR = "ROAM_TEST_BOOT_TIMEOUT"


def resolveBootTimeout(bootTimeout=None):
    """Decide how long the first `expect` may wait for the game to boot.

    An explicit argument wins (runScript's kwarg, roamScript.py's
    --boot-timeout); otherwise $ROAM_TEST_BOOT_TIMEOUT; otherwise the default
    tuned for the ubuntu CI runner. The env var is the only lever that reaches
    a whole `pytest tests/integration/` run — both test modules construct the
    harness with no arguments, and on a host slower than CI (importing pygame
    alone can take tens of seconds under load) every boot-dependent test
    otherwise fails at 10s with an empty transcript.

    A malformed or non-positive *env* value falls back to the default rather
    than raising: a typo in a shell export should not turn every playthrough
    into a failure that reads like a game bug. An explicit argument is taken
    at face value — it's a per-call decision, so a deliberate 0 stays 0."""
    if bootTimeout is not None:
        return float(bootTimeout)
    raw = os.environ.get(BOOT_TIMEOUT_ENV_VAR)
    if raw is None:
        return DEFAULT_BOOT_TIMEOUT
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_BOOT_TIMEOUT
    return value if value > 0 else DEFAULT_BOOT_TIMEOUT


# @author Claude
# @since June 14th, 2026
#
# A reusable end-to-end driver for the text/terminal frontend (epic #433 / the
# text-UI payoff #239). It launches `roam.py --text` under a pseudo-terminal so
# the game sees a real interactive TTY (cbreak mode, arrow escape sequences,
# Enter as CR), then lets a test send keystrokes and wait for expected screen
# text to appear. This exercises the whole stack a unit test cannot: the real
# process, the InputSource decoding, the Renderer/Clock loop, and clean
# shutdown. Bugs first found this way include the world-entry geometry.Rect
# crash, cbreak Enter translation, and the "c opens naming and types itself"
# batch. POSIX only (it needs pty); skip elsewhere.
#
# Use as a context manager so the child is always reaped and the terminal
# released:
#     with TextPlaythrough() as game:
#         game.expect("Roam")          # main menu painted
#         game.send("\r")              # Enter -> save selection
#         ...
#     assert game.cleanExit()          # no traceback on the child's stderr
class TextPlaythrough:
    def __init__(self, saveName=None, bootTimeout=None):
        # A unique, self-cleaning save name keeps runs from colliding and from
        # leaving state in the repo's saves/ directory.
        self._saveName = saveName or ("_pytest_play_%d" % os.getpid())
        self._bootTimeout = resolveBootTimeout(bootTimeout)
        self._proc = None
        self._master = None
        self._buffer = ""  # ANSI-stripped output seen so far
        self._stderr = ""

    # --- lifecycle ---

    def __enter__(self):
        import pty

        master, slave = pty.openpty()
        env = dict(os.environ)
        env["SDL_VIDEODRIVER"] = "dummy"
        env["SDL_AUDIODRIVER"] = "dummy"
        # A playthrough must never be counted as a player, nor write the
        # usage-reporting first-run marker into the repo's config.yml.
        env["ROAM_USAGE_REPORTING"] = "0"
        self._proc = subprocess.Popen(
            [sys.executable, "src/roam.py", "--text"],
            stdin=slave,
            stdout=slave,
            stderr=subprocess.PIPE,
            cwd=REPO_ROOT,
            env=env,
            close_fds=True,
        )
        os.close(slave)
        self._master = master
        return self

    def __exit__(self, excType, excValue, traceback):
        # Ask the game to quit the way a Ctrl+C user would, then reap it.
        if self._proc is not None and self._proc.poll() is None:
            try:
                self._proc.send_signal(signal.SIGINT)
                self._proc.wait(timeout=5)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                self._proc.kill()
        if self._proc is not None and self._proc.stderr is not None:
            # Append: a failing `expect` may already have drained part of this
            # stream to explain itself, and that text must not be lost here.
            self._stderr += self._proc.stderr.read().decode("utf-8", "ignore")
        if self._master is not None:
            try:
                os.close(self._master)
            except OSError:
                pass
        self._cleanupSave()
        return False

    def _cleanupSave(self):
        import glob
        import shutil

        # A prefix glob, not just an exact match on self._saveName: a script
        # that renames the save mid-run (SaveSelectionScreen's rename dialog
        # does a real os.rename) leaves the original name gone and a new one
        # behind that this class was never told about. self._saveName is
        # always a freshly generated, effectively-unique token, so matching
        # anything starting with it can't catch a real user save.
        for savePath in glob.glob(
            os.path.join(REPO_ROOT, "saves", self._saveName + "*")
        ):
            shutil.rmtree(savePath, ignore_errors=True)

    # --- driving ---

    def getSaveName(self):
        return self._saveName

    def send(self, keys):
        os.write(self._master, keys.encode())

    def _pump(self, timeout):
        # Drain whatever the child has emitted within the window into the
        # rolling buffer; tolerate the fd closing as the child exits.
        deadline = time.time() + timeout
        while time.time() < deadline:
            ready, _, _ = select.select([self._master], [], [], 0.1)
            if not ready:
                continue
            try:
                chunk = os.read(self._master, 65536)
            except OSError:
                break
            if not chunk:
                break
            self._buffer += _ANSI.sub("", chunk.decode("utf-8", "ignore"))

    def _drainStderr(self):
        # Non-blocking counterpart to __exit__'s read: pull whatever the child
        # has already written to stderr while it may still be running, so a
        # failure message can quote it. Reading the raw fd bypasses the
        # BufferedReader, which is safe because nothing reads it before
        # __exit__ collects the remainder.
        if self._proc is None or self._proc.stderr is None:
            return
        fd = self._proc.stderr.fileno()
        while True:
            ready, _, _ = select.select([fd], [], [], 0)
            if not ready:
                return
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                return
            if not chunk:
                return
            self._stderr += chunk.decode("utf-8", "ignore")

    def describeChild(self):
        """One line (plus any stderr) on what the game process is doing.

        A wait that times out with an empty transcript is otherwise
        unreadable: a child that crashed on a missing dependency, one that
        exited immediately, and one still importing pygame on a slow host all
        look identical. `cleanExit`/`getStderr` can't fill the gap because
        stderr is only collected once the context manager exits — long after
        the assertion was raised and formatted."""
        if self._proc is None:
            return "child: not started"
        returnCode = self._proc.poll()
        state = (
            "still running"
            if returnCode is None
            else "exited with code %d" % returnCode
        )
        self._drainStderr()
        stderr = self._stderr.strip()
        if not stderr:
            return "child: %s, no stderr" % state
        return "child: %s, stderr:\n%s" % (state, stderr)

    def expect(self, text, timeout=None):
        """Wait until `text` appears in the (ANSI-stripped) output. Returns the
        accumulated buffer on success; raises AssertionError on timeout so a
        failing playthrough names the screen it was waiting for."""
        timeout = self._bootTimeout if timeout is None else timeout
        deadline = time.time() + timeout
        while time.time() < deadline:
            if text in self._buffer:
                return self._buffer
            self._pump(0.2)
        raise AssertionError(
            "timed out after %.1fs waiting for %r; %s\nlast output:\n%s"
            % (timeout, text, self.describeChild(), self.tail())
        )

    def drain(self, seconds=0.5):
        self._pump(seconds)
        return self._buffer

    def resetBuffer(self):
        """Discard everything captured so far. The buffer only ever grows
        (it's a running transcript, not a live screen snapshot), so text a
        screen showed once keeps matching `expect`/`assertContains` forever
        even after navigating away — resetting it is what makes "we left
        that screen" or "this went from on to off" provable rather than
        assumed."""
        self._buffer = ""

    # --- inspection ---

    def tail(self, lines=25):
        kept = [line for line in self._buffer.splitlines() if line.strip()]
        return "\n".join(kept[-lines:])

    def getStderr(self):
        return self._stderr

    def cleanExit(self):
        # The text frontend must shut down without dumping a Python traceback
        # (a crash also leaves the user's terminal stuck in cbreak mode).
        return "Traceback (most recent call last)" not in self._stderr
