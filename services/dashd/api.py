# SPDX-License-Identifier: AGPL-3.0-or-later
"""
dashd - Dashboard API
=====================
REST + WebSocket dashboard with cookie-backed auth, safe bind defaults,
and a snapshot contract that matches the bundled React frontend assets.
"""
import asyncio
import logging
import os
import re
import secrets
import time
import urllib.request
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from clawos_core.catalog import (
    get_extension,
    get_pack,
    get_provider_profile,
    list_eval_suites,
    list_extensions,
    list_packs,
    list_provider_profiles,
    list_traces,
    make_trace,
    record_trace,
    test_provider_profile,
)
from clawos_core.config.loader import get as get_config
from clawos_core.constants import (
    CONFIG_DIR,
    DEFAULT_WORKSPACE,
    MEMORY_DIR,
    PORT_DASHD,
    WORKSPACE_DIR,
)
from clawos_core.events.bus import EV_SERVICE_DOWN, EV_SERVICE_UP, get_bus
from clawos_core.presence import (
    build_attention_events,
    build_today_briefing,
    get_presence_payload,
    get_voice_session,
    list_missions,
    set_voice_mode,
    start_mission,
    sync_presence_from_setup,
    update_autonomy_policy,
    update_presence_profile,
)

log = logging.getLogger("dashd")

DEFAULT_COOKIE_NAME = "clawos_dashboard"
SETUP_ACCESS_HEADER = "x-clawos-setup"
SETUP_ACCESS_VALUE = "1"
DASHBOARD_STATIC_DIR = Path(__file__).parent / "static"
DASHBOARD_STATIC_INDEX = DASHBOARD_STATIC_DIR / "index.html"

try:
    from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
    from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
    from fastapi.openapi.utils import get_openapi
    from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
    from fastapi.staticfiles import StaticFiles
    import uvicorn

    FASTAPI_OK = True
except ImportError:
    FASTAPI_OK = False
    FastAPI = WebSocket = WebSocketDisconnect = HTTPException = None
    HTMLResponse = JSONResponse = None
    get_openapi = get_redoc_html = get_swagger_ui_html = None
    Depends = None
    Request = Response = object

    def Header(default=""):
        return default

    def require_auth(*_args, **_kwargs):
        return None


_WORKBENCH_SESSIONS: deque = deque(maxlen=50)
_VOLATILE_SECRETS: dict[str, str] = {}


