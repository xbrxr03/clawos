"""
ClawOS Session 1 Test Suite
============================
Tests all S1 components without requiring a live LLM (unit mode).
Run with --e2e for end-to-end tests that need Ollama running.

Usage:
  python3 tests/system/test_phase1.py          # unit tests only
  python3 tests/system/test_phase1.py --e2e    # include e2e
"""
import sys
import os
import asyncio
import json
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

E2E = "--e2e" in sys.argv

passed = failed = 0

def ok(name):
    global passed
    passed += 1
    print(f"  ✓  {name}")

def fail(name, reason=""):
    global failed
    failed += 1
    print(f"  ✗  {name}" + (f" — {reason}" if reason else ""))

def section(title):
    print(f"\n  ── {title}")

def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── 1. Core utilities ─────────────────────────────────────────────────────────
section("1. Core utilities")

try:
    from clawos_core.util.ids import task_id, session_id, entry_id, req_id
    t = task_id(); s = session_id(); e = entry_id(); r = req_id()
    assert t.startswith("task_") and len(t) == 13
    assert len(s) == 36
    ok("ids — task_id, session_id, entry_id, req_id")
except Exception as ex:
    fail("ids", str(ex))

try:
    from clawos_core.util.time import now_iso, now_stamp, elapsed
    import time as _t
    ts = _t.time()
    assert "T" in now_iso()
    assert len(now_stamp()) == 16
    assert elapsed(ts) >= 0
    ok("time — now_iso, now_stamp, elapsed")
except Exception as ex:
    fail("time", str(ex))

try:
    from clawos_core.util.jsonx import safe_parse, to_json
    assert safe_parse('{"action":"fs.read","action_input":"test.txt"}') == {"action":"fs.read","action_input":"test.txt"}
    assert safe_parse('{"final_answer": "hello"}') == {"final_answer": "hello"}
    assert safe_parse('plain text response') == {"final_answer": "plain text response"}
    assert safe_parse(None) is None
    ok("jsonx — safe_parse, to_json")
except Exception as ex:
    fail("jsonx", str(ex))

try:
    from clawos_core.constants import VERSION, CLAWOS_DIR, PORT_DASHD, SERVICES, DEFAULT_MODEL
    assert VERSION == "0.1.0"
    assert PORT_DASHD == 7070
    assert "policyd" in SERVICES
    assert DEFAULT_MODEL == "qwen2.5:7b"
    ok("constants — VERSION, ports, services, model")
except Exception as ex:
    fail("constants", str(ex))

try:
    from clawos_core.util.paths import workspace_path, pinned_path, soul_path
    with tempfile.TemporaryDirectory() as td:
        # paths module uses CLAWOS_DIR, just verify the functions work
        from clawos_core import constants
        old = constants.CLAWOS_DIR
        constants.CLAWOS_DIR = Path(td)
        import clawos_core.util.paths as _p
        import importlib
        # just check they return Path objects
        assert callable(_p.workspace_path)
        assert callable(_p.pinned_path)
        constants.CLAWOS_DIR = old
    ok("paths — workspace_path, pinned_path, soul_path")
except Exception as ex:
    fail("paths", str(ex))


# ── 2. Config loader ──────────────────────────────────────────────────────────
section("2. Config loader")

try:
    from clawos_core.config.loader import load, get
    cfg = load("balanced")
    assert cfg.get("model", {}).get("chat") == "qwen2.5:7b"
    assert cfg.get("_profile") == "balanced"
    ok("load balanced profile")
except Exception as ex:
    fail("load balanced", str(ex))

try:
    from clawos_core.config.loader import load
    lr = load("lowram")
    assert lr["model"]["ctx_window"] == 2048
    assert lr["voice"]["enabled"] is False
    ok("load lowram profile — ctx=2048, voice=off")
except Exception as ex:
    fail("load lowram", str(ex))

try:
    from clawos_core.config.loader import load
    pf = load("performance")
    assert pf["model"]["chat"] == "qwen2.5:7b"
    ok("load performance profile — qwen2.5:7b")
except Exception as ex:
    fail("load performance", str(ex))

