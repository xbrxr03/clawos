"""a2ad standalone entrypoint."""
import asyncio
import logging
logging.basicConfig(level=logging.INFO)

from services.a2ad.service import start

if __name__ == "__main__":
    asyncio.run(start())
