"""
dashd — ClawOS Dashboard Backend
Port: 7070
Serves: REST API + WebSocket event stream for the React frontend
"""

import asyncio
import json
import logging
import os
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# ── Paths ──────────────────────────────────────────────────────────────────────
HOME = Path.home()
CLAWOS_DIR = HOME / "clawos"
LOG_DIR = CLAWOS_DIR / "logs"
MEMORY_DIR = CLAWOS_DIR / "memory"
WORKSPACE_DIR = CLAWOS_DIR / "workspace"
AUDIT_LOG = LOG_DIR / "audit.jsonl"
TASK_DB = MEMORY_DIR / "tasks.db"

# ── Service endpoints ──────────────────────────────────────────────────────────
POLICYD_URL = "http://localhost:7074"
MEMD_URL = "http://localhost:7073"
MODELD_URL = "http://localhost:7075"
AGENTD_URL = "http://localhost:7072"
OLLAMA_URL = "http://localhost:11434"

logger = logging.getLogger("dashd")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [dashd] %(message)s")


# ── WebSocket connection manager ───────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        logger.info(f"WS client connected ({len(self.active)} total)")

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)
        logger.info(f"WS client disconnected ({len(self.active)} remaining)")

    async def broadcast(self, event: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active.remove(ws)


manager = ConnectionManager()


# ── Log tailer — streams audit.jsonl to all WS clients ────────────────────────
async def tail_audit_log():
    """Tail the audit log and broadcast new entries to all connected clients."""
    if not AUDIT_LOG.exists():
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        AUDIT_LOG.touch()

    async with aiofiles.open(AUDIT_LOG, "r") as f:
        await f.seek(0, 2)  # seek to end
        while True:
            line = await f.readline()
            if line:
                try:
                    entry = json.loads(line.strip())
                    await manager.broadcast({"type": "audit_event", "data": entry})
                except json.JSONDecodeError:
                    pass
            else:
                await asyncio.sleep(0.2)


# ── Service health poller ──────────────────────────────────────────────────────
async def poll_service_health():
    """Poll all services every 5s and broadcast status changes."""
    services = {
        "policyd": POLICYD_URL,
        "memd": MEMD_URL,
        "modeld": MODELD_URL,
        "agentd": AGENTD_URL,
        "ollama": OLLAMA_URL,
    }
    last_status = {}

    async with httpx.AsyncClient(timeout=2.0) as client:
        while True:
            current = {}
            for name, url in services.items():
                try:
                    r = await client.get(f"{url}/health")
                    current[name] = "up" if r.status_code == 200 else "degraded"
                except Exception:
                    current[name] = "down"

            if current != last_status:
                await manager.broadcast({"type": "service_health", "data": current})
                last_status = current.copy()

            await asyncio.sleep(5)


# ── Lifespan ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("dashd starting on :7070")
    asyncio.create_task(tail_audit_log())
    asyncio.create_task(poll_service_health())
    yield
    logger.info("dashd shutting down")


# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(title="ClawOS Dashboard", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── WebSocket endpoint ─────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        # Send initial state snapshot on connect
        snapshot = await build_snapshot()
        await ws.send_json({"type": "snapshot", "data": snapshot})

        while True:
            # Keep alive — client can send pings
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(ws)


# ── Snapshot builder ───────────────────────────────────────────────────────────
async def build_snapshot() -> dict:
    """Build full state snapshot for new WS connections."""
    return {
        "tasks": await get_tasks_data(),
        "approvals": await get_approvals_data(),
        "models": await get_models_data(),
        "services": await get_services_health(),
        "audit_tail": await get_audit_tail(50),
        "memory": await get_memory_stats(),
        "workspaces": await get_workspaces(),
    }


# ── REST: Health ───────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "up", "service": "dashd", "port": 7070}


# ── REST: Tasks ───────────────────────────────────────────────────────────────
@app.post("/api/tasks/submit")
async def api_submit_task(body: dict):
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{AGENTD_URL}/submit", json=body, timeout=10.0)
            return r.json()
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/tasks")
async def api_tasks():
    return await get_tasks_data()


async def get_tasks_data() -> dict:
    """Read task state from agentd or task DB."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{AGENTD_URL}/tasks")
            if r.status_code == 200:
                return r.json()
    except Exception:
        pass

    # Fallback: read from SQLite task DB
    return _read_task_db()


def _read_task_db() -> dict:
    if not TASK_DB.exists():
        return {"active": [], "queued": [], "failed": [], "completed": []}

    try:
        conn = sqlite3.connect(str(TASK_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        result = {"active": [], "queued": [], "failed": [], "completed": []}
        for status in result:
            cur.execute(
                "SELECT * FROM tasks WHERE status=? ORDER BY created_at DESC LIMIT 50",
                (status,),
            )
            result[status] = [dict(r) for r in cur.fetchall()]
        conn.close()
        return result
    except Exception as e:
        logger.warning(f"Task DB read failed: {e}")
        return {"active": [], "queued": [], "failed": [], "completed": []}


# ── REST: Approvals ────────────────────────────────────────────────────────────
@app.get("/api/approvals")
async def api_approvals():
    return await get_approvals_data()


@app.post("/api/approvals/{approval_id}/approve")
async def api_approve(approval_id: str):
    return await _send_approval_decision(approval_id, "approved")


@app.post("/api/approvals/{approval_id}/deny")
async def api_deny(approval_id: str):
    return await _send_approval_decision(approval_id, "denied")


async def get_approvals_data() -> list:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{POLICYD_URL}/approvals/pending")
            if r.status_code == 200:
                return r.json()
    except Exception:
        pass
    return []


async def _send_approval_decision(approval_id: str, decision: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(
                f"{POLICYD_URL}/approvals/{approval_id}/{decision}"
            )
            result = {"approval_id": approval_id, "decision": decision, "ok": r.status_code == 200}
            await manager.broadcast({"type": "approval_resolved", "data": result})
            return result
    except Exception as e:
        return {"approval_id": approval_id, "decision": decision, "ok": False, "error": str(e)}


# ── REST: Models ───────────────────────────────────────────────────────────────
@app.get("/api/models")
async def api_models():
    return await get_models_data()


@app.post("/api/models/{model_name}/pull")
async def api_pull_model(model_name: str):
    """Trigger Ollama model pull — streams progress via WS."""
    asyncio.create_task(_stream_model_pull(model_name))
    return {"ok": True, "model": model_name, "status": "pulling"}


@app.delete("/api/models/{model_name}")
async def api_delete_model(model_name: str):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.delete(f"{OLLAMA_URL}/api/delete", json={"name": model_name})
            return {"ok": r.status_code == 200, "model": model_name}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def get_models_data() -> dict:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
            if r.status_code == 200:
                data = r.json()
                models = data.get("models", [])
                # Enrich with running status
                try:
                    ps = await client.get(f"{OLLAMA_URL}/api/ps")
                    running = {m["name"] for m in ps.json().get("models", [])} if ps.status_code == 200 else set()
                except Exception:
                    running = set()

                for m in models:
                    m["running"] = m["name"] in running
                    m["size_gb"] = round(m.get("size", 0) / 1e9, 2)

                return {"models": models, "default": "qwen2.5:7b"}
    except Exception as e:
        logger.warning(f"Ollama models fetch failed: {e}")
    return {"models": [], "default": "qwen2.5:7b"}


async def _stream_model_pull(model_name: str):
    """Pull model and stream progress events over WebSocket."""
    async with httpx.AsyncClient(timeout=600.0) as client:
        try:
            async with client.stream(
                "POST", f"{OLLAMA_URL}/api/pull", json={"name": model_name}
            ) as r:
                async for line in r.aiter_lines():
                    if line:
                        try:
                            event = json.loads(line)
                            await manager.broadcast({
                                "type": "model_pull_progress",
                                "model": model_name,
                                "data": event,
                            })
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            await manager.broadcast({
                "type": "model_pull_error",
                "model": model_name,
                "error": str(e),
            })


# ── REST: Services health ──────────────────────────────────────────────────────
@app.get("/api/services")
async def api_services():
    return await get_services_health()


async def get_services_health() -> dict:
    import subprocess, asyncio
    result = {}

    # clawos.service covers policyd/memd/modeld/agentd — all run inside the daemon
    async def check_systemd(unit: str) -> str:
        try:
            r = await asyncio.create_subprocess_exec(
                "systemctl", "--user", "is-active", unit,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
            out, _ = await r.communicate()
            return out.decode().strip()
        except Exception:
            return "unknown"

    # Check parent clawos.service
    daemon_status = await check_systemd("clawos.service")
    daemon_up = daemon_status == "active"

    # Services that live inside the daemon process
    for name in ["policyd", "memd", "modeld", "agentd"]:
        result[name] = {
            "status": "up" if daemon_up else "down",
            "port": None,
            "latency_ms": None,
        }

    # Ollama — check via HTTP since it has a real endpoint
    async with httpx.AsyncClient(timeout=1.5) as client:
        try:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
            result["ollama"] = {
                "status": "up" if r.status_code == 200 else "degraded",
                "port": 11434,
                "latency_ms": int(r.elapsed.total_seconds() * 1000),
            }
        except Exception:
            result["ollama"] = {"status": "down", "port": 11434, "latency_ms": None}

    return result


# ── REST: Audit log ────────────────────────────────────────────────────────────
@app.get("/api/audit")
async def api_audit(limit: int = 100, offset: int = 0):
    entries = await get_audit_tail(limit, offset)
    return {"entries": entries, "total": len(entries)}


async def get_audit_tail(limit: int = 50, offset: int = 0) -> list:
    if not AUDIT_LOG.exists():
        return []
    try:
        async with aiofiles.open(AUDIT_LOG, "r") as f:
            lines = await f.readlines()

        entries = []
        for line in reversed(lines):
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

        return entries[offset : offset + limit]
    except Exception as e:
        logger.warning(f"Audit log read failed: {e}")
        return []


# ── REST: Memory stats ─────────────────────────────────────────────────────────
@app.get("/api/memory")
async def api_memory():
    return await get_memory_stats()


async def get_memory_stats() -> dict:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{MEMD_URL}/stats")
            if r.status_code == 200:
                return r.json()
    except Exception:
        pass

    # Fallback: read from disk
    stats: dict[str, Any] = {}
    chroma_db = MEMORY_DIR / "chroma"
    sqlite_db = MEMORY_DIR / "memory.db"

    if chroma_db.exists():
        stats["chroma_size_mb"] = round(
            sum(f.stat().st_size for f in chroma_db.rglob("*") if f.is_file()) / 1e6, 2
        )
    if sqlite_db.exists():
        stats["sqlite_size_mb"] = round(sqlite_db.stat().st_size / 1e6, 2)

    pinned = WORKSPACE_DIR / "nexus_default" / "PINNED.md"
    history = WORKSPACE_DIR / "nexus_default" / "HISTORY.md"
    workflow = WORKSPACE_DIR / "nexus_default" / "WORKFLOW.md"

    stats["pinned_lines"] = _count_lines(pinned)
    stats["history_lines"] = _count_lines(history)
    stats["workflow_lines"] = _count_lines(workflow)

    return stats


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return sum(1 for _ in open(path))
    except Exception:
        return 0


# ── REST: Workspaces ───────────────────────────────────────────────────────────
@app.get("/api/workspaces")
async def api_workspaces():
    return await get_workspaces()


async def get_workspaces() -> list:
    if not WORKSPACE_DIR.exists():
        return []
    workspaces = []
    for ws_dir in sorted(WORKSPACE_DIR.iterdir()):
        if ws_dir.is_dir():
            pinned = ws_dir / "PINNED.md"
            workflow = ws_dir / "WORKFLOW.md"
            workspaces.append({
                "name": ws_dir.name,
                "path": str(ws_dir),
                "has_pinned": pinned.exists(),
                "has_workflow": workflow.exists(),
                "pinned_preview": _read_preview(pinned),
                "workflow_preview": _read_preview(workflow),
                "modified": ws_dir.stat().st_mtime,
            })
    return workspaces


def _read_preview(path: Path, chars: int = 200) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text()[:chars]
    except Exception:
        return ""


# ── REST: System stats ─────────────────────────────────────────────────────────
@app.get("/api/system")
async def api_system():
    import shutil
    disk = shutil.disk_usage(str(HOME))
    stats = {
        "disk_total_gb": round(disk.total / 1e9, 1),
        "disk_used_gb": round(disk.used / 1e9, 1),
        "disk_free_gb": round(disk.free / 1e9, 1),
        "uptime_seconds": time.time() - _start_time,
    }
    # Try to get memory info
    try:
        mem = Path("/proc/meminfo").read_text()
        total = int([l for l in mem.splitlines() if "MemTotal" in l][0].split()[1])
        avail = int([l for l in mem.splitlines() if "MemAvailable" in l][0].split()[1])
        stats["ram_total_gb"] = round(total / 1e6, 1)
        stats["ram_used_gb"] = round((total - avail) / 1e6, 1)
        stats["ram_free_gb"] = round(avail / 1e6, 1)
    except Exception:
        pass
    return stats


_start_time = time.time()


# ── Entry point ────────────────────────────────────────────────────────────────


# ── Token usage endpoint ───────────────────────────────────────────────────────
@app.get("/api/tokens")
async def api_tokens():
    try:
        from services.metricd.service import get_metrics
        m = get_metrics()
        workspaces = m.workspace_summary()
        # Enrich with week totals
        for ws in workspaces:
            ws["tokens_week"] = m.week_tokens(ws["workspace_id"])
        return {"workspaces": workspaces}
    except Exception as e:
        return {"workspaces": [], "error": str(e)}

# ── A2A peers endpoint ────────────────────────────────────────────────────────
@app.get("/api/peers")
async def api_peers():
    try:
        from services.a2ad.discovery import get_peers
        return {"peers": get_peers()}
    except Exception:
        return {"peers": []}

# ── A2A delegate endpoint ─────────────────────────────────────────────────────
@app.post("/api/delegate")
async def api_delegate(body: dict):
    peer_url = body.get("peer_url", "")
    task     = body.get("task", "")
    if not peer_url or not task:
        return {"error": "peer_url and task required"}
    try:
        from services.gatewayd.service import delegate_to_peer
        result = await delegate_to_peer(peer_url, task)
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}

# ── LEARNED.md endpoint ───────────────────────────────────────────────────────
@app.get("/api/learned")
async def api_learned():
    try:
        from services.memd.service import get_learned
        from clawos_core.constants import DEFAULT_WORKSPACE
        content = get_learned(DEFAULT_WORKSPACE)
        return {"content": content, "workspace": DEFAULT_WORKSPACE}
    except Exception as e:
        return {"content": "", "error": str(e)}

# ── Nexus Chat API ───────────────────────────────────────────────────────────
@app.post("/api/nexus/chat")
async def api_nexus_chat(body: dict):
    message = (body.get("message") or "").strip()
    if not message:
        return {"reply": "", "error": "empty message"}
    try:
        from services.agentd.service import get_manager
        mgr = get_manager()
        result = await mgr.chat_direct_with_steps(message, workspace_id="nexus_default")
        return result  # {"reply": str, "tool_steps": list}
    except Exception as e:
        return {"reply": "", "error": str(e), "tool_steps": []}

# ── Workflows API ────────────────────────────────────────────────────────────
@app.get("/api/workflows/list")
async def api_workflows_list(category: str = None, search: str = None):
    try:
        from workflows.engine import get_engine
        eng = get_engine()
        eng.load_registry()
        wfs = eng.list_workflows(category=category, search=search)
        return [
            {
                "id":          m.id,
                "name":        m.name,
                "category":    m.category,
                "description": m.description,
                "tags":        m.tags,
                "requires":    m.requires,
                "destructive": m.destructive,
                "timeout_s":   m.timeout_s,
            }
            for m in wfs
        ]
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/workflows/{workflow_id}/run")
async def api_workflow_run(workflow_id: str, body: dict = None):
    try:
        from workflows.engine import get_engine
        eng          = get_engine()
        body         = body or {}
        wf_args      = body.get("args", {})
        workspace_id = body.get("workspace_id", "nexus_default")
        result = await eng.run(workflow_id, wf_args, workspace_id=workspace_id)
        return {
            "status":   result.status,
            "output":   result.output,
            "error":    result.error,
            "metadata": result.metadata,
        }
    except KeyError:
        from fastapi import HTTPException
        raise HTTPException(404, f"Workflow not found: {workflow_id}")
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(500, str(e))


# ── A2A Agent Card (serve from dashd too for convenience) ────────────────────
@app.get("/.well-known/agent.json")
async def agent_card():
    try:
        from services.a2ad.agent_card import build_card
        from services.a2ad.discovery import get_local_ip
        card = build_card(local_ip=get_local_ip())
        return card.to_dict()
    except Exception as e:
        return {"error": str(e)}



# ── REST: Runtimes status ─────────────────────────────────────────────────────
@app.get("/api/runtimes")
async def api_runtimes():
    """Return status of all three runtimes: Nexus, PicoClaw, OpenClaw."""
    import shutil, subprocess

    # Nexus — always running if ClawOS daemon is running
    daemon_status = "unknown"
    try:
        r = await asyncio.create_subprocess_exec(
            "systemctl", "--user", "is-active", "clawos.service",
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        out, _ = await r.communicate()
        daemon_status = out.decode().strip()
    except Exception:
        pass
    nexus_running = daemon_status == "active"

    # PicoClaw — check binary + version
    picoclaw_ok = shutil.which("picoclaw") is not None
    picoclaw_running = False
    if picoclaw_ok:
        try:
            r = subprocess.run(["picoclaw", "version"],
                               capture_output=True, timeout=2)
            picoclaw_running = r.returncode == 0
        except Exception:
            pass

    # OpenClaw — check binary + gateway health on port 18789
    openclaw_ok = shutil.which("openclaw") is not None
    openclaw_running = False
    if openclaw_ok:
        try:
            async with httpx.AsyncClient() as c:
                r = await c.get("http://127.0.0.1:18789/health", timeout=1.5)
                openclaw_running = r.status_code == 200
        except Exception:
            pass

    # Detect configured model from openclaw.json if available
    import json as _json
    from pathlib import Path as _Path
    oc_model = "cloud"
    try:
        oc_cfg = _Path.home() / ".openclaw" / "openclaw.json"
        if oc_cfg.exists():
            cfg = _json.loads(oc_cfg.read_text())
            primary = cfg.get("agents", {}).get("defaults", {}).get("model", {}).get("primary", "")
            if primary:
                oc_model = primary.split("/")[-1] if "/" in primary else primary
    except Exception:
        pass

    return {
        "nexus":    {"installed": True,           "running": nexus_running,    "model": "local"},
        "picoclaw": {"installed": picoclaw_ok,     "running": picoclaw_running, "model": "local"},
        "openclaw": {"installed": openclaw_ok,     "running": openclaw_running, "model": oc_model},
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("service:app", host="0.0.0.0", port=7070, reload=False, log_level="info")

_static = Path(__file__).parent / "static"
if _static.exists():
    # SPA catch-all: serve index.html for any non-API, non-asset path
    # so React Router handles /workflows, /settings, etc.
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        index = _static / "index.html"
        asset = _static / full_path
        if asset.exists() and asset.is_file():
            return FileResponse(str(asset))
        return FileResponse(str(index))

    app.mount("/assets", StaticFiles(directory=str(_static / "assets")), name="assets")