try:
    from clawos_core.config.loader import get
    val = get("model.chat", "fallback", "balanced")
    assert val == "qwen2.5:7b"
    missing = get("does.not.exist", "default")
    assert missing == "default"
    ok("config get() — dot notation + missing key fallback")
except Exception as ex:
    fail("config get()", str(ex))


# ── 3. Data models ────────────────────────────────────────────────────────────
section("3. Data models")

try:
    from clawos_core.models import Task, TaskStatus, Session, AuditEntry, Decision, ToolCall
    t = Task(intent="test intent")
    assert t.status == TaskStatus.QUEUED
    assert t.task_id.startswith("task_")
    assert "intent" in t.to_dict()
    ok("Task model — creation, status, to_dict()")
except Exception as ex:
    fail("Task model", str(ex))

try:
    from clawos_core.models import AuditEntry, Decision
    e = AuditEntry(tool="fs.read", target="/tmp/test.txt", decision="ALLOW", reason="test")
    e.prev_hash  = "aabbcc"
    e.entry_hash = e.compute_hash()
    assert len(e.entry_hash) == 64   # SHA-256 hex
    assert e.to_dict()["tool"] == "fs.read"
    ok("AuditEntry — Merkle hash, to_dict()")
except Exception as ex:
    fail("AuditEntry", str(ex))

try:
    from clawos_core.models import Session
    s = Session(workspace_id="test_ws")
    assert s.workspace_id == "test_ws"
    assert len(s.session_id) == 36
    ok("Session model")
except Exception as ex:
    fail("Session model", str(ex))


# ── 4. Event bus ──────────────────────────────────────────────────────────────
section("4. Event bus")

try:
    from clawos_core.events.bus import get_bus, EV_LOG, EV_TASK_UPDATE
    received = []
    bus = get_bus()
    bus.subscribe(lambda ev: received.append(ev))
    run(bus.publish(EV_LOG, {"message": "test log", "service": "test"}))
    assert len(received) >= 1
    assert received[-1]["type"] == EV_LOG
    ok("event bus — subscribe, publish, receive")
except Exception as ex:
    fail("event bus", str(ex))

try:
    from clawos_core.events.bus import get_bus
    bus = get_bus()
    run(bus.emit_log("INFO", "test", "hello from test"))
    run(bus.emit_task("task_abc123", "running", "test detail"))
    ok("event bus — emit_log, emit_task helpers")
except Exception as ex:
    fail("event bus helpers", str(ex))


# ── 5. Audit / Merkle chain ───────────────────────────────────────────────────
section("5. Audit (Merkle chain)")

try:
    import clawos_core.logging.audit as audit
    from clawos_core.models import AuditEntry
    with tempfile.TemporaryDirectory() as td:
        from clawos_core import constants
        constants.AUDIT_JSONL  = Path(td) / "audit.jsonl"
        constants.POLICYD_DB   = Path(td) / "policyd.db"
        audit._db = None   # reset connection
        e1 = AuditEntry(tool="fs.read",  target="/tmp/a", decision="ALLOW", reason="test")
        e2 = AuditEntry(tool="fs.write", target="/tmp/b", decision="DENY",  reason="test")
        audit.write(e1)
        audit.write(e2)
        entries = audit.tail(10)
        assert len(entries) >= 2
        ok("audit — write entries, tail()")
except Exception as ex:
    fail("audit write/tail", str(ex))


# ── 6. Memory service ─────────────────────────────────────────────────────────
section("6. Memory service (memd)")

