# SPDX-License-Identifier: AGPL-3.0-or-later
import asyncio
import json
import logging
import signal
import subprocess
import sys
import time

PtyProcess = None
PTY_IMPORT_ERROR = None

if sys.platform == "win32":
    try:
        from winpty import PtyProcess as _PtyProcess  # pywinpty
        PtyProcess = _PtyProcess
    except ImportError as exc:
        PTY_IMPORT_ERROR = exc
else:
    try:
        from ptyprocess import PtyProcessUnicode as _PtyProcess
        PtyProcess = _PtyProcess
    except ImportError as exc:
        PTY_IMPORT_ERROR = exc

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

log = logging.getLogger("dashd")

JARVIS_CMD = ["ollama", "launch", "openclaw", "--model", "kimi-k2.5:cloud"]
READ_CHUNK_SIZE = 1024
SHUTDOWN_TIMEOUT_SECONDS = 3.0


def _spawn_pty():
    if sys.platform == "win32":
        try:
            return PtyProcess.spawn(JARVIS_CMD)
        except (TypeError, ValueError):
            return PtyProcess.spawn(subprocess.list2cmdline(JARVIS_CMD))
    return PtyProcess.spawn(JARVIS_CMD)


def _read_pty_chunk(pty) -> bytes:
    if sys.platform == "win32":
        chunk = pty.read()
    else:
        chunk = pty.read(READ_CHUNK_SIZE)
    if isinstance(chunk, bytes):
        return chunk
    return chunk.encode("utf-8", errors="replace")


def _write_pty(pty, data: str) -> None:
    pty.write(data)


def _resize_pty(pty, rows: int, cols: int) -> None:
    if rows <= 0 or cols <= 0:
        return
    resize = getattr(pty, "setwinsize", None)
    if callable(resize):
        resize(rows, cols)
        return
    resize = getattr(pty, "set_size", None)
    if callable(resize):
        resize(cols, rows)


def _pty_is_alive(pty) -> bool:
    isalive = getattr(pty, "isalive", None)
    if callable(isalive):
        try:
            return bool(isalive())
        except Exception:
            return False
    is_alive = getattr(pty, "is_alive", None)
    if callable(is_alive):
        try:
            return bool(is_alive())
        except Exception:
            return False
    return False


def _terminate_once(pty) -> None:
    if sys.platform != "win32":
        kill = getattr(pty, "kill", None)
        if callable(kill):
            kill(signal.SIGTERM)
            return
    terminate = getattr(pty, "terminate", None)
    if callable(terminate):
        try:
            terminate()
        except TypeError:
            terminate(False)


def _kill_once(pty) -> None:
    if sys.platform != "win32":
        kill = getattr(pty, "kill", None)
        if callable(kill):
            kill(signal.SIGKILL)
            return
    terminate = getattr(pty, "terminate", None)
    if callable(terminate):
        try:
            terminate(True)
            return
        except TypeError:
            try:
                terminate()
                return
            except Exception:
                pass
    close = getattr(pty, "close", None)
    if callable(close):
        try:
            close(force=True)
        except TypeError:
            close()


def _shutdown_pty(pty) -> None:
    try:
        _terminate_once(pty)
    except Exception:
        log.exception("Failed to send initial termination signal to JARVIS PTY")

    deadline = time.monotonic() + SHUTDOWN_TIMEOUT_SECONDS
    while _pty_is_alive(pty) and time.monotonic() < deadline:
        time.sleep(0.05)

    if _pty_is_alive(pty):
        try:
            _kill_once(pty)
        except Exception:
            log.exception("Failed to force-kill JARVIS PTY")

    close = getattr(pty, "close", None)
    if callable(close):
        try:
            close(force=True)
        except TypeError:
            try:
                close()
            except Exception:
                pass


def _parse_resize_payload(payload: str) -> tuple[int, int] | None:
    try:
        message = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(message, dict) or message.get("type") != "resize":
        return None
    try:
        cols = int(message.get("cols", 0))
        rows = int(message.get("rows", 0))
    except (TypeError, ValueError):
        return None
    return rows, cols


async def _close_websocket(websocket: WebSocket) -> None:
    try:
        await websocket.close()
    except Exception:
        pass


def register(app: FastAPI) -> None:
    if PTY_IMPORT_ERROR is not None or PtyProcess is None:
        log.warning("JARVIS PTY websocket unavailable: %s", PTY_IMPORT_ERROR)
        return

    from services.dashd.api import _websocket_authorized

    @app.websocket("/ws/jarvis")
    async def jarvis_websocket(websocket: WebSocket):
        if not _websocket_authorized(websocket):
            await websocket.close(code=4401)
            return

        await websocket.accept()
        loop = asyncio.get_running_loop()

        try:
            pty = await loop.run_in_executor(None, _spawn_pty)
        except Exception:
            log.exception("Failed to spawn JARVIS PTY")
            await websocket.close(code=1011)
            return

        stop = asyncio.Event()

        async def pty_to_ws() -> None:
            try:
                while not stop.is_set():
                    try:
                        chunk = await loop.run_in_executor(None, _read_pty_chunk, pty)
                    except EOFError:
                        break
                    if not chunk:
                        break
                    await websocket.send_bytes(chunk)
            except Exception:
                if not stop.is_set():
                    log.exception("JARVIS PTY-to-websocket bridge failed")
            finally:
                stop.set()
                await _close_websocket(websocket)

        async def ws_to_pty() -> None:
            try:
                while not stop.is_set():
                    message = await websocket.receive()
                    if message.get("type") == "websocket.disconnect":
                        break

                    text_payload = message.get("text")
                    if text_payload is not None:
                        resize = _parse_resize_payload(text_payload)
                        if resize is not None:
                            rows, cols = resize
                            await loop.run_in_executor(None, _resize_pty, pty, rows, cols)
                            continue
                        await loop.run_in_executor(None, _write_pty, pty, text_payload)
                        continue

                    byte_payload = message.get("bytes")
                    if byte_payload is not None:
                        text = byte_payload.decode("utf-8", errors="replace")
                        await loop.run_in_executor(None, _write_pty, pty, text)
            except WebSocketDisconnect:
                pass
            except Exception:
                if not stop.is_set():
                    log.exception("JARVIS websocket-to-PTY bridge failed")
            finally:
                stop.set()
                await loop.run_in_executor(None, _terminate_once, pty)

        results = await asyncio.gather(pty_to_ws(), ws_to_pty(), return_exceptions=True)
        for result in results:
            if isinstance(result, Exception) and not isinstance(result, WebSocketDisconnect):
                log.error("JARVIS websocket task ended with error: %s", result)

        await loop.run_in_executor(None, _shutdown_pty, pty)
        await _close_websocket(websocket)
