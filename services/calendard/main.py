# SPDX-License-Identifier: AGPL-3.0-or-later
"""calendard — Calendar Service runner."""
import logging
import os

log = logging.getLogger("calendard")

try:
    from fastapi import FastAPI
    from services.calendard.service import router

    app = FastAPI(title="ClawOS Calendar API", version="0.1.0", docs_url=None, redoc_url=None)
    app.include_router(router)

    @app.get("/health")
    async def calendard_health():
        return {"status": "ok", "service": "calendard"}
except ImportError:
    app = None


def run():
    if app is None:
        log.error("fastapi not installed — calendard unavailable")
        return
    import uvicorn
    port = int(os.environ.get("CALENDARD_PORT", "7092"))
    host = os.environ.get("CALENDARD_HOST", "127.0.0.1")
    log.info("Starting calendard on %s:%s", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info", access_log=False)


if __name__ == "__main__":
    run()