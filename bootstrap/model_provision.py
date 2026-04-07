# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Pull and verify a model via Ollama.
Shows real-time download progress in terminal.
"""
import subprocess
import sys
import shutil
import time
import re
from clawos_core.service_manager import service_hint


def ollama_running() -> bool:
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
        return True
    except Exception:
        return False


def model_present(model: str) -> bool:
    try:
        r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
        return model.split(":")[0] in r.stdout
    except Exception:
        return False


def _progress_snapshot(model: str, status: str, percent: int | None = None, eta_seconds: int | None = None) -> dict:
    payload = {"model": model, "status": status}
    if percent is not None:
        payload["percent"] = max(0, min(percent, 100))
    if eta_seconds is not None:
        payload["eta_seconds"] = max(0, eta_seconds)
    return payload


def _parse_percent(line: str) -> int | None:
    match = re.search(r"(\d{1,3})%", line)
    if not match:
        return None
    return max(0, min(int(match.group(1)), 100))


def pull(model: str, show_progress: bool = True, progress_callback=None) -> bool:
    """Pull model. Returns True on success."""
    if not shutil.which("ollama"):
        print("  [ERROR] ollama not found. Install: curl -fsSL https://ollama.com/install.sh | sh")
        if progress_callback:
            progress_callback(_progress_snapshot(model, "ollama not found", 0))
        return False

    if model_present(model):
        print(f"  [OK] {model} already present")
        if progress_callback:
            progress_callback(_progress_snapshot(model, "already present", 100, 0))
        return True

    print(f"  Pulling {model} ...", flush=True)
    if progress_callback:
        progress_callback(_progress_snapshot(model, "starting pull", 0))

    try:
        started = time.monotonic()
        proc = subprocess.Popen(
            ["ollama", "pull", model],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        for line in proc.stdout:
            line = line.strip()
            if line and show_progress:
                # Show last 80 chars on same line
                print(f"\r  {line[-78:]:<78}", end="", flush=True)
            if line and progress_callback:
                percent = _parse_percent(line)
                eta_seconds = None
                if percent and percent < 100:
                    elapsed = max(time.monotonic() - started, 0.1)
                    eta_seconds = int((elapsed / percent) * (100 - percent))
                progress_callback(_progress_snapshot(model, line, percent, eta_seconds))
        proc.wait()
        print()
        if proc.returncode == 0:
            print(f"  [OK] {model} ready")
            if progress_callback:
                progress_callback(_progress_snapshot(model, "ready", 100, 0))
            return True
        else:
            print(f"  [ERROR] pull exited {proc.returncode}")
            if progress_callback:
                progress_callback(_progress_snapshot(model, f"pull exited {proc.returncode}", 0))
            return False
    except Exception as e:
        print(f"  [ERROR] {e}")
        if progress_callback:
            progress_callback(_progress_snapshot(model, str(e), 0))
        return False


def ensure_model(model: str, show_progress: bool = True, progress_callback=None) -> bool:
    """Start Ollama if needed, then ensure model is available."""
    if not ollama_running():
        print("  Starting Ollama ...", end="", flush=True)
        if progress_callback:
            progress_callback(_progress_snapshot(model, "starting ollama", 0))
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        import time
        for _ in range(10):
            time.sleep(1)
            if ollama_running():
                print(" ready")
                break
        else:
            print(f" failed to start ({service_hint('start', 'ollama.service')})")
            if progress_callback:
                progress_callback(_progress_snapshot(model, "failed to start ollama", 0))
            return False

    return pull(model, show_progress=show_progress, progress_callback=progress_callback)
