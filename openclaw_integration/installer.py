"""
ClawOS OpenClaw Installer
==========================
Gets OpenClaw running offline with Ollama on Linux.
Handles: Node.js, npm install, offline config, Linux auth fix, model pull.
WhatsApp is handled by openclaw's own: openclaw channels login whatsapp
"""
import json
import logging
import os
import shutil
import subprocess
from pathlib import Path

from openclaw_integration.config_gen import (
    write_config, apply_auth_fix, detect_best_model,
    GOOD_MODELS, OPENCLAW_DIR
)
from openclaw_integration.compression import (
    setup_compression, start_headroom, patch_openclaw_config_for_headroom
)

log = logging.getLogger("openclaw")

MIN_RAM_GB   = 14
NODE_MIN_VER = 22


def _ram_gb() -> float:
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal"):
                    return round(int(line.split()[1]) / 1e6, 1)
    except Exception:
        pass
    return 0.0


def _node_version() -> int:
    try:
        r = subprocess.run(["node", "--version"],
                           capture_output=True, text=True, timeout=5)
        return int(r.stdout.strip().lstrip("v").split(".")[0])
    except Exception:
        return 0


def _run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True,
                          text=True, timeout=300, **kw)


def system_check() -> dict:
    node_ver = _node_version()
    return {
        "node":         shutil.which("node") is not None,
        "node_version": node_ver,
        "node_ok":      node_ver >= NODE_MIN_VER,
        "npm":          shutil.which("npm") is not None,
        "openclaw":     shutil.which("openclaw") is not None,
        "ollama":       shutil.which("ollama") is not None,
        "ram_gb":       _ram_gb(),
        "ram_ok":       _ram_gb() >= MIN_RAM_GB,
    }


def ensure_node() -> bool:
    ver = _node_version()
    if ver >= NODE_MIN_VER:
        print(f"  ✓  Node.js v{ver}")
        return True
    print(f"  Node.js {NODE_MIN_VER}+ required (found v{ver or 'none'})")
    print("  Installing via NodeSource ...")
    try:
        subprocess.run(
            "curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -",
            shell=True, check=True, executable="/bin/bash"
        )
        subprocess.run(["sudo", "apt-get", "install", "-y", "nodejs"], check=True)
        ver = _node_version()
        if ver >= NODE_MIN_VER:
            print(f"  ✓  Node.js v{ver} installed")
            return True
        print(f"  ✗  Install failed (got v{ver})")
        return False
    except Exception as e:
        print(f"  ✗  {e}")
        print("  Manual: curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo bash -")
        print("          sudo apt install nodejs")
        return False


def install_openclaw(force: bool = False) -> bool:
    if shutil.which("openclaw") and not force:
        try:
            r = _run(["openclaw", "--version"])
            print(f"  ✓  OpenClaw {r.stdout.strip()}")
        except Exception:
            print("  ✓  OpenClaw already installed")
        return True
    print("  Installing OpenClaw via npm (~2 min) ...")
    r = subprocess.run(["npm", "install", "-g", "openclaw@latest"],
                       timeout=300)
    if r.returncode != 0:
        print("  ✗  npm install failed")
        return False
    # Fix PATH if needed
    if not shutil.which("openclaw"):
        try:
            r2 = _run(["npm", "bin", "-g"])
            npm_bin = r2.stdout.strip()
            if npm_bin and (Path(npm_bin) / "openclaw").exists():
                os.environ["PATH"] = npm_bin + ":" + os.environ.get("PATH", "")
                bashrc = Path.home() / ".bashrc"
                if npm_bin not in bashrc.read_text():
                    with open(bashrc, "a") as f:
                        f.write(f'\nexport PATH="{npm_bin}:$PATH"\n')
                print(f"  ✓  Installed at {npm_bin}")
                print("  ·  Run: source ~/.bashrc")
                return True
        except Exception:
            pass
        print("  ✗  OpenClaw not in PATH — reopen terminal and retry")
        return False
    print("  ✓  OpenClaw installed")
    return True


