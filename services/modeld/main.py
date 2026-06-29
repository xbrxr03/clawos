# SPDX-License-Identifier: AGPL-3.0-or-later
"""modeld entry point."""
import asyncio
import logging
logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
from services.modeld.service import get_service  # noqa: E402
from clawos_core.constants import PORT_MODELD  # noqa: E402
from clawos_core.daemon_http import serve_health  # noqa: E402

async def main():
    svc = get_service()
    h = svc.health()
    log = logging.getLogger("modeld")
    log.info(f"modeld ready — ollama={'running' if h['ollama_running'] else 'NOT running'} model={h['current_model']}")
    asyncio.create_task(serve_health("modeld", PORT_MODELD, health_fn=svc.health))
    while True:
        await asyncio.sleep(3600)
if __name__ == "__main__":
    asyncio.run(main())