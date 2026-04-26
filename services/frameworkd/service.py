# SPDX-License-Identifier: AGPL-3.0-or-later
"""
frameworkd — Framework Store lifecycle service.

Manages the install / start / stop / remove lifecycle of AI agent frameworks.
Exposes a REST API consumed by dashd (Frameworks tab) and clawctl.

Frameworks are defined as YAML manifests in frameworks/catalog/.
Each installed framework runs as a separate systemd service.
All frameworks route model calls through the LiteLLM proxy (llmd).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

log = logging.getLogger("frameworkd")

# Active framework name (Nexus routes traffic here)
_active_framework: str = "nexus"  # default — Nexus native runtime


# ── Public API (used by dashd routes + clawctl) ────────────────────────────────

def list_frameworks(profile_id: Optional[str] = None) -> list[dict]:
    """Return all frameworks enriched with state + compatibility."""
    from frameworks.registry import get_registry
    if profile_id is None:
        try:
            from bootstrap.hardware_probe import load_saved
            hw = load_saved()
            profile_id = hw.profile_id
        except Exception:
            profile_id = "x86-cpu-16gb"
    return get_registry().list_for_tier(profile_id)


def install_framework(name: str) -> dict:
    """
    Install a framework.  Blocking call — runs install synchronously.
    Returns {ok, message}.
    """
    from frameworks.installer import install
    messages: list[str] = []

    ok = install(name, progress=lambda m: messages.append(m))
    return {
        "ok":      ok,
        "name":    name,
        "message": "\n".join(messages) if messages else ("Success" if ok else "Failed"),
    }


def remove_framework(name: str) -> dict:
    from frameworks.installer import remove
    messages: list[str] = []
    ok = remove(name, progress=lambda m: messages.append(m))
    return {
        "ok":      ok,
        "name":    name,
        "message": "\n".join(messages) if messages else ("Removed" if ok else "Failed"),
    }


def start_framework(name: str) -> dict:
    from frameworks.runner import start
    ok = start(name)
    return {"ok": ok, "name": name}


def stop_framework(name: str) -> dict:
    from frameworks.runner import stop
    ok = stop(name)
    return {"ok": ok, "name": name}


def framework_status(name: str) -> dict:
    from frameworks.runner import status
    return status(name)


def all_statuses() -> list[dict]:
    from frameworks.runner import status_all
    return status_all()


def get_active_framework() -> str:
    return _active_framework


def set_active_framework(name: str) -> dict:
    """
    Set which framework gatewayd routes inbound messages to.
    'nexus' always works (built-in).  Others must be running.
    """
    global _active_framework
    from frameworks.registry import get_registry
    from frameworks.runner import status as fw_status

    if name == "nexus":
        _active_framework = "nexus"
        log.info("frameworkd: active framework set to nexus (built-in)")
        return {"ok": True, "active": "nexus"}

    manifest = get_registry().get(name)
    if manifest is None:
        return {"ok": False, "error": f"Unknown framework '{name}'"}

    st = fw_status(name)
    if st["state"] != "running":
        # Try to start it
        from frameworks.runner import start
        if not start(name):
            return {"ok": False, "error": f"{name} is not running and could not be started"}

    _active_framework = name
    log.info(f"frameworkd: active framework set to {name}")
    return {"ok": True, "active": name}


# ── Background health sync ─────────────────────────────────────────────────────

async def _sync_states_loop(interval: int = 30) -> None:
    """Periodically sync systemd states into the registry."""
    from frameworks.runner import status_all
    from frameworks.registry import get_registry, AppState

    while True:
        try:
            for st in status_all():
                name = st["name"]
                running = st["state"] == "running"
                installed = st.get("systemd") == "active" or running
                reg = get_registry()
                if running:
                    reg.set_state(name, AppState.RUNNING)
                elif installed:
                    reg.set_state(name, AppState.INSTALLED)
        except Exception as e:
            log.debug(f"frameworkd: state sync error: {e}")
        await asyncio.sleep(interval)


def start_background_sync() -> None:
    """Start the background state-sync loop (call once at service startup)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_sync_states_loop())
        else:
            asyncio.ensure_future(_sync_states_loop())
    except Exception as e:
        log.warning(f"frameworkd: could not start background sync: {e}")
