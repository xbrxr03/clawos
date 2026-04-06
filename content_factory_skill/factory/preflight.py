#!/usr/bin/env python3
"""
preflight.py — pre-flight system check for the AI Content Factory.

Tests every component before you submit a real job:
  - Environment and config
  - Filesystem structure
  - All Python modules import correctly
  - Ollama is running and model is available
  - Piper TTS can synthesise audio
  - ComfyUI is running and checkpoint is loaded
  - Job creation and lifecycle (dry run, no LLM calls)
  - Agent heartbeat system
  - Event logger
  - Lease manager
  - Dashboard API

Usage:
  python preflight.py              # full check
  python preflight.py --no-comfy  # skip ComfyUI check (if not running)
  python preflight.py --no-ollama # skip Ollama check
  python preflight.py --quick     # only env + imports + filesystem
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# ── colours ───────────────────────────────────────────────────────────────────
GREEN  = "\033[0;32m"
AMBER  = "\033[0;33m"
RED    = "\033[0;31m"
BLUE   = "\033[0;34m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):    print(f"  {GREEN}✓{RESET}  {msg}")
def warn(msg):  print(f"  {AMBER}⚠{RESET}  {msg}")
def fail(msg):  print(f"  {RED}✗{RESET}  {msg}")
def info(msg):  print(f"  {BLUE}→{RESET}  {msg}")
def header(msg):print(f"\n{BOLD}{msg}{RESET}")

PASS = 0
WARN = 0
FAIL = 0

def check(condition, pass_msg, fail_msg, warning=False):
    global PASS, WARN, FAIL
    if condition:
        ok(pass_msg)
        PASS += 1
    elif warning:
        warn(fail_msg)
        WARN += 1
    else:
        fail(fail_msg)
        FAIL += 1
    return condition


# ─────────────────────────────────────────────────────────────────────────────
# Parse args
# ─────────────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Factory pre-flight check")
parser.add_argument("--no-comfy",  action="store_true", help="Skip ComfyUI check")
parser.add_argument("--no-ollama", action="store_true", help="Skip Ollama check")
parser.add_argument("--no-piper",  action="store_true", help="Skip Piper TTS check")
parser.add_argument("--quick",     action="store_true", help="Env + imports + filesystem only")
args = parser.parse_args()

print(f"\n{BOLD}AI Content Factory — Pre-flight Check{RESET}")
print("=" * 50)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Environment
# ─────────────────────────────────────────────────────────────────────────────
header("1. Environment")

factory_root = Path(os.environ.get("FACTORY_ROOT", Path(__file__).parent))
check(factory_root.exists(), f"FACTORY_ROOT={factory_root}", f"FACTORY_ROOT not found: {factory_root}")

pythonpath = os.environ.get("PYTHONPATH", "")
check(str(factory_root) in pythonpath,
      f"PYTHONPATH includes factory root",
      "PYTHONPATH does not include factory root — agents may fail to import core modules",
      warning=True)

check(sys.version_info >= (3, 11),
      f"Python {sys.version_info.major}.{sys.version_info.minor}",
      f"Python 3.11+ required, got {sys.version_info.major}.{sys.version_info.minor}")

env_file = factory_root / ".env"
check(env_file.exists(), ".env file exists", ".env missing — run: cp .env.example .env", warning=True)

# Key env vars
for var in ["OLLAMA_MODEL", "PIPER_BIN", "COMFYUI_DIR", "COMFYUI_CHECKPOINT"]:
    val = os.environ.get(var, "")
    check(bool(val), f"{var}={val}", f"{var} not set in environment", warning=True)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Filesystem
# ─────────────────────────────────────────────────────────────────────────────
header("2. Filesystem structure")

required_dirs = [
    "agents", "core", "dashboard", "schemas", "services",
    "jobs/inbox", "jobs/active", "jobs/completed", "jobs/failed",
    "artifacts", "logs", "state/agents", "state/events", "state/leases", "state/metrics",
]
for d in required_dirs:
    p = factory_root / d
    check(p.exists(), f"/{d}", f"/{d} missing — run: mkdir -p {p}")

required_files = [
    "agents/foreman_agent.py", "agents/writer_agent.py",
    "agents/visual_agent.py",  "agents/voice_agent.py",
    "agents/monitor_agent.py",
    "core/config.py", "core/job_store.py", "core/lease_manager.py",
    "core/agent_base.py", "core/event_logger.py", "core/resource_guard.py",
    "dashboard/inspector.html",
    "schemas/job.schema.json", "schemas/job_templates.json",
    "factoryctl.py",
]
for f in required_files:
    p = factory_root / f
    check(p.exists(), f"/{f}", f"/{f} missing")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Python imports
# ─────────────────────────────────────────────────────────────────────────────
header("3. Python module imports")

sys.path.insert(0, str(factory_root))

modules = [
    ("core.config",        "PHASE_SEQUENCE"),
    ("core.job_store",     "JobStore"),
    ("core.lease_manager", "LeaseManager"),
    ("core.event_logger",  "EventLogger"),
    ("core.agent_base",    "AgentBase"),
    ("core.resource_guard","ResourceGuard"),
]
for mod_name, attr in modules:
    try:
        mod = __import__(mod_name, fromlist=[attr])
        getattr(mod, attr)
        ok(f"import {mod_name}")
        PASS += 1
    except Exception as e:
        fail(f"import {mod_name}: {e}")
        FAIL += 1

try:
    import psutil
    ok(f"import psutil ({psutil.__version__})")
    PASS += 1
except ImportError:
    fail("psutil not installed — run: pip install psutil")
    FAIL += 1

try:
    import requests
    ok(f"import requests ({requests.__version__})")
    PASS += 1
except ImportError:
    warn("requests not installed — visual_agent needs it: pip install requests")
    WARN += 1

if args.quick:
    print(f"\n{BOLD}Quick check complete.{RESET}")
    print(f"  {GREEN}passed: {PASS}{RESET}  {AMBER}warnings: {WARN}{RESET}  {RED}failed: {FAIL}{RESET}")
    sys.exit(1 if FAIL > 0 else 0)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Job lifecycle (dry run)
# ─────────────────────────────────────────────────────────────────────────────
header("4. Job lifecycle (dry run)")

tmp_root = Path(tempfile.mkdtemp(prefix="factory_preflight_"))
try:
    # Patch config to use temp dir
    import core.config as cfg
    _orig_vals = {k: getattr(cfg, k) for k in [
        "ROOT","JOBS_ROOT","INBOX_DIR","ACTIVE_DIR","COMPLETED_DIR","FAILED_DIR",
        "ARTIFACTS_DIR","LOGS_DIR","STATE_DIR","AGENTS_STATE","EVENTS_FILE",
        "METRICS_FILE","LEASES_DIR","DASHBOARD_DIR"
    ]}
    cfg.ROOT          = tmp_root
    cfg.JOBS_ROOT     = tmp_root/"jobs"
    cfg.INBOX_DIR     = tmp_root/"jobs"/"inbox"
    cfg.ACTIVE_DIR    = tmp_root/"jobs"/"active"
    cfg.COMPLETED_DIR = tmp_root/"jobs"/"completed"
    cfg.FAILED_DIR    = tmp_root/"jobs"/"failed"
    cfg.ARTIFACTS_DIR = tmp_root/"artifacts"
    cfg.LOGS_DIR      = tmp_root/"logs"
    cfg.STATE_DIR     = tmp_root/"state"
    cfg.AGENTS_STATE  = tmp_root/"state"/"agents"
    cfg.EVENTS_FILE   = tmp_root/"state"/"events"/"events.jsonl"
    cfg.METRICS_FILE  = tmp_root/"state"/"metrics"/"system.json"
    cfg.LEASES_DIR    = tmp_root/"state"/"leases"
    cfg.DASHBOARD_DIR = tmp_root/"dashboard"
    for mod in list(sys.modules.values()):
        n = getattr(mod, "__name__", "") or ""
        if n.startswith("core.") or n.startswith("agents."):
            for attr in _orig_vals:
                if hasattr(mod, attr): setattr(mod, attr, getattr(cfg, attr))
    cfg.ensure_dirs()

    from core.job_store   import JobStore
    from core.lease_manager import LeaseManager
    from core.event_logger  import EventLogger

    # Create job
    store = JobStore()
    job   = store.create("preflight test topic", priority=5)
    check(job["status"] == "pending", "job created with status=pending", "job creation failed")
    check((cfg.INBOX_DIR / job["job_id"]).exists(), "job directory in inbox", "job dir missing")

    # Promote to active
    store.promote_to_active(job["job_id"])
    check((cfg.ACTIVE_DIR / job["job_id"]).exists(), "job promoted to active", "promote failed")

    # Lease
    lm    = LeaseManager()
    lease = lm.write_lease(job["job_id"], "writer_agent", "writing", "medium")
    check(lm.has_active_lease(job["job_id"]), "lease issued successfully", "lease issue failed")
    ttl   = lease.get("lease_expiration", "")
    check(bool(ttl), f"lease expiration set: {ttl[:19]}", "lease expiration missing")

    # Events
    el = EventLogger()
    el.emit(job["job_id"], "preflight", "start", "writing", "preflight test event")
    events = el.tail(5)
    check(len(events) > 0, "event logged and readable", "event log failed")

    # Phase advance
    store.update_phase(job["job_id"], "writing")
    store.advance_phase(job["job_id"])
    loaded = store.load(job["job_id"])
    check(loaded["phase"] == "voice", f"phase advanced to voice", f"expected voice got {loaded['phase']}")

    # Cancel
    lm.release_lease(job["job_id"], "writer_agent")
    store.cancel_job(job["job_id"], "preflight test cancel")
    cancelled = store.load(job["job_id"])
    check(cancelled["status"] == "cancelled", "job cancelled correctly", "cancel failed")

    # Queue depth
    job2  = store.create("second test job")
    depth = store.queue_depth()
    check(depth["inbox"] >= 1, f"queue depth: inbox={depth['inbox']}", "queue depth failed")

    # Templates
    tmpl_file = factory_root / "schemas" / "job_templates.json"
    templates = json.loads(tmpl_file.read_text())["templates"]
    check(len(templates) >= 3, f"job templates: {list(templates.keys())}", "templates missing")

finally:
    # Restore config
    for k, v in _orig_vals.items():
        setattr(cfg, k, v)
    for mod in list(sys.modules.values()):
        n = getattr(mod, "__name__", "") or ""
        if n.startswith("core.") or n.startswith("agents."):
            for attr in _orig_vals:
                if hasattr(mod, attr): setattr(mod, attr, _orig_vals[attr])
    shutil.rmtree(tmp_root, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Ollama
# ─────────────────────────────────────────────────────────────────────────────
if not args.no_ollama:
    header("5. Ollama (LLM)")
    try:
        import requests as _req
        r = _req.get("http://localhost:11434/api/version", timeout=5)
        check(r.status_code == 200, f"Ollama API responding (v{r.json().get('version','?')})",
              "Ollama not responding — run: ollama serve")

        model = os.environ.get("OLLAMA_MODEL", "mistral")
        r2 = _req.get("http://localhost:11434/api/tags", timeout=5)
        models = [m["name"].split(":")[0] for m in r2.json().get("models", [])]
        check(model in models,
              f"Model '{model}' is available",
              f"Model '{model}' not found — run: ollama pull {model}  (available: {models})",
              warning=True)

        # Quick generation test
        info(f"Testing generation with {model} (may take 30s)...")
        r3 = _req.post("http://localhost:11434/api/generate",
                       json={"model": model, "prompt": "Say 'OK' and nothing else.", "stream": False},
                       timeout=120)
        check(r3.status_code == 200 and len(r3.json().get("response","")) > 0,
              f"Generation works (response: {r3.json().get('response','').strip()[:40]})",
              "Generation failed")
    except Exception as e:
        warn(f"Ollama check failed: {e}")
        WARN += 1
else:
    warn("Ollama check skipped (--no-ollama)")
    WARN += 1


# ─────────────────────────────────────────────────────────────────────────────
# 6. Piper TTS
# ─────────────────────────────────────────────────────────────────────────────
if not args.no_piper:
    header("6. Piper TTS")
    piper_bin  = os.environ.get("PIPER_BIN", "piper")
    model_dir  = os.environ.get("PIPER_MODEL_DIR", "/usr/share/piper/voices")
    voice      = os.environ.get("PIPER_VOICE", "en_US-lessac-medium.onnx")
    model_path = Path(model_dir) / voice

    check(shutil.which(piper_bin) is not None,
          f"piper binary found: {shutil.which(piper_bin)}",
          f"piper not found at '{piper_bin}' — check PIPER_BIN")

    check(model_path.exists(),
          f"Voice model: {model_path.name} ({model_path.stat().st_size // 1024 // 1024}MB)",
          f"Voice model not found: {model_path}",
          warning=True)

    if model_path.exists() and shutil.which(piper_bin):
        info("Testing speech synthesis...")
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                out = tmp.name
            result = subprocess.run(
                [piper_bin, "--model", str(model_path), "--output_file", out],
                input="Preflight check. The factory is ready.",
                capture_output=True, text=True, timeout=30,
            )
            wav_exists = Path(out).exists() and Path(out).stat().st_size > 1000
            check(wav_exists, f"Speech synthesis works ({Path(out).stat().st_size // 1024}KB WAV)",
                  f"Piper synthesis failed: {result.stderr[:100]}")
            Path(out).unlink(missing_ok=True)
        except Exception as e:
            warn(f"Piper test failed: {e}")
            WARN += 1
else:
    warn("Piper check skipped (--no-piper)")
    WARN += 1


# ─────────────────────────────────────────────────────────────────────────────
# 7. ComfyUI
# ─────────────────────────────────────────────────────────────────────────────
if not args.no_comfy:
    header("7. ComfyUI (image generation)")
    try:
        import requests as _req
        r = _req.get("http://localhost:8188/system_stats", timeout=5)
        check(r.status_code == 200,
              f"ComfyUI API responding (v{r.json().get('system',{}).get('comfyui_version','?')})",
              "ComfyUI not responding — start it first or use --no-comfy")

        checkpoint = os.environ.get("COMFYUI_CHECKPOINT", "dreamshaper.safetensors")
        r2 = _req.get("http://localhost:8188/object_info/CheckpointLoaderSimple", timeout=5)
        ckpts = r2.json().get("CheckpointLoaderSimple",{}).get(
            "input",{}).get("required",{}).get("ckpt_name",[[]])[0]
        check(checkpoint in ckpts,
              f"Checkpoint '{checkpoint}' is available",
              f"Checkpoint '{checkpoint}' not found. Available: {ckpts}",
              warning=True)

        # Quick 1-step generation test
        info("Testing image generation (1 step, 64x64 — should take <30s)...")
        workflow = {
            "3": {"class_type": "KSampler", "inputs": {
                "seed": 1, "steps": 1, "cfg": 1.0,
                "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0,
                "model": ["4",0], "positive": ["6",0],
                "negative": ["7",0], "latent_image": ["5",0]}},
            "4": {"class_type":"CheckpointLoaderSimple","inputs":{"ckpt_name":checkpoint}},
            "5": {"class_type":"EmptyLatentImage","inputs":{"width":64,"height":64,"batch_size":1}},
            "6": {"class_type":"CLIPTextEncode","inputs":{"text":"test","clip":["4",1]}},
            "7": {"class_type":"CLIPTextEncode","inputs":{"text":"bad","clip":["4",1]}},
            "8": {"class_type":"VAEDecode","inputs":{"samples":["3",0],"vae":["4",2]}},
            "9": {"class_type":"SaveImage","inputs":{"filename_prefix":"preflight_test","images":["8",0]}},
        }
        r3 = _req.post("http://localhost:8188/prompt", json={"prompt": workflow}, timeout=10)
        pid = r3.json().get("prompt_id")
        check(bool(pid), f"Prompt queued: {pid}", "Failed to queue prompt")

        if pid:
            deadline = time.time() + 120
            done = False
            while time.time() < deadline:
                time.sleep(3)
                hist = _req.get(f"http://localhost:8188/history/{pid}", timeout=5).json()
                if pid in hist:
                    imgs = hist[pid].get("outputs",{}).get("9",{}).get("images",[])
                    check(len(imgs) > 0, "Image generation works", "No image in output")
                    done = True
                    break
            if not done:
                warn("ComfyUI generation timed out in preflight (may still work for full jobs)")
                WARN += 1
    except Exception as e:
        warn(f"ComfyUI check failed: {e}")
        WARN += 1
else:
    warn("ComfyUI check skipped (--no-comfy)")
    WARN += 1


# ─────────────────────────────────────────────────────────────────────────────
# 8. Dashboard API
# ─────────────────────────────────────────────────────────────────────────────
header("8. Dashboard API")
try:
    import requests as _req
    port = int(os.environ.get("FACTORY_MONITOR_PORT", 7000))
    r = _req.get(f"http://localhost:{port}/health", timeout=5)
    check(r.status_code == 200, f"Monitor API responding on :{port}", 
          f"Monitor not running on :{port} — start monitor_agent.py", warning=True)

    if r.status_code == 200:
        data = r.json()
        check("agent_health" in data, "Health response has agent_health", "agent_health missing")
        check("queue_depth"  in data, "Health response has queue_depth",  "queue_depth missing")
        check("system"       in data, "Health response has system metrics","system missing")
        
        r2 = _req.get(f"http://localhost:{port}/", timeout=5)
        check(r2.status_code == 200 and b"Factory Inspector" in r2.content,
              "Dashboard HTML served at /", "Dashboard not served correctly")
except Exception as e:
    warn(f"Dashboard check failed: {e} — is monitor_agent.py running?")
    WARN += 1


# ─────────────────────────────────────────────────────────────────────────────
# 9. Disk space
# ─────────────────────────────────────────────────────────────────────────────
header("9. Resources")
try:
    import psutil
    disk  = psutil.disk_usage(str(factory_root))
    mem   = psutil.virtual_memory()
    free_gb  = disk.free  / 1024**3
    free_ram = mem.available / 1024**3

    check(free_gb  > 10, f"Disk free: {free_gb:.1f}GB",
          f"Low disk: only {free_gb:.1f}GB free (need 10GB+ for models)", warning=True)
    check(free_ram > 4,  f"RAM available: {free_ram:.1f}GB",
          f"Low RAM: {free_ram:.1f}GB available (need 4.5GB for Mistral)", warning=True)
    ok(f"Total RAM: {mem.total/1024**3:.1f}GB")
    PASS += 1
except Exception as e:
    warn(f"Resource check failed: {e}")
    WARN += 1


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"{BOLD}Pre-flight summary{RESET}")
print(f"  {GREEN}✓ passed:   {PASS}{RESET}")
print(f"  {AMBER}⚠ warnings: {WARN}{RESET}")
print(f"  {RED}✗ failed:   {FAIL}{RESET}")
print()

if FAIL == 0 and WARN == 0:
    print(f"{GREEN}{BOLD}All checks passed. Factory is ready to run.{RESET}")
    print(f"\nSubmit your first job:")
    print(f"  cd {factory_root}")
    print(f"  ./factoryctl new-job \"Your topic\" --template educational_video")
elif FAIL == 0:
    print(f"{AMBER}{BOLD}Ready with warnings. Factory should work but review the warnings above.{RESET}")
    print(f"\nSubmit your first job:")
    print(f"  cd {factory_root}")
    print(f"  ./factoryctl new-job \"Your topic\" --template educational_video")
else:
    print(f"{RED}{BOLD}Failures detected. Fix the issues above before submitting jobs.{RESET}")

print()
sys.exit(1 if FAIL > 0 else 0)
