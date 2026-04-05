"""
setupd - reusable setup backend for ClawOS Setup.
"""
from __future__ import annotations

import asyncio
import logging
import os
import platform
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from clawos_core.constants import (
    CLAWOS_DIR,
    DEFAULT_WORKSPACE,
    LOGS_DIR,
    MEMORY_DIR,
    PORT_SETUPD,
    SUPPORT_DIR,
    WORKSPACE_DIR,
)
from clawos_core.desktop_integration import autostart_supported, desktop_posture, enable_launch_on_login
from clawos_core.service_manager import service_manager_name, start as start_service
from services.setupd.state import SetupState

log = logging.getLogger("setupd")
SETUP_ACCESS_HEADER = "x-clawos-setup"
SETUP_ACCESS_VALUE = "1"

try:
    from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
    import uvicorn

    FASTAPI_OK = True
except ImportError:
    FASTAPI_OK = False
    FastAPI = HTTPException = Request = WebSocket = WebSocketDisconnect = None
    uvicorn = None


class SetupService:
    def __init__(self):
        self._state = SetupState.load()
        self._task: asyncio.Task | None = None
        self._listeners: set[WebSocket] = set()

    def get_state(self) -> SetupState:
        return self._state

    def _persist(self):
        self._state.save()

    def _log(self, message: str):
        self._state.logs.append(message)
        self._state.logs = self._state.logs[-50:]
        self._persist()

    async def broadcast(self):
        if not self._listeners:
            return
        dead = set()
        payload = self.to_dict()
        for listener in self._listeners:
            try:
                await listener.send_json({"type": "setup_state", "data": payload})
            except Exception:
                dead.add(listener)
        for listener in dead:
            self._listeners.discard(listener)

    def build_plan(self) -> dict[str, Any]:
        state = self._state
        state.progress_stage = "planned"
        state.plan_steps = [
            "Inspect hardware and service manager",
            "Bootstrap workspace and memory backends",
            f"Provision model(s): {', '.join(state.selected_models)}",
            "Start ClawOS services",
            "Finalize support and diagnostics paths",
        ]
        if state.launch_on_login and autostart_supported():
            state.plan_steps.append("Enable Command Center launch on login")
        self._persist()
        return {
            "summary": f"Apply {state.recommended_profile} profile on {state.platform} with {', '.join(state.selected_models)}",
            "steps": state.plan_steps,
        }

    async def _apply(self):
        from bootstrap.bootstrap import run as bootstrap_run

        state = self._state
        state.progress_stage = "applying"
        state.last_error = ""
        state.retry_state = ""
        self._log("Preparing setup plan")
        await self.broadcast()

        try:
            self._log(f"Bootstrapping workspace {state.workspace}")
            await asyncio.to_thread(
                bootstrap_run,
                profile=state.recommended_profile,
                yes=True,
                workspace=state.workspace or DEFAULT_WORKSPACE,
            )
            await self.broadcast()

            self._log("Attempting to start ClawOS user service")
            try:
                ok, detail = await asyncio.to_thread(start_service, "clawos.service")
                self._log(detail or ("ClawOS service started" if ok else "Service start requested"))
            except Exception as exc:
                self._log(f"Service start skipped: {exc}")

            if state.launch_on_login and autostart_supported():
                try:
                    path = await asyncio.to_thread(enable_launch_on_login)
                    self._log(f"Launch on login enabled at {path}")
                except Exception as exc:
                    self._log(f"Launch on login skipped: {exc}")

            self._log("Setup complete")
            state.progress_stage = "complete"
            state.completion_marker = True
            self._persist()
            await self.broadcast()
        except Exception as exc:
            state.progress_stage = "error"
            state.last_error = str(exc)
            state.retry_state = "last_step_failed"
            self._log(f"Setup failed: {exc}")
            self._persist()
            await self.broadcast()
        finally:
            self._task = None

    async def _repair(self):
        state = self._state
        state.progress_stage = "repairing"
        state.last_error = ""
        self._log("Starting repair checks")
        await self.broadcast()

        try:
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
            WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
            MEMORY_DIR.mkdir(parents=True, exist_ok=True)

            workspace_name = state.workspace or DEFAULT_WORKSPACE
            (WORKSPACE_DIR / workspace_name).mkdir(parents=True, exist_ok=True)
            (MEMORY_DIR / workspace_name).mkdir(parents=True, exist_ok=True)
            self._log(f"Prepared workspace paths for {workspace_name}")

            plan = self.build_plan()
            self._log(f"Rebuilt setup plan with {len(plan.get('steps', []))} steps")

            try:
                ok, detail = await asyncio.to_thread(start_service, "clawos.service")
                self._log(detail or ("ClawOS service started during repair" if ok else "Service start requested"))
            except Exception as exc:
                self._log(f"Service repair skipped: {exc}")

            if state.launch_on_login and autostart_supported():
                try:
                    path = await asyncio.to_thread(enable_launch_on_login)
                    self._log(f"Launch on login verified at {path}")
                except Exception as exc:
                    self._log(f"Launch on login repair skipped: {exc}")

            state.progress_stage = "complete" if state.completion_marker else "planned"
            self._log("Repair checks complete")
            self._persist()
            await self.broadcast()
        except Exception as exc:
            state.progress_stage = "error"
            state.last_error = str(exc)
            state.retry_state = "repair_failed"
            self._log(f"Repair failed: {exc}")
            self._persist()
            await self.broadcast()
        finally:
            self._task = None

    def apply(self):
        if self._task and not self._task.done():
            return {"ok": True, "status": "running"}
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(self._apply())
        return {"ok": True, "status": "started"}

    def repair(self):
        if self._task and not self._task.done():
            return {"ok": True, "status": "running"}
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(self._repair())
        return {"ok": True, "status": "started"}

    def retry(self):
        self._state.retry_state = ""
        self._persist()
        return self.apply()

    def cancel(self):
        if self._task and not self._task.done():
            self._task.cancel()
            self._state.progress_stage = "cancelled"
            self._state.retry_state = "cancelled"
            self._log("Setup cancelled")
            self._persist()
            return {"ok": True, "status": "cancelled"}
        return {"ok": True, "status": "idle"}

    def diagnostics(self) -> dict[str, Any]:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
        return {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "service_manager": service_manager_name(),
            "clawos_dir": str(CLAWOS_DIR),
            "logs_dir": str(LOGS_DIR),
            "support_dir": str(SUPPORT_DIR),
            "cwd": os.getcwd(),
            "desktop": desktop_posture(),
        }

    def to_dict(self) -> dict[str, Any]:
        return self._state.__dict__.copy()

    def health(self) -> dict[str, Any]:
        return {
            "status": "running" if self._task and not self._task.done() else "ok",
            "progress_stage": self._state.progress_stage,
            "completion_marker": self._state.completion_marker,
        }