def configure_offline(model: str = None) -> dict:
    if model is None:
        model = detect_best_model()
    config_path = write_config(model)
    auth_path   = apply_auth_fix()
    print(f"  ✓  Config:   {config_path}")
    print(f"  ✓  Auth fix: {auth_path}")
    print(f"  ✓  Model:    {model} (offline, no API keys)")
    return {"config": str(config_path), "auth_fix": str(auth_path), "model": model}


def ensure_model(model: str) -> bool:
    try:
        r = _run(["ollama", "list"])
        if model.split(":")[0] in r.stdout:
            print(f"  ✓  {model} already present")
            return True
    except Exception:
        pass
    print(f"  Pulling {model} ...")
    proc = subprocess.Popen(
        ["ollama", "pull", model],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1
    )
    for line in proc.stdout:
        line = line.strip()
        if line:
            print(f"\r  {line[-74:]:<74}", end="", flush=True)
    proc.wait()
    print()
    if proc.returncode == 0:
        print(f"  ✓  {model} ready")
        return True
    print(f"  ✗  Pull failed")
    return False


def start_gateway() -> subprocess.Popen:
    # Also ensure headroom is running when gateway starts
    try:
        from openclaw_integration.compression import (
            headroom_installed, headroom_running,
            start_headroom, patch_openclaw_config_for_headroom
        )
        if headroom_installed() and not headroom_running():
            if start_headroom():
                patch_openclaw_config_for_headroom()
    except Exception:
        pass
    return subprocess.Popen(
        ["openclaw", "gateway", "start"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def stop_gateway():
    subprocess.run(["openclaw", "gateway", "stop"],
                   capture_output=True, timeout=10)


def restart_gateway():
    subprocess.run(["openclaw", "gateway", "restart"],
                   capture_output=True, timeout=15)


def gateway_status() -> str:
    try:
        r = _run(["openclaw", "status"])
        return r.stdout.strip()[:120]
    except Exception as e:
        return f"error: {e}"


def add_whatsapp_allowlist(phone: str):
    """Add user's phone to OpenClaw's WhatsApp allowFrom list."""
    config_path = OPENCLAW_DIR / "openclaw.json"
    if not config_path.exists():
        return
    try:
        cfg = json.loads(config_path.read_text())
        cfg.setdefault("channels", {}).setdefault("whatsapp", {})
        cfg["channels"]["whatsapp"]["dmPolicy"]  = "allowlist"
        cfg["channels"]["whatsapp"]["allowFrom"] = [phone]
        config_path.write_text(json.dumps(cfg, indent=2))
        print(f"  ✓  WhatsApp allowlist: {phone}")
    except Exception as e:
        log.warning(f"Allowlist update failed: {e}")


def install(model: str = None, force: bool = False,
            skip_whatsapp: bool = False) -> dict:
    """Full install: Node → OpenClaw → config → model → optionally WhatsApp."""
    status = {}
    print()
    print("  ── ClawOS × OpenClaw Installer ──────────────")
    print()

    # RAM warning
    ram = _ram_gb()
    if ram < MIN_RAM_GB:
        print(f"  ⚠  {ram}GB RAM (recommended {MIN_RAM_GB}GB+)")
        print(f"     iGPU takes ~8GB on ROG Ally — close Chrome/other apps")
        ans = input("  Continue? [y/N]: ").strip().lower()
        if ans != "y":
            return {"cancelled": True}
        status["ram_warning"] = f"{ram}GB"

    if not ensure_node():
        return {"error": "Node.js install failed"}
    status["node"] = True

    if not install_openclaw(force):
        return {"error": "OpenClaw install failed"}
    status["openclaw"] = True

    cfg = configure_offline(model)
    status.update(cfg)
    model = cfg["model"]

    ok = ensure_model(model)
    status["model_ready"] = ok

    # Install and configure token compression (default on)
    comp = setup_compression(show_progress=True)
    status["compression"] = comp

    print()
    print("  ── Done ──────────────────────────────────────")
    print()
    print("  Next steps:")
    print()
    print("  1. Start gateway:    clawctl openclaw start")
    print("  2. Link WhatsApp:    openclaw channels login whatsapp")
    print("  3. Check status:     clawctl openclaw status")
    print("  4. Open TUI:         openclaw tui")
    print()
    print("  Or run full onboard: openclaw onboard")
    print()

    status["success"] = True
    return status
