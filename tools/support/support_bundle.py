# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Create a lightweight ClawOS support bundle.
"""
from __future__ import annotations

import json
import platform
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from clawos_core.constants import (
    CLAWOS_CONFIG,
    CONFIG_DIR,
    HARDWARE_JSON,
    LOGS_DIR,
    PRESENCE_STATE_JSON,
    SETUP_STATE_JSON,
    SUPPORT_DIR,
)
from clawos_core.desktop_integration import desktop_posture

REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r'(?im)^(\s*export\s+[A-Z0-9_]*(TOKEN|KEY|SECRET|PASSWORD)[A-Z0-9_]*\s*=\s*).*$'),
        r"\1[REDACTED]",
    ),
    (
        re.compile(r'(?im)^(\s*(Authorization|authorization)\s*[:=]\s*Bearer\s+).*$'),
        r"\1[REDACTED]",
    ),
    (
        re.compile(r'(?im)^(\s*("?(token|api[_-]?key|secret|password|passwd|auth_token)"?\s*[:=]\s*)).*$'),
        r'\1"[REDACTED]"',
    ),
)


def _redact_text(text: str) -> str:
    redacted = text
    for pattern, replacement in REDACTION_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def _write_text_or_raw(archive: zipfile.ZipFile, path: Path, arcname: str):
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        archive.write(path, arcname=arcname)
        return
    if path.name == PRESENCE_STATE_JSON.name:
        try:
            payload = json.loads(text)
        except Exception:
            archive.writestr(arcname, _redact_text(text))
            return
        voice = payload.get("voice_session") or {}
        voice["last_utterance"] = "[REDACTED]"
        voice["last_response"] = "[REDACTED]"
        payload["voice_session"] = voice
        payload["missions"] = [{"id": item.get("id", ""), "status": item.get("status", ""), "trust_lane": item.get("trust_lane", "")} for item in payload.get("missions", [])]
        archive.writestr(arcname, json.dumps(payload, indent=2))
        return
    archive.writestr(arcname, _redact_text(text))


def create_support_bundle() -> Path:
    SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    bundle_path = SUPPORT_DIR / f"clawos-support-{stamp}.zip"

    manifest = {
      "created_at": stamp,
      "platform": platform.platform(),
      "python": platform.python_version(),
      "logs_dir": str(LOGS_DIR),
      "config_dir": str(CONFIG_DIR),
      "desktop": desktop_posture(),
    }

    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))

        for path in [CLAWOS_CONFIG, HARDWARE_JSON, SETUP_STATE_JSON, PRESENCE_STATE_JSON]:
            if path.exists():
                _write_text_or_raw(archive, path, arcname=f"config/{path.name}")

        if LOGS_DIR.exists():
            for log_file in LOGS_DIR.glob("*.log"):
                _write_text_or_raw(archive, log_file, arcname=f"logs/{log_file.name}")
            audit = LOGS_DIR / "audit.jsonl"
            if audit.exists():
                _write_text_or_raw(archive, audit, arcname="logs/audit.jsonl")

    try:
        bundle_path.chmod(0o600)
    except OSError:
        pass

    return bundle_path


if __name__ == "__main__":
    print(create_support_bundle())