_SERVICE: SetupService | None = None


def get_service() -> SetupService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = SetupService()
    return _SERVICE


def create_app() -> "FastAPI":
    if not FASTAPI_OK:
        raise RuntimeError("fastapi not installed")

    app = FastAPI(title="ClawOS Setup", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None)
    service = get_service()

    def _origin_is_trusted(origin: str) -> bool:
        if not origin:
            return True
        try:
            parsed = urlparse(origin)
        except Exception:
            return False
        return parsed.scheme in {"http", "https"} and (parsed.hostname or "").lower() in {"127.0.0.1", "localhost", "::1"}

    def _require_setup_access(request: Request):
        if request.headers.get(SETUP_ACCESS_HEADER, "").strip() != SETUP_ACCESS_VALUE:
            raise HTTPException(status_code=401, detail="Setup access header required")
        if not _origin_is_trusted(request.headers.get("origin", "")):
            raise HTTPException(status_code=401, detail="Untrusted setup origin")

    @app.get("/health")
    async def health():
        return service.health()

    @app.get("/api/setup/state")
    async def state(request: Request):
        _require_setup_access(request)
        return service.to_dict()

    @app.post("/api/setup/plan")
    async def plan(request: Request):
        _require_setup_access(request)
        return service.build_plan()

    @app.post("/api/setup/apply")
    async def apply(request: Request):
        _require_setup_access(request)
        return service.apply()

    @app.post("/api/setup/retry")
    async def retry(request: Request):
        _require_setup_access(request)
        return service.retry()

    @app.post("/api/setup/repair")
    async def repair(request: Request):
        _require_setup_access(request)
        return service.repair()

    @app.post("/api/setup/cancel")
    async def cancel(request: Request):
        _require_setup_access(request)
        return service.cancel()

    @app.get("/api/setup/logs")
    async def logs(request: Request):
        _require_setup_access(request)
        return {"logs": service.get_state().logs}

    @app.get("/api/setup/diagnostics")
    async def diagnostics(request: Request):
        _require_setup_access(request)
        return service.diagnostics()

    @app.websocket("/ws/setup")
    async def setup_ws(websocket: WebSocket):
        if websocket.query_params.get("setup", "").strip() != SETUP_ACCESS_VALUE:
            await websocket.close(code=4401)
            return
        if not _origin_is_trusted(websocket.headers.get("origin", "")):
            await websocket.close(code=4401)
            return
        await websocket.accept()
        service._listeners.add(websocket)
        try:
            await websocket.send_json({"type": "setup_state", "data": service.to_dict()})
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            service._listeners.discard(websocket)
        except Exception:
            service._listeners.discard(websocket)

    return app


def run():
    if not FASTAPI_OK:
        raise RuntimeError("fastapi not installed")
    uvicorn.run(create_app(), host="127.0.0.1", port=PORT_SETUPD, log_level="warning")
