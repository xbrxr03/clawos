# SPDX-License-Identifier: AGPL-3.0-or-later
"""clawd entry point."""
import asyncio, logging
logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
from services.clawd.service import get_daemon
from clawos_core.constants import PORT_CLAWD
from clawos_core.daemon_http import serve_health

async def main():
    d = get_daemon()
    await d.start()
    asyncio.create_task(serve_health("clawd", PORT_CLAWD, health_fn=d.health))
    while True:
        await asyncio.sleep(3600)
if __name__ == "__main__":
    asyncio.run(main())