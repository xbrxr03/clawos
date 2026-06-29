# SPDX-License-Identifier: AGPL-3.0-or-later
"""policyd entry point."""
import asyncio
import logging
logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
from services.policyd.service import get_engine  # noqa: E402
from clawos_core.constants import PORT_POLICYD  # noqa: E402
from clawos_core.daemon_http import serve_health  # noqa: E402

def _policyd_health():
    engine = get_engine()
    return {
        "status": "up",
        "pending_approvals": len(engine._pending),
    }

async def main():
    get_engine()
    logging.getLogger("policyd").info("policyd ready")
    asyncio.create_task(serve_health("policyd", PORT_POLICYD, health_fn=_policyd_health))
    while True:
        await asyncio.sleep(3600)
if __name__ == "__main__":
    asyncio.run(main())