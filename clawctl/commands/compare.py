# SPDX-License-Identifier: AGPL-3.0-or-later
"""
compare — Side-by-side model comparison.

Asks the same prompt to multiple models and shows responses
side by side for quality evaluation.
"""
import json
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field


@dataclass
class ModelResponse:
    """A single model's response to a prompt."""
    model: str
    response: str
    tokens_per_sec: float = 0.0
    total_tokens: int = 0
    duration_ms: int = 0
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "response": self.response,
            "tokens_per_sec": round(self.tokens_per_sec, 1),
            "total_tokens": self.total_tokens,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


@dataclass
class CompareSession:
    """A comparison session with results from multiple models."""
    prompt: str
    models: list[str]
    responses: list[ModelResponse] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_dict(self) -> dict:
        return {
            "prompt": self.prompt,
            "models": self.models,
            "responses": [r.to_dict() for r in self.responses],
            "created_at": self.created_at,
        }


def _query_ollama(model: str, prompt: str, host: str = "http://127.0.0.1:11434") -> ModelResponse:
    """Query a single model via Ollama API."""
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": 512},
    }).encode()

    start = time.monotonic()
    try:
        req = urllib.request.Request(
            f"{host}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        elapsed = time.monotonic() - start
        duration_ms = int(elapsed * 1000)

        response_text = data.get("response", "")
        eval_count = data.get("eval_count", 0)
        data.get("eval_count", 0) / max(data.get("eval_duration", 1), 1) * 1e6 if data.get("eval_duration") else 0
        tokens_per_sec = eval_count / elapsed if elapsed > 0 and eval_count > 0 else 0

        return ModelResponse(
            model=model,
            response=response_text,
            tokens_per_sec=tokens_per_sec,
            total_tokens=eval_count,
            duration_ms=duration_ms,
        )
    except (urllib.error.URLError, ConnectionRefusedError, TimeoutError) as exc:
        return ModelResponse(model=model, response="", error=str(exc))
    except Exception as exc:
        return ModelResponse(model=model, response="", error=f"Unexpected: {exc}")


def run_compare(prompt: str, models: list[str], host: str = "http://127.0.0.1:11434") -> CompareSession:
    """Run a comparison across multiple models sequentially."""
    session = CompareSession(prompt=prompt, models=models)
    for model in models:
        resp = _query_ollama(model, prompt, host)
        session.responses.append(resp)
    return session


def run_compare_parallel(prompt: str, models: list[str], host: str = "http://127.0.0.1:11434") -> CompareSession:
    """Run a comparison using threads for parallel execution."""
    import concurrent.futures
    session = CompareSession(prompt=prompt, models=models)
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(models), 4)) as pool:
        futures = {pool.submit(_query_ollama, m, prompt, host): m for m in models}
        for future in concurrent.futures.as_completed(futures):
            session.responses.append(future.result())
    # Sort by model order
    model_order = {m: i for i, m in enumerate(models)}
    session.responses.sort(key=lambda r: model_order.get(r.model, 99))
    return session