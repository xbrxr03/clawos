# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS a2ad - Agent-to-Agent Protocol Server
============================================
Implements the A2A protocol with safer defaults: loopback bind unless the
operator intentionally configures a bearer token for remote access.
"""
import asyncio
import json
import logging
import os
import secrets
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Optional

from clawos_core.config.loader import get as get_config
from clawos_core.constants import A2A_BEARER_TOKEN_ENV, DEFAULT_WORKSPACE, PORT_A2AD

log = logging.getLogger("a2ad")

_zeroconf = None

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse, StreamingResponse
    import uvicorn

    FASTAPI_OK = True
except ImportError:
    FASTAPI_OK = False
    FastAPI = HTTPException = Request = None
    JSONResponse = StreamingResponse = None


@dataclass(frozen=True)
class A2ASettings:
    host: str = "127.0.0.1"
    port: int = PORT_A2AD
    auth_token: str = ""
    mdns_enabled: bool = False


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


def _extract_bearer_token(authorization: str) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer":
        return ""
    return token.strip()


def _token_matches(candidate: str, expected: str) -> bool:
    return bool(candidate and expected) and secrets.compare_digest(candidate, expected)


def load_a2a_settings(overrides: Optional[dict[str, Any]] = None) -> A2ASettings:
    overrides = overrides or {}
    host = str(overrides.get("host", get_config("a2a.host", "127.0.0.1")))
    port = int(overrides.get("port", get_config("a2a.port", PORT_A2AD)))
    auth_token = str(
        overrides["auth_token"]
        if "auth_token" in overrides
        else os.environ.get(A2A_BEARER_TOKEN_ENV, get_config("a2a.auth_token", ""))
    ).strip()
    mdns_enabled = _coerce_bool(
        overrides.get("mdns_enabled", get_config("a2a.mdns_enabled", False)),
        False,
    )

    if not auth_token and not _is_loopback_host(host):
        log.warning(
            "a2ad requested a non-loopback bind without a bearer token; forcing 127.0.0.1"
        )
        host = "127.0.0.1"
        mdns_enabled = False

    if _is_loopback_host(host) and mdns_enabled:
        log.warning("a2ad mDNS disabled because the server is bound to loopback only")
        mdns_enabled = False

    return A2ASettings(host=host, port=port, auth_token=auth_token, mdns_enabled=mdns_enabled)


def _is_request_authorized(request: Request, auth_token: str) -> bool:
    if not auth_token:
        return True
    return _token_matches(
        _extract_bearer_token(request.headers.get("Authorization", "")),
        auth_token,
    )


def create_app(settings: Optional[dict[str, Any]] = None) -> "FastAPI":
    if not FASTAPI_OK:
        raise RuntimeError("fastapi not installed")

    from clawos_core.models import A2ATask
    from services.a2ad.agent_card import build_card
    from services.a2ad.discovery import get_local_ip, get_peers, publish, start_discovery
    from services.a2ad.task_handler import handle_task

    def _require_auth(request: Request):
        settings_obj: A2ASettings = request.app.state.settings
        if _is_request_authorized(request, settings_obj.auth_token):
            return
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )

    @asynccontextmanager
    async def lifespan(app_obj: "FastAPI"):
        global _zeroconf
        settings_obj: A2ASettings = app_obj.state.settings
        if settings_obj.mdns_enabled:
            start_discovery()
            _zeroconf = publish(DEFAULT_WORKSPACE)
        try:
            yield
        finally:
            if _zeroconf is not None:
                try:
                    _zeroconf.close()
                except Exception:
                    pass
                _zeroconf = None

    app = FastAPI(
        title="ClawOS A2A Server",
        version="1.1",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.settings = load_a2a_settings(settings)

    @app.get("/.well-known/agent.json")
    async def agent_card():
        local_ip = get_local_ip()
        card = build_card(DEFAULT_WORKSPACE, local_ip)
        return JSONResponse(card.to_dict())

    @app.post("/a2a/tasks/send")
    async def receive_task(body: dict, request: Request):
        _require_auth(request)

        msg_parts = body.get("message", {}).get("parts", [])
        intent = " ".join(
            part.get("text", "")
            for part in msg_parts
            if part.get("type") == "text"
        ).strip()
        workspace = body.get("metadata", {}).get("workspace", DEFAULT_WORKSPACE)
        task_id = body.get("id", "")

        if not intent:
            return JSONResponse({"error": "no intent"}, status_code=400)

        a2a_task = A2ATask(task_id=task_id or None, intent=intent, workspace=workspace)
        log.info("A2A task received: %s", intent[:60])
        result = await handle_task(a2a_task)

        return JSONResponse(
            {
                "id": a2a_task.task_id,
                "status": {"state": "completed"},
                "artifacts": [{"parts": [{"type": "text", "text": result}]}],
            }
        )

    @app.get("/a2a/tasks/{task_id}/subscribe")
    async def subscribe_task(task_id: str, request: Request):
        _require_auth(request)

        async def _gen() -> AsyncIterator[str]:
            try:
                from services.agentd.service import get_manager

                manager = get_manager()
                for _ in range(240):
                    await asyncio.sleep(0.5)
                    task = manager._tasks.get(task_id)
                    if not task:
                        yield f"data: {json.dumps({'status': 'not_found'})}\n\n"
                        return
                    if task.status.value in {"completed", "failed"}:
                        payload = {
                            "status": task.status.value,
                            "result": task.result or task.error,
                        }
                        yield f"data: {json.dumps(payload)}\n\n"
                        return
                    yield f"data: {json.dumps({'status': task.status.value})}\n\n"
                yield f"data: {json.dumps({'status': 'timeout'})}\n\n"
            except Exception as exc:
                yield f"data: {json.dumps({'error': str(exc)})}\n\n"

        return StreamingResponse(_gen(), media_type="text/event-stream")

    @app.get("/a2a/peers")
    async def list_peers(request: Request):
        _require_auth(request)
        return JSONResponse({"peers": get_peers()})

    @app.get("/health")
    async def health():
        settings_obj: A2ASettings = app.state.settings
        return {
            "service": "a2ad",
            "status": "ok",
            "port": settings_obj.port,
            "host": settings_obj.host,
            "auth_enabled": bool(settings_obj.auth_token),
            "mdns_enabled": settings_obj.mdns_enabled,
        }

    return app


async def start():
    if not FASTAPI_OK:
        log.error("fastapi/uvicorn not installed - a2ad unavailable")
        return

    app = create_app()
    settings: A2ASettings = app.state.settings
    log.info("a2ad starting on %s:%s", settings.host, settings.port)
    config = uvicorn.Config(app, host=settings.host, port=settings.port, log_level="warning")
    await uvicorn.Server(config).serve()
