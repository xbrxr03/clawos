# SPDX-License-Identifier: AGPL-3.0-or-later
"""
llmd — LiteLLM proxy manager.

Starts a LiteLLM proxy that exposes a single OpenAI-compatible endpoint
(default http://localhost:11500/v1) backed by Ollama (or any configured
provider).  Every agent framework installed via the ClawOS Framework Store
points its api_base at this proxy — so all frameworks share one model
backend without needing individual Ollama credentials.

Per-framework virtual API keys provide usage isolation and per-key budgets.

Architecture adapted from tinyagentos/llm_proxy.py
(AGPL-3.0, https://github.com/jaylfc/tinyagentos).
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import signal
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Optional

log = logging.getLogger("llmd")

# ── Defaults ───────────────────────────────────────────────────────────────────

PROXY_PORT      = int(os.environ.get("LLMD_PORT", 11500))
OLLAMA_HOST     = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
HEALTH_TIMEOUT  = 30        # seconds to wait for proxy to become healthy
HEALTH_INTERVAL = 0.5
KEY_FILE        = Path.home() / ".claw" / "llmd_keys.json"

# Backend type → LiteLLM model prefix
_BACKEND_TYPE_MAP = {
    "ollama":     "ollama_chat",
    "rkllama":    "ollama_chat",   # Rockchip RKLLM also uses Ollama protocol
    "llama-cpp":  "llamacpp",
    "vllm":       "openai",        # vLLM exposes OpenAI-compatible API
    "exo":        "openai",
    "mlx":        "openai",
    "openai":     "openai",
    "anthropic":  "anthropic",
}

# Model name substrings that identify embedding models (skip for chat routing)
_EMBED_KEYWORDS = (
    "embed", "bge-", "gte-", "e5-", "arctic-embed", "nomic-embed",
    "snowflake-arctic", "mxbai-embed",
)


# ── Config generation ──────────────────────────────────────────────────────────

def _is_embed_model(name: str) -> bool:
    n = name.lower()
    return any(k in n for k in _EMBED_KEYWORDS)


def _discover_ollama_models(host: str) -> list[dict]:
    """Return list of {name, size_mb} dicts from Ollama /api/tags."""
    try:
        req = urllib.request.Request(f"{host}/api/tags", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        return data.get("models", [])
    except (json.JSONDecodeError, ValueError) as e:
        log.debug(f"llmd: Ollama model discovery failed: {e}")
        return []


def generate_litellm_config(
    backends: list[dict] | None = None,
    port: int = PROXY_PORT,
    master_key: str | None = None,
) -> str:
    """
    Build a LiteLLM proxy config.yaml as a string.

    backends: list of {url, type} dicts.  Defaults to Ollama on OLLAMA_HOST.
    """
    if backends is None:
        backends = [{"url": OLLAMA_HOST, "type": "ollama"}]

    models: list[dict] = []
    embed_models: list[dict] = []

    for backend in backends:
        url = backend["url"]
        btype = backend.get("type", "ollama")
        prefix = _BACKEND_TYPE_MAP.get(btype, "openai")
        api_base = url

        # Add a generic catch-all routing entry for this backend
        models.append({
            "model_name": "default",
            "litellm_params": {
                "model": f"{prefix}/{api_base}",
                "api_base": api_base,
            },
        })

        # Auto-discover specific models from Ollama backends
        if btype in ("ollama", "rkllama"):
            discovered = _discover_ollama_models(url)
            for m in discovered:
                name = m.get("name", "")
                if not name:
                    continue
                if _is_embed_model(name):
                    embed_models.append({
                        "model_name": name,
                        "litellm_params": {
                            "model": f"ollama/{name}",
                            "api_base": url,
                        },
                    })
                else:
                    models.append({
                        "model_name": name,
                        "litellm_params": {
                            "model": f"{prefix}/{name}",
                            "api_base": url,
                        },
                    })

    config: dict = {
        "model_list": models + embed_models,
        "litellm_settings": {
            "drop_params": True,
            "set_verbose": False,
        },
        "general_settings": {
            "master_key": master_key or _load_or_create_master_key(),
        },
        "router_settings": {
            "routing_strategy": "simple-shuffle",
        },
    }

    # Serialise as YAML manually (avoid pyyaml dependency in minimal installs)
    lines = ["model_list:"]
    for m in config["model_list"]:
        lines.append(f"  - model_name: {m['model_name']}")
        lines.append("    litellm_params:")
        for k, v in m["litellm_params"].items():
            lines.append(f"      {k}: {v}")
    lines.append("litellm_settings:")
    lines.append("  drop_params: true")
    lines.append("  set_verbose: false")
    lines.append("general_settings:")
    lines.append(f"  master_key: {config['general_settings']['master_key']}")
    lines.append("router_settings:")
    lines.append("  routing_strategy: simple-shuffle")
    return "\n".join(lines)


# ── Virtual key management ─────────────────────────────────────────────────────

def _load_keys() -> dict:
    if KEY_FILE.exists():
        try:
            return json.loads(KEY_FILE.read_text())
        except (json.JSONDecodeError, ValueError):
            log.debug(f"failed: {e}")
            pass
            pass
    return {}


def _save_keys(keys: dict) -> None:
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    KEY_FILE.write_text(json.dumps(keys, indent=2))


def _load_or_create_master_key() -> str:
    keys = _load_keys()
    if "master" not in keys:
        keys["master"] = f"sk-clawos-{secrets.token_hex(16)}"
        _save_keys(keys)
    return keys["master"]


def create_virtual_key(framework_name: str) -> str:
    """
    Return a stable virtual API key for a framework.
    Keys persist in ~/.claw/llmd_keys.json.
    """
    keys = _load_keys()
    key_name = f"framework_{framework_name}"
    if key_name not in keys:
        keys[key_name] = f"sk-{framework_name}-{secrets.token_hex(12)}"
        _save_keys(keys)
    return keys[key_name]


def get_virtual_key(framework_name: str) -> Optional[str]:
    return _load_keys().get(f"framework_{framework_name}")


# ── Proxy lifecycle ────────────────────────────────────────────────────────────

class LLMProxy:
    """
    Manages a LiteLLM proxy subprocess.
    Config is written to a temp file; SIGHUP triggers hot-reload.
    """

    def __init__(self, port: int = PROXY_PORT):
        self.port = port
        self._proc: Optional[subprocess.Popen] = None
        self._config_path: Optional[Path] = None

    @property
    def base_url(self) -> str:
        return f"http://localhost:{self.port}/v1"

    def _write_config(self, config_yaml: str) -> Path:
        if self._config_path is None:
            fd, path = tempfile.mkstemp(suffix=".yaml", prefix="clawos_litellm_")
            os.close(fd)
            self._config_path = Path(path)
        self._config_path.write_text(config_yaml)
        return self._config_path

    def start(self, backends: list[dict] | None = None) -> bool:
        """Start the proxy. Returns True if healthy within HEALTH_TIMEOUT."""
        config_yaml = generate_litellm_config(backends=backends, port=self.port)
        cfg_path = self._write_config(config_yaml)
        log.info(f"llmd: starting LiteLLM proxy on :{self.port}")
        try:
            self._proc = subprocess.Popen(
                ["litellm", "--config", str(cfg_path), "--port", str(self.port)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            log.error("llmd: litellm not found — install with: pip install litellm[proxy]")
            return False

        return self._wait_healthy()

    def _wait_healthy(self) -> bool:
        deadline = time.time() + HEALTH_TIMEOUT
        while time.time() < deadline:
            if self._proc and self._proc.poll() is not None:
                log.error("llmd: proxy process exited unexpectedly")
                return False
            try:
                with urllib.request.urlopen(
                    f"http://localhost:{self.port}/health", timeout=2
                ) as r:
                    if r.status == 200:
                        log.info(f"llmd: proxy healthy at {self.base_url}")
                        return True
            except (OSError, ConnectionRefusedError, TimeoutError) as e:
                log.debug(f"suppressed: {e}")
            time.sleep(HEALTH_INTERVAL)
        log.error(f"llmd: proxy did not become healthy within {HEALTH_TIMEOUT}s")
        return False

    def reload(self, backends: list[dict] | None = None) -> None:
        """Hot-reload config via SIGHUP — no restart needed."""
        if self._proc is None or self._proc.poll() is not None:
            log.warning("llmd: reload called but proxy is not running — starting")
            self.start(backends=backends)
            return
        config_yaml = generate_litellm_config(backends=backends, port=self.port)
        self._write_config(config_yaml)
        log.info("llmd: sending SIGHUP for config hot-reload")
        try:
            self._proc.send_signal(signal.SIGHUP)
        except (AttributeError, ProcessLookupError):
            # Windows doesn't support SIGHUP — restart instead
            log.info("llmd: SIGHUP unavailable, restarting proxy")
            self.stop()
            self.start(backends=backends)

    def stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            log.info("llmd: stopping proxy")
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def health(self) -> dict:
        running = self.is_running()
        reachable = False
        if running:
            try:
                with urllib.request.urlopen(
                    f"http://localhost:{self.port}/health", timeout=2
                ) as r:
                    reachable = r.status == 200
            except (OSError, ConnectionRefusedError, TimeoutError):
                log.debug(f"failed: {e}")
                pass
                pass
        return {
            "running": running,
            "reachable": reachable,
            "port": self.port,
            "base_url": self.base_url,
        }


# ── Singleton ──────────────────────────────────────────────────────────────────

_proxy: Optional[LLMProxy] = None


def get_proxy() -> LLMProxy:
    global _proxy
    if _proxy is None:
        from clawos_core.config.loader import get
        port = int(get("llm_proxy.port", PROXY_PORT))
        _proxy = LLMProxy(port=port)
    return _proxy


def ensure_running(backends: list[dict] | None = None) -> bool:
    """Start proxy if not already running. Returns True if healthy."""
    proxy = get_proxy()
    if proxy.is_running():
        return True
    return proxy.start(backends=backends)