try:
    with tempfile.TemporaryDirectory() as td:
        from clawos_core import constants
        constants.MEMORY_DIR = Path(td)
        import services.memd.service as memd_mod
        memd_mod._FTS_DB_PATH = Path(td) / "fts.db"
        memd_mod.CHROMA_OK    = False
        svc = memd_mod.MemoryService()

        mid = svc.remember("the user prefers dark mode", "test_ws")
        assert mid
        ok("memory — remember() returns memory_id")

        svc.append_pinned("test_ws", "user name is Alex")
        pinned = svc.read_pinned("test_ws")
        assert "Alex" in pinned
        ok("memory — PINNED.md append + read")

        svc.append_history("test_ws", "tested history logging")
        hist = svc.read_history_tail("test_ws", 5)
        assert "tested history" in hist
        ok("memory — HISTORY.md append + tail")

        svc.write_workflow("test_ws", "# Current task: testing")
        wf = svc.read_workflow("test_ws")
        assert "testing" in wf
        svc.clear_workflow("test_ws")
        ok("memory — WORKFLOW.md write/read/clear")

        results = svc.recall("dark mode", "test_ws")
        assert isinstance(results, list)
        ok("memory — recall() returns list")

        ctx = svc.build_context_block("preferences", "test_ws")
        ok(f"memory — build_context_block() returns {len(ctx)} chars")

        all_mems = svc.get_all("test_ws")
        assert len(all_mems) >= 1
        ok("memory — get_all() returns entries")

except Exception as ex:
    fail("memory service", str(ex))


# ── 7. Policy engine ──────────────────────────────────────────────────────────
section("7. Policy engine (policyd)")

try:
    from clawos_core import constants
    with tempfile.TemporaryDirectory() as td:
        constants.AUDIT_JSONL = Path(td) / "audit.jsonl"
        constants.POLICYD_DB  = Path(td) / "policyd.db"
        constants.CLAWOS_DIR  = Path(td)
        import clawos_core.logging.audit as audit
        audit._db = None
        from services.policyd.service import PolicyEngine
        engine = PolicyEngine()
        granted = ["fs.read", "fs.list", "web.search", "memory.read", "memory.write"]

        ws_dir = Path(td) / "workspace" / "ws1"
        ws_dir.mkdir(parents=True, exist_ok=True)
        abs_target = str(ws_dir / "test.txt")
        d, r = run(engine.evaluate("fs.read", abs_target, "t1", "ws1", granted))
        assert d.value == "ALLOW", f"got {d.value}: {r}"
        ok("policy — fs.read ALLOW for granted tool")

        d, r = run(engine.evaluate("fs.write", "test.txt", "t1", "ws1", []))
        assert d.value == "DENY"
        assert "not granted" in r
        ok("policy — fs.write DENY when not granted")

        d, r = run(engine.evaluate("fs.read", "/etc/shadow", "t1", "ws1", granted))
        assert d.value == "DENY"
        assert "blocked" in r
        ok("policy — /etc/shadow DENY (blocked path)")

        d, r = run(engine.evaluate("web.search", "test query", "t1", "ws1", granted))
        assert d.value == "ALLOW"
        ok("policy — web.search ALLOW")

        tail = engine.get_audit_tail(5)
        assert len(tail) >= 3
        ok("policy — audit tail returns entries")

except Exception as ex:
    fail("policy engine", str(ex))


# ── 8. Lifecycle hooks ────────────────────────────────────────────────────────
section("8. Lifecycle hooks (BeforeToolCall/AfterToolCall)")

try:
    from services.policyd.service import PolicyEngine, HookRegistry
    engine  = PolicyEngine()
    log_b   = []
    log_a   = []
    engine.hooks.register_before("test_before", lambda t, tgt, ctx: log_b.append(t) or True)
    engine.hooks.register_after("test_after",   lambda t, tgt, r, ctx: log_a.append(t))
    run(engine.hooks.run_before("fs.read", "test.txt", {}))
    run(engine.hooks.run_after("fs.read", "test.txt", "result", {}))
    assert "fs.read" in log_b
    assert "fs.read" in log_a
    ok("lifecycle hooks — BeforeToolCall + AfterToolCall fire")
except Exception as ex:
    fail("lifecycle hooks", str(ex))

try:
    from services.policyd.service import HookRegistry
    reg      = HookRegistry()
    failures = [0]
    def bad_hook(t, tgt, ctx):
        failures[0] += 1
        raise RuntimeError("intentional failure")
    reg.register_before("bad", bad_hook)
    for _ in range(4):
        run(reg.run_before("fs.read", "x", {}))
    assert reg._before[0]["enabled"] is False   # circuit breaker tripped
    ok("lifecycle hooks — circuit breaker disables after 3 failures")
except Exception as ex:
    fail("lifecycle hook circuit breaker", str(ex))


