# SPDX-License-Identifier: AGPL-3.0-or-later
"""picoclawd standalone entrypoint."""
import asyncio
import logging
logging.basicConfig(level=logging.INFO)

from services.picoclawd.service import get_picoclawd

if __name__ == "__main__":
    asyncio.run(get_picoclawd().start())
