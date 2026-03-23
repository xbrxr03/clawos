#!/usr/bin/env python3
"""
test_factory.py — content-factory preflight tests.
Usage:
  python3 test_factory.py           # full suite
  python3 test_factory.py --quick   # skip network + live services
  python3 test_factory.py --full    # includes live ComfyUI ping
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

FACTORY_DIR = Path(os.environ.get("FACTORY_ROOT", Path.home() / "factory"))
sys.path.insert(0, str(FACTORY_DIR))

G = "\033[38;5;84m✓\033[0m"
R = "\033[38;5;203m✗\033[0m"
S = "\033[38;5;245m·\033[0m"

passed = failed = skipped = 0

def ok(n):   global passed;  passed  += 1; print(f"  {G}  {n}")
def fail(n, r=""): global failed;  failed  += 1; print(f"  {R}  {n}" + (f" — {r}" if r else ""))
def skip(n, r=""): global skipped; skipped += 1; print(f"  {S}  {n} (skipped: {r})")
def section(t): print(f"\n  \033[38;5;75m──\033[0m  {t}")

parser = argparse.ArgumentParser()
parser.add_argument("--quick", action="store_true")
parser.add_argument("--full",  action="store_true")
args = parser.parse_args()

IN_CI = os.environ.get("CI", "").lower() == "true"

COMFYUI_DIR  = Path(os.environ.get("COMFYUI_DIR",  Path.home() / "ComfyUI"))
CKPT_NAME    = os.environ.get("COMFYUI_CHECKPOINT", "dreamshaper_8.safetensors")
PIPER_DIR    = Path(os.environ.get("PIPER_MODEL_DIR", Path.home() / ".local" / "share" / "piper"))
PIPER_MODEL  = PIPER_DIR / "en_US-lessac-medium.onnx"

# ── 1. Python imports ──────────────────────────────────────────────────────────
section("Python imports")
for pkg, install in [("psutil","psutil"),("pathvalidate","pathvalidate"),
                     ("requests","requests"),("PIL","pillow")]:
    try: __import__(pkg); ok(pkg)
    except ImportError: fail(pkg, f"pip install {install}")

# ── 2. Factory core ────────────────────────────────────────────────────────────
section("Factory core")
try:
    from core.config import (
        ROOT, INBOX_DIR, ACTIVE_DIR, ARTIFACTS_DIR, LOGS_DIR, AGENTS_STATE,
        LEASES_DIR, LEASE_TTL_SECONDS, LEASE_TTL_BY_CLASS, HEARTBEAT_INTERVAL,
        FOREMAN_TICK, RETRY_BACKOFF_SECONDS, RESOURCE_LIMITS, PHASE_ROUTING,
        PHASE_SEQUENCE, TERMINAL_PHASES, MAX_RETRIES,
    )
    ok("core.config — all constants present")
except ImportError as e:
    fail("core.config", str(e))

for mod in ["core.job_store","core.lease_manager","core.event_logger","core.agent_base"]:
    try: __import__(mod); ok(mod)
    except ImportError as e: fail(mod, str(e))

# ── 3. Agent imports ───────────────────────────────────────────────────────────
section("Agent imports")
for mod, cls in [
    ("agents.writer_agent","WriterAgent"),("agents.voice_agent","VoiceAgent"),
    ("agents.assembler_agent","AssemblerAgent"),("agents.visual_agent","VisualAgent"),
    ("agents.render_agent","RenderAgent"),("agents.upload_agent","UploadAgent"),
    ("agents.foreman_agent","ForemanAgent"),("agents.monitor_agent","MonitorAgent"),
]:
    try: m = __import__(mod, fromlist=[cls]); getattr(m, cls); ok(cls)
    except ImportError as e: fail(cls, str(e))

# ── 4. Directory structure ─────────────────────────────────────────────────────
section("Directory structure")
for d in [
    FACTORY_DIR/"agents", FACTORY_DIR/"core", FACTORY_DIR/"schemas",
    FACTORY_DIR/"jobs"/"inbox", FACTORY_DIR/"jobs"/"active",
    FACTORY_DIR/"jobs"/"completed", FACTORY_DIR/"jobs"/"failed",
    FACTORY_DIR/"artifacts", FACTORY_DIR/"logs",
    FACTORY_DIR/"state"/"agents", FACTORY_DIR/"state"/"events",
    FACTORY_DIR/"state"/"leases", FACTORY_DIR/"state"/"metrics",
]:
    if d.exists(): ok(str(d.relative_to(FACTORY_DIR)))
    else: fail(str(d.relative_to(FACTORY_DIR)), "missing")

# ── 5. Required files ──────────────────────────────────────────────────────────
section("Required files")
for f in [
    FACTORY_DIR/"schemas"/"job_templates.json",
    FACTORY_DIR/"factoryctl.py",
    FACTORY_DIR/"start.sh", FACTORY_DIR/"stop.sh",
    FACTORY_DIR/".env",
]:
    if f.exists(): ok(str(f.relative_to(FACTORY_DIR)))
    else: fail(str(f.relative_to(FACTORY_DIR)), "missing — run install.sh")

try:
    t = json.loads((FACTORY_DIR/"schemas"/"job_templates.json").read_text())
    if "documentary_video" in t.get("templates", {}):
        ok("documentary_video template present")
    else:
        fail("documentary_video template", "missing")
except Exception as e:
    fail("job_templates.json", str(e))

# ── 6. External tools ──────────────────────────────────────────────────────────
section("External tools")
for cmd, name in [("ffmpeg","ffmpeg"), ("piper","piper")] + \
                  ([] if IN_CI else [("ollama","ollama")]):
    r = subprocess.run(["which", cmd], capture_output=True)
    if r.returncode == 0: ok(f"{name} ({r.stdout.decode().strip()})")
    else: fail(name, f"'{cmd}' not in PATH — run install.sh")

if PIPER_MODEL.exists(): ok(f"Piper voice model present")
else: fail("Piper voice model", f"not found at {PIPER_MODEL} — run install.sh")

if IN_CI:
    skip("ComfyUI", "CI environment")
    skip(f"Checkpoint {CKPT_NAME}", "CI environment")
else:
    if (COMFYUI_DIR / "main.py").exists(): ok(f"ComfyUI present ({COMFYUI_DIR})")
    else: fail("ComfyUI", f"not found at {COMFYUI_DIR} — run install.sh")

    ckpt = COMFYUI_DIR / "models" / "checkpoints" / CKPT_NAME
    if ckpt.exists():
        size_gb = ckpt.stat().st_size / (1024**3)
        ok(f"{CKPT_NAME} ({size_gb:.1f}GB)")
    else:
        fail(CKPT_NAME, f"not found at {ckpt} — run install.sh")

# ── 7. Piper TTS synthesis ─────────────────────────────────────────────────────
section("Piper TTS synthesis")
if PIPER_MODEL.exists():
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        r = subprocess.run(
            ["piper", "--model", str(PIPER_MODEL), "--output_file", tmp_path],
            input="Content factory test.", capture_output=True, text=True, timeout=30
        )
        if r.returncode == 0 and Path(tmp_path).stat().st_size > 1000:
            ok(f"Piper synthesis works ({Path(tmp_path).stat().st_size//1024}KB)")
        else:
            fail("Piper synthesis", r.stderr.strip()[:120])
    except Exception as e:
        fail("Piper synthesis", str(e))
    finally:
        Path(tmp_path).unlink(missing_ok=True)
else:
    skip("Piper synthesis", "model not found")

# ── 8. Ollama ──────────────────────────────────────────────────────────────────
section("Ollama")
if IN_CI:
    skip("Ollama", "CI environment")
else:
    try:
        r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            models = [l.split()[0] for l in r.stdout.strip().splitlines()[1:] if l]
            ok(f"Ollama running — {', '.join(models) or 'no models'}")
            if any("qwen2.5" in m for m in models):
                ok("qwen2.5:7b available")
            else:
                fail("qwen2.5:7b", "not found — run: ollama pull qwen2.5:7b")
        else:
            fail("Ollama", "not running — run: ollama serve")
    except Exception as e:
        fail("Ollama", str(e))

# ── 9. Job lifecycle ───────────────────────────────────────────────────────────
section("Job lifecycle")
try:
    import importlib
    import core.config as cfg_mod

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["FACTORY_ROOT"] = tmp
        importlib.reload(cfg_mod)
        cfg_mod.ensure_dirs()

        from core.job_store import JobStore
        js = JobStore()

        result = js.create("test topic", priority=5, template="documentary_video")
        # create() may return job dict or job_id string depending on version
        if isinstance(result, dict):
            job_id = result["job_id"]
        else:
            job_id = result
        ok(f"JobStore.create → {job_id}")

        loaded = js.load(job_id)
        assert loaded["topic"] == "test topic"
        ok("JobStore.load — correct")

        js.update_phase(job_id, "writing")
        assert js.load(job_id)["phase"] == "writing"
        ok("JobStore.update_phase → writing")

        js.advance_phase(job_id)
        assert js.load(job_id)["phase"] == "voice"
        ok("JobStore.advance_phase → voice")

    os.environ["FACTORY_ROOT"] = str(FACTORY_DIR)
    importlib.reload(cfg_mod)

except Exception as e:
    fail("Job lifecycle", str(e))

# ── 10. ComfyUI live ping (--full only) ───────────────────────────────────────
section("ComfyUI API")
if args.quick or IN_CI:
    skip("ComfyUI ping", "--quick / CI mode")
elif args.full:
    try:
        import requests as req
        r = req.get("http://localhost:8188/system_stats", timeout=5)
        if r.status_code == 200: ok("ComfyUI responding at localhost:8188")
        else: fail("ComfyUI", f"HTTP {r.status_code}")
    except Exception:
        skip("ComfyUI ping", "not running yet (starts automatically when job reaches visual phase)")
else:
    skip("ComfyUI ping", "use --full to test live ComfyUI")

# ── Summary ────────────────────────────────────────────────────────────────────
total = passed + failed + skipped
print(f"\n  {'─'*46}")
print(f"  {G} {passed} passed  {R} {failed} failed  {S} {skipped} skipped  ({total} total)")
print()
if failed > 0:
    print("  Fix failures above then run: bash ~/factory/start.sh")
    sys.exit(1)
else:
    print("  All checks passed.")
    print("    bash ~/factory/start.sh")
    print(f"    python3 factoryctl.py new-job \"your topic\" --template documentary_video")
print()
