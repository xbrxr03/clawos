"""voiced entry point."""
import asyncio, logging
logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
from services.voiced.service import get_service
async def main():
    svc = get_service()
    await svc.start()
    while True:
        await asyncio.sleep(3600)
if __name__ == "__main__":
    asyncio.run(main())
