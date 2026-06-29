# SPDX-License-Identifier: AGPL-3.0-or-later
"""memd entry point."""
import asyncio
import logging
logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
from services.memd.service import MemoryService, CHROMA_OK  # noqa: E402
from clawos_core.constants import PORT_MEMD  # noqa: E402
from clawos_core.daemon_http import serve_health  # noqa: E402

def _memd_health():
    return {
        "status": "up",
        "chromadb": CHROMA_OK,
        "fts5": True,
    }

async def main():
    MemoryService()
    logging.getLogger("memd").info("memd ready")
    asyncio.create_task(serve_health("memd", PORT_MEMD, health_fn=_memd_health))
    while True:
        await asyncio.sleep(3600)
if __name__ == "__main__":
    asyncio.run(main())