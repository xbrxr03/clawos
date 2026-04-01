"""
ClawOS a2ad — Agent-to-Agent Protocol Server
=============================================
Implements the A2A Protocol (Google → Linux Foundation open standard).
Makes each ClawOS workspace an A2A-addressable agent node.

Endpoints:
  GET  /.well-known/agent.json         — Agent Card (discovery)
  POST /a2a/tasks/send                 — Accept inbound task
  GET  /a2a/tasks/{id}/subscribe       — SSE stream for task progress
  GET  /a2a/peers                      — List discovered LAN peers
  GET  /health                         — Health check
"""
import asyncio
import json
import logging
import os
from typing import AsyncIterator

log = logging.getLogger("a2ad")

_zeroconf = None   # keep mDNS alive


async def start():
    global _zeroconf
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse, StreamingResponse
    import uvicorn
    from clawos_core.constants import PORT_A2AD, DEFAULT_WORKSPACE, A2A_BEARER_TOKEN_ENV
    from services.a2ad.agent_card import build_card
    from services.a2ad.task_handler import handle_task
    from services.a2ad.discovery import get_peers, start_discovery, publish, get_local_ip
    from clawos_core.models import A2ATask
    from clawos_core.config.loader import get

    app = FastAPI(title="ClawOS A2A Server", version="1.0")
    _AUTH_TOKEN = os.environ.get(A2A_BEARER_TOKEN_ENV, get("a2a.auth_token", ""))

    def _check_auth(request) -> bool:
        if not _AUTH_TOKEN:
            return True   # no token configured = open
        auth = request.headers.get("Authorization", "")
        return auth == f"Bearer {_AUTH_TOKEN}"

    @app.get("/.well-known/agent.json")
    async def agent_card():
        local_ip = get_local_ip()
        card = build_card(DEFAULT_WORKSPACE, local_ip)
        return JSONResponse(card.to_dict())

    @app.post("/a2a/tasks/send")
    async def receive_task(body: dict, request=None):
        # Parse A2A task envelope
        msg_parts = body.get("message", {}).get("parts", [])
        intent = " ".join(p.get("text", "") for p in msg_parts if p.get("type") == "text")
        workspace = body.get("metadata", {}).get("workspace", DEFAULT_WORKSPACE)
        task_id  = body.get("id", "")

        if not intent:
            return JSONResponse({"error": "no intent"}, status_code=400)

        a2a_task = A2ATask(
            task_id=task_id or None,
            intent=intent,
            workspace=workspace,
        )
        # Log via audit
        log.info(f"A2A task received: {intent[:60]}")

        # Run through agentd
        result = await handle_task(a2a_task)

        return JSONResponse({
            "id": a2a_task.task_id,
            "status": {"state": "completed"},
            "artifacts": [{"parts": [{"type": "text", "text": result}]}],
        })

    @app.get("/a2a/tasks/{task_id}/subscribe")
    async def subscribe_task(task_id: str):
        """SSE stream — returns one event then closes (simple implementation)."""
        async def _gen() -> AsyncIterator[str]:
            try:
                from services.agentd.service import get_manager
                manager = get_manager()
                for _ in range(240):
                    await asyncio.sleep(0.5)
                    t = manager._tasks.get(task_id)
                    if not t:
                        yield f"data: {json.dumps({'status': 'not_found'})}\n\n"
                        return
                    if t.status.value in ("completed", "failed"):
                        yield f"data: {json.dumps({'status': t.status.value, 'result': t.result or t.error})}\n\n"
                        return
                    yield f"data: {json.dumps({'status': t.status.value})}\n\n"
                yield f"data: {json.dumps({'status': 'timeout'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(_gen(), media_type="text/event-stream")

    @app.get("/a2a/peers")
    async def list_peers():
        return JSONResponse({"peers": get_peers()})

    @app.get("/health")
    async def health():
        return {"service": "a2ad", "status": "ok", "port": PORT_A2AD}

    # Start mDNS
    if get("a2a.mdns_enabled", True):
        start_discovery()
        _zeroconf = publish(DEFAULT_WORKSPACE)

    log.info(f"a2ad starting on port {PORT_A2AD}")
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT_A2AD,
                            log_level="warning")
    await uvicorn.Server(config).serve()
