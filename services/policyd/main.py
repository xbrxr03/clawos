# SPDX-License-Identifier: AGPL-3.0-or-later
"""policyd entry point."""
import asyncio, logging, sys
logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
from services.policyd.service import get_engine
async def main():
    engine = get_engine()
    logging.getLogger("policyd").info("policyd ready")
    while True:
        await asyncio.sleep(3600)
if __name__ == "__main__":
    asyncio.run(main())
