"""
dashd - Dashboard API
=====================
REST + WebSocket dashboard with cookie-backed auth, safe bind defaults,
and a snapshot contract that matches the bundled single-file frontend.
"""
import asyncio
import logging
import os
import secrets
import time
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from clawos_core.config.loader import get as get_config
from clawos_core.constants import (
    CONFIG_DIR,
    DEFAULT_WORKSPACE,
    MEMORY_DIR,
    PORT_DASHD,
    WORKSPACE_DIR,
)
from clawos_core.events.bus import EV_SERVICE_DOWN, EV_SERVICE_UP, get_bus

log = logging.getLogger("dashd")

DEFAULT_COOKIE_NAME = "clawos_dashboard"
DASHBOARD_HTML = Path(__file__).parent.parent.parent / "clients" / "dashboard" / "index.html"

try:
    from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn

    FASTAPI_OK = True
except ImportError:
    FASTAPI_OK = False
    FastAPI = WebSocket = WebSocketDisconnect = HTTPException = None
    HTMLResponse = JSONResponse = None
    Depends = None
    Request = Response = object

    def Header(default=""):
        return default

    def require_auth(*_args, **_kwargs):
        return None


@dataclass(frozen=True)
class DashboardSettings:
    host: str = "127.0.0.1"
    port: int = PORT_DASHD
    auth_required: bool = True
    token: str = ""
    cookie_name: str = DEFAULT_COOKIE_NAME


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
        dead: list[WebSocket] = []
        for ws in self._ws:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _is_loopback_host(host: str) -> bool:
    host = (host or "").strip().lower()
    return host in {"127.0.0.1", "localhost", "::1"}


def _dashboard_token_file() -> Path:
    return CONFIG_DIR / "dashboard.token"


def _load_dashboard_token(auth_required: bool) -> str:
    env_token = os.environ.get("CLAWOS_DASHBOARD_TOKEN", "").strip()
    if env_token:
        return env_token
    if not auth_required:
        return ""

    token_file = _dashboard_token_file()
    token_file.parent.mkdir(parents=True, exist_ok=True)
    if not token_file.exists():
        token_file.write_text(secrets.token_urlsafe(32), encoding="utf-8")
        try:
            token_file.chmod(0o600)
        except OSError:
            pass
    return token_file.read_text(encoding="utf-8").strip()


def load_dashboard_settings(overrides: Optional[dict[str, Any]] = None) -> DashboardSettings:
    overrides = overrides or {}
    host = str(overrides.get("host", get_config("dashboard.host", "127.0.0.1")))
    port = int(overrides.get("port", get_config("dashboard.port", PORT_DASHD)))
    auth_required = _coerce_bool(
        overrides.get("auth_required", get_config("dashboard.auth_required", True)),
        True,
    )
    token = str(overrides["token"]) if "token" in overrides else _load_dashboard_token(auth_required)
    cookie_name = str(overrides.get("cookie_name", DEFAULT_COOKIE_NAME))

    if not auth_required and not _is_loopback_host(host):
        log.warning(
            "dashd requested a non-loopback bind without auth; forcing 127.0.0.1"
        )
        host = "127.0.0.1"

    return DashboardSettings(
        host=host,
        port=port,
        auth_required=auth_required,
        token=token,
        cookie_name=cookie_name,
    )


def _extract_bearer_token(authorization: str) -> str:
    if not authorization:
        return ""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return ""
    return token.strip()


def _token_matches(candidate: str, expected: str) -> bool:
    if not candidate or not expected:
        return False
    return secrets.compare_digest(candidate, expected)


def _is_request_authorized(request: Request, authorization: str = "") -> bool:
    settings: DashboardSettings = request.app.state.settings
    if not settings.auth_required:
        return True
    token = _extract_bearer_token(authorization) or request.cookies.get(settings.cookie_name, "")
    return _token_matches(token, settings.token)