def _workbench_fetch(url: str, timeout: int = 12) -> dict:
    """Fetch a URL server-side and return extracted title, text, and links."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http and https URLs are supported")

    req = urllib.request.Request(url, headers={"User-Agent": "ClawOS-Workbench/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        raw = resp.read(512 * 1024)

    try:
        html = raw.decode("utf-8", errors="replace")
    except (OSError, RuntimeError, AttributeError):
        html = raw.decode("latin-1", errors="replace")

    title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = re.sub(r"\s+", " ", title_m.group(1)).strip() if title_m else parsed.netloc
    title = title[:200]

    links_raw = re.findall(r'href=["\']([^"\'#?][^"\']*)["\']', html)
    links = list(dict.fromkeys(ln for ln in links_raw if ln.startswith("http")))[:20]

    clean = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<style[^>]*>.*?</style>", " ", clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<[^>]+>", " ", clean)
    clean = re.sub(r"&[a-z#0-9]+;", " ", clean)
    clean = re.sub(r"[ \t]{2,}", " ", clean)
    clean = re.sub(r"\n{3,}", "\n\n", clean).strip()

    return {
        "url": url,
        "title": title,
        "text": clean[:8000],
        "links": links,
        "word_count": len(clean.split()),
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


@dataclass(frozen=True)
class DashboardSettings:
    host: str = "0.0.0.0"
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
            except (OSError, ConnectionError, TimeoutError):
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


def _origin_is_trusted(origin: str) -> bool:
    if not origin:
        return True
    try:
        parsed = urlparse(origin)
    except (ValueError, OSError, AttributeError):
        return False
    return parsed.scheme in {"http", "https"} and _is_loopback_host(parsed.hostname or "")


def _request_targets_loopback(request: Request) -> bool:
    try:
        if _is_loopback_host(request.url.hostname or ""):
            return True
    except (OSError, RuntimeError, AttributeError) as e:
        log.debug(f"unexpected: {e}")
        pass
    client = getattr(request, "client", None)
    return _is_loopback_host(getattr(client, "host", ""))


def _websocket_targets_loopback(websocket: WebSocket) -> bool:
    try:
        if _is_loopback_host(websocket.url.hostname or ""):
            return True
    except (OSError, ConnectionError, TimeoutError) as e:
        log.debug(f"failed: {e}")
        pass
    client = getattr(websocket, "client", None)
    return _is_loopback_host(getattr(client, "host", ""))


def _has_setup_access(request: Request) -> bool:
    header_value = request.headers.get(SETUP_ACCESS_HEADER, "").strip()
    if header_value != SETUP_ACCESS_VALUE:
        return False
    return _origin_is_trusted(request.headers.get("origin", ""))


def _dashboard_token_file() -> Path:
    return CONFIG_DIR / "dashboard.token"


def _dashboard_session_token_file() -> Path:
    return CONFIG_DIR / "dashboard.session"


def _set_dashboard_session_cookie(
    response: Response,
    request: Request,
    settings: Optional[DashboardSettings] = None,
) -> None:
    settings = settings or request.app.state.settings
    if not settings.auth_required:
        return
    response.set_cookie(
        settings.cookie_name,
        _load_dashboard_session_token(settings.auth_required),
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
        max_age=86400,
        path="/",
    )


def _can_auto_bootstrap_local_session(request: Request) -> bool:
    settings: DashboardSettings = request.app.state.settings
    if not settings.auth_required:
        return False
    if not _request_targets_loopback(request):
        return False
    if not _origin_is_trusted(request.headers.get("origin", "")):
        return False
    if not _origin_is_trusted(request.headers.get("referer", "")):
        return False
    return True


def _dashboard_index_response(request: Request) -> FileResponse:
    response = FileResponse(
        str(DASHBOARD_STATIC_INDEX),
        headers={
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
        },
    )
    if _can_auto_bootstrap_local_session(request):
        _set_dashboard_session_cookie(response, request)
    return response


def _load_or_create_secret(path: Path) -> str:
    cache_key = str(path)
    if cache_key in _VOLATILE_SECRETS and not path.exists():
        return _VOLATILE_SECRETS[cache_key]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            secret = secrets.token_urlsafe(32)
            path.write_text(secret, encoding="utf-8")
            try:
                path.chmod(0o600)
            except OSError as e:
                log.debug(f"suppressed: {e}")
            _VOLATILE_SECRETS[cache_key] = secret
            return secret
        secret = path.read_text(encoding="utf-8").strip()
        _VOLATILE_SECRETS[cache_key] = secret
        return secret
    except OSError:
        secret = _VOLATILE_SECRETS.get(cache_key) or secrets.token_urlsafe(32)
        _VOLATILE_SECRETS[cache_key] = secret
        return secret


def _load_dashboard_token(auth_required: bool) -> str:
    env_token = os.environ.get("CLAWOS_DASHBOARD_TOKEN", "").strip()
    if env_token:
        return env_token
    return ""


def _load_dashboard_session_token(auth_required: bool) -> str:
    if not auth_required:
        return ""
    return _load_or_create_secret(_dashboard_session_token_file())


def rotate_dashboard_session_token() -> str:
    token = secrets.token_urlsafe(32)
    path = _dashboard_session_token_file()
    _VOLATILE_SECRETS[str(path)] = token
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(token, encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError as e:
            log.debug(f"suppressed: {e}")
    except OSError as e:
        log.debug(f"suppressed: {e}")
    return token


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
    bearer_token = _extract_bearer_token(authorization)
    if _token_matches(bearer_token, settings.token):
        return True
    cookie_token = request.cookies.get(settings.cookie_name, "")
    return _token_matches(cookie_token, _load_dashboard_session_token(settings.auth_required))


def require_auth(request: Request, authorization: str = Header(default="")):
    if _is_request_authorized(request, authorization=authorization):
        return
    raise HTTPException(
        status_code=401,
        detail="Unauthorized",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_setup_access(request: Request, authorization: str = Header(default="")):
    settings: DashboardSettings = request.app.state.settings
    if _is_request_authorized(request, authorization=authorization):
        return
    if _setup_bypass_allowed(settings, request):
        return
    raise HTTPException(
        status_code=401,
        detail="Unauthorized",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_auth_or_setup_access(request: Request, authorization: str = Header(default="")):
    settings: DashboardSettings = request.app.state.settings
    if _is_request_authorized(request, authorization=authorization):
        return
    if _setup_bypass_allowed(settings, request):
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


def _deep_health_check() -> dict:
    """Run a deep health check beyond just 'are services up?'.

    Checks: Ollama running, default model present, disk space,
    ChromaDB availability, voice deps (whisper/piper).
    Returns a dict with booleans and human-readable warnings.
    """
    from clawos_core.constants import DEFAULT_MODEL, CLAWOS_DIR
    result: dict = {}

    # Ollama
    try:
        from services.modeld.ollama_client import is_running, model_exists
        result["ollama_running"] = is_running()
        if result["ollama_running"]:
            result["default_model_present"] = model_exists(DEFAULT_MODEL)
            if not result["default_model_present"]:
                result["default_model_warning"] = f"Default model {DEFAULT_MODEL} not found in Ollama"
    except ImportError:
        result["ollama_running"] = False
        result["default_model_present"] = False

    # Disk space
    import shutil
    try:
        disk = shutil.disk_usage(str(CLAWOS_DIR.parent) if CLAWOS_DIR.exists() else "/")
        result["disk_free_gb"] = round(disk.free / 1e9, 1)
        result["disk_total_gb"] = round(disk.total / 1e9, 1)
        if disk.free < 500_000_000:
            result["disk_warning"] = f"Only {result['disk_free_gb']}GB free"
    except OSError:
        result["disk_free_gb"] = -1

    # ChromaDB
    try:
        import chromadb  # noqa: F401
        result["chromadb_available"] = True
    except ImportError:
        result["chromadb_available"] = False
        result["chromadb_warning"] = "Semantic search disabled — install chromadb for full memory"

    # Whisper (STT)
    try:
        import whisper  # noqa: F401
        result["whisper_available"] = True
    except ImportError:
        result["whisper_available"] = False
        result["whisper_warning"] = "Voice STT disabled — install openai-whisper"

    # Piper (TTS)
    try:
        import piper  # noqa: F401
        result["piper_available"] = True
    except ImportError:
        # piper might be a CLI binary, not a Python package
        import shutil as _sh
        result["piper_available"] = bool(_sh.which("piper"))
        if not result["piper_available"]:
            result["piper_warning"] = "Voice TTS disabled — install piper-tts"

    # Playwright (browser)
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        result["playwright_available"] = True
    except ImportError:
        result["playwright_available"] = False
        result["playwright_warning"] = "Browser tools disabled — install playwright"

    # Warnings summary
    warnings = [k.replace("_warning", "") for k in result if k.endswith("_warning")]
    result["warnings"] = warnings

    return result


def _collect_service_health() -> dict[str, dict]:
    services: dict[str, dict] = {
        "dashd": {"status": "up", "latency_ms": 0},
    }

    checks = {}
    try:
        from services.agentd.health import health as agentd_health

        checks["agentd"] = agentd_health
    except (ImportError, ModuleNotFoundError) as e:
        log.debug(f"suppressed: {e}")
    try:
        from services.clawd.health import health as clawd_health

        checks["clawd"] = clawd_health
    except (ImportError, ModuleNotFoundError) as e:
        log.debug(f"suppressed: {e}")
    try:
        from services.mcpd.health import health as mcpd_health

        checks["mcpd"] = mcpd_health
    except (ImportError, ModuleNotFoundError) as e:
        log.debug(f"suppressed: {e}")
    try:
        from services.observd.health import health as observd_health

        checks["observd"] = observd_health
    except (ImportError, ModuleNotFoundError) as e:
        log.debug(f"suppressed: {e}")
    try:
        from services.voiced.health import health as voiced_health

        checks["voiced"] = voiced_health
    except (ImportError, ModuleNotFoundError) as e:
        log.debug(f"suppressed: {e}")
    try:
        from services.desktopd.health import health as desktopd_health

        checks["desktopd"] = desktopd_health
    except (ImportError, ModuleNotFoundError) as e:
        log.debug(f"suppressed: {e}")
    try:
        from services.memd.health import health as memd_health

        checks["memd"] = memd_health
    except (ImportError, ModuleNotFoundError) as e:
        log.debug(f"suppressed: {e}")
    try:
        from services.modeld.health import health as modeld_health

        checks["modeld"] = modeld_health
    except (ImportError, ModuleNotFoundError) as e:
        log.debug(f"suppressed: {e}")
    try:
        from services.policyd.health import health as policyd_health

        checks["policyd"] = policyd_health
    except (ImportError, ModuleNotFoundError) as e:
        log.debug(f"suppressed: {e}")
    try:
        from services.setupd.health import health as setupd_health

        checks["setupd"] = setupd_health
    except (ImportError, ModuleNotFoundError) as e:
        log.debug(f"suppressed: {e}")
    try:
        from services.voiced.health import health as voiced_health

        checks["voiced"] = voiced_health
    except (ImportError, ModuleNotFoundError) as e:
        log.debug(f"suppressed: {e}")
    # PicoClaw — check if process is running via port
    try:
        import urllib.request as _ur
        _r = _ur.urlopen("http://127.0.0.1:18800/health", timeout=1)
        checks["picoclaw"] = lambda: {"status": "up"}
    except (OSError, ConnectionRefusedError, TimeoutError):
        import shutil as _sh
        checks["picoclaw"] = lambda: {"status": "installed" if _sh.which("picoclaw") else "not_installed"}
    # OpenClaw — check if binary exists and gateway is reachable
    try:
        import urllib.request as _ur2
        _r2 = _ur2.urlopen("http://127.0.0.1:18789/health", timeout=1)
        checks["openclaw"] = lambda: {"status": "up"}
    except (OSError, ConnectionRefusedError, TimeoutError):
        import shutil as _sh2
        checks["openclaw"] = lambda: {"status": "installed" if _sh2.which("openclaw") else "not_installed"}

    for name, check in checks.items():
        started = time.perf_counter()
        try:
            data = check() or {}
            latency_ms = max(1, int((time.perf_counter() - started) * 1000))
            services[name] = {
                "status": _normalize_service_status(name, data.get("status"), data),
                "latency_ms": latency_ms,
            }
        except (OSError, ValueError) as exc:
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
    except (ImportError, ConnectionError, OSError, RuntimeError) as exc:
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
            except (OSError, AttributeError, RuntimeError):
                chroma_count = 0

        return {
            "workspace": workspace,
            "pinned_lines": _count_nonempty_lines(mem.read_pinned(workspace)),
            "workflow_lines": _count_nonempty_lines(mem.read_workflow(workspace)),
            "chroma_count": chroma_count,
            "fts_count": len(entries),
            "entries": entries,
        }
    except (ImportError, ModuleNotFoundError) as exc:
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
    except (OSError, PermissionError) as exc:
        log.debug("workspace listing unavailable: %s", exc)
        return [
            {"name": DEFAULT_WORKSPACE, "has_pinned": False, "memory_count": 0, "history_count": 0}
        ]


def _setup_state():
    try:
        from services.setupd.state import SetupState

        return SetupState.load()
    except (ImportError, ModuleNotFoundError):
        return None


def _voice_service():
    from services.voiced.service import get_service

    return get_service()


def _jarvis_service():
    from services.jarvisd.service import get_service

    return get_service()


def _setup_bypass_allowed(settings: DashboardSettings, request: Request) -> bool:
    is_local = _request_targets_loopback(request) or _is_loopback_host(settings.host)
    if not is_local:
        return False
    state = _setup_state()
    if getattr(state, "completion_marker", False):
        return False
    return _has_setup_access(request)


def _pack_payloads() -> list[dict]:
    state = _setup_state()
    primary = getattr(state, "primary_pack", "")
    secondary = set(getattr(state, "secondary_packs", []) or [])
    return [
        {
            **pack.to_dict(),
            "installed": pack.id == primary or pack.id in secondary,
            "primary": pack.id == primary,
            "secondary": pack.id in secondary,
        }
        for pack in list_packs()
    ]


def _provider_payloads() -> list[dict]:
    state = _setup_state()
    selected = getattr(state, "selected_provider_profile", "local-ollama")
    payloads = []
    for profile in list_provider_profiles():
        result = test_provider_profile(profile.id)
        payloads.append(
            {
                **profile.to_dict(),
                "selected": profile.id == selected,
                "status": result.get("status", "unknown"),
                "detail": result.get("detail", ""),
            }
        )
    return payloads


def _extension_payloads() -> list[dict]:
    state = _setup_state()
    installed = set(getattr(state, "installed_extensions", []) or [])
    primary = getattr(state, "primary_pack", "")
    return [
        {
            **extension.to_dict(),
            "installed": extension.id in installed,
            "recommended_for_primary": primary in extension.packs,
        }
        for extension in list_extensions()
    ]


def _eval_payloads() -> list[dict]:
    state = _setup_state()
    active_packs = {
        getattr(state, "primary_pack", ""),
        *list(getattr(state, "secondary_packs", []) or []),
    }
    payloads = []
    for suite in list_eval_suites():
        payloads.append(
            {
                **suite.to_dict(),
                "active": suite.pack_id in active_packs,
            }
        )
    return payloads


def _approval_payloads() -> list[dict]:
    try:
        from services.policyd.service import get_engine

        return list(get_engine().get_pending_approvals() or [])
    except (ImportError, ModuleNotFoundError):
        return []


def _build_snapshot(app: "FastAPI") -> dict:
    return {
        "services": _collect_service_health(),
        "events": list(app.state.event_history),
        "models": _collect_models(),
        "tasks": [],
        "approvals": _approval_payloads(),
        "voice": get_voice_session(),
        "jarvis": _jarvis_service().session(),
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
    query_token = websocket.query_params.get("token", "")
    bearer_token = _extract_bearer_token(websocket.headers.get("authorization", ""))
    if _token_matches(query_token, settings.token):
        return True
    if _token_matches(bearer_token, settings.token):
        return True

    cookie_token = websocket.cookies.get(settings.cookie_name, "")
    if not _token_matches(cookie_token, _load_dashboard_session_token(settings.auth_required)):
        return False

    # Cookie-backed websocket sessions are intended for the bundled browser UI,
    # so require a trusted local origin before allowing the connection.
    return _origin_is_trusted(websocket.headers.get("origin", ""))


def _setup_websocket_authorized(websocket: WebSocket) -> bool:
    settings: DashboardSettings = websocket.app.state.settings
    setup_signal = websocket.query_params.get("setup", "").strip() == SETUP_ACCESS_VALUE
    state = _setup_state()
    if (
        not getattr(state, "completion_marker", False)
        and _websocket_targets_loopback(websocket)
        and setup_signal
        and _origin_is_trusted(websocket.headers.get("origin", ""))
    ):
        return True
    return _websocket_authorized(websocket)


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
        if event.get("type") in {"workflow_progress", "workflow_error"}:
            await mgr.broadcast(
                {
                    "type": event.get("type"),
                    "data": {
                        key: value
                        for key, value in event.items()
                        if key not in {"type", "timestamp"}
                    },
                }
            )
        if event.get("type") in {EV_SERVICE_UP, EV_SERVICE_DOWN}:
            await mgr.broadcast({"type": "service_health", "data": _collect_service_health()})

    def _on_bus_event(event: dict):
        try:
            asyncio.get_running_loop().create_task(_fan_out_bus_event(event))
        except RuntimeError:
            return

    async def _fan_out_voice_session(session: dict[str, Any]):
        await mgr.broadcast({"type": "voice_session", "data": session})

    async def _fan_out_jarvis_session(session: dict[str, Any]):
        await mgr.broadcast({"type": "jarvis_session", "data": session})

    @asynccontextmanager
    async def lifespan(app_obj: "FastAPI"):
        bus.subscribe(app_obj.state.bus_handler)
        app_obj.state.voice_listener = _fan_out_voice_session
        app_obj.state.jarvis_listener = _fan_out_jarvis_session
        voice_service = _voice_service()
        jarvis_service = _jarvis_service()
        add_listener = getattr(voice_service, "add_session_listener", None)
        if callable(add_listener):
            add_listener(app_obj.state.voice_listener)
        add_jarvis_listener = getattr(jarvis_service, "add_session_listener", None)
        if callable(add_jarvis_listener):
            add_jarvis_listener(app_obj.state.jarvis_listener)
        app_obj.state.health_task = asyncio.create_task(_service_health_loop(app_obj))
        try:
            yield
        finally:
            bus.unsubscribe(app_obj.state.bus_handler)
            remove_listener = getattr(voice_service, "remove_session_listener", None)
            if callable(remove_listener):
                remove_listener(app_obj.state.voice_listener)
            remove_jarvis_listener = getattr(jarvis_service, "remove_session_listener", None)
            if callable(remove_jarvis_listener):
                remove_jarvis_listener(app_obj.state.jarvis_listener)
            task = app_obj.state.health_task
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError as e:
                    log.debug(f"suppressed: {e}")

    app = FastAPI(
        title="ClawOS Dashboard API",
        description="ClawOS command center REST API — 100+ endpoints for agents, workflows, brain, voice, and more.",
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
    app.state.voice_listener = None
    app.state.jarvis_listener = None
    app.state.openapi_schema = None

    def _build_openapi_schema() -> dict[str, Any]:
        schema = app.state.openapi_schema
        if schema is None:
            schema = get_openapi(
                title=app.title,
                version=app.version,
                description=app.description,
                routes=app.routes,
            )
            app.state.openapi_schema = schema
        return schema

    @app.get("/api/openapi.json", dependencies=[Depends(require_auth)], include_in_schema=False)
    async def openapi_schema():
        return JSONResponse(_build_openapi_schema())

    @app.get("/api/docs", dependencies=[Depends(require_auth)], include_in_schema=False)
    async def swagger_ui():
        return get_swagger_ui_html(openapi_url="/api/openapi.json", title=f"{app.title} Docs")

    @app.get("/api/redoc", dependencies=[Depends(require_auth)], include_in_schema=False)
    async def redoc_ui():
        return get_redoc_html(openapi_url="/api/openapi.json", title=f"{app.title} ReDoc")

    @app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
    async def root(request: Request):
        if DASHBOARD_STATIC_INDEX.exists():
            return _dashboard_index_response(request)
        return HTMLResponse(
            "<h1>ClawOS Dashboard</h1><p>Built frontend not found in services/dashd/static.</p>",
            status_code=503,
        )

    @app.get("/api/health")
    async def health():
        settings_obj: DashboardSettings = app.state.settings
        service_health = _collect_service_health()
        model_info = _collect_models()

        # Deep health: Ollama + default model + disk space
        deep = _deep_health_check()

        overall = "ok"
        if deep.get("ollama_running") is False:
            overall = "degraded"
        if deep.get("default_model_present") is False:
            overall = "degraded"
        if deep.get("disk_free_gb", 999) < 1:
            overall = "degraded"

        # Any core service down?
        for svc_name, svc_data in service_health.items():
            if svc_data.get("status") == "down" and svc_name in ("memd", "policyd", "modeld"):
                overall = "degraded"

        return {
            "status": overall,
            "auth_required": settings_obj.auth_required,
            "host": settings_obj.host,
            "port": settings_obj.port,
            "local_only": _is_loopback_host(settings_obj.host),
            "services": service_health,
            "models": model_info,
            "deep": deep,
        }

    @app.get("/api/session")
    async def session(request: Request):
        settings_obj: DashboardSettings = request.app.state.settings
        authenticated = _is_request_authorized(request)
        bootstrapped = False
        if not authenticated and _can_auto_bootstrap_local_session(request):
            authenticated = True
            bootstrapped = True

        response = JSONResponse({
            "auth_required": settings_obj.auth_required,
            "authenticated": authenticated,
        })
        if bootstrapped:
            _set_dashboard_session_cookie(response, request, settings_obj)
        return response

    @app.post("/api/login")
    async def login(body: dict, request: Request):
        settings_obj: DashboardSettings = request.app.state.settings
        if not settings_obj.auth_required:
            return JSONResponse({"ok": True, "auth_required": False})

        token_ok = body.get("token") == settings_obj.token
        auto_ok = _can_auto_bootstrap_local_session(request)
        if not token_ok and not auto_ok:
            raise HTTPException(
                status_code=401,
                detail="Unauthorized",
                headers={"WWW-Authenticate": "Bearer"},
            )

        response = JSONResponse({"ok": True, "auth_required": True})
        _set_dashboard_session_cookie(response, request, settings_obj)
        return response

    @app.post("/api/logout")
    async def logout(request: Request):
        settings_obj: DashboardSettings = request.app.state.settings
        response = JSONResponse({"ok": True})
        response.delete_cookie(settings_obj.cookie_name, path="/")
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
        except (json.JSONDecodeError, ValueError):
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
        except (json.JSONDecodeError, ValueError):
            from services.agentd.service import get_manager

            intent = str((body or {}).get("intent", "")).strip()
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

    @app.get("/api/packs", dependencies=[Depends(require_auth_or_setup_access)])
    async def packs():
        return _pack_payloads()

    @app.post("/api/packs/install", dependencies=[Depends(require_auth)])
    async def install_pack(body: dict | None = None):
        payload = body or {}
        pack_id = str(payload.get("pack_id", "")).strip()
        if not pack_id:
            raise HTTPException(status_code=400, detail="pack_id required")
        pack = get_pack(pack_id)
        if not pack:
            raise HTTPException(status_code=404, detail="Pack not found")

        from services.setupd.state import SetupState

        state = SetupState.load()
        primary = bool(payload.get("primary", False))
        if primary or not state.primary_pack:
            state.primary_pack = pack.id
            state.secondary_packs = [item for item in state.secondary_packs if item != pack.id]
        elif pack.id != state.primary_pack and pack.id not in state.secondary_packs:
            state.secondary_packs.append(pack.id)

        provider_profile = str(payload.get("provider_profile", "")).strip()
        if provider_profile:
            if not get_provider_profile(provider_profile):
                raise HTTPException(status_code=400, detail="Unknown provider profile")
            state.selected_provider_profile = provider_profile

        for extension_id in pack.extension_recommendations[:2]:
            if extension_id not in state.installed_extensions:
                state.installed_extensions.append(extension_id)
        state.save()
        record_trace(
            make_trace(
                title=f"Installed pack {pack.name}",
                category="packs",
                status="completed",
                provider=state.selected_provider_profile,
                pack_id=pack.id,
                tools=["dashd.packs.install"],
            )
        )
        return {"ok": True, "pack": pack.to_dict(), "state": state.__dict__}

    @app.get("/api/providers", dependencies=[Depends(require_auth_or_setup_access)])
    async def providers():
        return _provider_payloads()

    @app.post("/api/providers/test", dependencies=[Depends(require_auth_or_setup_access)])
    async def test_provider(body: dict | None = None):
        profile_id = str((body or {}).get("id", "")).strip()
        if not profile_id:
            raise HTTPException(status_code=400, detail="id required")
        result = test_provider_profile(profile_id)
        record_trace(
            make_trace(
                title=f"Tested provider {profile_id}",
                category="providers",
                status="completed" if result.get("ok") else "warning",
                provider=profile_id,
                tools=["dashd.providers.test"],
                metadata={"status": result.get("status", "unknown")},
            )
        )
        return result

    @app.post("/api/providers/switch", dependencies=[Depends(require_auth_or_setup_access)])
    async def switch_provider(body: dict | None = None):
        profile_id = str((body or {}).get("id", "")).strip()
        profile = get_provider_profile(profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Provider profile not found")

        from services.setupd.state import SetupState

        state = SetupState.load()
        state.selected_provider_profile = profile.id
        state.save()
        record_trace(
            make_trace(
                title=f"Switched provider to {profile.name}",
                category="providers",
                status="completed",
                provider=profile.id,
                pack_id=state.primary_pack,
                tools=["dashd.providers.switch"],
            )
        )
        return {"ok": True, "provider": profile.to_dict(), "state": state.__dict__}

    @app.get("/api/presence", dependencies=[Depends(require_auth_or_setup_access)])
    async def presence():
        return get_presence_payload()

    @app.post("/api/presence", dependencies=[Depends(require_auth_or_setup_access)])
    async def update_presence(body: dict | None = None):
        payload = body or {}
        state = _setup_state()
        if state:
            assistant_identity = str(payload.get("assistant_identity", "")).strip()
            if assistant_identity:
                state.assistant_identity = assistant_identity
            if isinstance(payload.get("presence_profile"), dict):
                state.presence_profile.update(payload["presence_profile"])
            voice_mode = str(payload.get("voice_mode", "")).strip()
            if voice_mode:
                state.voice_mode = voice_mode
                state.voice_enabled = voice_mode != "off"
            primary_goals = payload.get("primary_goals")
            if isinstance(primary_goals, list) and primary_goals:
                state.primary_goals = [str(item).strip() for item in primary_goals if str(item).strip()]
            briefing_enabled = payload.get("briefing_enabled")
            if isinstance(briefing_enabled, bool):
                state.briefing_enabled = briefing_enabled
            state.save()
            sync_presence_from_setup(state)

        profile_payload = dict(payload.get("presence_profile") or {})
        if payload.get("assistant_identity"):
            profile_payload["assistant_identity"] = payload["assistant_identity"]
        if payload.get("voice_mode"):
            profile_payload["preferred_voice_mode"] = payload["voice_mode"]
            try:
                set_voice_mode(str(payload["voice_mode"]))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
        response = update_presence_profile(profile_payload) if profile_payload else get_presence_payload()
        record_trace(
            make_trace(
                title="Updated Nexus presence",
                category="presence",
                status="completed",
                provider=getattr(state, "selected_provider_profile", ""),
                pack_id=getattr(state, "primary_pack", ""),
                tools=["dashd.presence.update"],
            )
        )
        return response

    @app.get("/api/attention", dependencies=[Depends(require_auth)])
    async def attention():
        return build_attention_events(
            services=_collect_service_health(),
            approvals=_approval_payloads(),
            missions=list_missions(),
        )

    @app.get("/api/briefings/today", dependencies=[Depends(require_auth)])
    async def today_briefing():
        return build_today_briefing(
            setup_state=_setup_state(),
            services=_collect_service_health(),
            approvals=_approval_payloads(),
            missions=list_missions(),
        )

    @app.get("/api/briefings/morning", dependencies=[Depends(require_auth)])
    async def morning_briefing():
        import json as _json
        import shutil
        import urllib.parse

        # System health
        services = _collect_service_health()
        up_count = sum(1 for v in services.values() if v.get("status") in {"up", "running"})
        total_count = len(services)

        # Disk usage
        disk_pct = 0
        try:
            usage = shutil.disk_usage("/")
            disk_pct = round(usage.used / usage.total * 100)
        except (OSError, PermissionError) as e:
            log.debug(f"suppressed: {e}")

        # RAM usage
        ram_total_gb = 0
        ram_used_gb = 0
        try:
            import psutil
            m = psutil.virtual_memory()
            ram_total_gb = round(m.total / 1e9, 1)
            ram_used_gb = round(m.used / 1e9, 1)
        except (ImportError, ModuleNotFoundError) as e:
            log.debug(f"suppressed: {e}")

        # Approvals
        approvals = _approval_payloads()

        # Brain stats
        node_count = 0
        edge_count = 0
        try:
            from services.braind.service import get_brain
            brain_svc = get_brain()
            g = brain_svc.graph()
            node_count = len(g.get("nodes", []))
            edge_count = len(g.get("links", []))
        except (ImportError, ModuleNotFoundError) as e:
            log.debug(f"suppressed: {e}")

        # Jarvis briefing sources (weather text + source status)
        jarvis = _jarvis_service()
        try:
            briefing_payload, source_status = jarvis._briefing_sources()
        except (OSError, ValueError):
            briefing_payload, source_status = {}, {}

        # Structured calendar events
        calendar_items: list[dict] = []
        try:
            ics_url = str(get_config("jarvis.briefing.calendar_ics_url", "")).strip()
            if ics_url:
                import icalendar  # type: ignore[import]
                from datetime import date, datetime
                with urllib.request.urlopen(ics_url, timeout=10) as resp:  # noqa: S310
                    cal = icalendar.Calendar.from_ical(resp.read())
                today = date.today()
                ev_list: list[tuple[str, str]] = []
                for component in cal.walk():
                    if component.name != "VEVENT":
                        continue
                    dtstart = component.get("dtstart")
                    if not dtstart:
                        continue
                    dt = dtstart.dt
                    event_date = dt if isinstance(dt, date) and not isinstance(dt, datetime) else getattr(dt, "date", lambda: today)()
                    if event_date != today:
                        continue
                    summary = str(component.get("summary", "")).strip()
                    if not summary:
                        continue
                    time_str = dt.strftime("%H:%M") if isinstance(dt, datetime) else "all-day"
                    ev_list.append((time_str, summary))
                ev_list.sort()
                calendar_items = [{"time": t, "title": s} for t, s in ev_list[:6]]
        except (OSError, ConnectionRefusedError, TimeoutError) as e:
            log.debug(f"suppressed: {e}")

        # Structured weather (temp + description)
        weather_temp = None
        weather_desc = None
        try:
            lat = get_config("jarvis.briefing.latitude")
            lon = get_config("jarvis.briefing.longitude")
            tz = str(get_config("jarvis.briefing.timezone", "auto"))
            if lat and lon:
                url = (
                    "https://api.open-meteo.com/v1/forecast?"
                    + urllib.parse.urlencode({
                        "latitude": lat, "longitude": lon,
                        "current": "temperature_2m,weather_code", "timezone": tz,
                    })
                )
                with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
                    w_data = _json.loads(resp.read().decode())
                current = w_data.get("current", {})
                weather_temp = current.get("temperature_2m")
                code = int(current.get("weather_code", 0))
                try:
                    from services.jarvisd.service import WEATHER_CODES
                    weather_desc = WEATHER_CODES.get(code, "settled")
                except (ImportError, ModuleNotFoundError):
                    weather_desc = "settled"
        except (json.JSONDecodeError, ValueError) as e:
            log.debug(f"suppressed: {e}")

        return {
            "weather": {
                "temp": weather_temp,
                "desc": weather_desc,
                "summary": briefing_payload.get("weather", ""),
                "source": source_status.get("weather", "unknown"),
            },
            "calendar": {
                "events": calendar_items,
                "source": source_status.get("calendar", "unknown"),
            },
            "system": {
                "services_up": up_count,
                "services_total": total_count,
                "disk_pct": disk_pct,
                "ram_total_gb": ram_total_gb,
                "ram_used_gb": ram_used_gb,
            },
            "approvals": {
                "count": len(approvals),
                "items": approvals[:5],
            },
            "brain": {
                "node_count": node_count,
                "edge_count": edge_count,
            },
            "sources": source_status,
        }

    @app.get("/api/missions", dependencies=[Depends(require_auth)])
    async def missions():
        return list_missions()

    @app.post("/api/missions", dependencies=[Depends(require_auth)])
    async def missions_start(body: dict | None = None):
        payload = body or {}
        title = str(payload.get("title", "")).strip()
        summary = str(payload.get("summary", "")).strip()
        trust_lane = str(payload.get("trust_lane", "trusted-automatic")).strip() or "trusted-automatic"
        if not title:
            raise HTTPException(status_code=400, detail="title required")
        mission = start_mission(title, summary=summary, trust_lane=trust_lane)
        state = _setup_state()
        record_trace(
            make_trace(
                title=f"Mission started: {title}",
                category="missions",
                status="completed",
                provider=getattr(state, "selected_provider_profile", ""),
                pack_id=getattr(state, "primary_pack", ""),
                tools=["dashd.missions.start"],
                metadata={"trust_lane": trust_lane},
            )
        )
        return {"ok": True, "mission": mission}

    @app.get("/api/voice/session", dependencies=[Depends(require_auth)])
    async def voice_session():
        return _voice_service().session()

    @app.get("/api/voice/health", dependencies=[Depends(require_auth_or_setup_access)])
    async def voice_health():
        return _voice_service().health()

    @app.post("/api/voice/test", dependencies=[Depends(require_auth_or_setup_access)])
    async def voice_test(body: dict | None = None):
        payload = body or {}
        kind = str(payload.get("kind", "pipeline")).strip() or "pipeline"
        sample_text = str(payload.get("sample_text", "Voice pipeline ready.")).strip() or "Voice pipeline ready."
        service = _voice_service()
        if kind == "microphone":
            result = await service.test_microphone()
        elif kind == "wake_word":
            result = await service.test_wake_word()
        else:
            result = await service.test_pipeline(sample_text=sample_text)
        await app.state.connections.broadcast({"type": "voice_session", "data": service.session()})
        return result

    @app.post("/api/voice/push-to-talk", dependencies=[Depends(require_auth_or_setup_access)])
    async def voice_push_to_talk():
        service = _voice_service()
        result = await service.push_to_talk()
        await app.state.connections.broadcast({"type": "voice_session", "data": service.session()})
        return result

    @app.post("/api/voice/mode", dependencies=[Depends(require_auth_or_setup_access)])
    async def voice_mode(body: dict | None = None):
        mode = str((body or {}).get("mode", "")).strip()
        if not mode:
            raise HTTPException(status_code=400, detail="mode required")
        try:
            session = await _voice_service().set_mode(mode)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        state = _setup_state()
        if state:
            state.voice_mode = mode
            state.voice_enabled = mode != "off"
            state.save()
            sync_presence_from_setup(state)

        await app.state.connections.broadcast({"type": "voice_session", "data": session})
        return session

    @app.get("/api/voice/elevenlabs-config", dependencies=[Depends(require_auth)])
    async def elevenlabs_config_get():
        from clawos_core.config import get as cfg_get
        from adapters.audio.elevenlabs_adapter import _get_api_key, _get_voice_id
        key = _get_api_key()
        return {
            "enabled": cfg_get("voice.tts_provider", "piper") == "elevenlabs",
            "voice_id": _get_voice_id(),
            "key_set": bool(key),
        }

    @app.post("/api/voice/elevenlabs-config", dependencies=[Depends(require_auth)])
    async def elevenlabs_config_set(body: dict | None = None):
        import yaml
        from clawos_core.constants import CLAWOS_CONFIG
        payload = body or {}
        api_key = str(payload.get("api_key", "")).strip()
        voice_id = str(payload.get("voice_id", "")).strip() or "nPczCjzI2devNBz1zQrb"

        if not api_key:
            raise HTTPException(status_code=400, detail="api_key required")

        # Load existing user config
        user_cfg: dict = {}
        if CLAWOS_CONFIG.exists():
            with open(CLAWOS_CONFIG) as f:
                user_cfg = yaml.safe_load(f) or {}

        # Write ElevenLabs settings
        user_cfg.setdefault("voice", {})
        user_cfg["voice"]["tts_provider"] = "elevenlabs"
        user_cfg["voice"]["elevenlabs_voice_id"] = voice_id
        user_cfg.setdefault("secrets", {})
        user_cfg["secrets"]["elevenlabs_api_key"] = api_key

        CLAWOS_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        with open(CLAWOS_CONFIG, "w") as f:
            yaml.dump(user_cfg, f, default_flow_style=False)

        # Inject into env so adapter picks it up immediately (no restart needed)
        import os
        os.environ["ELEVENLABS_API_KEY"] = api_key

        # Reset adapter so it reloads with new key
        try:
            from adapters.audio import elevenlabs_adapter
            elevenlabs_adapter.reset()
        except (ImportError, ModuleNotFoundError) as e:
            log.debug(f"suppressed: {e}")

        # Quick test synthesis to validate key
        tested = False
        try:
            from adapters.audio.elevenlabs_adapter import speak as xi_speak
            audio = xi_speak("JARVIS online.")
            tested = bool(audio)
        except (ImportError, ModuleNotFoundError) as e:
            log.debug(f"suppressed: {e}")

        if not tested:
            raise HTTPException(status_code=400, detail="ElevenLabs key saved but test synthesis failed — check your key")

        return {"ok": True, "tested": True, "voice_id": voice_id}

    @app.get("/api/jarvis/session", dependencies=[Depends(require_auth)])
    async def jarvis_session():
        return _jarvis_service().session()

    @app.get("/api/jarvis/health", dependencies=[Depends(require_auth)])
    async def jarvis_health():
        return _jarvis_service().health()

    @app.get("/api/jarvis/config", dependencies=[Depends(require_auth)])
    async def jarvis_config_get():
        return _jarvis_service().config()

    @app.post("/api/jarvis/config", dependencies=[Depends(require_auth)])
    async def jarvis_config_set(body: dict | None = None):
        config = _jarvis_service().set_config(body or {})
        session = _jarvis_service().session()
        await app.state.connections.broadcast({"type": "jarvis_session", "data": session})
        return {"ok": True, "config": config, "session": session}

    @app.post("/api/jarvis/push-to-talk", dependencies=[Depends(require_auth)])
    async def jarvis_push_to_talk():
        service = _jarvis_service()
        try:
            result = await service.push_to_talk()
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        await app.state.connections.broadcast({"type": "jarvis_session", "data": service.session()})
        return result

    @app.post("/api/jarvis/chat", dependencies=[Depends(require_auth)])
    async def jarvis_chat(body: dict | None = None):
        payload = body or {}
        message = str(payload.get("message", "")).strip()
        thread_key = str(payload.get("thread_key", "jarvis-ui")).strip() or "jarvis-ui"
        source = str(payload.get("source", "jarvis-ui:text")).strip() or "jarvis-ui:text"
        if not message:
            raise HTTPException(status_code=400, detail="message required")
        service = _jarvis_service()
        try:
            result = await service.chat(message, thread_key=thread_key, source=source)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        await app.state.connections.broadcast({"type": "jarvis_session", "data": result["session"]})
        return result

    @app.post("/api/jarvis/mode", dependencies=[Depends(require_auth)])
    async def jarvis_mode(body: dict | None = None):
        mode = str((body or {}).get("mode", "")).strip()
        if not mode:
            raise HTTPException(status_code=400, detail="mode required")
        try:
            session = await _jarvis_service().set_mode(mode)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        await app.state.connections.broadcast({"type": "jarvis_session", "data": session})
        return session

    @app.get("/api/extensions", dependencies=[Depends(require_auth_or_setup_access)])
    async def extensions():
        return _extension_payloads()

    @app.post("/api/extensions/install", dependencies=[Depends(require_auth)])
    async def install_extension(body: dict | None = None):
        extension_id = str((body or {}).get("id", "")).strip()
        extension = get_extension(extension_id)
        if not extension:
            raise HTTPException(status_code=404, detail="Extension not found")

        from services.setupd.state import SetupState

        state = SetupState.load()
        if extension.id not in state.installed_extensions:
            state.installed_extensions.append(extension.id)
        state.save()
        record_trace(
            make_trace(
                title=f"Installed extension {extension.name}",
                category="extensions",
                status="completed",
                provider=state.selected_provider_profile,
                pack_id=state.primary_pack,
                tools=["dashd.extensions.install"],
            )
        )
        return {"ok": True, "extension": extension.to_dict(), "state": state.__dict__}

    @app.get("/api/traces", dependencies=[Depends(require_auth)])
    async def traces(limit: int = 40):
        return list_traces(limit)

    @app.get("/api/evals", dependencies=[Depends(require_auth_or_setup_access)])
    async def evals():
        return _eval_payloads()

    @app.get("/api/a2a/agent-card", dependencies=[Depends(require_auth)])
    async def a2a_agent_card():
        from services.a2ad.agent_card import build_card
        from services.a2ad.discovery import get_local_ip, get_peers

        return {"card": build_card(local_ip=get_local_ip()).to_dict(), "peers": get_peers()}

    @app.post("/api/a2a/tasks", dependencies=[Depends(require_auth)])
    async def a2a_tasks(body: dict | None = None):
        payload = body or {}
        peer_url = str(payload.get("peer_url", "")).strip()
        intent = str(payload.get("intent", "")).strip()
        workspace = str(payload.get("workspace", DEFAULT_WORKSPACE)).strip() or DEFAULT_WORKSPACE
        if not peer_url or not intent:
            raise HTTPException(status_code=400, detail="peer_url and intent required")

        import json as _json
        import urllib.request as _ur
        req_body = _json.dumps({"intent": intent, "workspace": workspace}).encode()
        req = _ur.Request(
            f"{peer_url.rstrip('/')}/a2a/tasks",
            data=req_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with _ur.urlopen(req, timeout=30) as resp:  # noqa: S310
                result = _json.loads(resp.read().decode())
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(status_code=502, detail=f"Peer unreachable: {exc}")
        record_trace(
            make_trace(
                title="Delegated A2A task",
                category="a2a",
                status="completed",
                provider="a2a",
                tools=["dashd.a2a.tasks"],
                metadata={"peer_url": peer_url, "workspace": workspace},
            )
        )
        return {"ok": True, "result": result}

    @app.get("/api/setup/state", dependencies=[Depends(require_setup_access)])
    async def setup_state():
        from services.setupd.service import get_service

        return get_service().to_dict()

    @app.post("/api/setup/inspect", dependencies=[Depends(require_setup_access)])
    async def setup_inspect():
        from services.setupd.service import get_service

        return get_service().inspect()

    @app.post("/api/setup/select-pack", dependencies=[Depends(require_setup_access)])
    async def setup_select_pack(body: dict | None = None):
        from services.setupd.service import get_service

        payload = body or {}
        pack_id = str(payload.get("pack_id", "")).strip()
        if not pack_id:
            raise HTTPException(status_code=400, detail="pack_id required")
        secondary = payload.get("secondary_packs")
        if secondary is not None and not isinstance(secondary, list):
            raise HTTPException(status_code=400, detail="secondary_packs must be a list")
        provider_profile = str(payload.get("provider_profile", "")).strip()
        try:
            return get_service().select_pack(pack_id, secondary_packs=secondary, provider_profile=provider_profile)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/setup/presence", dependencies=[Depends(require_setup_access)])
    async def setup_presence(body: dict | None = None):
        from services.setupd.service import get_service

        try:
            return get_service().update_presence(body)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/setup/options", dependencies=[Depends(require_setup_access)])
    async def setup_options(body: dict | None = None):
        from services.setupd.service import get_service

        try:
            return get_service().update_options(body)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/setup/autonomy", dependencies=[Depends(require_setup_access)])
    async def setup_autonomy(body: dict | None = None):
        from services.setupd.service import get_service

        try:
            return get_service().update_autonomy(body)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/setup/install-milestone", dependencies=[Depends(require_setup_access)])
    async def setup_install_milestone(body: dict | None = None):
        # install.sh POSTs here as each install phase runs. Upsert-by-id, so
        # a phase can transition running → done without duplicating.
        from services.setupd.service import get_service

        try:
            return get_service().record_install_milestone(body)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/setup/import/openclaw", dependencies=[Depends(require_setup_access)])
    async def setup_import_openclaw(body: dict | None = None):
        from services.setupd.service import get_service

        source_path = str((body or {}).get("source_path", "")).strip()
        return get_service().import_openclaw(source_path)

    @app.post("/api/setup/plan", dependencies=[Depends(require_setup_access)])
    async def setup_plan():
        from services.setupd.service import get_service

        return get_service().build_plan()

    @app.post("/api/setup/model", dependencies=[Depends(require_setup_access)])
    async def setup_model(body: dict | None = None):
        from services.setupd.service import get_service

        try:
            return get_service().prepare_model(str((body or {}).get("model", "")).strip())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/setup/voice-test", dependencies=[Depends(require_setup_access)])
    async def setup_voice_test(body: dict | None = None):
        from services.setupd.service import get_service

        sample_text = str((body or {}).get("sample_text", "")).strip()
        return await get_service().run_voice_test(sample_text=sample_text)

    @app.post("/api/setup/voice-greet", dependencies=[Depends(require_setup_access)])
    async def setup_voice_greet(body: dict | None = None):
        """Fire-and-forget JARVIS TTS greeting for the Summary → Dashboard handoff.
        The Summary screen calls this immediately before navigating to '/' so the
        user hears Piper say their name as the dashboard paints."""
        from services.setupd.service import get_service

        line = str((body or {}).get("line", "")).strip()
        return await get_service().speak_greeting(line=line)

    @app.post("/api/setup/apply", dependencies=[Depends(require_setup_access)])
    async def setup_apply():
        from services.setupd.service import get_service

        return get_service().apply()

    @app.post("/api/setup/retry", dependencies=[Depends(require_setup_access)])
    async def setup_retry():
        from services.setupd.service import get_service

        return get_service().retry()

    @app.post("/api/setup/repair", dependencies=[Depends(require_setup_access)])
    async def setup_repair():
        from services.setupd.service import get_service

        return get_service().repair()

    @app.post("/api/setup/cancel", dependencies=[Depends(require_setup_access)])
    async def setup_cancel():
        from services.setupd.service import get_service

        return get_service().cancel()

    @app.get("/api/setup/logs", dependencies=[Depends(require_setup_access)])
    async def setup_logs():
        from services.setupd.service import get_service

        return {"logs": get_service().get_state().logs}

    @app.get("/api/setup/diagnostics", dependencies=[Depends(require_setup_access)])
    async def setup_diagnostics():
        from services.setupd.service import get_service

        return get_service().diagnostics()

    @app.get("/api/setup/frameworks", dependencies=[Depends(require_setup_access)])
    async def setup_frameworks(profile_id: str = ""):
        """Framework catalog enriched with tier compatibility for the
        FrameworkScreen. Falls back to profile_id derived from current
        state.detected_hardware when the query param is omitted.
        """
        from services.setupd.service import get_service

        svc = get_service()
        pid = (profile_id or "").strip()
        if not pid:
            hw = svc.get_state().detected_hardware or {}
            pid = str(hw.get("profile_id", "")).strip()
        try:
            from frameworks.registry import get_registry

            items = get_registry().list_for_tier(pid or "unknown")
        except (ImportError, ModuleNotFoundError):
            items = []
        return {"profile_id": pid, "frameworks": items}

    @app.post("/api/support/bundle", dependencies=[Depends(require_setup_access)])
    async def support_bundle():
        from tools.support.support_bundle import create_support_bundle

        bundle = create_support_bundle()
        return {"path": str(bundle), "name": bundle.name}

    @app.get("/api/desktop/posture", dependencies=[Depends(require_auth)])
    async def desktop_posture_endpoint():
        from clawos_core.desktop_integration import desktop_posture

        return desktop_posture()

    @app.post("/api/desktop/launch-on-login", dependencies=[Depends(require_auth)])
    async def desktop_launch_on_login(body: dict = None):
        from clawos_core.desktop_integration import (
            desktop_posture,
            disable_launch_on_login,
            enable_launch_on_login,
        )

        payload = body or {}
        enabled = bool(payload.get("enabled", True))
        command = str(payload.get("command", "")).strip() or None

        try:
            changed_path = enable_launch_on_login(command) if enabled else disable_launch_on_login()
        except (OSError, RuntimeError) as exc:
            raise HTTPException(status_code=500, detail=str(exc))

        response = desktop_posture()
        response["changed_path"] = str(changed_path) if changed_path else response.get("launch_on_login_path", "")
        response["message"] = "Launch on login enabled" if enabled else "Launch on login disabled"
        return response

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
        except (ImportError, ModuleNotFoundError) as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.post("/api/workflows/{workflow_id}/run", dependencies=[Depends(require_auth)])
    async def run_workflow(workflow_id: str, body: dict = None):
        workflow_args = (body or {}).get("args", {})
        workspace_id = (body or {}).get("workspace", DEFAULT_WORKSPACE)
        try:
            from workflows.engine import get_engine

            eng = get_engine()
            eng.load_registry()
            result = await eng.run(workflow_id, workflow_args, workspace_id=workspace_id)
            return {
                "status": result.status.value,
                "output": result.output,
                "metadata": result.metadata,
                "error": result.error,
            }
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Workflow not found: {workflow_id}")
        except (OSError, ConnectionError, TimeoutError) as exc:
            await mgr.broadcast(
                {
                    "type": "workflow_error",
                    "data": {"id": workflow_id, "error": str(exc)},
                }
            )
            raise HTTPException(status_code=500, detail=str(exc))

    @app.post("/api/workbench/fetch", dependencies=[Depends(require_auth)])
    async def workbench_fetch(body: dict | None = None):
        url = str((body or {}).get("url", "")).strip()
        if not url:
            raise HTTPException(status_code=400, detail="url required")
        try:
            page = await asyncio.get_event_loop().run_in_executor(None, _workbench_fetch, url)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except (OSError, RuntimeError, TimeoutError) as exc:
            raise HTTPException(status_code=502, detail=f"Fetch failed: {exc}")
        return page

    @app.post("/api/workbench/research", dependencies=[Depends(require_auth)])
    async def workbench_research(body: dict | None = None):
        payload = body or {}
        query = str(payload.get("query", "")).strip()
        url = str(payload.get("url", "")).strip()
        workspace = str(payload.get("workspace", DEFAULT_WORKSPACE))
        if not query and not url:
            raise HTTPException(status_code=400, detail="query or url required")

        page: dict | None = None
        if url:
            try:
                page = await asyncio.get_event_loop().run_in_executor(None, _workbench_fetch, url)
            except (OSError, RuntimeError, TimeoutError):
                page = None

        context_parts = []
        if query:
            context_parts.append(f"Research task: {query}")
        if url:
            context_parts.append(f"Source URL: {url}")
        if page:
            context_parts.append(f"Page title: {page['title']}")
            context_parts.append(f"Page content:\n{page['text'][:4000]}")
        intent = "\n\n".join(context_parts)

        session_id = secrets.token_urlsafe(8)
        session: dict = {
            "id": session_id,
            "query": query or url,
            "url": url,
            "status": "submitted",
            "page": page,
            "task_id": None,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        try:
            from services.agentd.service import get_manager
            task = await get_manager().submit(intent, workspace_id=workspace, channel="workbench")
            session["task_id"] = task.task_id
            session["status"] = "analyzing"
        except (ImportError, ModuleNotFoundError):
            session["status"] = "error"

        _WORKBENCH_SESSIONS.appendleft(session)
        record_trace(
            make_trace(
                title=f"Workbench research: {(query or url)[:60]}",
                category="workbench",
                status="completed" if session["task_id"] else "warning",
                tools=["workbench.research"],
                metadata={"url": url, "has_page": page is not None},
            )
        )
        return {"ok": bool(session["task_id"]), "session": session}

    @app.get("/api/workbench/sessions", dependencies=[Depends(require_auth)])
    async def workbench_sessions():
        return list(_WORKBENCH_SESSIONS)

    # ── Research engine ────────────────────────────────────────────────────────

    @app.post("/api/research/start", dependencies=[Depends(require_auth)])
    async def research_start(body: dict | None = None):
        payload = body or {}
        query = str(payload.get("query", "")).strip()
        seed_urls = [str(u) for u in (payload.get("seed_urls") or []) if u]
        provider_override = str(payload.get("provider", "")).strip() or None
        api_key_override = str(payload.get("api_key", "")).strip() or None
        workspace = str(payload.get("workspace", DEFAULT_WORKSPACE))
        if not query and not seed_urls:
            raise HTTPException(status_code=400, detail="query or seed_urls required")

        from services.researchd.engine import get_engine as get_research_engine
        eng = get_research_engine()
        session = await asyncio.get_event_loop().run_in_executor(
            None, lambda: eng.start_session(query or seed_urls[0], seed_urls, provider_override, api_key_override)
        )
        session = await asyncio.get_event_loop().run_in_executor(None, eng.fetch_sources, session)

        try:
            from services.agentd.service import get_manager
            intent = eng.build_agent_intent(session)
            task = await get_manager().submit(intent, workspace_id=workspace, channel="research")
            eng.mark_done(session, task_id=task.task_id)
        except (ImportError, ModuleNotFoundError) as exc:
            log.warning("Research agent submit failed: %s", exc)
            eng.mark_error(session, str(exc))

        record_trace(
            make_trace(
                title=f"Research: {(query or seed_urls[0])[:60]}",
                category="research",
                status="completed" if session.status == "done" else "warning",
                tools=["researchd.start"],
                metadata={
                    "provider": session.provider,
                    "sources": len(session.sources),
                    "citations": len(session.citations),
                },
            )
        )
        return session.to_dict()

    @app.get("/api/research/sessions", dependencies=[Depends(require_auth)])
    async def research_sessions():
        from services.researchd.engine import ResearchSession
        return ResearchSession.list_all()

    @app.get("/api/research/sessions/{session_id}", dependencies=[Depends(require_auth)])
    async def research_session_detail(session_id: str):
        from services.researchd.engine import ResearchSession
        session = ResearchSession.load(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session.to_dict()

    @app.post("/api/research/sessions/{session_id}/resume", dependencies=[Depends(require_auth)])
    async def research_resume(session_id: str, body: dict | None = None):
        workspace = str((body or {}).get("workspace", DEFAULT_WORKSPACE))
        from services.researchd.engine import get_engine as get_research_engine
        eng = get_research_engine()
        session = eng.resume_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        session = await asyncio.get_event_loop().run_in_executor(None, eng.fetch_sources, session)
        try:
            from services.agentd.service import get_manager
            intent = eng.build_agent_intent(session)
            task = await get_manager().submit(intent, workspace_id=workspace, channel="research")
            eng.mark_done(session, task_id=task.task_id)
        except (ImportError, ModuleNotFoundError) as exc:
            eng.mark_error(session, str(exc))
        return session.to_dict()

    @app.post("/api/research/sessions/{session_id}/pause", dependencies=[Depends(require_auth)])
    async def research_pause(session_id: str):
        from services.researchd.engine import get_engine as get_research_engine
        ok = get_research_engine().pause_session(session_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"ok": True}

    @app.delete("/api/research/sessions/{session_id}", dependencies=[Depends(require_auth)])
    async def research_delete(session_id: str):
        from services.researchd.engine import get_engine as get_research_engine
        ok = get_research_engine().delete_session(session_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"ok": True}

    # ── Pack Studio ───────────────────────────────────────────────────────────

    @app.get("/api/studio/programs", dependencies=[Depends(require_auth)])
    async def studio_list_programs():
        from clawos_core.catalog import list_workflow_programs
        return [p.to_dict() for p in list_workflow_programs()]

    @app.post("/api/studio/programs", dependencies=[Depends(require_auth)])
    async def studio_save_program(body: dict | None = None):
        from clawos_core.catalog import save_workflow_program
        payload = body or {}
        if not payload.get("id") or not payload.get("name"):
            raise HTTPException(status_code=400, detail="id and name required")
        result = save_workflow_program(payload)
        record_trace(
            make_trace(
                title=f"Studio: saved program {payload.get('name')}",
                category="studio",
                status="completed",
                tools=["studio.save"],
                metadata={"program_id": payload.get("id")},
            )
        )
        return result

    @app.delete("/api/studio/programs/{program_id}", dependencies=[Depends(require_auth)])
    async def studio_delete_program(program_id: str):
        from clawos_core.catalog import delete_workflow_program
        ok = delete_workflow_program(program_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Program not found")
        return {"ok": True}

    @app.post("/api/studio/programs/{program_id}/deploy", dependencies=[Depends(require_auth)])
    async def studio_deploy_program(program_id: str):
        from clawos_core.catalog import get_workflow_program
        program = get_workflow_program(program_id)
        if not program:
            raise HTTPException(status_code=404, detail="Program not found")
        # Build intent from program nodes and submit to agentd
        intent = f"Execute workflow program: {program.name}\n\n{program.summary or ''}"
        if program.checkpoints:
            intent += "\n\nSteps:\n" + "\n".join(f"  - {step}" for step in program.checkpoints)
        try:
            from services.agentd.service import get_manager
            task = await get_manager().submit(intent, workspace_id=DEFAULT_WORKSPACE, channel="studio")
            return {"ok": True, "task_id": task.task_id, "program": program.to_dict()}
        except (ImportError, ModuleNotFoundError) as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    # ── Framework Store ───────────────────────────────────────────────────────

    @app.get("/api/frameworks", dependencies=[Depends(require_auth)])
    async def frameworks_list():
        from services.frameworkd.service import list_frameworks, get_active_framework
        try:
            from bootstrap.hardware_probe import load_saved
            hw = load_saved()
            profile_id = hw.profile_id
        except (ImportError, ModuleNotFoundError):
            profile_id = "x86-cpu-16gb"
        rows = list_frameworks(profile_id)
        active = get_active_framework()
        return {"frameworks": rows, "active": active, "profile_id": profile_id}

    @app.post("/api/frameworks/{name}/install", dependencies=[Depends(require_auth)])
    async def frameworks_install(name: str):
        from services.frameworkd.service import install_framework
        name = name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="name required")
        result = await asyncio.get_event_loop().run_in_executor(
            None, install_framework, name
        )
        if not result["ok"]:
            raise HTTPException(status_code=500, detail=result["message"])
        return result

    @app.delete("/api/frameworks/{name}", dependencies=[Depends(require_auth)])
    async def frameworks_remove(name: str):
        from services.frameworkd.service import remove_framework
        result = await asyncio.get_event_loop().run_in_executor(
            None, remove_framework, name
        )
        if not result["ok"]:
            raise HTTPException(status_code=500, detail=result["message"])
        return result

    @app.post("/api/frameworks/{name}/start", dependencies=[Depends(require_auth)])
    async def frameworks_start(name: str):
        from services.frameworkd.service import start_framework
        result = start_framework(name)
        if not result["ok"]:
            raise HTTPException(status_code=500, detail=f"Could not start {name}")
        return result

    @app.post("/api/frameworks/{name}/stop", dependencies=[Depends(require_auth)])
    async def frameworks_stop(name: str):
        from services.frameworkd.service import stop_framework
        return stop_framework(name)

    @app.get("/api/frameworks/active", dependencies=[Depends(require_auth)])
    async def frameworks_get_active():
        from services.frameworkd.service import get_active_framework
        return {"active": get_active_framework()}

    @app.put("/api/frameworks/active", dependencies=[Depends(require_auth)])
    async def frameworks_set_active(body: dict | None = None):
        name = str((body or {}).get("name", "")).strip()
        if not name:
            raise HTTPException(status_code=400, detail="name required")
        from services.frameworkd.service import set_active_framework
        result = set_active_framework(name)
        if not result["ok"]:
            raise HTTPException(status_code=400, detail=result.get("error", "Failed"))
        return result

    # ── OMI ambient AI integration ──────────────────────────────────────────

    @app.post("/api/omi/transcript")
    async def omi_transcript(request: Request):
        """Real-time transcript webhook from OMI macOS app. No auth — OMI sends unsigned."""
        uid = request.query_params.get("uid", "default")
        body = await request.json()
        segments = body.get("segments", [])
        from services.omid.service import get_service
        reply = get_service().handle_transcript(uid, segments)
        return {"message": reply}

    @app.post("/api/omi/conversation")
    async def omi_conversation(request: Request):
        """Conversation-end webhook from OMI macOS app. No auth — OMI sends unsigned."""
        uid = request.query_params.get("uid", "default")
        body = await request.json()
        from services.omid.service import get_service
        reply = await get_service().handle_conversation(uid, body)
        return {"message": reply}

    @app.get("/api/omi/status", dependencies=[Depends(require_auth)])
    async def omi_status():
        """OMI integration stats + webhook URLs."""
        from services.omid.service import get_service
        return get_service().get_stats()

    @app.get("/api/omi/conversations", dependencies=[Depends(require_auth)])
    async def omi_conversations(limit: int = 20):
        """List recent OMI conversations stored in memory."""
        from services.omid.service import get_service
        return {"conversations": get_service().list_conversations(limit)}

    # ── A2A federation peer management ────────────────────────────────────────

    @app.get("/api/a2a/peers", dependencies=[Depends(require_auth)])
    async def a2a_list_peers():
        from services.a2ad.peer_registry import get_registry
        return get_registry().list_peers()

    @app.post("/api/a2a/peers", dependencies=[Depends(require_auth)])
    async def a2a_add_peer(body: dict | None = None):
        payload = body or {}
        url = str(payload.get("url", "")).strip()
        name = str(payload.get("name", "")).strip()
        trust_tier = str(payload.get("trust_tier", "unverified")).strip()
        if not url:
            raise HTTPException(status_code=400, detail="url required")
        from services.a2ad.peer_registry import get_registry
        peer = get_registry().add_peer(url, name=name, trust_tier=trust_tier)
        return peer.to_dict()

    @app.delete("/api/a2a/peers/{peer_id}", dependencies=[Depends(require_auth)])
    async def a2a_remove_peer(peer_id: str):
        from services.a2ad.peer_registry import get_registry
        ok = get_registry().remove_peer(peer_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Peer not found")
        return {"ok": True}

    @app.post("/api/a2a/peers/{peer_id}/trust", dependencies=[Depends(require_auth)])
    async def a2a_set_trust(peer_id: str, body: dict | None = None):
        trust_tier = str((body or {}).get("trust_tier", "trusted")).strip()
        from services.a2ad.peer_registry import get_registry
        peer = get_registry().set_trust(peer_id, trust_tier)
        if not peer:
            raise HTTPException(status_code=404, detail="Peer not found or invalid trust tier")
        return peer.to_dict()

    @app.post("/api/a2a/peers/{peer_id}/probe", dependencies=[Depends(require_auth)])
    async def a2a_probe_peer(peer_id: str):
        from services.a2ad.peer_registry import get_registry
        try:
            peer = await asyncio.get_event_loop().run_in_executor(
                None, get_registry().probe_peer, peer_id
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except (OSError, RuntimeError, TimeoutError) as exc:
            raise HTTPException(status_code=502, detail=str(exc))
        return peer.to_dict()

    @app.get("/api/a2a/signing-key", dependencies=[Depends(require_auth)])
    async def a2a_signing_key_info():
        from services.a2ad.peer_registry import get_registry
        return {"fingerprint": get_registry().get_signing_key_fingerprint()}

    # ── MCP manager ───────────────────────────────────────────────────────────

    @app.get("/api/mcp/servers", dependencies=[Depends(require_auth)])
    async def mcp_list_servers():
        from services.mcpd.service import get_service as get_mcp
        return get_mcp().list_servers()

    @app.get("/api/mcp/well-known", dependencies=[Depends(require_auth)])
    async def mcp_well_known():
        from services.mcpd.service import MCPService
        return MCPService.WELL_KNOWN

    @app.post("/api/mcp/servers", dependencies=[Depends(require_auth)])
    async def mcp_add_server(body: dict | None = None):
        payload = body or {}
        name = str(payload.get("name", "")).strip()
        transport = str(payload.get("transport", "stdio")).strip()
        if not name:
            raise HTTPException(status_code=400, detail="name required")
        if transport not in ("stdio", "http"):
            raise HTTPException(status_code=400, detail="transport must be stdio or http")
        command = payload.get("command") or []
        endpoint = str(payload.get("endpoint", "")).strip()
        env = dict(payload.get("env") or {})
        if transport == "stdio" and not command:
            raise HTTPException(status_code=400, detail="command required for stdio transport")
        if transport == "http" and not endpoint:
            raise HTTPException(status_code=400, detail="endpoint required for http transport")
        from services.mcpd.service import get_service as get_mcp
        cfg = get_mcp().add_server(name, transport, command=command, endpoint=endpoint, env=env)
        return cfg.to_dict()

    @app.delete("/api/mcp/servers/{server_id}", dependencies=[Depends(require_auth)])
    async def mcp_remove_server(server_id: str):
        from services.mcpd.service import get_service as get_mcp
        ok = get_mcp().remove_server(server_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Server not found")
        return {"ok": True}

    @app.patch("/api/mcp/servers/{server_id}", dependencies=[Depends(require_auth)])
    async def mcp_update_server(server_id: str, body: dict | None = None):
        from services.mcpd.service import get_service as get_mcp
        cfg = get_mcp().update_server(server_id, body or {})
        if not cfg:
            raise HTTPException(status_code=404, detail="Server not found")
        return cfg.to_dict()

    @app.post("/api/mcp/servers/{server_id}/connect", dependencies=[Depends(require_auth)])
    async def mcp_connect_server(server_id: str):
        from services.mcpd.service import get_service as get_mcp
        try:
            cfg = await get_mcp().connect(server_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=502, detail=str(exc))
        record_trace(
            make_trace(
                title=f"MCP connect: {cfg.name}",
                category="mcp",
                status="completed" if cfg.status == "connected" else "warning",
                tools=["mcpd.connect"],
                metadata={"server": cfg.name, "transport": cfg.transport, "tools": len(cfg.tools)},
            )
        )
        return cfg.to_dict()

    @app.get("/api/mcp/tools", dependencies=[Depends(require_auth)])
    async def mcp_list_tools():
        from services.mcpd.service import get_service as get_mcp
        return get_mcp().list_all_tools()

    @app.get("/api/mcp/resources", dependencies=[Depends(require_auth)])
    async def mcp_list_resources():
        from services.mcpd.service import get_service as get_mcp
        return get_mcp().list_all_resources()

    @app.post("/api/mcp/call", dependencies=[Depends(require_auth)])
    async def mcp_call_tool(body: dict | None = None):
        payload = body or {}
        server_id = str(payload.get("server_id", "")).strip()
        tool_name = str(payload.get("tool", "")).strip()
        arguments = dict(payload.get("arguments") or {})
        if not server_id or not tool_name:
            raise HTTPException(status_code=400, detail="server_id and tool required")
        from services.mcpd.service import get_service as get_mcp
        try:
            result = await get_mcp().call_tool(server_id, tool_name, arguments)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
        record_trace(
            make_trace(
                title=f"MCP tool call: {tool_name}",
                category="mcp",
                status="completed",
                tools=[f"mcp.{tool_name}"],
                metadata={"server_id": server_id, "tool": tool_name},
            )
        )
        return {"ok": True, "result": result}

    @app.post("/api/mcp/resources/read", dependencies=[Depends(require_auth)])
    async def mcp_read_resource(body: dict | None = None):
        payload = body or {}
        server_id = str(payload.get("server_id", "")).strip()
        uri = str(payload.get("uri", "")).strip()
        if not server_id or not uri:
            raise HTTPException(status_code=400, detail="server_id and uri required")
        from services.mcpd.service import get_service as get_mcp
        try:
            result = await get_mcp().read_resource(server_id, uri)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail=str(exc))
        return {"ok": True, "content": result}

    # ── Kizuna (絆) — Living Knowledge Graph ────────────────────────────────

    @app.get("/api/brain/status", dependencies=[Depends(require_auth)])
    async def brain_status():
        """Get Kizuna ingestion status and node/edge counts."""
        try:
            from services.braind.service import get_brain
            return get_brain().get_status()
        except (ImportError, ModuleNotFoundError) as e:
            return {"node_count": 0, "edge_count": 0, "ingesting": False, "error": str(e)}

    @app.get("/api/brain/graph", dependencies=[Depends(require_auth)])
    async def brain_graph():
        """Get {nodes, links} for react-force-graph-3d renderer."""
        try:
            from services.braind.service import get_brain
            return get_brain().get_graph()
        except (ImportError, ModuleNotFoundError) as e:
            return {"nodes": [], "links": [], "error": str(e)}

    @app.get("/api/brain/node/{node_id}", dependencies=[Depends(require_auth)])
    async def brain_node(node_id: str):
        """Get detail for a single node: neighbors, sources, pagerank."""
        try:
            from services.braind.service import get_brain
            node = get_brain().get_node(node_id)
            if not node:
                raise HTTPException(status_code=404, detail="Node not found")
            return node
        except HTTPException:
            raise
        except (OSError, ValueError) as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/brain/context", dependencies=[Depends(require_auth)])
    async def brain_context(q: str = ""):
        """GraphRAG context retrieval — used by agents for context assembly."""
        if not q:
            return {"nodes": [], "context_text": ""}
        try:
            from services.braind.service import get_brain
            return get_brain().get_context(q)
        except (ImportError, ModuleNotFoundError) as e:
            return {"nodes": [], "context_text": "", "error": str(e)}

    @app.get("/api/brain/gaps", dependencies=[Depends(require_auth)])
    async def brain_gaps():
        """Find isolated nodes and disconnected clusters."""
        try:
            from services.braind.service import get_brain
            return {"gaps": get_brain().get_gaps()}
        except (ImportError, ModuleNotFoundError) as e:
            return {"gaps": [], "error": str(e)}

    @app.post("/api/brain/expand", dependencies=[Depends(require_auth)])
    async def brain_expand(body: dict | None = None):
        """Agent write-back — add new knowledge to brain (significance-filtered)."""
        payload = body or {}
        text = str(payload.get("text", "")).strip()
        source = str(payload.get("source", "agent"))
        task_id = str(payload.get("task_id", ""))
        if not text:
            raise HTTPException(status_code=400, detail="text required")
        try:
            from services.braind.service import get_brain
            return await get_brain().expand_from_agent(text, source=source, task_id=task_id)
        except (ImportError, ModuleNotFoundError) as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/brain/upload", dependencies=[Depends(require_auth)])
    async def brain_upload(request):
        """Upload ZIP of documents for ingestion into Kizuna."""
        import tempfile
        from fastapi import Request
        from pathlib import Path
        try:
            from services.braind.service import get_brain
            brain = get_brain()

            if brain.get_status()["ingesting"]:
                raise HTTPException(status_code=409, detail="Ingestion already in progress")

            # Read the upload
            body = await request.body()
            if not body:
                raise HTTPException(status_code=400, detail="No file data received")

            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
                f.write(body)
                tmp_path = Path(f.name)

            # Start ingestion in background
            asyncio.create_task(brain.ingest_zip(tmp_path))

            return {"ok": True, "message": "Ingestion started — watch /api/brain/status for progress"}
        except HTTPException:
            raise
        except (OSError, ValueError) as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.websocket("/ws/brain")
    async def brain_websocket(websocket: WebSocket):
        """WebSocket for real-time ingestion progress and neuron-firing events."""
        from fastapi.websockets import WebSocketDisconnect
        if not _websocket_authorized(websocket):
            await websocket.close(code=4401)
            return
        await websocket.accept()

        try:
            from services.braind.service import get_brain
            brain = get_brain()

            async def send_progress(event: str, data: dict):
                try:
                    await websocket.send_json({"event": event, **data})
                except (OSError, ConnectionError, TimeoutError) as e:
                    log.debug(f"unexpected: {e}")
                    pass
                    pass

            brain.register_ws_callback(send_progress)

            # Send current status immediately
            await websocket.send_json({"event": "status", **brain.get_status()})

            # Keep alive
            while True:
                try:
                    msg = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                    if msg == "ping":
                        await websocket.send_json({"event": "pong"})
                except asyncio.TimeoutError:
                    await websocket.send_json({"event": "heartbeat"})
                except (ImportError, ModuleNotFoundError):
                    break

        except WebSocketDisconnect as e:
            log.debug(f"suppressed: {e}")
        except (OSError, ConnectionError, TimeoutError) as e:
            log.debug(f"failed: {e}")
            pass
        finally:
            try:
                from services.braind.service import get_brain
                get_brain().unregister_ws_callback(send_progress)
            except (ImportError, ModuleNotFoundError):
                log.debug(f"failed: {e}")
                pass
                pass

    # ── License & Feature Gate (Phase 16) ─────────────────────────────────────

    @app.get("/api/license", dependencies=[Depends(require_auth)])
    async def license_get():
        """Get current license status."""
        try:
            from clawos_core.license import get_license_manager
            mgr = get_license_manager()
            return mgr.get_status()
        except (ImportError, ModuleNotFoundError) as e:
            return {"tier": "free", "valid": False, "error": str(e)}

    @app.post("/api/license/activate", dependencies=[Depends(require_auth)])
    async def license_activate(body: dict | None = None):
        """Activate a license key."""
        key = str((body or {}).get("key", "")).strip()
        if not key:
            raise HTTPException(status_code=400, detail="key required")
        try:
            from clawos_core.license import get_license_manager
            mgr = get_license_manager()
            result = mgr.activate(key)
            if not result["ok"]:
                raise HTTPException(status_code=400, detail=result["error"])
            return result
        except HTTPException:
            raise
        except (OSError, ValueError) as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/license/deactivate", dependencies=[Depends(require_auth)])
    async def license_deactivate():
        """Deactivate license on this machine."""
        try:
            from clawos_core.license import get_license_manager
            return get_license_manager().deactivate()
        except (ImportError, ModuleNotFoundError) as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ── Proactive Ambient Intelligence (Phase 8) ─────────────────────────────

    @app.get("/api/suggestions", dependencies=[Depends(require_auth)])
    async def suggestions_get():
        """Return proactive suggestion cards for the Overview page."""
        try:
            from clawos_core.ambient import get_suggestions
            return {"suggestions": get_suggestions()}
        except (ImportError, ModuleNotFoundError) as e:
            log.warning(f"Suggestions check failed: {e}")
            return {"suggestions": []}

    @app.delete("/api/suggestions/{suggestion_id}", dependencies=[Depends(require_auth)])
    async def suggestions_dismiss(suggestion_id: str):
        """Dismiss a suggestion card."""
        try:
            from clawos_core.ambient import dismiss_suggestion
            ok = dismiss_suggestion(suggestion_id)
            return {"ok": ok}
        except (ImportError, ModuleNotFoundError) as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/suggestions/refresh", dependencies=[Depends(require_auth)])
    async def suggestions_refresh():
        """Force-refresh ambient checks immediately."""
        try:
            from clawos_core.ambient import run_checks
            results = run_checks(force=True)
            return {"suggestions": [s.to_dict() for s in results]}
        except (ImportError, ModuleNotFoundError) as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ── Skill Marketplace (Phase 15) ──────────────────────────────────────────

    @app.get("/api/skills", dependencies=[Depends(require_auth)])
    async def skills_search(q: str = "", page: int = 1, limit: int = 20):
        """Search ClawHub for skills."""
        try:
            from skills.marketplace.registry import search_skills
            return search_skills(query=q, page=page, limit=limit)
        except (ImportError, ModuleNotFoundError) as e:
            return {"results": [], "total": 0, "error": str(e)}

    @app.get("/api/skills/installed", dependencies=[Depends(require_auth)])
    async def skills_installed():
        """List installed skills."""
        try:
            from skills.marketplace.registry import get_installed_skills
            return {"skills": get_installed_skills()}
        except (ImportError, ModuleNotFoundError) as e:
            return {"skills": [], "error": str(e)}

    @app.post("/api/skills/install", dependencies=[Depends(require_auth)])
    async def skills_install(body: dict | None = None):
        """Install a skill from ClawHub."""
        payload = body or {}
        skill_id = str(payload.get("skill_id", "")).strip()
        if not skill_id:
            raise HTTPException(status_code=400, detail="skill_id required")
        force = bool(payload.get("force", False))
        allow_community = bool(payload.get("allow_community", True))
        try:
            from skills.marketplace.installer import install_skill
            result = install_skill(skill_id, force=force, allow_community=allow_community)
            if not result["ok"]:
                raise HTTPException(status_code=400, detail=result["error"])
            return result
        except HTTPException:
            raise
        except (OSError, subprocess.SubprocessError, RuntimeError) as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/skills/{skill_id}", dependencies=[Depends(require_auth)])
    async def skills_remove(skill_id: str):
        """Remove an installed skill."""
        try:
            from skills.marketplace.installer import uninstall_skill
            result = uninstall_skill(skill_id)
            if not result["ok"]:
                raise HTTPException(status_code=404, detail=result["error"])
            return result
        except HTTPException:
            raise
        except (OSError, subprocess.SubprocessError, RuntimeError) as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ── Evolution Log (Learning Log) ─────────────────────────────────────────

    EVOLUTION_PATH = Path(__file__).parent.parent.parent / "EVOLUTION.md"

    @app.get("/api/evolution", dependencies=[Depends(require_auth)])
    async def get_evolution():
        """Return the EVOLUTION.md learning log as structured data."""
        if not EVOLUTION_PATH.exists():
            return {"entries": [], "total": 0}
        try:
            text = EVOLUTION_PATH.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return {"entries": [], "total": 0}

        entries = []
        # Split on level-2 headings of the form "## YYYY-MM-DD — Title"
        blocks = re.split(r"\n(?=## \d{4}-\d{2}-\d{2})", text)
        for block in blocks:
            heading_m = re.match(
                r"^## (\d{4}-\d{2}-\d{2})\s+[—\-]+\s+(.+)", block.strip()
            )
            if not heading_m:
                continue
            date = heading_m.group(1)
            title = heading_m.group(2).strip()

            def _extract(label: str, src: str) -> str:
                m = re.search(
                    rf"\*\*{re.escape(label)}\*\*[:\s]*(.*?)(?=\n\*\*|\Z)",
                    src,
                    re.DOTALL,
                )
                return m.group(1).strip() if m else ""

            entries.append(
                {
                    "date": date,
                    "title": title,
                    "sections": {
                        "what_happened": _extract("What happened:", block),
                        "root_cause": _extract("Root cause:", block),
                        "learned": _extract("What ClawOS learned:", block),
                        "fix": _extract("Fix shipped:", block),
                    },
                }
            )

        return {"entries": entries, "total": len(entries)}

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
        except (OSError, ConnectionError, TimeoutError):
            mgr.disconnect(websocket)

    @app.websocket("/ws/setup")
    async def setup_ws_endpoint(websocket: WebSocket):
        if not _setup_websocket_authorized(websocket):
            await websocket.close(code=4401)
            return

        from services.setupd.service import get_service

        service = get_service()
        await websocket.accept()
        service._listeners.add(websocket)
        try:
            await websocket.send_json({"type": "setup_state", "data": service.to_dict()})
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            service._listeners.discard(websocket)
        except (OSError, ConnectionError, TimeoutError):
            service._listeners.discard(websocket)

    @app.websocket("/ws/jarvis")
    async def jarvis_ws_endpoint(websocket: WebSocket):
        """WebSocket for real-time Jarvis session state updates."""
        if not _websocket_authorized(websocket):
            await websocket.close(code=4401)
            return
        await websocket.accept()
        service = _jarvis_service()

        async def on_session(session: dict) -> None:
            try:
                await websocket.send_json({"type": "jarvis_session", "data": session})
            except (OSError, ConnectionError, TimeoutError) as e:
                log.debug(f"unexpected: {e}")
                pass
                pass

        service.add_session_listener(on_session)
        try:
            await websocket.send_json({"type": "jarvis_session", "data": service.session()})
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            service.remove_session_listener(on_session)
        except (OSError, ConnectionError, TimeoutError):
            service.remove_session_listener(on_session)

    if DASHBOARD_STATIC_DIR.exists():
        assets_dir = DASHBOARD_STATIC_DIR / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str, request: Request):
            if not full_path or full_path.startswith("api") or full_path.startswith("ws"):
                raise HTTPException(status_code=404, detail="Not found")
            asset = DASHBOARD_STATIC_DIR / full_path
            if asset.exists() and asset.is_file():
                return FileResponse(str(asset))
            if DASHBOARD_STATIC_INDEX.exists():
                return _dashboard_index_response(request)
            raise HTTPException(status_code=404, detail="Not found")

    return app


def run():
    if not FASTAPI_OK:
        log.error("fastapi/uvicorn not installed - dashboard unavailable")
        return
    app = create_app()
    settings: DashboardSettings = app.state.settings
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="warning")
