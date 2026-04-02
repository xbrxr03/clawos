#!/usr/bin/env python3
"""
ClawOS daemon — headless service runner
Starts the full ClawOS stack without the interactive REPL.
Used by systemd to keep services alive as a background process.

Usage:
    python3 ~/clawos/clients/daemon/daemon.py
    systemctl --user start clawos
"""
import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from clawos_core.constants import DEFAULT_WORKSPACE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [clawosd] %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("clawosd")


async def run_daemon(workspace: str = DEFAULT_WORKSPACE):
    log.info("ClawOS daemon starting...")

    # Export stored secrets to environment early — child processes inherit them
    try:
        from services.secretd.service import get_store
        store = get_store()
        store.export_to_env()
        log.info(f"secretd: {store.count()} secret(s) loaded into environment")
    except Exception as e:
        log.warning(f"secretd export failed (non-fatal): {e}")

    # Import and start the same services the REPL uses
    try:
        from runtimes.agent.runtime import build_runtime
        from services.memd.service import MemoryService
        from services.skilld.service import get_loader

        log.info(f"Loading workspace: {workspace}")
        agent = await build_runtime(workspace)
        memory = MemoryService()
        skills = get_loader()

        log.info(f"Model: {agent.model}")
        log.info(f"Skills loaded: {skills.count}")
        log.info("ClawOS daemon ready.")

        from services.agentd.service import get_manager
        mgr = get_manager()
        await mgr.start()
        asyncio.create_task(mgr.start_api())

    except Exception as e:
        log.error(f"Failed to start ClawOS services: {e}")
        sys.exit(1)

    # Also start dashd if available
    try:
        import uvicorn
        dashboard_dir = Path(__file__).parent.parent.parent / "dashboard" / "backend"
        if (dashboard_dir / "service.py").exists():
            sys.path.insert(0, str(dashboard_dir))
            config = uvicorn.Config(
                "service:app",
                host="0.0.0.0",
                port=7070,
                log_level="warning",
                
            )
            server = uvicorn.Server(config)
            asyncio.create_task(server.serve())
            log.info("Dashboard started: http://localhost:7070")
    except Exception as e:
        log.warning(f"Dashboard not started: {e}")

    # Handle shutdown signals gracefully
    stop_event = asyncio.Event()

    def _shutdown(sig, frame):
        log.info(f"Received {signal.Signals(sig).name}, shutting down...")
        stop_event.set()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    log.info("Daemon holding. Send SIGTERM to stop.")
    await stop_event.wait()
    log.info("ClawOS daemon stopped.")


def main():
    workspace = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_WORKSPACE
    asyncio.run(run_daemon(workspace))


if __name__ == "__main__":
    main()