def require_auth(request: Request, authorization: str = Header(default="")):
    if _is_request_authorized(request, authorization=authorization):
        return
    raise HTTPException(
        status_code=401,
        detail="Unauthorized",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _normalize_event(event: dict) -> dict:
    return {
        "type": event.get("type", "event"),
        "timestamp": event.get("timestamp", ""),
        "data": {
            key: value
            for key, value in event.items()
            if key not in {"type", "timestamp"}
        },
    }


def _normalize_service_status(name: str, raw: Any, data: dict) -> str:
    status = str(raw or "").strip().lower()
    if name == "modeld":
        if data.get("ollama_running"):
            return "up"
        return "degraded" if data else "down"
    if status in {"ok", "up", "running", "healthy"}:
        return "up"
    if status in {"down", "stopped", "failed", "error"}:
        return "down"
    return status or "unknown"


def _collect_service_health() -> dict[str, dict]:
    services: dict[str, dict] = {
        "dashd": {"status": "up", "latency_ms": 0},
    }

    checks = {}
    try:
        from services.agentd.health import health as agentd_health

        checks["agentd"] = agentd_health
    except Exception:
        pass
    try:
        from services.clawd.health import health as clawd_health

        checks["clawd"] = clawd_health
    except Exception:
        pass
    try:
        from services.memd.health import health as memd_health

        checks["memd"] = memd_health
    except Exception:
        pass
    try:
        from services.modeld.health import health as modeld_health

        checks["modeld"] = modeld_health
    except Exception:
        pass
    try:
        from services.policyd.health import health as policyd_health

        checks["policyd"] = policyd_health
    except Exception:
        pass

    for name, check in checks.items():
        started = time.perf_counter()
        try:
            data = check() or {}
            latency_ms = max(1, int((time.perf_counter() - started) * 1000))
            services[name] = {
                "status": _normalize_service_status(name, data.get("status"), data),
                "latency_ms": latency_ms,
            }
        except Exception as exc:
            latency_ms = max(1, int((time.perf_counter() - started) * 1000))
            services[name] = {
                "status": "down",
                "latency_ms": latency_ms,
                "error": str(exc),
            }
    return services


def _collect_models() -> list[dict]:
    try:
        from services.modeld.ollama_client import is_running, list_models
        from services.modeld.service import get_service

        running = is_running()
        current = get_service().get_model()
        raw_models = list_models() if running else []
        models: list[dict] = []
        for model in raw_models:
            name = model.get("name", "")
            if not name:
                continue
            size = model.get("size") or model.get("details", {}).get("parameter_size", "")
            models.append(
                {
                    "name": name,
                    "size": str(size) if size else "",
                    "running": running,
                    "default": name == current,
                }
            )
        if current and not any(item["name"] == current for item in models):
            models.insert(
                0,
                {
                    "name": current,
                    "size": "",
                    "running": False,
                    "default": True,
                },
            )
        return models
    except Exception as exc:
        log.debug("model snapshot unavailable: %s", exc)
        return []


def _count_nonempty_lines(text: str) -> int:
    return len([line for line in text.splitlines() if line.strip()])


def _memory_summary(workspace: str) -> dict:
    try:
        from services.memd.service import CHROMA_OK, MemoryService, _chroma

        mem = MemoryService()
        entries = mem.get_all(workspace, limit=100)
        chroma_count = 0
        if CHROMA_OK:
            try:
                chroma_count = _chroma.get_or_create_collection(f"ws_{workspace}").count()
            except Exception:
                chroma_count = 0

        return {
            "workspace": workspace,
            "pinned_lines": _count_nonempty_lines(mem.read_pinned(workspace)),
            "workflow_lines": _count_nonempty_lines(mem.read_workflow(workspace)),
            "chroma_count": chroma_count,
            "fts_count": len(entries),
            "entries": entries,
        }
    except Exception as exc:
        log.debug("memory summary unavailable: %s", exc)
        return {
            "workspace": workspace,
            "pinned_lines": 0,
            "workflow_lines": 0,
            "chroma_count": 0,
            "fts_count": 0,
            "entries": [],
        }


def _list_workspaces() -> list[dict]:
    try:
        from services.memd.service import MemoryService

        mem = MemoryService()
        names: set[str] = set()
        if WORKSPACE_DIR.exists():
            names.update(path.name for path in WORKSPACE_DIR.iterdir() if path.is_dir())
        if MEMORY_DIR.exists():
            names.update(path.name for path in MEMORY_DIR.iterdir() if path.is_dir())
        if not names:
            names.add(DEFAULT_WORKSPACE)

        workspaces = []
        for name in sorted(names):
            summary = _memory_summary(name)
            workspaces.append(
                {
                    "name": name,
                    "has_pinned": (MEMORY_DIR / name / "PINNED.md").exists(),
                    "memory_count": summary.get("fts_count", 0),
                    "history_count": len(mem.get_all(name, limit=100)),
                }
            )
        return workspaces
    except Exception as exc:
        log.debug("workspace listing unavailable: %s", exc)
        return [
            {"name": DEFAULT_WORKSPACE, "has_pinned": False, "memory_count": 0, "history_count": 0}
        ]


def _build_snapshot(app: "FastAPI") -> dict:
    return {
        "services": _collect_service_health(),
        "events": list(app.state.event_history),
        "models": _collect_models(),
    }


async def _service_health_loop(app: "FastAPI"):
    while True:
        await asyncio.sleep(15)
        await app.state.connections.broadcast(
            {"type": "service_health", "data": _collect_service_health()}
        )


def _websocket_authorized(websocket: WebSocket) -> bool:
    settings: DashboardSettings = websocket.app.state.settings
    if not settings.auth_required:
        return True
    token = (
        websocket.query_params.get("token", "")
        or _extract_bearer_token(websocket.headers.get("authorization", ""))
        or websocket.cookies.get(settings.cookie_name, "")
    )
    return _token_matches(token, settings.token)


def create_app(settings: Optional[dict[str, Any]] = None) -> "FastAPI":
    if not FASTAPI_OK:
        raise RuntimeError("fastapi not installed")

    mgr = ConnectionManager()
    bus = get_bus()
    event_history: deque[dict] = deque(maxlen=50)

    async def _fan_out_bus_event(event: dict):
        normalized = _normalize_event(event)
        event_history.appendleft(normalized)
        await mgr.broadcast({"type": "audit_event", "data": normalized})
        if event.get("type") in {EV_SERVICE_UP, EV_SERVICE_DOWN}:
            await mgr.broadcast({"type": "service_health", "data": _collect_service_health()})

    def _on_bus_event(event: dict):
        try:
            asyncio.get_running_loop().create_task(_fan_out_bus_event(event))
        except RuntimeError:
            return

    @asynccontextmanager
    async def lifespan(app_obj: "FastAPI"):
        bus.subscribe(app_obj.state.bus_handler)
        app_obj.state.health_task = asyncio.create_task(_service_health_loop(app_obj))
        try:
            yield
        finally:
            bus.unsubscribe(app_obj.state.bus_handler)
            task = app_obj.state.health_task
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    app = FastAPI(
        title="ClawOS Dashboard",
        version="0.2.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.settings = load_dashboard_settings(settings)
    app.state.connections = mgr
    app.state.event_history = event_history
    app.state.health_task = None
    app.state.bus_handler = _on_bus_event

    @app.get("/", response_class=HTMLResponse)
    async def root():
        if DASHBOARD_HTML.exists():
            return HTMLResponse(DASHBOARD_HTML.read_text(encoding="utf-8", errors="ignore"))
        return HTMLResponse("<h1>ClawOS Dashboard</h1><p>Frontend not found.</p>")

    @app.get("/api/health")
    async def health():
        settings_obj: DashboardSettings = app.state.settings
        return {
            "status": "ok",
            "auth_required": settings_obj.auth_required,
            "services": _collect_service_health(),
            "models": _collect_models(),
        }

    @app.get("/api/session")
    async def session(request: Request):
        settings_obj: DashboardSettings = request.app.state.settings
        return {
            "auth_required": settings_obj.auth_required,
            "authenticated": _is_request_authorized(request),
        }

    @app.post("/api/login")
    async def login(body: dict, request: Request):
        settings_obj: DashboardSettings = request.app.state.settings
        if not settings_obj.auth_required:
            return JSONResponse({"ok": True, "auth_required": False})

        token = str((body or {}).get("token", "")).strip()
        if not _token_matches(token, settings_obj.token):
            raise HTTPException(
                status_code=401,
                detail="Unauthorized",
                headers={"WWW-Authenticate": "Bearer"},
            )

        response = JSONResponse({"ok": True, "auth_required": True})
        response.set_cookie(
            settings_obj.cookie_name,
            token,
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="strict",
            max_age=86400,
        )
        return response

    @app.post("/api/logout")
    async def logout(request: Request):
        settings_obj: DashboardSettings = request.app.state.settings
        response = JSONResponse({"ok": True})
        response.delete_cookie(settings_obj.cookie_name)
        return response

    @app.get("/api/tasks", dependencies=[Depends(require_auth)])
    async def list_tasks(limit: int = 20):
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "http://127.0.0.1:7072/tasks",
                    params={"limit": limit},
                    timeout=2.0,
                )
                return resp.json()
        except Exception:
            from services.agentd.service import get_manager

            return get_manager().list_tasks(limit)

    @app.post("/api/tasks/submit", dependencies=[Depends(require_auth)])
    async def submit_task(body: dict):
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "http://127.0.0.1:7072/submit",
                    json=body,
                    timeout=5.0,
                )
                return resp.json()
        except Exception:
            from services.agentd.service import get_manager

            intent = str((body or {}).get("intent") or (body or {}).get("task") or "").strip()
            workspace = str((body or {}).get("workspace") or DEFAULT_WORKSPACE)
            channel = str((body or {}).get("channel") or "dashboard")
            if not intent:
                raise HTTPException(status_code=400, detail="intent required")
            task = await get_manager().submit(intent, workspace_id=workspace, channel=channel)
            return {"task_id": task.task_id, "status": "queued"}

    @app.get("/api/tasks/{task_id}", dependencies=[Depends(require_auth)])
    async def get_task(task_id: str):
        from services.agentd.service import get_manager

        task = get_manager().get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task.to_dict()

    @app.post("/api/chat", dependencies=[Depends(require_auth)])
    async def chat(body: dict):
        message = str((body or {}).get("message", "")).strip()
        workspace = str((body or {}).get("workspace", DEFAULT_WORKSPACE))
        if not message:
            raise HTTPException(status_code=400, detail="message required")
        from services.agentd.service import get_manager

        task = await get_manager().submit(message, workspace_id=workspace, channel="dashboard")
        return {"task_id": task.task_id, "status": task.status.value}

    @app.post("/api/approve/{request_id}", dependencies=[Depends(require_auth)])
    async def approve(request_id: str, body: dict = None):
        approve_it = bool((body or {}).get("approve", True))
        from services.policyd.service import get_engine

        ok = get_engine().decide_approval(request_id, approve_it)
        return {"ok": ok}

    @app.get("/api/approvals", dependencies=[Depends(require_auth)])
    async def approvals():
        from services.policyd.service import get_engine

        return get_engine().get_pending_approvals()

    @app.get("/api/audit", dependencies=[Depends(require_auth)])
    async def audit(n: int = 20):
        from services.policyd.service import get_engine

        return get_engine().get_audit_tail(n)

    @app.get("/api/memory/{workspace}", dependencies=[Depends(require_auth)])
    async def memory(workspace: str):
        return _memory_summary(workspace)

    @app.get("/api/workspaces", dependencies=[Depends(require_auth)])
    async def workspaces():
        return {"workspaces": _list_workspaces()}

    @app.get("/api/models", dependencies=[Depends(require_auth)])
    async def models():
        model_snapshot = _collect_models()
        return {"running": any(model.get("running") for model in model_snapshot), "models": model_snapshot}

    @app.get("/api/workflows/list", dependencies=[Depends(require_auth)])
    async def list_workflows(category: str = None, search: str = None):
        try:
            from workflows.engine import get_engine

            eng = get_engine()
            eng.load_registry()
            workflows = eng.list_workflows(category=category, search=search)
            return [
                {
                    "id": workflow.id,
                    "name": workflow.name,
                    "category": workflow.category,
                    "description": workflow.description,
                    "tags": workflow.tags,
                    "requires": workflow.requires,
                    "platforms": workflow.platforms,
                    "needs_agent": workflow.needs_agent,
                    "destructive": workflow.destructive,
                    "timeout_s": workflow.timeout_s,
                }
                for workflow in workflows
            ]
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.post("/api/workflows/{workflow_id}/run", dependencies=[Depends(require_auth)])
    async def run_workflow(workflow_id: str, body: dict = None):
        workflow_args = (body or {}).get("args", {})
        workspace_id = (body or {}).get("workspace", DEFAULT_WORKSPACE)
        try:
            from workflows.engine import get_engine

            eng = get_engine()
            eng.load_registry()
            await mgr.broadcast(
                {
                    "type": "workflow_progress",
                    "data": {"id": workflow_id, "status": "running"},
                }
            )
            result = await eng.run(workflow_id, workflow_args, workspace_id=workspace_id)
            await mgr.broadcast(
                {
                    "type": "workflow_progress",
                    "data": {
                        "id": workflow_id,
                        "status": result.status.value,
                        "output": result.output[:500] if result.output else "",
                    },
                }
            )
            return {
                "status": result.status.value,
                "output": result.output,
                "metadata": result.metadata,
                "error": result.error,
            }
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Workflow not found: {workflow_id}")
        except Exception as exc:
            await mgr.broadcast(
                {
                    "type": "workflow_error",
                    "data": {"id": workflow_id, "error": str(exc)},
                }
            )
            raise HTTPException(status_code=500, detail=str(exc))

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket):
        if not _websocket_authorized(websocket):
            await websocket.close(code=4401)
            return

        await mgr.connect(websocket)
        try:
            await websocket.send_json({"type": "snapshot", "data": _build_snapshot(app)})
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            mgr.disconnect(websocket)
        except Exception:
            mgr.disconnect(websocket)

    return app


def run():
    if not FASTAPI_OK:
        log.error("fastapi/uvicorn not installed - dashboard unavailable")
        return
    app = create_app()
    settings: DashboardSettings = app.state.settings
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="warning")
