# SPDX-License-Identifier: AGPL-3.0-or-later
"""maild — Email Service runner."""
import logging
import os

log = logging.getLogger("maild")

try:
    from fastapi import FastAPI
    from services.maild.service import router

    app = FastAPI(title="ClawOS Mail API", version="0.1.0", docs_url=None, redoc_url=None)
    app.include_router(router)

    @app.get("/health")
    async def maild_health():
        return {"status": "ok", "service": "maild"}
except ImportError:
    app = None


def run():
    if app is None:
        log.error("fastapi not installed — maild unavailable")
        return
    import uvicorn
    port = int(os.environ.get("MAILD_PORT", "7093"))
    host = os.environ.get("MAILD_HOST", "127.0.0.1")
    log.info("Starting maild on %s:%s", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info", access_log=False)


if __name__ == "__main__":
    run()