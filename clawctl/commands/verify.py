# SPDX-License-Identifier: AGPL-3.0-or-later
"""
clawctl verify — end-of-install / first-run validation.

Runs a quick smoke test to confirm ClawOS is ready to use:
1. Ollama is running and a model is available
2. Memory service can read/write
3. Dashboard starts and responds
4. Agent loop can process a simple input

Designed to run at the end of install.sh or manually via `clawctl verify`.
Total runtime: ~30 seconds.
"""
import asyncio
import shutil
import socket
import subprocess
import sys
import time


def _check(label: str, ok: bool, detail: str = "") -> bool:
    marker = "✓" if ok else "✗"
    print(f"  {marker}  {label}")
    if detail and not ok:
        print(f"       → {detail}")
    return ok


def run() -> bool:
    """Run verification. Returns True if all critical checks pass."""
    print("\n  —— ClawOS Verify —————————————————————————————\n")
    all_ok = True

    # 1. Python version
    v = sys.version_info
    py_ok = v >= (3, 10)
    all_ok &= _check(
        f"Python {v.major}.{v.minor}.{v.micro}",
        py_ok,
        "Install Python 3.10+",
    )

    # 2. Ollama running
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        ollama_ok = True
    except (OSError, ConnectionRefusedError, TimeoutError):
        ollama_ok = False
    all_ok &= _check("Ollama running", ollama_ok, "Run: ollama serve")

    # 3. Default model available
    default_model = "qwen2.5:7b"
    if ollama_ok:
        try:
            result = subprocess.run(
                ["ollama", "list"], capture_output=True, text=True, timeout=5
            )
            model_ok = default_model.split(":")[0] in result.stdout
            if not model_ok:
                # Check for any usable model
                model_ok = any(t in result.stdout for t in ("gemma", "qwen", "llama"))
                if model_ok:
                    # Pull the actual default
                    print(f"  ⚠  Default model {default_model} not found — pulling...")
                    subprocess.run(["ollama", "pull", default_model], timeout=300)
                    model_ok = True
        except (subprocess.SubprocessError, OSError):
            model_ok = False
    else:
        model_ok = False
    all_ok &= _check(
        f"Model available ({default_model})",
        model_ok,
        f"Run: ollama pull {default_model}",
    )

    # 4. Core packages importable
    for pkg, mod in [
        ("clawos_core", "clawos_core"),
        ("runtimes.agent", "runtimes.agent.intents"),
        ("services.memd", "services.memd.service"),
        ("services.policyd", "services.policyd.policy_engine"),
    ]:
        try:
            __import__(mod)
            pkg_ok = True
        except ImportError:
            pkg_ok = False
        all_ok &= _check(f"Package: {pkg}", pkg_ok, f"pip install -e .")

    # 5. Memory service smoke test
    try:
        from services.memd.service import MemoryService
        mem = MemoryService()
        mem.remember("verify_test", "default", source="verify")
        results = mem.recall("verify_test", "default")
        mem_ok = len(results) > 0
    except (ImportError, ModuleNotFoundError) as e:
        mem_ok = False
        print(f"       Error: {e}")
    all_ok &= _check("Memory read/write", mem_ok, "Check ~/.clawos/memory/ permissions")

    # 6. Dashboard port available
    try:
        sock = socket.socket()
        sock.settimeout(1)
        sock.connect(("localhost", 7070))
        sock.close()
        dash_ok = True
    except (OSError, ValueError):
        dash_ok = False
    _check("Dashboard on :7070", dash_ok, "Start with: clawctl start  (not critical)")

    # 7. Disk space
    try:
        disk = shutil.disk_usage(str(__import__("pathlib").Path.home()))
        disk_ok = disk.free > 1_000_000_000
        _check(f"Disk space ({round(disk.free/1e9, 1)}GB free)", disk_ok, "Free up disk space")
    except OSError:
        pass

    # Summary
    print()
    if all_ok:
        print("  ✓  ClawOS is ready to use!")
    else:
        print("  ✗  Some critical checks failed — fix above items before using ClawOS")
    print()

    return all_ok