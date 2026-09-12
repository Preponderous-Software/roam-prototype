"""Pyodide entry point — runs inside a Web Worker after game.zip is unpacked.

The Worker has already:
  - inserted /game/src and /game/web into sys.path
  - set os.environ['ROAM_SAVE_DIR'] = '/saves'  (OPFS mount)
  - exposed globalThis.sabMeta / sabData / sabRingSize / Atomics / sendToMain
  - exposed globalThis.syncSaves() which flushes the OPFS mount

This file is exec()'d by pyodide.runPythonAsync() and shares that namespace,
so all js module globals are reachable via `from js import ...`.
"""

import concurrent.futures as _cf
import json
import queue

import js as _js
from js import Atomics, sabData, sabMeta, sabRingSize, sendToMain
from pyodide.ffi import to_js as _to_js

# ── Pyodide thread compatibility ──────────────────────────────────────────────
# Pyodide's CDN WASM build cannot spawn OS threads.  Patch concurrent.futures
# BEFORE game modules import them so all ThreadPoolExecutor usage runs tasks
# synchronously rather than crashing.
# pyodide_compat.py lives at /game/web/, which the Worker adds to sys.path.
from pyodide_compat import _PyodideExecutor  # noqa: E402

_cf.ThreadPoolExecutor = _PyodideExecutor


def _post(obj):
    """Send obj to the main thread, converting Python dicts to JS objects."""
    if isinstance(obj, str):
        sendToMain(obj)
    else:
        sendToMain(_to_js(obj, dict_converter=_js.Object.fromEntries))


# ── game imports (must come after the patches above) ─────────────────────────
from config.config import Config
from rendering.textClock import TextClock
from rendering.webInputSource import WebInputSource
from rendering.webRenderer import WebRenderer
from roam import Roam

_SAB_RING = int(sabRingSize)


class PyodideInputSource(WebInputSource):
    """WebInputSource backed by the main-thread SharedArrayBuffer ring buffer.

    The main thread writes newline-terminated UTF-8 messages:
      - ANSI key sequences:   ``\\x1b[A\\n``
      - JSON control messages: ``{"type":"mouse_down","x":0,"y":0,"button":1}\\n``

    JSON messages are dispatched to updateMouse/moveMouse as side effects;
    ANSI strings are returned to the parent's ANSI parser.
    """

    def _readFromQueue(self):
        try:
            return self._inputQueue.get_nowait()
        except queue.Empty:
            pass

        line = self._drain_sab_line()
        if not line:
            import time

            time.sleep(0.02)
            return ""

        if line.startswith("{"):
            self._handle_json(line)
            return ""

        return line

    def _drain_sab_line(self):
        write_idx = int(Atomics.load(sabMeta, 0))
        read_idx = int(Atomics.load(sabMeta, 1))
        if write_idx == read_idx:
            return ""
        result = bytearray()
        while read_idx != write_idx:
            b = int(sabData[read_idx % _SAB_RING])
            read_idx += 1
            if b == 10:  # newline = message boundary
                break
            result.append(b)
        Atomics.store(sabMeta, 1, read_idx)
        return result.decode("utf-8", errors="ignore")

    def _handle_json(self, line):
        from rendering.inputEvent import EventType, InputEvent

        try:
            msg = json.loads(line)
            t = msg.get("type")
            if t == "resize":
                w, h = int(msg.get("w", 0)), int(msg.get("h", 0))
                if w > 0 and h > 0:
                    self._renderer.resize(w, h)
                    self.queueEvent(InputEvent(EventType.WINDOW_RESIZE, size=(w, h)))
            elif t in ("mouse_down", "mouse_up"):
                self.updateMouse(
                    int(msg.get("x", 0)),
                    int(msg.get("y", 0)),
                    int(msg.get("button", 1)),
                    t == "mouse_down",
                )
            elif t == "mouse_move":
                self.moveMouse(int(msg.get("x", 0)), int(msg.get("y", 0)))
        except (json.JSONDecodeError, KeyError, ValueError):
            pass


def _send_frame(payload):
    sendToMain(payload)


input_source = PyodideInputSource()
renderer = WebRenderer(_send_frame, inputSource=input_source)
input_source._renderer = renderer  # needed so resize events can call renderer.resize()
clock = TextClock()


class _PyodideFrontend:
    def getRenderer(self):
        return renderer

    def getInputSource(self):
        return input_source

    def getClock(self):
        return clock

    def setCaption(self, c):
        pass

    def reset(self):
        pass

    def quit(self):
        pass


config = Config()
# No traceClient: the browser build never reports usage (no OS threads or
# sockets under Emscripten), so Roam keeps its default disabled client.
roam = Roam(config, frontend=_PyodideFrontend())

_post({"type": "ready"})

while True:
    result = roam.run()
    if result != "restart":
        break
    roam.restart()

# Game exited — flush final saves to IndexedDB before the Worker goes idle.
# time.sleep() yields to the JS event loop so the syncfs() callback fires.
try:
    import time as _time

    from js import syncSaves as _syncSaves

    _syncSaves()
    _time.sleep(0.5)
except Exception:
    pass
