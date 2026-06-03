# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Lightweight HTTP health server for daemon services.

Many ClawOS services are pure async daemons (clawd, memd, policyd, modeld)
that don't expose HTTP endpoints. The dashboard can't check their health
because it can't reach them over HTTP.

This module provides a minimal FastAPI app with /health that can be
started alongside any daemon's async loop using asyncio.create_task().
"""
import asyncio
import logging
from typing import Any, Callable, Optional

from fastapi import FastAPI
import uvicorn

log = logging.getLogger("daemon_http")


def create_health_app(
    service_name: str,
    health_fn: Optional[Callable[[], dict]] = None,
    extra_routes: Optional[list[tuple[str, Any]]] = None,
) -> FastAPI:
    """Create a minimal FastAPI app with /health for a daemon service.

    Args:
        service_name: Human-readable service name (e.g. "clawd")
        health_fn: Optional callable returning a health dict. If None,
                   returns basic {"status": "up", "service": name}.
        extra_routes: Optional list of (path, handler) tuples to add.

    Returns:
        FastAPI app ready to serve.
    """
    app = FastAPI(title=f"{service_name} daemon", docs_url=None, redoc_url=None)

    @app.get("/health")
    def health():
        if health_fn:
            result = health_fn()
            result.setdefault("service", service_name)
            result.setdefault("status", "up")
            return result
        return {"status": "up", "service": service_name}

    if extra_routes:
        for path, handler in extra_routes:
            app.add_api_route(path, handler, methods=["GET"])

    return app


async def serve_health(
    service_name: str,
    port: int,
    host: str = "127.0.0.1",
    health_fn: Optional[Callable[[], dict]] = None,
    extra_routes: Optional[list[tuple[str, Any]]] = None,
) -> None:
    """Start a health HTTP server as an asyncio task.

    Usage in main.py:
        asyncio.create_task(serve_health("clawd", 7071, health_fn=daemon.health))

    This runs forever alongside the daemon's main loop.
    """
    app = create_health_app(service_name, health_fn, extra_routes)
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    log.info(f"{service_name} health server starting on {host}:{port}")
    await server.serve()