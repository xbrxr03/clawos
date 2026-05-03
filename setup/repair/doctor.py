# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS Doctor — diagnose issues and suggest fixes.
Checks dependencies, service-manager status, and core runtime files.
"""
import shutil
import subprocess
import sys
from pathlib import Path

from clawos_core.platform import is_macos
from clawos_core.service_manager import service_hint, service_manager_name


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
    manager = service_manager_name()
    print("\n  —— ClawOS Doctor ———————————————————————————————\n")

    version = sys.version_info
    results.append(
        _check(
            f"Python {version.major}.{version.minor}.{version.micro}",
            version >= (3, 10),
            "Install Python 3.10+: brew install python@3.11" if is_macos() else "Install Python 3.10+: sudo apt install python3.11",
        )
    )

    for pkg, module_name in [
        ("pyyaml", "yaml"),
        ("aiohttp", "aiohttp"),
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("ollama", "ollama"),
    ]:
        try:
            __import__(module_name)
            ok = True
        except ImportError:
            ok = False
        results.append(_check(f"Python package: {pkg}", ok, f"pip install {pkg} --break-system-packages"))

    for pkg, module_name in [
        ("json_repair", "json_repair"),
        ("chromadb", "chromadb"),
        ("whisper", "whisper"),
    ]:
        try:
            __import__(module_name)
            ok = True
        except ImportError:
            ok = False
        status = "✓" if ok else "○"
        extra = "" if ok else f"  (pip install {pkg} --break-system-packages)"
        print(f"  {status}  Optional: {pkg}{extra}")

    print()

    for binary, install in [
        ("ollama", "curl -fsSL https://ollama.com/install.sh | sh"),
        ("piper", "pip install piper-tts --break-system-packages"),
        ("node", "brew install node" if is_macos() else "curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo bash - && sudo apt install nodejs"),
        ("npm", "(comes with node)"),
        ("arecord", "Linux-only capture helper"),
        ("git", "brew install git" if is_macos() else "sudo apt install git"),
    ]:
        ok = shutil.which(binary) is not None or (binary == "arecord" and is_macos())
        results.append(_check(f"Binary: {binary}", ok, install if not ok else ""))

    print()

    try:
        import urllib.request

        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        ollama_running = True
    except Exception:
        ollama_running = False
    results.append(_check("Ollama running", ollama_running, f"ollama serve  (or: {service_hint('start', 'ollama.service')})"))

    if ollama_running:
        try:
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
            has_model = any(token in result.stdout for token in ("gemma", "qwen", "llama"))
            results.append(_check("At least one model available", has_model, "ollama pull qwen2.5:3b"))

            # Check if DEFAULT_MODEL is actually installed
            from clawos_core.constants import DEFAULT_MODEL
            default_present = DEFAULT_MODEL.split(":")[0] in result.stdout
            results.append(_check(
                f"Default model installed ({DEFAULT_MODEL})",
                default_present,
                f"ollama pull {DEFAULT_MODEL}",
            ))
        except Exception:
            pass

    print()

    from clawos_core.constants import CLAWOS_CONFIG, CLAWOS_DIR, CONFIG_DIR, DEFAULT_WORKSPACE, HARDWARE_JSON, MEMORY_DIR
    from clawos_core.util.paths import soul_path

    for label, path in [
        ("CLAWOS_DIR exists", CLAWOS_DIR),
        ("config/ exists", CONFIG_DIR),
        ("memory/ exists", MEMORY_DIR),
    ]:
        results.append(_check(label, path.exists(), f"mkdir -p {path}"))

    results.append(_check("clawos.yaml exists", CLAWOS_CONFIG.exists(), "python3 -m bootstrap.bootstrap"))
    results.append(_check("hardware.json exists", HARDWARE_JSON.exists(), "python3 -m bootstrap.bootstrap"))
    results.append(_check(f"Workspace '{DEFAULT_WORKSPACE}' seeded", soul_path(DEFAULT_WORKSPACE).exists(), "python3 -m bootstrap.bootstrap"))

    print()

    import socket

    def _port_open(port: int) -> bool:
        try:
            sock = socket.socket()
            sock.settimeout(1)
            sock.connect(("localhost", port))
            sock.close()
            return True
        except Exception:
            return False

    results.append(_check("Dashboard running (:7070)", _port_open(7070),
                          "bash scripts/dev_boot.sh  OR  python3 -m services.dashd.main"))

    # Optional daemons added in v0.1.x — won't block, just inform.
    for label, port, hint in [
        ("desktopd (:7080)", 7080, "python3 -m services.desktopd.main"),
        ("reminderd (:7087)", 7087, "systemctl --user start clawos-reminderd"),
        ("waketrd (:7088)",  7088, "systemctl --user start clawos-waketrd"),
    ]:
        ok = _port_open(port)
        marker = "✓" if ok else "○"
        if ok:
            print(f"  {marker}  {label}")
        else:
            print(f"  {marker}  {label}  (start: {hint})")
        results.append({"label": label, "ok": ok, "fix": hint})

    # Verify the agent tool registry is internally consistent — easy bug to
    # introduce when adding tools, hard to spot without explicit check.
    try:
        from runtimes.agent.tool_schemas import ALL_TOOLS
        from runtimes.agent.tools import NATIVE_TOOLS
        schemas, dispatchers = set(ALL_TOOLS), set(NATIVE_TOOLS)
        diff = schemas.symmetric_difference(dispatchers)
        results.append(_check(
            f"Agent tool registry coherent ({len(schemas)} tools)",
            not diff,
            f"Mismatch: {sorted(diff)}",
        ))
    except Exception as e:
        results.append(_check("Agent tool registry", False, str(e)))

    # Model routing consistency — ensure router.py is the single authority
    try:
        from runtimes.agent.router import pick_model, SMART_MODEL
        from clawos_core.constants import DEFAULT_MODEL
        router_default = pick_model("hello world").model
        consistent = (DEFAULT_MODEL == SMART_MODEL or DEFAULT_MODEL == router_default)
        results.append(_check(
            f"Model defaults consistent (DEFAULT_MODEL={DEFAULT_MODEL}, router smart={SMART_MODEL})",
            consistent,
            f"Set DEFAULT_MODEL in constants.py to match SMART_MODEL ({SMART_MODEL})",
        ))
    except Exception as e:
        results.append(_check("Model routing consistency", False, str(e)))

    # Disk space warning
    import shutil as _shutil
    try:
        disk = _shutil.disk_usage(str(Path.home()))
        results.append(_check(
            f"Disk space ({round(disk.free/1e9, 1)}GB free)",
            disk.free > 1_000_000_000,  # 1GB minimum
            "Free up disk space — models need room to load",
        ))
    except OSError:
        pass

    if manager == "launchd":
        print("  ○  launchd user agents")
        print(f"       start:  {service_hint('start', 'clawos.service')}")
        print(f"       stop:   {service_hint('stop', 'clawos.service')}")
        print(f"       status: {service_hint('status', 'clawos.service')}")

    passed = sum(1 for item in results if item["ok"])
    total = len(results)
    print(f"\n  {'—' * 45}")
    print(f"  {passed}/{total} checks passed", end="")
    if passed == total:
        print("  ✓  all good")
    else:
        print(f"  |  {total - passed} issues found")
    print()
    return results
