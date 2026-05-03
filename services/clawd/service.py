# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS clawd — Orchestration Daemon
=====================================
Hardware detection, scheduler supervisor, service coordinator.
Heartbeat: reads HEARTBEAT.md and schedules proactive tasks.
"""
import asyncio
import logging
from pathlib import Path
from clawos_core.config.loader import load as load_config
from clawos_core.constants import DEFAULT_WORKSPACE

log = logging.getLogger("clawd")


class OrchestrationDaemon:
    def __init__(self):
        self.config   = load_config()
        self.profile  = self.config.get("_profile", "balanced")
        self._running = False

    async def start(self):
        self._running = True
        log.info(f"clawd started — profile={self.profile}")
        asyncio.create_task(self._heartbeat_loop())

    async def stop(self):
        self._running = False

    async def _heartbeat_loop(self):
        """Check HEARTBEAT.md and emit scheduled tasks to agentd."""
        while self._running:
            try:
                from clawos_core.constants import WORKSPACE_DIR, DEFAULT_WORKSPACE
                from clawos_core.events.bus import get_bus
                hb_file = WORKSPACE_DIR / DEFAULT_WORKSPACE / "HEARTBEAT.md"
                if hb_file.exists():
                    await get_bus().emit_log("info", "clawd", "heartbeat check")
            except (ImportError, ModuleNotFoundError) as e:
                log.warning(f"heartbeat error: {e}")
            await asyncio.sleep(300)

    def hardware_info(self) -> dict:
        from clawos_core.constants import HARDWARE_JSON
        if HARDWARE_JSON.exists():
            import json
            return json.loads(HARDWARE_JSON.read_text())
        return {}

    def health(self) -> dict:
        return {
            "status":  "running" if self._running else "stopped",
            "profile": self.profile,
        }


_daemon = None

def get_daemon() -> OrchestrationDaemon:
    global _daemon
    if _daemon is None:
        _daemon = OrchestrationDaemon()
    return _daemon


# ── A2A server ────────────────────────────────────────────────────────────────
async def start_a2a_server(daemon: "OrchestrationDaemon"):
    """Start Nexus A2A endpoint for OpenClaw peer communication."""
    try:
        from fastapi import FastAPI
        import uvicorn
        from clawos_core.constants import A2A_PORT_NEXUS, DEFAULT_WORKSPACE

        app = FastAPI(title="Nexus A2A")

        @app.get("/.well-known/agent-card.json")
        def agent_card():
            return {
                "name": "Nexus",
                "description": "ClawOS local agent. File ops, shell, memory, workspace tools.",
                "url": f"http://localhost:{A2A_PORT_NEXUS}/a2a",
                "version": "1.0",
                "skills": [
                    {"name": "filesystem",  "description": "Read, write, search files in workspace"},
                    {"name": "shell",       "description": "Run allowlisted shell commands"},
                    {"name": "memory",      "description": "Store and recall facts across sessions"},
                    {"name": "workspace",   "description": "Create and manage workspaces"},
                ],
                "provider": {"name": "ClawOS", "url": "https://github.com/xbrxr03/clawos"},
            }

        @app.post("/a2a/tasks/send")
        async def receive_task(body: dict):
            """Receive task from OpenClaw, run through full Nexus ReAct loop."""
            intent = body.get("message", {}).get("parts", [{}])[0].get("text", "")
            workspace = body.get("metadata", {}).get("workspace", DEFAULT_WORKSPACE)
            if not intent:
                return {"error": "no message"}
            try:
                from services.agentd.service import get_manager
                reply = await get_manager().chat_direct(intent, workspace_id=workspace,
                                                        source="a2a:openclaw")
            except (ImportError, ModuleNotFoundError) as e:
                reply = f"[Error] {e}"
            return {
                "id": body.get("id", ""),
                "status": {"state": "completed"},
                "artifacts": [{"parts": [{"type": "text", "text": reply}]}],
            }

        config = uvicorn.Config(app, host="127.0.0.1",
                                port=A2A_PORT_NEXUS, log_level="warning")
        await uvicorn.Server(config).serve()
    except (ImportError, ModuleNotFoundError) as e:
        log.warning(f"Nexus A2A server not started: {e}")

