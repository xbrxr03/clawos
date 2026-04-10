# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Generate pre-patched openclaw.json for offline Ollama use.
Compatible with OpenClaw 2026.4.5+ schema (stripped deprecated keys).
"""
import json
import subprocess
from pathlib import Path

OPENCLAW_DIR  = Path.home() / ".openclaw"
CONFIG_PATH   = OPENCLAW_DIR / "openclaw.json"
AUTH_FIX_PATH = OPENCLAW_DIR / "agents" / "main" / "agent" / "auth-profiles.json"

# qwen3 excluded — Ollama bug #14745 (prints tool calls instead of executing)
GOOD_MODELS = {
    "qwen2.5:1.5b":    {"ctx": 4096,  "tier": "basic"},
    "qwen2.5:3b":      {"ctx": 8192,  "tier": "standard"},
    "qwen2.5:7b":      {"ctx": 8192,  "tier": "full"},
    "kimi-k2.5:cloud": {"ctx": 32768, "tier": "openclaw"},
}

CTX_CAP = 8192  # hard cap for local models — prevents 262k OOM


def gen_config(model: str = "qwen2.5:7b", openrouter_key: str = "") -> dict:
    """
    Pre-patched openclaw.json for OpenClaw 2026.4.5+.
    Removed: maxOutput, inputCostPer1M, outputCostPer1M, capabilities,
             cloud, network, _clawos, skills.web-browser, skills.file-manager
    """
    import os
    key = openrouter_key or os.environ.get("OPENROUTER_API_KEY", "") or "__OPENROUTER_API_KEY__"

    m   = GOOD_MODELS.get(model, {"ctx": CTX_CAP})
    ctx = min(m["ctx"], CTX_CAP) if "cloud" not in model else m["ctx"]

    providers = {
        "ollama": {
            "baseUrl": "http://127.0.0.1:11434/v1",
            "apiKey":  "ollama-local",
            "api":     "openai-completions",
            "models":  [{
                "id":            model,
                "name":          model,
                "contextWindow": ctx,
            }]
        }
    }

    # Always include openrouter so placer.py can write the key later
    providers["openrouter"] = {
        "baseUrl": "https://openrouter.ai/api/v1",
        "apiKey":  key,
        "api":     "openai-completions",
        "models": [
            {"id": "moonshotai/kimi-k2",                 "name": "Kimi k2.5",     "contextWindow": 131072},
            {"id": "openai/gpt-4o",                      "name": "GPT-4o",        "contextWindow": 128000},
            {"id": "anthropic/claude-sonnet-4-20250514", "name": "Claude Sonnet", "contextWindow": 200000},
        ]
    }

    has_cloud = bool(openrouter_key or (os.environ.get("OPENROUTER_API_KEY", "") not in ("", "__OPENROUTER_API_KEY__")))
    default_model = "openrouter/moonshotai/kimi-k2" if has_cloud else f"ollama/{model}"

    return {
        "gateway": {"mode": "local", "port": 18789},
        "models":  {"providers": providers},
        "agents": {
            "defaults": {
                "model": {"primary": default_model},
                "memorySearch": {"enabled": False},
            }
        },
        "cloud":   {"enabled": has_cloud},
        "network": {"mode": "online" if has_cloud else "offline"},
        "skills": {},
    }


def apply_auth_fix() -> Path:
    """Fix Linux issue #22055 — 'No API key found for provider ollama'."""
    AUTH_FIX_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUTH_FIX_PATH.write_text(json.dumps({
        "ollama:local": {"type": "token", "provider": "ollama", "token": "ollama-local"},
        "lastGood":     {"ollama": "ollama:local"},
    }, indent=2))
    return AUTH_FIX_PATH


def write_config(model: str = "qwen2.5:7b", openrouter_key: str = "") -> Path:
    OPENCLAW_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(gen_config(model, openrouter_key=openrouter_key), indent=2))
    return CONFIG_PATH


def detect_best_model() -> str:
    """Pick best available Ollama model that supports OpenClaw tool calling."""
    try:
        r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
        output = r.stdout.lower()
        for model in ["qwen2.5:7b", "qwen2.5:3b", "qwen2.5:1.5b"]:
            if model.split(":")[0] in output:
                return model
    except Exception:
        pass
    return "qwen2.5:7b"
