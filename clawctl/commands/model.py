# SPDX-License-Identifier: AGPL-3.0-or-later
"""clawctl model — manage Ollama models."""
import subprocess
from clawctl.ui.banner import success, error, info, table


def run_list():
    print()
    try:
        r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            error("Ollama not running — start with: ollama serve")
            return
        lines = r.stdout.strip().splitlines()
        if len(lines) <= 1:
            info("No models installed. Pull one: clawctl model pull gemma3:4b")
            return
        for line in lines:
            print(f"  {line}")
    except FileNotFoundError:
        error("ollama not found — install: curl -fsSL https://ollama.com/install.sh | sh")
    print()


def run_pull(model: str):
    print()
    info(f"Pulling {model} ...")
    from bootstrap.model_provision import pull
    ok = pull(model, show_progress=True)
    if ok:
        success(f"{model} ready")
    else:
        error(f"Failed to pull {model}")
    print()


def run_remove(model: str):
    print()
    r = subprocess.run(["ollama", "rm", model], capture_output=True, text=True)
    if r.returncode == 0:
        success(f"Removed {model}")
    else:
        error(r.stderr.strip() or f"Could not remove {model}")
    print()


def run_set_default(model: str):
    print()
    from clawos_core.constants import CLAWOS_CONFIG, CONFIG_DIR
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        import yaml
        cfg = {}
        if CLAWOS_CONFIG.exists():
            with open(CLAWOS_CONFIG) as f:
                cfg = yaml.safe_load(f) or {}
        cfg.setdefault("model", {})["chat"] = model
        with open(CLAWOS_CONFIG, "w") as f:
            yaml.dump(cfg, f)
    except ImportError:
        existing = CLAWOS_CONFIG.read_text() if CLAWOS_CONFIG.exists() else ""
        CLAWOS_CONFIG.write_text(existing + f"\nmodel:\n  chat: {model}\n")
    success(f"Default model set to {model}")
    info("Restart agentd to apply: clawctl restart agentd")
    print()
