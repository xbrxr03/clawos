#!/usr/bin/env python3
"""
test_factory.py — Content Factory preflight and integration tests.

Usage:
  python3 test_factory.py           # full test suite
  python3 test_factory.py --quick   # fast checks only (no LLM, no network)
  python3 test_factory.py --full    # includes live Ollama + Pollinations tests
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

FACTORY_DIR = Path(os.environ.get("FACTORY_ROOT", Path.home() / "factory"))
sys.path.insert(0, str(FACTORY_DIR))

PASS  = "\033[38;5;84m✓\033[0m"
FAIL  = "\033[38;5;203m✗\033[0m"
SKIP  = "\033[38;5;245m·\033[0m"
WARN  = "\033[38;5;220m!\033[0m"

passed = 0
failed = 0
skipped = 0


def ok(name):
    global passed
    passed += 1
    print(f"  {PASS}  {name}")


def fail(name, reason=""):
    global failed
    failed += 1
    print(f"  {FAIL}  {name}" + (f" — {reason}" if reason else ""))


def skip(name, reason=""):
    global skipped
    skipped += 1
    print(f"  {SKIP}  {name} (skipped: {reason})")


def section(title):
    print(f"\n  \033[38;5;75m──\033[0m  {title}")


# ── 1. Imports ─────────────────────────────────────────────────────────────────

section("Python imports")

try:
    import psutil
    ok("psutil")
except ImportError:
    fail("psutil", "pip install psutil")

try:
    import pathvalidate
    ok("pathvalidate")
except ImportError:
    fail("pathvalidate", "pip install pathvalidate")

try:
    import requests
    ok("requests")
except ImportError:
    fail("requests", "pip install requests")

try:
    import PIL
    ok("pillow")
except ImportError:
    fail("pillow", "pip install pillow")

# ── 2. Factory core imports ────────────────────────────────────────────────────

section("Factory core")

try:
    from core.config import (
        ROOT, INBOX_DIR, ACTIVE_DIR, COMPLETED_DIR, FAILED_DIR,
        ARTIFACTS_DIR, LOGS_DIR, AGENTS_STATE, LEASES_DIR,
        LEASE_TTL_SECONDS, LEASE_TTL_BY_CLASS, HEARTBEAT_INTERVAL,
        FOREMAN_TICK, RETRY_BACKOFF_SECONDS, RESOURCE_LIMITS,
        PHASE_ROUTING, PHASE_SEQUENCE, TERMINAL_PHASES, MAX_RETRIES,
    )
    ok("core.config — all constants present")
except ImportError as e:
    fail("core.config", str(e))

try:
    from core.job_store import JobStore
    ok("core.job_store")
except ImportError as e:
    fail("core.job_store", str(e))

try:
    from core.lease_manager import LeaseManager
    ok("core.lease_manager")
except ImportError as e:
    fail("core.lease_manager", str(e))

try:
    from core.event_logger import EventLogger
    ok("core.event_logger")
except ImportError as e:
    fail("core.event_logger", str(e))

try:
    from core.agent_base import AgentBase
    ok("core.agent_base")
except ImportError as e:
    fail("core.agent_base", str(e))

# ── 3. Agent imports ───────────────────────────────────────────────────────────

section("Agent imports")

agents_to_check = [
    ("agents.writer_agent",    "WriterAgent"),
    ("agents.voice_agent",     "VoiceAgent"),
    ("agents.assembler_agent", "AssemblerAgent"),
    ("agents.visual_agent",    "VisualAgent"),
    ("agents.render_agent",    "RenderAgent"),
    ("agents.upload_agent",    "UploadAgent"),
    ("agents.foreman_agent",   "ForemanAgent"),
    ("agents.monitor_agent",   "MonitorAgent"),
]

for module, cls in agents_to_check:
    try:
        mod = __import__(module, fromlist=[cls])
        getattr(mod, cls)
        ok(f"{module}.{cls}")
    except ImportError as e:
        fail(f"{module}.{cls}", str(e))

# ── 4. Directory structure ────────────────────────────────────────────────────

section("Directory structure")

required_dirs = [
    FACTORY_DIR / "agents",
    FACTORY_DIR / "core",
    FACTORY_DIR / "schemas",
    FACTORY_DIR / "jobs" / "inbox",
    FACTORY_DIR / "jobs" / "active",
    FACTORY_DIR / "jobs" / "completed",
    FACTORY_DIR / "jobs" / "failed",
    FACTORY_DIR / "artifacts",
    FACTORY_DIR / "logs",
    FACTORY_DIR / "state" / "agents",
    FACTORY_DIR / "state" / "events",
    FACTORY_DIR / "state" / "leases",
    FACTORY_DIR / "state" / "metrics",
]

for d in required_dirs:
    if d.exists():
        ok(str(d.relative_to(FACTORY_DIR)))
    else:
        fail(str(d.relative_to(FACTORY_DIR)), "directory missing")

# ── 5. Required files ─────────────────────────────────────────────────────────

section("Required files")

required_files = [
    FACTORY_DIR / "schemas" / "job_templates.json",
    FACTORY_DIR / "factoryctl.py",
    FACTORY_DIR / "start.sh",
    FACTORY_DIR / "stop.sh",
]

for f in required_files:
    if f.exists():
        ok(str(f.relative_to(FACTORY_DIR)))
    else:
        fail(str(f.relative_to(FACTORY_DIR)), "file missing")

# Check job_templates has documentary_video
try:
    templates = json.loads((FACTORY_DIR / "schemas" / "job_templates.json").read_text())
    if "documentary_video" in templates.get("templates", {}):
        ok("job_templates.json has documentary_video template")
    else:
        fail("job_templates.json", "missing documentary_video template")
except Exception as e:
    fail("job_templates.json", str(e))

# ── 6. External tools ─────────────────────────────────────────────────────────

section("External tools")

def check_command(cmd, name):
    result = subprocess.run(["which", cmd], capture_output=True)
    if result.returncode == 0:
        ok(f"{name} ({result.stdout.decode().strip()})")
        return True
    else:
        fail(name, f"'{cmd}' not found in PATH")
        return False

check_command("ffmpeg", "ffmpeg")
check_command("piper",  "piper")
check_command("ollama", "ollama")

# Check piper model
piper_model_dir = Path(os.environ.get("PIPER_MODEL_DIR",
                                       Path.home() / ".local" / "share" / "piper"))
piper_model = piper_model_dir / "en_US-lessac-medium.onnx"
if piper_model.exists():
    ok(f"Piper voice model ({piper_model})")
else:
    fail("Piper voice model", f"not found at {piper_model}")

# ── 7. Piper TTS test ─────────────────────────────────────────────────────────

section("Piper TTS synthesis")

if piper_model.exists():
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        result = subprocess.run(
            ["piper", "--model", str(piper_model), "--output_file", tmp_path],
            input="Content factory voice test.",
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and Path(tmp_path).stat().st_size > 1000:
            size_kb = Path(tmp_path).stat().st_size // 1024
            ok(f"Piper synthesis works ({size_kb}KB generated)")
        else:
            fail("Piper synthesis", result.stderr.strip()[:100])
    except Exception as e:
        fail("Piper synthesis", str(e))
    finally:
        Path(tmp_path).unlink(missing_ok=True)
else:
    skip("Piper synthesis", "model not found")

# ── 8. Ollama connection ──────────────────────────────────────────────────────

section("Ollama")

try:
    result = subprocess.run(
        ["ollama", "list"],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode == 0:
        models = [line.split()[0] for line in result.stdout.strip().splitlines()[1:] if line]
        ok(f"Ollama running — models: {', '.join(models) or 'none'}")
        if "qwen2.5:7b" in " ".join(models):
            ok("qwen2.5:7b available")
        else:
            fail("qwen2.5:7b", f"not found. Run: ollama pull qwen2.5:7b. Available: {models}")
    else:
        fail("Ollama", "not running — start with: ollama serve")
except Exception as e:
    fail("Ollama", str(e))

# ── 9. Job lifecycle (no LLM) ─────────────────────────────────────────────────

section("Job lifecycle")

try:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["FACTORY_ROOT"] = tmp

        # Re-import with new root
        import importlib
        import core.config as cfg_mod
        importlib.reload(cfg_mod)
        from core.config import ensure_dirs
        ensure_dirs()

        from core.job_store import JobStore
        js = JobStore()

        job_id = js.create("test topic", priority=5, template="documentary_video")
        ok(f"JobStore.create → {job_id}")

        job = js.load(job_id)
        assert job["topic"] == "test topic", "topic mismatch"
        assert job["status"] == "pending", "status should be pending"
        ok("JobStore.load — topic and status correct")

        js.update_phase(job_id, "writing")
        job = js.load(job_id)
        assert job["phase"] == "writing"
        ok("JobStore.update_phase → writing")

        js.advance_phase(job_id)
        job = js.load(job_id)
        assert job["phase"] == "voice", f"expected voice, got {job['phase']}"
        ok("JobStore.advance_phase → voice")

        js.record_error(job_id, "test error")
        ok("JobStore.record_error")

    # Reset FACTORY_ROOT
    os.environ["FACTORY_ROOT"] = str(FACTORY_DIR)
    importlib.reload(cfg_mod)

except Exception as e:
    fail("Job lifecycle", str(e))

# ── 10. Visual agent Pollinations (network, --full only) ──────────────────────

args = argparse.ArgumentParser()
args.add_argument("--quick", action="store_true")
args.add_argument("--full",  action="store_true")
parsed = args.parse_args()

section("Pollinations.ai image generation")

if parsed.quick:
    skip("Pollinations test", "--quick mode")
else:
    try:
        import urllib.request
        import urllib.parse
        prompt = urllib.parse.quote("a simple red circle on white background")
        url    = f"https://image.pollinations.ai/prompt/{prompt}?width=128&height=128&nologo=true"
        req    = urllib.request.Request(url, headers={"User-Agent": "ClawOS-Test/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        if len(data) > 1000:
            ok(f"Pollinations.ai reachable ({len(data):,} bytes)")
        else:
            fail("Pollinations.ai", f"response too small ({len(data)} bytes)")
    except Exception as e:
        warn_msg = str(e)
        if "urlopen" in warn_msg.lower() or "connection" in warn_msg.lower():
            skip("Pollinations.ai", "no internet access")
        else:
            fail("Pollinations.ai", warn_msg)

# ── Summary ───────────────────────────────────────────────────────────────────

total = passed + failed + skipped
print(f"\n  {'─' * 44}")
print(f"  {PASS} {passed} passed  {FAIL} {failed} failed  {SKIP} {skipped} skipped  ({total} total)")
print()

if failed > 0:
    print("  Fix the failures above, then run: bash ~/factory/start.sh")
    print()
    sys.exit(1)
else:
    print("  All checks passed. Start the factory:")
    print("    bash ~/factory/start.sh")
    print("    python3 factoryctl.py new-job \"your topic\" --template documentary_video")
    print()
    sys.exit(0)
