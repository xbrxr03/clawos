"""clawd entry point."""
import asyncio, logging
logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
from services.clawd.service import get_daemon
async def main():
    d = get_daemon()
    await d.start()
    while True:
        await asyncio.sleep(3600)
if __name__ == "__main__":
    asyncio.run(main())
