# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Config loader — loads defaults.yaml then merges profile overrides.
Result is a flat dict accessible as ClawOSConfig.
"""
import copy
import os
from pathlib import Path
from typing import Any

try:
    import yaml
    YAML_OK = True
except ImportError:
    YAML_OK = False

CONFIGS_DIR = Path(__file__).parent.parent.parent / "configs"

def _load_yaml(path: Path) -> dict:
    if not YAML_OK:
        return {}
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}

def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for k, v in override.items():
        if k.startswith("_"):
            result[k] = v
            continue
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result

def load(profile: str = None) -> dict:
    """
    Load config. Merges: defaults → profile → env overrides → user config.
    Profile: lowram | balanced | performance | None (auto-detect).
    """
    # Base defaults
    config = _load_yaml(CONFIGS_DIR / "defaults.yaml")

    # Profile override
    if profile is None:
        profile = os.environ.get("CLAWOS_PROFILE", "balanced")
    profile_path = CONFIGS_DIR / f"{profile}.yaml"
    if profile_path.exists():
        config = _deep_merge(config, _load_yaml(profile_path))

    # User config override (~/.clawos/clawos.yaml)
    from clawos_core.constants import CLAWOS_CONFIG
    if CLAWOS_CONFIG.exists():
        config = _deep_merge(config, _load_yaml(CLAWOS_CONFIG))

    # Env overrides
    if os.environ.get("CLAWOS_MODEL"):
        config.setdefault("model", {})["chat"] = os.environ["CLAWOS_MODEL"]
    if os.environ.get("OLLAMA_HOST"):
        config.setdefault("model", {})["host"] = os.environ["OLLAMA_HOST"]

    config["_profile"] = profile
    return config


def get(key: str, default: Any = None, profile: str = None) -> Any:
    """Get a single config value using dot notation: get('model.chat')."""
    config = load(profile)
    parts = key.split(".")
    val = config
    for p in parts:
        if isinstance(val, dict):
            val = val.get(p)
        else:
            return default
    return val if val is not None else default
