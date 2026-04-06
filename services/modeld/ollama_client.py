# SPDX-License-Identifier: AGPL-3.0-or-later
"""Ollama client — chat, pull, list, health."""
import asyncio
import logging
from clawos_core.constants import OLLAMA_HOST, DEFAULT_MODEL

log = logging.getLogger("modeld")

try:
    import ollama as _lib
    OLLAMA_OK = True
except ImportError:
    OLLAMA_OK = False


def _client():
    return _lib.Client(host=OLLAMA_HOST)


def is_running() -> bool:
    try:
        import urllib.request
        urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=2)
        return True
    except Exception:
        return False


def list_models() -> list[dict]:
    if not OLLAMA_OK or not is_running():
        return []
    try:
        return _client().list()["models"]
    except Exception:
        return []


def model_exists(name: str) -> bool:
    return any(m.get("name", "").startswith(name.split(":")[0])
               for m in list_models())


async def pull(model: str = DEFAULT_MODEL) -> bool:
    if not OLLAMA_OK:
        return False
    loop = asyncio.get_event_loop()
    def _sync():
        try:
            _client().pull(model)
            return True
        except Exception as e:
            log.error(f"Pull failed: {e}")
            return False
    return await loop.run_in_executor(None, _sync)


async def chat(messages: list, model: str = DEFAULT_MODEL,
               temperature: float = 0.3, num_ctx: int = 4096) -> str:
    if not OLLAMA_OK:
        raise RuntimeError("ollama not installed")
    loop = asyncio.get_event_loop()
    def _sync():
        r = _client().chat(model=model, messages=messages,
                           options={"temperature": temperature, "num_ctx": num_ctx})
        return r["message"]["content"]
    return await loop.run_in_executor(None, _sync)


async def embed(text: str, model: str = "nomic-embed-text") -> list[float]:
    if not OLLAMA_OK:
        return []
    loop = asyncio.get_event_loop()
    def _sync():
        try:
            r = _client().embeddings(model=model, prompt=text)
            return r["embedding"]
        except Exception:
            return []
    return await loop.run_in_executor(None, _sync)
