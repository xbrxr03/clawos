# SPDX-License-Identifier: AGPL-3.0-or-later
"""
OpenClaw Gateway HTTP adapter for JARVIS.

This module talks to OpenClaw's OpenResponses-compatible HTTP endpoint and
auto-manages the small config changes JARVIS requires.
"""
from __future__ import annotations

import json
import os
import secrets
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from openclaw_integration.config_gen import CONFIG_PATH, OPENCLAW_DIR

_PORT_OPENCLAW = 18789
from openclaw_integration.launcher import is_installed, is_running, start, status

GATEWAY_TOKEN_PATH = OPENCLAW_DIR / "gateway.token"
DEFAULT_AGENT_ID = "main"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _gateway_dict(config: dict[str, Any]) -> dict[str, Any]:
    gateway = config.setdefault("gateway", {})
    if not isinstance(gateway, dict):
        gateway = {}
        config["gateway"] = gateway
    return gateway


def _http_dict(config: dict[str, Any]) -> dict[str, Any]:
    gateway = _gateway_dict(config)
    http_cfg = gateway.setdefault("http", {})
    if not isinstance(http_cfg, dict):
        http_cfg = {}
        gateway["http"] = http_cfg
    return http_cfg


def _gateway_endpoint_config(config: dict[str, Any]) -> dict[str, Any]:
    http_cfg = _http_dict(config)
    endpoints = http_cfg.setdefault("endpoints", {})
    if not isinstance(endpoints, dict):
        endpoints = {}
        http_cfg["endpoints"] = endpoints
    responses = endpoints.setdefault("responses", {})
    if not isinstance(responses, dict):
        responses = {}
        endpoints["responses"] = responses
    return responses


def _gateway_auth(config: dict[str, Any]) -> dict[str, Any]:
    gateway = _gateway_dict(config)
    auth = gateway.setdefault("auth", {})
    if not isinstance(auth, dict):
        auth = {}
        gateway["auth"] = auth
    return auth


def _generated_token() -> str:
    return secrets.token_urlsafe(24)


def _config_port(config: dict[str, Any]) -> int:
    gateway = _gateway_dict(config)
    try:
        return int(gateway.get("port") or _PORT_OPENCLAW)
    except Exception:
        return _PORT_OPENCLAW


def gateway_url(config: dict[str, Any] | None = None) -> str:
    config = config or _load_json(CONFIG_PATH)
    port = _config_port(config)
    return f"http://127.0.0.1:{port}"


def get_gateway_token(config: dict[str, Any] | None = None) -> str:
    env_token = os.environ.get("OPENCLAW_GATEWAY_TOKEN", "").strip()
    if env_token:
        return env_token

    config = config or _load_json(CONFIG_PATH)
    auth = _gateway_auth(config)
    for key in ("token", "password"):
        value = str(auth.get(key, "")).strip()
        if value:
            return value

    if GATEWAY_TOKEN_PATH.exists():
        try:
            return GATEWAY_TOKEN_PATH.read_text(encoding="utf-8").strip()
        except OSError:
            return ""
    return ""


def ensure_responses_endpoint() -> dict[str, Any]:
    """
    Patch OpenClaw config so the OpenResponses HTTP endpoint is available.
    """
    config = _load_json(CONFIG_PATH)
    changed = False

    gateway = _gateway_dict(config)
    if not gateway.get("port"):
        gateway["port"] = _PORT_OPENCLAW
        changed = True

    responses = _gateway_endpoint_config(config)
    if responses.get("enabled") is not True:
        responses["enabled"] = True
        changed = True

    auth = _gateway_auth(config)
    mode = str(auth.get("mode", "")).strip() or "token"
    if auth.get("mode") != mode:
        auth["mode"] = mode
        changed = True

    token = get_gateway_token(config)
    if mode in {"token", "password"} and not token:
        token = _generated_token()
        auth["token" if mode == "token" else "password"] = token
        changed = True

    if changed:
        _save_json(CONFIG_PATH, config)

    if token:
        try:
            GATEWAY_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
            GATEWAY_TOKEN_PATH.write_text(token, encoding="utf-8")
        except OSError:
            pass

    return {
        "config_path": str(CONFIG_PATH),
        "gateway_url": gateway_url(config),
        "gateway_port": _config_port(config),
        "auth_mode": mode,
        "token_present": bool(token),
        "responses_enabled": bool(responses.get("enabled")),
        "config_changed": changed,
    }


def gateway_health() -> dict[str, Any]:
    config = _load_json(CONFIG_PATH)
    ensure_summary = ensure_responses_endpoint()
    running = is_running()
    launcher_status = status()
    return {
        "installed": bool(launcher_status.get("installed") or is_installed()),
        "running": bool(launcher_status.get("running") or running),
        "gateway_port": int(launcher_status.get("port") or ensure_summary["gateway_port"]),
        "gateway_url": ensure_summary["gateway_url"],
        "responses_enabled": ensure_summary["responses_enabled"],
        "auth_mode": ensure_summary["auth_mode"],
        "token_present": ensure_summary["token_present"],
        "config_path": ensure_summary["config_path"],
        "token_path": str(GATEWAY_TOKEN_PATH),
        "config_present": CONFIG_PATH.exists(),
        "agent_id": DEFAULT_AGENT_ID,
        "raw_config": config,
    }


def ensure_gateway_ready() -> dict[str, Any]:
    info = gateway_health()
    if info["installed"] and not info["running"]:
        start()
        info = gateway_health()
    return info


def _extract_output_text(payload: dict[str, Any]) -> str:
    direct = str(payload.get("output_text", "")).strip()
    if direct:
        return direct

    output = payload.get("output")
    if isinstance(output, list):
        chunks: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("text"), str) and item["text"].strip():
                chunks.append(item["text"].strip())
            for content in item.get("content") or []:
                if not isinstance(content, dict):
                    continue
                text = str(content.get("text") or content.get("value") or "").strip()
                if text:
                    chunks.append(text)
        if chunks:
            return "\n".join(chunks).strip()

    response = payload.get("response")
    if isinstance(response, dict):
        nested = _extract_output_text(response)
        if nested:
            return nested

    text = str(payload.get("text") or payload.get("message") or "").strip()
    return text


def request_response(
    message: str,
    *,
    session_key: str,
    channel: str = "jarvis-ui",
    agent_id: str = DEFAULT_AGENT_ID,
    instructions: str = "",
    previous_response_id: str = "",
) -> dict[str, Any]:
    info = ensure_gateway_ready()
    if not info["installed"]:
        raise RuntimeError("OpenClaw is not installed")
    if not info["running"]:
        raise RuntimeError("OpenClaw gateway is not running")
    if not info["responses_enabled"]:
        raise RuntimeError("OpenClaw responses endpoint is disabled")

    token = get_gateway_token()
    payload: dict[str, Any] = {
        "model": "openclaw",
        "input": message,
        "user": session_key,
    }
    if instructions:
        payload["instructions"] = instructions
    if previous_response_id:
        payload["previous_response_id"] = previous_response_id

    headers = {
        "Content-Type": "application/json",
        "x-openclaw-agent-id": agent_id,
        "x-openclaw-session-key": session_key,
        "x-openclaw-message-channel": channel,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(
        f"{info['gateway_url']}/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenClaw HTTP {exc.code}: {detail[:240]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenClaw gateway request failed: {exc.reason}") from exc

    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenClaw returned invalid JSON") from exc

    text = _extract_output_text(decoded)
    return {
        "text": text,
        "response_id": str(decoded.get("id", "")).strip(),
        "session_key": session_key,
        "channel": channel,
        "raw": decoded,
    }
