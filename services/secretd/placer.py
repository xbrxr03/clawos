"""
Key placement engine.
Given a dict of {key_id: value}, writes each key to all its registered locations.
Handles: env files (.bashrc/.zshrc), JSON files (openclaw.json), secretd store.
Idempotent — safe to run multiple times.
"""

import json
import os
import re
from pathlib import Path
from clawos_core.key_registry import KEY_REGISTRY


def place_all(keys: dict) -> dict:
    """
    Place all provided keys into their registered locations.
    keys: {key_id: value} — only place keys that have non-empty values
    Returns: {key_id: [list of locations written]}
    """
    results = {}
    registry = {k["id"]: k for k in KEY_REGISTRY}

    for key_id, value in keys.items():
        if not value or not str(value).strip():
            continue
        if key_id not in registry:
            continue
        entry = registry[key_id]
        written = []
        for placement in entry["placements"]:
            try:
                loc = _place_one(key_id, str(value).strip(), placement)
                if loc:
                    written.append(loc)
            except Exception:
                pass  # non-fatal
        results[key_id] = written

    return results


def _place_one(key_id: str, value: str, placement: dict) -> str:
    ptype = placement["type"]

    if ptype == "env":
        return _place_env(key_id, value, placement["file"], placement["var"])

    elif ptype == "json_key":
        return _place_json(value, placement["file"], placement["path"])

    elif ptype == "secretd":
        return _place_secretd(placement["key"], value)

    return ""


def _place_env(key_id: str, value: str, filepath: str, var_name: str) -> str:
    path = Path(filepath).expanduser()
    if not path.exists():
        return ""
    content = path.read_text()
    line = f'export {var_name}="{value}"'
    pattern = rf'^export {re.escape(var_name)}=.*$'
    if re.search(pattern, content, re.MULTILINE):
        content = re.sub(pattern, line, content, flags=re.MULTILINE)
    else:
        content = content.rstrip("\n") + f"\n{line}\n"
    path.write_text(content)
    return str(path)


def _place_json(value: str, filepath: str, key_path: list) -> str:
    path = Path(filepath).expanduser()
    if not path.exists():
        return ""
    try:
        data = json.loads(path.read_text())
    except Exception:
        return ""
    obj = data
    for part in key_path[:-1]:
        if part not in obj:
            obj[part] = {}
        obj = obj[part]
    obj[key_path[-1]] = value
    path.write_text(json.dumps(data, indent=2))
    return str(path)


def _place_secretd(secret_key: str, value: str) -> str:
    try:
        from services.secretd.service import get_store
        store = get_store()
        store.set(secret_key, value)
        return f"secretd:{secret_key}"
    except Exception:
        return ""


def get_existing_keys() -> dict:
    """
    Read back any keys already stored in secretd.
    Used to pre-fill the wizard form on re-run.
    """
    result = {}
    try:
        from services.secretd.service import get_store
        store = get_store()
        for entry in KEY_REGISTRY:
            for placement in entry["placements"]:
                if placement["type"] == "secretd":
                    val = store.get(placement["key"])
                    if val:
                        result[entry["id"]] = val
                        break
    except Exception:
        pass
    return result
