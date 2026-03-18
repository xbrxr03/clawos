"""
ClawOS Doctor — diagnose issues and suggest fixes.
Checks every dependency, service, and config file.
"""
import shutil
import subprocess
import sys
from pathlib import Path


def _check(label: str, ok: bool, fix: str = "") -> dict:
    status = "✓" if ok else "✗"
    if not ok and fix:
        print(f"  {status}  {label}")
        print(f"       FIX: {fix}")
    else:
        print(f"  {status}  {label}")
    return {"label": label, "ok": ok, "fix": fix}


def run_all() -> list[dict]:
    results = []
    print("\n  ── ClawOS Doctor ───────────────────────────────\n")

    # Python version
    v = sys.version_info
    results.append(_check(
        f"Python {v.major}.{v.minor}.{v.micro}",
        v >= (3, 10),
        "Install Python 3.10+: sudo apt install python3.11"
    ))

    # Core Python deps
    for pkg, imp in [
        ("pyyaml",     "yaml"),
        ("aiohttp",    "aiohttp"),
        ("fastapi",    "fastapi"),
        ("uvicorn",    "uvicorn"),
        ("ollama",     "ollama"),
    ]:
        try:
            __import__(imp)
            ok = True
        except ImportError:
            ok = False
        results.append(_check(
            f"Python package: {pkg}",
            ok,
            f"pip install {pkg} --break-system-packages"
        ))

    # Optional packages
    for pkg, imp in [
        ("json_repair", "json_repair"),
        ("chromadb",    "chromadb"),
        ("whisper",     "whisper"),
    ]:
        try:
            __import__(imp)
            ok = True
        except ImportError:
            ok = False
        s = "✓" if ok else "○"  # ○ = optional, not fatal
        print(f"  {s}  Optional: {pkg}" + ("" if ok else f"  (pip install {pkg} --break-system-packages)"))

    print()

    # System binaries
    for binary, install in [
        ("ollama",    "curl -fsSL https://ollama.com/install.sh | sh"),
        ("piper",     "pip install piper-tts --break-system-packages"),
        ("node",      "curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo bash - && sudo apt install nodejs"),
        ("npm",       "(comes with node)"),
        ("arecord",   "sudo apt install alsa-utils"),
        ("git",       "sudo apt install git"),
    ]:
        ok = shutil.which(binary) is not None
        results.append(_check(
            f"Binary: {binary}",
            ok,
            install if not ok else ""
        ))

    print()

    # Ollama running + models
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        ollama_running = True
    except Exception:
        ollama_running = False
    results.append(_check(
        "Ollama running",
        ollama_running,
        "ollama serve  (or: systemctl --user start ollama)"
    ))

    if ollama_running:
        try:
            r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
            has_model = "gemma3" in r.stdout or "qwen" in r.stdout or "llama" in r.stdout
            results.append(_check(
                "At least one model available",
                has_model,
                "ollama pull gemma3:4b"
            ))
        except Exception:
            pass

    print()

    # ClawOS dirs
    from clawos_core.constants import CLAWOS_DIR, CONFIG_DIR, MEMORY_DIR
    for label, path in [
        ("CLAWOS_DIR exists",  CLAWOS_DIR),
        ("config/ exists",     CONFIG_DIR),
        ("memory/ exists",     MEMORY_DIR),
    ]:
        results.append(_check(label, path.exists(),
                              f"mkdir -p {path}"))

    # Config files
    from clawos_core.constants import CLAWOS_CONFIG, HARDWARE_JSON
    results.append(_check("clawos.yaml exists", CLAWOS_CONFIG.exists(),
                          "python3 -m bootstrap.bootstrap"))
    results.append(_check("hardware.json exists", HARDWARE_JSON.exists(),
                          "python3 -m bootstrap.bootstrap"))

    # Default workspace
    from clawos_core.constants import DEFAULT_WORKSPACE
    from clawos_core.util.paths import soul_path, pinned_path
    results.append(_check(
        f"Workspace '{DEFAULT_WORKSPACE}' seeded",
        soul_path(DEFAULT_WORKSPACE).exists(),
        "bash scripts/seed_workspace.sh"
    ))

    print()

    # Dashboard port
    try:
        import socket
        s = socket.socket()
        s.settimeout(1)
        s.connect(("localhost", 7070))
        s.close()
        dash_up = True
    except Exception:
        dash_up = False
    results.append(_check(
        "Dashboard running (:7070)",
        dash_up,
        "bash scripts/dev_boot.sh  OR  python3 -m services.dashd.main"
    ))

    # Summary
    passed = sum(1 for r in results if r["ok"])
    total  = len(results)
    print(f"\n  ─────────────────────────────────────────────")
    print(f"  {passed}/{total} checks passed", end="")
    if passed == total:
        print("  ✓  all good")
    else:
        print(f"  |  {total-passed} issues found")
    print()
    return results
