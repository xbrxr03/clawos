# SPDX-License-Identifier: AGPL-3.0-or-later
"""noted — Notes Service runner."""
import logging
import os

log = logging.getLogger("noted")

try:
    from fastapi import FastAPI
    from services.noted.service import router

    app = FastAPI(title="ClawOS Notes API", version="0.1.0", docs_url=None, redoc_url=None)
    app.include_router(router)

    @app.get("/health")
    async def noted_health():
        return {"status": "ok", "service": "noted"}
except ImportError:
    app = None


def run():
    if app is None:
        log.error("fastapi not installed — noted unavailable")
        return
    import uvicorn
    port = int(os.environ.get("NOTED_PORT", "7091"))
    host = os.environ.get("NOTED_HOST", "127.0.0.1")
    log.info("Starting noted on %s:%s", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info", access_log=False)


if __name__ == "__main__":
    run()