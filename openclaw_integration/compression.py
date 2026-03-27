"""
ClawOS token compression for OpenClaw + cloud model users.
Installs and manages Headroom (context proxy) and RTK (CLI output compression).

Architecture:
  User → nexus/OpenClaw → Headroom (:8787) → Cloud API (kimi, gpt, etc.)
  Shell commands → RTK → compressed output → OpenClaw context

Both are transparent — OpenClaw and users don't change how they work.
"""
import json
import logging
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

log = logging.getLogger("compression")

HEADROOM_PORT    = 8787
HEADROOM_PID     = Path.home() / ".local" / "share" / "clawos" / "headroom.pid"
HEADROOM_LOG     = Path.home() / "clawos" / "logs" / "headroom.log"
RTK_BIN          = Path.home() / ".local" / "bin" / "rtk"
RTK_INSTALL_URL  = "https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh"
CLAWOS_STATE_DIR = Path.home() / ".local" / "share" / "clawos"


# ── Headroom ──────────────────────────────────────────────────────────────────

def headroom_installed() -> bool:
    try:
        r = subprocess.run(
            ["python3", "-m", "headroom", "--version"],
            capture_output=True, text=True, timeout=5
        )
        return r.returncode == 0
    except Exception:
        return False


def headroom_running() -> bool:
    """Check if headroom proxy is listening on its port."""
    try:
        urllib.request.urlopen(
            f"http://localhost:{HEADROOM_PORT}/health", timeout=2
        )
        return True
    except Exception:
        pass
    try:
        urllib.request.urlopen(
            f"http://localhost:{HEADROOM_PORT}/stats", timeout=2
        )
        return True
    except Exception:
        return False


def install_headroom(show_progress: bool = True) -> bool:
    """pip install headroom-ai[proxy]"""
    if show_progress:
        print("  Installing Headroom (context compression proxy) ...")
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install",
             "headroom-ai[proxy]", "--break-system-packages", "-q"],
            timeout=120
        )
        if r.returncode == 0:
            if show_progress:
                print("  ✓  Headroom installed")
            return True
        if show_progress:
            print("  ✗  Headroom install failed — continuing without it")
        return False
    except Exception as e:
        log.warning(f"Headroom install error: {e}")
        return False


def start_headroom() -> bool:
    """Start headroom proxy as a background process."""
    if headroom_running():
        return True
    if not headroom_installed():
        return False
    CLAWOS_STATE_DIR.mkdir(parents=True, exist_ok=True)
    HEADROOM_LOG.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(HEADROOM_LOG, "a") as logf:
            proc = subprocess.Popen(
                [sys.executable, "-m", "headroom", "proxy",
                 "--port", str(HEADROOM_PORT),
                 "--no-cache",        # simpler, no extra DB
                 "--log-level", "warning"],
                stdout=logf, stderr=logf,
                start_new_session=True,
            )
        HEADROOM_PID.write_text(str(proc.pid))
        import time; time.sleep(1.5)
        if headroom_running():
            log.info(f"Headroom started (pid {proc.pid}) on :{HEADROOM_PORT}")
            return True
        return False
    except Exception as e:
        log.warning(f"Headroom start failed: {e}")
        return False


def stop_headroom():
    if HEADROOM_PID.exists():
        try:
            pid = int(HEADROOM_PID.read_text().strip())
            os.kill(pid, 15)  # SIGTERM
            HEADROOM_PID.unlink()
        except Exception:
            pass


def headroom_stats() -> dict:
    """Fetch compression stats from headroom proxy."""
    try:
        with urllib.request.urlopen(
            f"http://localhost:{HEADROOM_PORT}/stats", timeout=2
        ) as r:
            return json.loads(r.read())
    except Exception:
        return {}


# ── RTK ───────────────────────────────────────────────────────────────────────

def rtk_installed() -> bool:
    """Check RTK binary exists and is the correct one (token killer, not type kit)."""
    if not RTK_BIN.exists() and not shutil.which("rtk"):
        return False
    try:
        r = subprocess.run(
            ["rtk", "gain"],
            capture_output=True, text=True, timeout=5
        )
        # If rtk gain works, it's the right package
        return r.returncode == 0 or "tokens" in r.stdout.lower() or "commands" in r.stdout.lower()
    except Exception:
        return False


def install_rtk(show_progress: bool = True) -> bool:
    """Install RTK from GitHub install script."""
    if rtk_installed():
        if show_progress:
            print("  ✓  RTK already installed")
        return True

    if show_progress:
        print("  Installing RTK (CLI output compression) ...")

    # Try cargo install from git first (avoids crates.io name collision)
    if shutil.which("cargo"):
        try:
            r = subprocess.run(
                ["cargo", "install", "--git",
                 "https://github.com/rtk-ai/rtk", "--locked", "-q"],
                timeout=300, capture_output=True
            )
            if r.returncode == 0 and rtk_installed():
                if show_progress:
                    print("  ✓  RTK installed via cargo")
                return True
        except Exception:
            pass

    # Fallback: curl install script
    try:
        r = subprocess.run(
            "curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk"
            "/refs/heads/master/install.sh | sh",
            shell=True, executable="/bin/bash",
            timeout=120, capture_output=True
        )
        if r.returncode == 0 and rtk_installed():
            if show_progress:
                print("  ✓  RTK installed")
            return True
    except Exception as e:
        log.warning(f"RTK curl install failed: {e}")

    if show_progress:
        print("  ⚠  RTK install failed — shell output will not be compressed")
        print("     Install manually: cargo install --git https://github.com/rtk-ai/rtk")
    return False


