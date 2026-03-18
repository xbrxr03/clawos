"""memd entry point."""
import asyncio, logging
logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
from services.memd.service import MemoryService
async def main():
    MemoryService()
    logging.getLogger("memd").info("memd ready")
    while True:
        await asyncio.sleep(3600)
if __name__ == "__main__":
    asyncio.run(main())
