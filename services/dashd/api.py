"""
dashd — Dashboard API
========================
REST + WebSocket dashboard. Observes all events via event bus.
Single-file frontend served at root.
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from clawos_core.constants import PORT_DASHD
from clawos_core.events.bus import get_bus

log = logging.getLogger("dashd")

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi import Depends, Header
    import uvicorn
    import secrets as _secrets
    from pathlib import Path as _Path2

    _TOKEN_FILE = _Path2.home() / ".local" / "share" / "clawos" / "dashboard.token"

    def _load_dashboard_token() -> str:
        _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not _TOKEN_FILE.exists():
            _TOKEN_FILE.write_text(_secrets.token_urlsafe(32))
            _TOKEN_FILE.chmod(0o600)
        return _TOKEN_FILE.read_text().strip()

    DASHBOARD_TOKEN = _load_dashboard_token()

    def require_auth(authorization: str = Header(default="")):
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Unauthorized")
        if authorization.removeprefix("Bearer ") != DASHBOARD_TOKEN:
            raise HTTPException(status_code=401, detail="Unauthorized")

    FASTAPI_OK = True

except ImportError:
    FASTAPI_OK = False
    FastAPI = WebSocket = WebSocketDisconnect = HTTPException = None
    HTMLResponse = JSONResponse = None
    DASHBOARD_TOKEN = ""

    def require_auth(*a, **kw):
        pass

DASHBOARD_HTML = Path(__file__).parent.parent.parent / "clients" / "dashboard" / "index.html"


class ConnectionManager:
    def __init__(self):
        self._ws: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._ws.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self._ws:
            self._ws.remove(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self._ws:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


def create_app() -> "FastAPI":
    if not FASTAPI_OK:
        raise RuntimeError("fastapi not installed")

    app  = FastAPI(title="ClawOS Dashboard", version="0.1.0")
    mgr  = ConnectionManager()
    bus  = get_bus()
    bus.subscribe(lambda ev: asyncio.create_task(mgr.broadcast(ev)))

    @app.get("/", response_class=HTMLResponse)
    async def root():
        if DASHBOARD_HTML.exists():
            return HTMLResponse(DASHBOARD_HTML.read_text())
        return HTMLResponse("<h1>ClawOS Dashboard</h1><p>Frontend not found.</p>")

    @app.get("/api/health")
    async def health():
        from services.modeld.service import get_service as get_model
        from services.policyd.service import get_engine
        return {"status": "ok", "model": get_model().health(),
                "pending_approvals": len(get_engine().get_pending_approvals())}

    @app.get("/api/tasks")
    async def list_tasks(limit: int = 20):
        from services.agentd.service import get_manager
        return get_manager().list_tasks(limit)

    @app.get("/api/tasks/{task_id}")
    async def get_task(task_id: str):
        from services.agentd.service import get_manager
        t = get_manager().get_task(task_id)
        if not t:
            raise HTTPException(404, "Task not found")
        return t.to_dict()

    @app.post("/api/chat")
    async def chat(body: dict):
        msg       = body.get("message", "").strip()
        workspace = body.get("workspace", "default")
        if not msg:
            raise HTTPException(400, "message required")
        from services.agentd.service import get_manager
        task = await get_manager().submit(msg, workspace_id=workspace, channel="dashboard")
        return {"task_id": task.task_id, "status": task.status.value}

    @app.post("/api/approve/{request_id}")
    async def approve(request_id: str, body: dict = None):
        approve_it = (body or {}).get("approve", True)
        from services.policyd.service import get_engine
        ok = get_engine().decide_approval(request_id, approve_it)
        return {"ok": ok}

    @app.get("/api/approvals")
    async def approvals():
        from services.policyd.service import get_engine
        return get_engine().get_pending_approvals()

    @app.get("/api/audit")
    async def audit(n: int = 20):
        from services.policyd.service import get_engine
        return get_engine().get_audit_tail(n)

    @app.get("/api/memory/{workspace}")
    async def memory(workspace: str, limit: int = 30):
        from services.memd.service import MemoryService
        return MemoryService().get_all(workspace, limit)

    @app.get("/api/models")
    async def models():
        from services.modeld.ollama_client import list_models, is_running
        return {"running": is_running(), "models": list_models()}

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket):
        await mgr.connect(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            mgr.disconnect(websocket)

    return app


def run():
    if not FASTAPI_OK:
        log.error("fastapi/uvicorn not installed — dashboard unavailable")
        return
    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=PORT_DASHD, log_level="warning")
