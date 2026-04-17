# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Framework registry — loads YAML manifests and tracks installed/running state.

Pattern adapted from tinyagentos/registry.py
(AGPL-3.0, https://github.com/jaylfc/tinyagentos).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional

log = logging.getLogger("frameworkd.registry")

CATALOG_DIR   = Path(__file__).parent / "catalog"
STATE_FILE    = Path.home() / ".claw" / "frameworks_state.json"


class AppState(str, Enum):
    AVAILABLE  = "available"
    INSTALLING = "installing"
    INSTALLED  = "installed"
    RUNNING    = "running"
    ERROR      = "error"
    REMOVING   = "removing"


@dataclass
class FrameworkManifest:
    name:              str
    version:           str       = "0.0.0"
    description:       str       = ""
    category:          str       = "framework"
    install_method:    str       = "pip"    # pip | npm | cargo | git | binary | managed_by
    package:           str       = ""
    entry_point:       str       = ""
    port:              int       = 0
    compatible_tiers:  list[str] = field(default_factory=list)
    incompatible_tiers: list[str] = field(default_factory=list)
    requires_ollama:   bool      = True
    requires_node:     bool      = False
    requires_rust:     bool      = False
    api_base:          str       = "http://localhost:11500/v1"
    managed_by:        str       = ""       # e.g. "openclaw_integration"
    repo:              str       = ""
    links:             dict      = field(default_factory=dict)
    tags:              list[str] = field(default_factory=list)

    @classmethod
    def from_file(cls, path: Path) -> "FrameworkManifest":
        """Parse a YAML manifest. Uses simple line-by-line parser (no pyyaml dep)."""
        raw = _parse_simple_yaml(path.read_text())
        # Normalise list fields
        for list_field in ("compatible_tiers", "incompatible_tiers", "tags"):
            val = raw.get(list_field, [])
            if isinstance(val, str):
                val = [v.strip().strip("[]") for v in val.split(",") if v.strip()]
            raw[list_field] = val
        # Normalise bool fields
        for bool_field in ("requires_ollama", "requires_node", "requires_rust"):
            raw[bool_field] = str(raw.get(bool_field, "true")).lower() in ("true", "yes", "1")
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in raw.items() if k in known})

    def is_compatible(self, profile_id: str) -> tuple[bool, str]:
        """Check if this framework supports the given hardware profile_id.

        Returns (ok, reason). reason is empty string if compatible.
        """
        if self.incompatible_tiers and profile_id in self.incompatible_tiers:
            return False, f"Your hardware ({profile_id}) is in the incompatible list"
        if self.compatible_tiers and profile_id not in self.compatible_tiers:
            return False, f"Your hardware ({profile_id}) is not in the supported list"
        return True, ""


def _parse_simple_yaml(text: str) -> dict:
    """Minimal YAML parser: handles scalar values, inline lists, and nested dicts."""
    result: dict = {}
    current_dict_key: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue

        # Detect nesting (2-space indent)
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        if indent == 0:
            current_dict_key = None

        if ":" not in stripped:
            continue

        key, _, val = stripped.partition(":")
        key = key.strip()
        val = val.strip()

        if not val and indent == 0:
            # This is a dict header like "links:"
            result[key] = {}
            current_dict_key = key
            continue

        if current_dict_key and indent > 0:
            if isinstance(result.get(current_dict_key), dict):
                result[current_dict_key][key] = _coerce(val)
            continue

        result[key] = _coerce(val)

    return result


def _coerce(val: str):
    """Coerce YAML scalar string to Python type."""
    if not val:
        return ""
    # Inline list [a, b, c]
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1]
        return [v.strip().strip("\"'") for v in inner.split(",") if v.strip()]
    # Quoted string
    if (val.startswith('"') and val.endswith('"')) or \
       (val.startswith("'") and val.endswith("'")):
        return val[1:-1]
    # Booleans
    if val.lower() in ("true", "yes"):
        return True
    if val.lower() in ("false", "no"):
        return False
    # Integer
    try:
        return int(val)
    except ValueError:
        pass
    return val


# ── State persistence ──────────────────────────────────────────────────────────

def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ── Registry ───────────────────────────────────────────────────────────────────

class FrameworkRegistry:
    """
    Loads all framework manifests from CATALOG_DIR and tracks their
    installed/running state in a JSON file.
    """

    def __init__(self, catalog_dir: Path = CATALOG_DIR):
        self._catalog_dir = catalog_dir
        self._manifests:  dict[str, FrameworkManifest] = {}
        self._state:      dict[str, str] = {}          # name → AppState value
        self._reload()

    def _reload(self) -> None:
        self._manifests = {}
        for yaml_file in sorted(self._catalog_dir.glob("*.yaml")):
            try:
                manifest = FrameworkManifest.from_file(yaml_file)
                self._manifests[manifest.name] = manifest
            except Exception as e:
                log.warning(f"registry: failed to load {yaml_file.name}: {e}")
        self._state = _load_state()
        log.info(f"registry: {len(self._manifests)} frameworks loaded")

    def all(self) -> list[FrameworkManifest]:
        return list(self._manifests.values())

    def get(self, name: str) -> Optional[FrameworkManifest]:
        return self._manifests.get(name)

    def state(self, name: str) -> AppState:
        return AppState(self._state.get(name, AppState.AVAILABLE))

    def set_state(self, name: str, state: AppState) -> None:
        self._state[name] = state.value
        _save_state(self._state)

    def is_installed(self, name: str) -> bool:
        return self.state(name) in (AppState.INSTALLED, AppState.RUNNING)

    def is_running(self, name: str) -> bool:
        return self.state(name) == AppState.RUNNING

    def list_for_tier(self, profile_id: str) -> list[dict]:
        """Return all frameworks enriched with compatibility + state for a given tier."""
        result = []
        for manifest in self.all():
            ok, reason = manifest.is_compatible(profile_id)
            result.append({
                "name":         manifest.name,
                "version":      manifest.version,
                "description":  manifest.description,
                "category":     manifest.category,
                "state":        self.state(manifest.name).value,
                "compatible":   ok,
                "incompatible_reason": reason,
                "tags":         manifest.tags,
                "links":        manifest.links,
                "port":         manifest.port,
            })
        return result


# ── Singleton ──────────────────────────────────────────────────────────────────

_registry: Optional[FrameworkRegistry] = None


def get_registry() -> FrameworkRegistry:
    global _registry
    if _registry is None:
        _registry = FrameworkRegistry()
    return _registry
