# SPDX-License-Identifier: AGPL-3.0-or-later
"""agentd entry point."""
import asyncio, logging
logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
from services.agentd.service import get_manager

async def main():
    # Wait for deps in dev mode (systemd/launchd handles ordering in prod)
    try:
        from clawos_core.startup_probe import AGENTD_DEPS, probe_and_start
        deps_ok = await probe_and_start(
            AGENTD_DEPS,
            lambda: None,  # no startup action, just probing
            "agentd",
            timeout_s=10,
        )
        if not deps_ok:
            import sys
            print("WARNING: agentd starting without all deps — some features may fail until services come online")
    except ImportError:
        pass  # startup_probe not available in minimal installs

    mgr = get_manager()
    await mgr.start()
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
