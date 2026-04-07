# SPDX-License-Identifier: AGPL-3.0-or-later
"""modeld entry point."""
import asyncio, logging
logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
from services.modeld.service import get_service
async def main():
    svc = get_service()
    h   = svc.health()
    log = logging.getLogger("modeld")
    log.info(f"modeld ready — ollama={'running' if h['ollama_running'] else 'NOT running'} model={h['current_model']}")
    while True:
        await asyncio.sleep(3600)
if __name__ == "__main__":
    asyncio.run(main())