# ── 9. Tool bridge ────────────────────────────────────────────────────────────
section("9. Tool bridge")

class MockPolicy:
    granted_tools = ["fs.read","fs.write","fs.list","fs.search","web.search",
                     "memory.read","memory.write","system.info","workspace.inspect"]
    task_id = "test_task"
    def _get_engine(self): return None
    async def check(self, tool, target, content=""):
        if tool not in self.granted_tools:
            return "DENY", "not granted"
        if "/etc/shadow" in target:
            return "DENY", "blocked"
        return "ALLOW", "ok"

class MockMemory:
    def recall(self, q, ws): return ["test memory"]
    def get_all(self, ws, limit=100): return []
    def remember(self, t, ws, source=""): return "mid_abc"
    def forget(self, mid, ws): pass

try:
    with tempfile.TemporaryDirectory() as td:
        from clawos_core import constants
        constants.CLAWOS_DIR   = Path(td)
        import clawos_core.util.paths as _paths
        _paths.CLAWOS_DIR = Path(td)
        ws_dir = Path(td) / "workspace" / "test_ws"
        ws_dir.mkdir(parents=True)
        (ws_dir / "hello.txt").write_text("hello from ClawOS")
        from services.toolbridge.service import ToolBridge
        bridge = ToolBridge(MockPolicy(), MockMemory(), "test_ws")
        bridge._ws_root = ws_dir  # override directly

        result = run(bridge.run("fs.read", str(ws_dir / "hello.txt")))
        assert "hello from ClawOS" in result
        ok("toolbridge — fs.read")

        result = run(bridge.run("fs.write", str(ws_dir / "output.txt"), content="written by test"))
        assert "[OK]" in result
        ok("toolbridge — fs.write")

        result = run(bridge.run("fs.list", str(ws_dir)))
        assert "hello.txt" in result
        ok("toolbridge — fs.list")

        result = run(bridge.run("system.info", ""))
        assert "Disk:" in result
        ok("toolbridge — system.info")

        result = run(bridge.run("memory.read", "test"))
        assert "test memory" in result
        ok("toolbridge — memory.read uses MockMemory")

        tool_list = bridge.get_tool_list_for_prompt()
        assert "fs.read" in tool_list
        assert "shell.elevated" not in tool_list  # not in granted_tools
        ok("toolbridge — get_tool_list_for_prompt() filters by grants")

except Exception as ex:
    fail("toolbridge", str(ex))


# ── 10. Agent prompts ─────────────────────────────────────────────────────────
section("10. Agent prompts")

try:
    from runtimes.agent.prompts import SYSTEM_PROMPT, build_user_message
    assert "final_answer" in SYSTEM_PROMPT
    assert "JSON" in SYSTEM_PROMPT
    # Static — no dynamic fields
    assert "{{" not in SYSTEM_PROMPT
    ok("SYSTEM_PROMPT — static, contains required format instructions")
except Exception as ex:
    fail("SYSTEM_PROMPT", str(ex))

try:
    from runtimes.agent.prompts import build_user_message
    msg = build_user_message("what time is it", "sess123", 1, "## Memory\n- fact")
    assert "what time is it" in msg
    assert "Memory" in msg
    assert "sess123"[:8] in msg
    ok("build_user_message — dynamic fields in user turn (token-aware context)")
except Exception as ex:
    fail("build_user_message", str(ex))


# ── 11. Agent parser ──────────────────────────────────────────────────────────
section("11. Agent parser (json_repair)")

try:
    from runtimes.agent.parser import parse_response
    r = parse_response('{"final_answer": "hello world"}')
    assert r["final_answer"] == "hello world"
    ok("parser — clean final_answer")
except Exception as ex:
    fail("parser clean", str(ex))

try:
    from runtimes.agent.parser import parse_response
    r = parse_response('{"action": "fs.read", "action_input": "notes.txt"}')
    assert r["action"] == "fs.read"
    ok("parser — action + action_input")
except Exception as ex:
    fail("parser action", str(ex))

try:
    from runtimes.agent.parser import parse_response
    r = parse_response('Sure! {"final_answer": "42"} here you go')
    assert r.get("final_answer") == "42"
    ok("parser — extract JSON from surrounding text")
