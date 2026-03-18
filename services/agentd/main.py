"""agentd entry point."""
import asyncio, logging
logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
from services.agentd.service import get_manager
async def main():
    mgr = get_manager()
    await mgr.start()
    while True:
        await asyncio.sleep(3600)
if __name__ == "__main__":
    asyncio.run(main())
