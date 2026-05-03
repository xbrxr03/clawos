# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Startup dependency probes — wait for dependent services before starting.

Used by services that need other services to be healthy (e.g. agentd
depends on memd + policyd). In production, systemd/launchd handles
ordering. In dev mode, this prevents race conditions.
"""
import asyncio
import logging
import socket
from typing import Sequence

log = logging.getLogger("clawos.startup")


async def wait_for_port(host: str, port: int, timeout_s: float = 30.0, label: str = "") -> bool:
    """Wait until a TCP port is accepting connections.

    Returns True if the port became available within timeout, False otherwise.
    """
    label = label or f"{host}:{port}"
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=2.0
            )
            writer.close()
            await writer.wait_closed()
            log.info(f"Dependency ready: {label}")
            return True
        except (OSError, ConnectionRefusedError, asyncio.TimeoutError):
            await asyncio.sleep(0.5)

    log.warning(f"Dependency NOT ready after {timeout_s}s: {label}")
    return False


async def wait_for_deps(deps: Sequence[tuple[str, int, str]], timeout_s: float = 30.0) -> bool:
    """Wait for multiple (host, port, label) dependencies in parallel.

    Returns True only if ALL deps became available within the timeout.
    """
    tasks = [wait_for_port(h, p, timeout_s, lbl) for h, p, lbl in deps]
    results = await asyncio.gather(*tasks)
    return all(results)


# Standard dependency maps for each service
AGENTD_DEPS = [
    ("127.0.0.1", 7073, "memd"),
    ("127.0.0.1", 7074, "policyd"),
    ("127.0.0.1", 7075, "modeld"),
]

TOOLBRIDGE_DEPS = [
    ("127.0.0.1", 7074, "policyd"),
]

VOICED_DEPS = [
    ("127.0.0.1", 7072, "agentd"),
]


async def probe_and_start(service_deps, startup_fn, service_name: str, timeout_s: float = 30.0):
    """Wait for deps, then call startup_fn. Logs warnings if deps aren't ready."""
    if service_deps:
        deps_ok = await wait_for_deps(service_deps, timeout_s)
        if not deps_ok:
            log.warning(
                f"{service_name}: some dependencies not ready — starting anyway "
                f"(may encounter errors until deps come online)"
            )
    return await startup_fn()