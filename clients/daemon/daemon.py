# SPDX-License-Identifier: AGPL-3.0-or-later
#!/usr/bin/env python3
"""
ClawOS daemon — headless service runner
Starts the full ClawOS stack without the interactive REPL.
Used by systemd to keep services alive as a background process.

Usage:
    python3 ~/clawos/clients/daemon/daemon.py
    Use clawctl start or the platform user service manager
"""
import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from clawos_core.constants import DEFAULT_WORKSPACE, PORT_DASHD, PORT_SETUPD

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [clawosd] %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("clawosd")


async def _start_dashboard() -> None:
    try:
        import uvicorn
        from services.dashd.api import create_app, load_dashboard_settings

        dash_settings = load_dashboard_settings()
        config = uvicorn.Config(
            create_app(),
            host=dash_settings.host,
            port=dash_settings.port,
            log_level="warning",
        )
        server = uvicorn.Server(config)
        asyncio.create_task(server.serve())
        log.info(f"Dashboard started: http://localhost:{PORT_DASHD}")
    except Exception as exc:
        log.warning(f"Dashboard not started: canonical dashd failed ({exc})")


async def _start_setupd() -> None:
    try:
        import uvicorn
        from services.setupd.service import create_app as create_setup_app

        setup_config = uvicorn.Config(
            create_setup_app(),
            host="127.0.0.1",
            port=PORT_SETUPD,
            log_level="warning",
        )
        setup_server = uvicorn.Server(setup_config)
        asyncio.create_task(setup_server.serve())
        log.info(f"Setup service started: http://127.0.0.1:{PORT_SETUPD}")
    except Exception as exc:
        log.warning(f"Setup service not started: {exc}")


async def _start_runtime_stack(workspace: str) -> None:
    from runtimes.agent.runtime import build_runtime
    from services.memd.service import MemoryService
    from services.skilld.service import get_loader
    from services.agentd.service import get_manager

    log.info(f"Loading workspace: {workspace}")
    agent = await build_runtime(workspace)
    MemoryService()
    skills = get_loader()

    log.info(f"Model: {agent.model}")
    log.info(f"Skills loaded: {skills.count}")
    log.info("ClawOS runtime ready.")

    mgr = get_manager()
    await mgr.start()
    asyncio.create_task(mgr.start_api())
    log.info("agentd API started.")


def _log_runtime_task_result(task: asyncio.Task) -> None:
    try:
        exc = task.exception()
    except asyncio.CancelledError:
        log.info("Runtime startup task cancelled.")
        return
    if exc:
        log.error(f"Runtime startup failed: {exc}")


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

    # Start browser surfaces first so first-run setup is available even if the
    # heavier runtime stack is still initializing in the background.
    await _start_dashboard()
    await _start_setupd()

    runtime_task = asyncio.create_task(_start_runtime_stack(workspace))
    runtime_task.add_done_callback(_log_runtime_task_result)

    # Handle shutdown signals gracefully
    stop_event = asyncio.Event()

    def _shutdown(sig, frame):
        log.info(f"Received {signal.Signals(sig).name}, shutting down...")
        stop_event.set()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    # Start Kizuna service (braind) — living knowledge graph
    try:
        from services.braind.service import get_brain
        brain = get_brain()
        stats = brain.stats()
        log.info(f"Kizuna (絆) ready: {stats['node_count']} nodes, {stats['edge_count']} edges")
    except Exception as brain_error:
        log.warning(f"Kizuna not started (non-fatal): {brain_error}")

    log.info("Daemon holding. Send SIGTERM to stop.")
    await stop_event.wait()
    log.info("ClawOS daemon stopped.")


def main():
    workspace = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_WORKSPACE
    asyncio.run(run_daemon(workspace))


if __name__ == "__main__":
    main()