def configure_rtk_hook() -> bool:
    """
    Install RTK's PreToolUse hook for OpenClaw.
    This transparently rewrites bash commands to rtk equivalents.
    """
    if not rtk_installed():
        return False
    try:
        r = subprocess.run(
            ["rtk", "init", "-g"],   # -g = global, default = claude/openclaw
            capture_output=True, text=True, timeout=15
        )
        return r.returncode == 0
    except Exception as e:
        log.warning(f"RTK hook setup failed: {e}")
        return False


def rtk_stats() -> dict:
    """Get RTK token savings stats."""
    try:
        r = subprocess.run(
            ["rtk", "gain", "--json"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0 and r.stdout.strip():
            return json.loads(r.stdout)
    except Exception:
        pass
    # Fallback: parse text output
    try:
        r = subprocess.run(
            ["rtk", "gain"],
            capture_output=True, text=True, timeout=5
        )
        return {"raw": r.stdout.strip()[:200]}
    except Exception:
        return {}


# ── OpenClaw config integration ───────────────────────────────────────────────

def patch_openclaw_config_for_headroom() -> bool:
    """
    Point OpenClaw's Ollama provider baseUrl through Headroom proxy.
    Headroom forwards to the real API and compresses context en route.
    Only patches if headroom is running.
    """
    if not headroom_running():
        return False

    from openclaw_integration.config_gen import CONFIG_PATH, OPENCLAW_DIR
    if not CONFIG_PATH.exists():
        return False

    try:
        cfg = json.loads(CONFIG_PATH.read_text())
        provider = cfg.get("models", {}).get("providers", {}).get("ollama", {})
        original = provider.get("baseUrl", "")

        # Already patched
        if str(HEADROOM_PORT) in original:
            return True

        # Store original for restore
        cfg["_headroom_original_baseUrl"] = original
        # Point through headroom
        provider["baseUrl"] = f"http://127.0.0.1:{HEADROOM_PORT}/v1"
        cfg["models"]["providers"]["ollama"] = provider
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
        log.info(f"OpenClaw config patched: {original} → headroom proxy")
        return True
    except Exception as e:
        log.warning(f"Config patch failed: {e}")
        return False


def restore_openclaw_config() -> bool:
    """Remove headroom proxy patch — restore direct API URL."""
    from openclaw_integration.config_gen import CONFIG_PATH
    if not CONFIG_PATH.exists():
        return False
    try:
        cfg = json.loads(CONFIG_PATH.read_text())
        original = cfg.pop("_headroom_original_baseUrl", None)
        if original:
            cfg["models"]["providers"]["ollama"]["baseUrl"] = original
            CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
        return True
    except Exception:
        return False


# ── Full setup ────────────────────────────────────────────────────────────────

def setup_compression(show_progress: bool = True) -> dict:
    """
    Install and configure both RTK and Headroom.
    Called automatically during clawctl openclaw install.
    """
    status = {"headroom": False, "rtk": False, "headroom_running": False}

    if show_progress:
        print()
        print("  ── Token Compression Setup ──────────────────")
        print("  (reduces cloud API token usage by 60-90%)")
        print()

    # Headroom
    if not headroom_installed():
        status["headroom"] = install_headroom(show_progress)
    else:
        status["headroom"] = True
        if show_progress:
            print("  ✓  Headroom already installed")

    if status["headroom"]:
        status["headroom_running"] = start_headroom()
        if status["headroom_running"]:
            patch_openclaw_config_for_headroom()
            if show_progress:
                print(f"  ✓  Headroom proxy running on :{HEADROOM_PORT}")
        else:
            if show_progress:
                print(f"  ⚠  Headroom installed but failed to start — will retry on next openclaw start")

    # RTK
    status["rtk"] = install_rtk(show_progress)
    if status["rtk"]:
        hook_ok = configure_rtk_hook()
        status["rtk_hook"] = hook_ok
        if hook_ok and show_progress:
            print("  ✓  RTK hook configured (bash commands auto-compressed)")
        elif not hook_ok and show_progress:
            print("  ⚠  RTK installed but hook setup failed")
            print("     Fix: rtk init -g")

    if show_progress:
        print()
        if status["headroom"] and status["rtk"]:
            print("  ✓  Compression stack ready")
            print("     Headroom: context compression (~34% savings)")
            print("     RTK:      CLI output compression (60-90% savings)")
        elif status["headroom"] or status["rtk"]:
            print("  ⚠  Partial compression (one tool failed — see above)")
        else:
            print("  ⚠  Compression skipped — install manually later:")
            print("     pip install headroom-ai[proxy] --break-system-packages")
            print("     cargo install --git https://github.com/rtk-ai/rtk")
        print()

    return status


def compression_status() -> dict:
    """Get current status of both compression tools."""
    stats = {}

    # Headroom
    h_installed = headroom_installed()
    h_running   = headroom_running()
    stats["headroom"] = {
        "installed": h_installed,
        "running":   h_running,
        "port":      HEADROOM_PORT,
        "stats":     headroom_stats() if h_running else {},
    }

    # RTK
    r_installed = rtk_installed()
    stats["rtk"] = {
        "installed": r_installed,
        "stats":     rtk_stats() if r_installed else {},
    }

    return stats
