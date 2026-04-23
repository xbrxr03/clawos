# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS OpenClaw installer.
Supports Linux and macOS for Node.js and OpenClaw bootstrap.
"""
import json
import logging
import os
import shutil
import subprocess
from pathlib import Path

from clawos_core.platform import homebrew_prefix, is_macos, ram_snapshot_gb
from openclaw_integration.compression import patch_openclaw_config_for_headroom, setup_compression, start_headroom
from openclaw_integration.config_gen import OPENCLAW_DIR, apply_auth_fix, detect_best_model, write_config

log = logging.getLogger("openclaw")

MIN_RAM_GB = 14
NODE_MIN_VER = 22


def _ram_gb() -> float:
    return ram_snapshot_gb().get("total_gb", 0.0)


def _node_version() -> int:
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
        return int(result.stdout.strip().lstrip("v").split(".")[0])
    except Exception:
        return 0


def _run(cmd, **kwargs):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300, **kwargs)


def _brew_bin() -> str | None:
    brew = shutil.which("brew")
    if brew:
        return brew
    candidate = homebrew_prefix() / "bin" / "brew"
    if candidate.exists():
        return str(candidate)
    return None


def _ensure_homebrew() -> str:
    brew = _brew_bin()
    if brew:
        return brew
    print("  Homebrew is required on macOS. Installing Homebrew ...")
    subprocess.run(
        [
            "/bin/bash",
            "-lc",
            'NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"',
        ],
        check=True,
    )
    brew = _brew_bin()
    if not brew:
        raise RuntimeError("Homebrew install completed but brew is not on PATH")
    return brew


def system_check() -> dict:
    node_ver = _node_version()
    ram = _ram_gb()
    return {
        "node": shutil.which("node") is not None,
        "node_version": node_ver,
        "node_ok": node_ver >= NODE_MIN_VER,
        "npm": shutil.which("npm") is not None,
        "openclaw": shutil.which("openclaw") is not None,
        "ollama": shutil.which("ollama") is not None,
        "ram_gb": ram,
        "ram_ok": ram >= MIN_RAM_GB,
    }


def ensure_node() -> bool:
    ver = _node_version()
    if ver >= NODE_MIN_VER:
        print(f"  ✓  Node.js v{ver}")
        return True

    print(f"  Node.js {NODE_MIN_VER}+ required (found v{ver or 'none'})")
    print("  Installing Node.js ...")
    try:
        if is_macos():
            brew = _ensure_homebrew()
            subprocess.run([brew, "install", "node"], check=True)
        else:
            subprocess.run(["sudo", "apt-get", "update"], check=True)
            subprocess.run(["sudo", "apt-get", "install", "-y", "nodejs", "npm"], check=True)
        ver = _node_version()
        if ver >= NODE_MIN_VER:
            print(f"  ✓  Node.js v{ver} installed")
            return True
        print(f"  ✗  Install failed (got v{ver})")
        return False
    except Exception as exc:
        print(f"  ✗  {exc}")
        print(
            "  Manual: brew install node"
            if is_macos()
            else "  Manual: install Node.js 22+ from your distro or the official NodeSource package instructions"
        )
        return False


def install_openclaw(force: bool = False) -> bool:
    local_prefix = Path.home() / ".local"
    local_bin = local_prefix / "bin"
    os.environ["PATH"] = str(local_bin) + ":" + os.environ.get("PATH", "")

    if shutil.which("openclaw") and not force:
        try:
            result = _run(["openclaw", "--version"])
            print(f"  ✓  OpenClaw {result.stdout.strip()}")
        except Exception:
            print("  ✓  OpenClaw already installed")
        return True

    try:
        subprocess.run(
            ["npm", "config", "set", "prefix", str(local_prefix)],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        pass

    print("  Installing OpenClaw via npm (~2 min) ...")
    result = subprocess.run(["npm", "install", "-g", "openclaw@latest"], timeout=300)
    if result.returncode != 0:
        print("  ✗  npm install failed")
        return False

    if shutil.which("openclaw"):
        print("  ✓  OpenClaw installed")
        return True

    try:
        npm_bin = _run(["npm", "bin", "-g"]).stdout.strip()
        if npm_bin and (Path(npm_bin) / "openclaw").exists():
            os.environ["PATH"] = npm_bin + ":" + os.environ.get("PATH", "")
            shell_rc = Path.home() / (".zprofile" if is_macos() else ".bashrc")
            existing = shell_rc.read_text(encoding="utf-8", errors="replace") if shell_rc.exists() else ""
            if npm_bin not in existing:
                with open(shell_rc, "a", encoding="utf-8") as handle:
                    handle.write(f'\nexport PATH="{npm_bin}:$PATH"\n')
            print(f"  ✓  Installed at {npm_bin}")
            return True
    except Exception:
        pass

    print("  ✗  OpenClaw not in PATH — reopen terminal and retry")
    return False


def configure_offline(model: str = None) -> dict:
    model = model or detect_best_model()
    config_path = write_config(model)
    auth_path = apply_auth_fix()
    print(f"  ✓  Config:   {config_path}")
    print(f"  ✓  Auth fix: {auth_path}")
    print(f"  ✓  Model:    {model} (offline, no API keys)")
    return {"config": str(config_path), "auth_fix": str(auth_path), "model": model}


def ensure_model(model: str) -> bool:
    try:
        listing = _run(["ollama", "list"])
        if model.split(":")[0] in listing.stdout:
            print(f"  ✓  {model} already present")
            return True
    except Exception:
        pass

    print(f"  Pulling {model} ...")
    process = subprocess.Popen(
        ["ollama", "pull", model],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    for line in process.stdout:
        line = line.strip()
        if line:
            print(f"\r  {line[-74:]:<74}", end="", flush=True)
    process.wait()
    print()
    if process.returncode == 0:
        print(f"  ✓  {model} ready")
        return True
    print("  ✗  Pull failed")
    return False


def start_gateway() -> subprocess.Popen:
    try:
        from openclaw_integration.compression import headroom_installed, headroom_running

        if headroom_installed() and not headroom_running():
            if start_headroom():
                patch_openclaw_config_for_headroom()
    except Exception:
        pass
    return subprocess.Popen(["openclaw", "gateway", "start"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def stop_gateway():
    subprocess.run(["openclaw", "gateway", "stop"], capture_output=True, timeout=10)


def restart_gateway():
    subprocess.run(["openclaw", "gateway", "restart"], capture_output=True, timeout=15)


def gateway_status() -> str:
    try:
        return _run(["openclaw", "status"]).stdout.strip()[:120]
    except Exception as exc:
        return f"error: {exc}"


def add_whatsapp_allowlist(phone: str):
    config_path = OPENCLAW_DIR / "openclaw.json"
    if not config_path.exists():
        return
    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
        cfg.setdefault("channels", {}).setdefault("whatsapp", {})
        cfg["channels"]["whatsapp"]["dmPolicy"] = "allowlist"
        cfg["channels"]["whatsapp"]["allowFrom"] = [phone]
        config_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        print(f"  ✓  WhatsApp allowlist: {phone}")
    except Exception as exc:
        log.warning(f"Allowlist update failed: {exc}")


def install(model: str = None, force: bool = False, skip_whatsapp: bool = False) -> dict:
    """Full install: Node -> OpenClaw -> config -> model -> compression."""
    status = {}
    print()
    print("  —— ClawOS × OpenClaw Installer ——————————————")
    print()

    ram = _ram_gb()
    if ram < MIN_RAM_GB:
        print(f"  ⚠  {ram}GB RAM (recommended {MIN_RAM_GB}GB+)")
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

    status["model_ready"] = ensure_model(model)
    status["compression"] = setup_compression(show_progress=True)

    print()
    print("  —— Done —————————————————————————————————————")
    print()
    print("  Next steps:")
    print("  1. Start gateway:    clawctl openclaw start")
    print("  2. Link WhatsApp:    openclaw channels login whatsapp")
    print("  3. Check status:     clawctl openclaw status")
    print("  4. Open TUI:         openclaw tui")
    print()

    status["success"] = True
    return status