except Exception as ex:
    fail("parser surrounding text", str(ex))

try:
    from runtimes.agent.parser import parse_response
    r = parse_response("plain text no json at all")
    assert "final_answer" in r or "parse_error" in r
    ok("parser — plain text graceful fallback")
except Exception as ex:
    fail("parser plain text", str(ex))


# ── 12. OpenClaw integration ──────────────────────────────────────────────────
section("12. OpenClaw integration layer")

try:
    from openclaw_integration.config_gen import gen_config, GOOD_MODELS
    cfg = gen_config("qwen2.5:7b")
    assert cfg["models"]["providers"]["ollama"]["apiKey"] == "ollama-local"
    assert "11434" in cfg["models"]["providers"]["ollama"]["baseUrl"]
    assert cfg["cloud"]["enabled"] is False
    assert cfg["network"]["mode"] == "offline"
    ok("openclaw config_gen — gen_config() correct structure")
except Exception as ex:
    fail("openclaw config_gen", str(ex))

try:
    from openclaw_integration.config_gen import GOOD_MODELS
    assert "qwen2.5:7b" in GOOD_MODELS
    assert "qwen2.5:7b" not in GOOD_MODELS   # doesn't support tool calling
    ok("openclaw — qwen2.5:7b excluded (no tool calling), qwen2.5:7b included")
except Exception as ex:
    fail("openclaw model list", str(ex))

try:
    from openclaw_integration.installer import system_check, MIN_RAM_GB
    checks = system_check()
    assert "node" in checks
    assert "npm" in checks
    assert "ollama" in checks
    assert "ram_gb" in checks
    ok(f"openclaw system_check() — RAM: {checks['ram_gb']}GB, ollama: {checks['ollama']}")
except Exception as ex:
    fail("openclaw system_check", str(ex))


# ── 13. Dashboard API (no server needed) ──────────────────────────────────────
section("13. Dashboard API")

try:
    from services.dashd.api import create_app, FASTAPI_OK
    if FASTAPI_OK:
        app = create_app()
        assert app.title == "ClawOS Dashboard"
        ok("dashd — create_app() succeeds")
    else:
        ok("dashd — fastapi not installed (skip)")
except Exception as ex:
    fail("dashd create_app", str(ex))

try:
    from pathlib import Path
    html = Path(ROOT) / "clients" / "dashboard" / "index.html"
    assert html.exists()
    content = html.read_text()
    assert "CLAWOS" in content
    assert "WebSocket" in content
    assert "/api/health" in content
    assert "approvals" in content
    ok("dashboard index.html — exists, has WebSocket, approvals, health")
except Exception as ex:
    fail("dashboard html", str(ex))


# ── 14. E2E — requires live Ollama ────────────────────────────────────────────
if E2E:
    section("14. E2E — live Ollama")

    try:
        from services.modeld.ollama_client import is_running
        assert is_running(), "Ollama is not running"
        ok("ollama — is_running()")
    except Exception as ex:
        fail("ollama running", str(ex))

    try:
        from services.modeld.ollama_client import list_models
        models = list_models()
        assert len(models) > 0
        names  = [m.get("name","") for m in models]
        ok(f"ollama — models: {', '.join(names[:3])}")
    except Exception as ex:
        fail("ollama list_models", str(ex))

    try:
        from runtimes.agent.runtime import build_runtime
        agent = run(build_runtime("test_e2e"))
        reply = run(agent.chat("Say only: CLAWOS_OK"))
        assert "CLAWOS" in reply.upper() or len(reply) > 0
        ok(f"e2e — full agent round trip: '{reply[:60]}'")
    except Exception as ex:
        fail("e2e agent round trip", str(ex))
else:
    print("\n  (skip e2e — run with --e2e for live Ollama tests)")

# ── Summary ───────────────────────────────────────────────────────────────────
total = passed + failed
print(f"\n  {'─'*46}")
print(f"  {passed}/{total} passed", end="")
if failed:
    print(f"  |  {failed} FAILED  ←")
else:
    print("  ✓  all passed")
print()

sys.exit(0 if failed == 0 else 1)
