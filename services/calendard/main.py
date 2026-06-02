# SPDX-License-Identifier: AGPL-3.0-or-later
"""calendard — Calendar Service runner."""
import logging
import os
import uvicorn

log = logging.getLogger("calendard")


def run():
    port = int(os.environ.get("CALENDARD_PORT", "7092"))
    host = os.environ.get("CALENDARD_HOST", "127.0.0.1")
    log.info("Starting calendard on %s:%s", host, port)
    uvicorn.run("services.calendard.service:app", host=host, port=port, log_level="info", access_log=False)


try:
    from fastapi import FastAPI
    from services.calendard.service import router

    app = FastAPI(title="ClawOS Calendar API", version="0.1.0", docs_url=None, redoc_url=None)
    app.include_router(router)

    @app.get("/health")
    async def root_health():
        return {"status": "ok", "service": "calendard"}
except ImportError:
    pass

if __name__ == "__main__":
    run()