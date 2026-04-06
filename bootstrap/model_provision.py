# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Pull and verify a model via Ollama.
Shows real-time download progress in terminal.
"""
import subprocess
import sys
import shutil
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


def pull(model: str, show_progress: bool = True) -> bool:
    """Pull model. Returns True on success."""
    if not shutil.which("ollama"):
        print("  [ERROR] ollama not found. Install: curl -fsSL https://ollama.com/install.sh | sh")
        return False

    if model_present(model):
        print(f"  [OK] {model} already present")
        return True

    print(f"  Pulling {model} ...", flush=True)
    try:
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
        proc.wait()
        print()
        if proc.returncode == 0:
            print(f"  [OK] {model} ready")
            return True
        else:
            print(f"  [ERROR] pull exited {proc.returncode}")
            return False
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False


def ensure_model(model: str) -> bool:
    """Start Ollama if needed, then ensure model is available."""
    if not ollama_running():
        print("  Starting Ollama ...", end="", flush=True)
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
            return False

    return pull(model)
