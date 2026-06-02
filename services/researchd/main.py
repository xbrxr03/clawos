# SPDX-License-Identifier: AGPL-3.0-or-later
"""
researchd — Deep Research Service runner
========================================
Starts the FastAPI research service on port 7079.
"""
import logging
import os

import uvicorn

log = logging.getLogger("researchd")


def run():
    """Start the researchd FastAPI server."""
    port = int(os.environ.get("RESEARCHD_PORT", "7089"))
    host = os.environ.get("RESEARCHD_HOST", "127.0.0.1")

    log.info("Starting researchd on %s:%s", host, port)
    uvicorn.run(
        "services.researchd.service:app",
        host=host,
        port=port,
        log_level="info",
        access_log=False,
    )


# Create the ASGI app for direct import
try:
    from fastapi import FastAPI
    from services.researchd.service import router

    app = FastAPI(
        title="ClawOS Research API",
        description="Multi-source deep research with citations.",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
    )
    app.include_router(router)

    @app.get("/health")
    async def root_health():
        return {"status": "ok", "service": "researchd"}

except ImportError:
    pass


if __name__ == "__main__":
    run()