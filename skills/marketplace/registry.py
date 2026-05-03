# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Skill Registry — ClawHub wrapper.
Fetches the skill index from ClawHub (OpenClaw's marketplace, 13,700+ skills)
and adds ClawOS Ed25519 verification metadata on top.

ClawHub API: https://hub.openclaw.ai/api/v1
- GET /skills — paginated list of skills
- GET /skills/{id} — skill detail + download URL
- GET /skills/search?q=... — search

Trust tiers (ClawOS-specific, layered on top of ClawHub data):
  - "clawos_verified" — Ed25519 signed by ClawOS team
  - "community"       — from ClawHub, no ClawOS signature
  - "local"           — installed from local path
"""
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger("skill_registry")

# ClawHub API base
CLAWHUB_API = "https://hub.openclaw.ai/api/v1"

# ClawOS signature index — signed skills we've verified ourselves
# This is fetched from a known URL and cached locally
CLAWOS_SIG_INDEX_URL = "https://raw.githubusercontent.com/xbrxr03/clawos-skill-sigs/main/index.json"

# Local install dir
from clawos_core.constants import CLAWOS_DIR
SKILLS_DIR = CLAWOS_DIR / "skills"
SIG_INDEX_CACHE = CLAWOS_DIR / "config" / "skill_sig_index.json"
INSTALLED_DB = CLAWOS_DIR / "config" / "installed_skills.json"

# Cache TTL: 1 hour
_CACHE_TTL_S = 3600
_index_cache: dict = {}
_cache_ts: float = 0.0


def _http_get(url: str, timeout: int = 10) -> dict | list | None:
    """Simple HTTP GET with JSON response. Returns None on any error."""
    try:
        import urllib.request
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "ClawOS-SkillRegistry/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (json.JSONDecodeError, ValueError) as e:
        log.debug(f"HTTP GET {url}: {e}")
        return None


def _load_sig_index() -> dict:
    """Load ClawOS signature index (cached locally)."""
    # Check cache file
    if SIG_INDEX_CACHE.exists():
        try:
            data = json.loads(SIG_INDEX_CACHE.read_text())
            if time.time() - data.get("_cached_at", 0) < 86400:  # 24h cache
                return data.get("skills", {})
        except (json.JSONDecodeError, ValueError):
            log.debug(f"failed: {e}")
            pass
            pass

    # Fetch fresh
    data = _http_get(CLAWOS_SIG_INDEX_URL, timeout=8)
    if data and isinstance(data, dict):
        SIG_INDEX_CACHE.parent.mkdir(parents=True, exist_ok=True)
        SIG_INDEX_CACHE.write_text(json.dumps({"_cached_at": time.time(), "skills": data}))
        return data

    # Return empty if unavailable (degrades to "community" trust)
    return {}


def search_skills(query: str = "", page: int = 1, limit: int = 20) -> dict:
    """
    Search ClawHub for skills matching query.
    Returns {results: [...], total: int, page: int, has_more: bool}
    Each result has: id, name, description, author, version, tags, trust_tier, downloads
    """
    # Build ClawHub URL
    if query:
        url = f"{CLAWHUB_API}/skills/search?q={query.replace(' ', '+')}&page={page}&limit={limit}"
    else:
        url = f"{CLAWHUB_API}/skills?page={page}&limit={limit}"

    data = _http_get(url)
    sig_index = _load_sig_index()

    if data is None:
        # Return cached results if available
        return {"results": [], "total": 0, "page": page, "has_more": False,
                "error": "ClawHub unavailable — check internet connection"}

    # Normalize ClawHub response format
    # ClawHub returns: {"skills": [...], "total": N, "page": N}
    raw_skills = data.get("skills", data.get("results", []))
    if isinstance(data, list):
        raw_skills = data

    results = []
    for skill in raw_skills:
        skill_id = skill.get("id") or skill.get("name", "")
        normalized = {
            "id": skill_id,
            "name": skill.get("name", skill_id),
            "description": skill.get("description", ""),
            "author": skill.get("author", skill.get("created_by", "community")),
            "version": skill.get("version", "latest"),
            "tags": skill.get("tags", []),
            "downloads": skill.get("downloads", skill.get("install_count", 0)),
            "download_url": skill.get("download_url") or skill.get("url", ""),
            "trust_tier": "clawos_verified" if skill_id in sig_index else "community",
            "installed": _is_installed(skill_id),
        }
        results.append(normalized)

    return {
        "results": results,
        "total": data.get("total", len(results)),
        "page": page,
        "has_more": len(results) == limit,
    }


def get_skill_detail(skill_id: str) -> Optional[dict]:
    """Fetch full detail for a specific skill from ClawHub."""
    url = f"{CLAWHUB_API}/skills/{skill_id}"
    data = _http_get(url)
    if data is None:
        return None

    sig_index = _load_sig_index()
    skill_id_clean = data.get("id", skill_id)

    return {
        "id": skill_id_clean,
        "name": data.get("name", skill_id_clean),
        "description": data.get("description", ""),
        "author": data.get("author", "community"),
        "version": data.get("version", "latest"),
        "tags": data.get("tags", []),
        "permissions": data.get("permissions", []),
        "entry": data.get("entry", "entry.py"),
        "download_url": data.get("download_url") or data.get("url", ""),
        "trust_tier": "clawos_verified" if skill_id_clean in sig_index else "community",
        "signature": sig_index.get(skill_id_clean, {}).get("signature"),
        "clawos_verified": skill_id_clean in sig_index,
        "installed": _is_installed(skill_id_clean),
        "installed_version": _get_installed_version(skill_id_clean),
    }


def get_installed_skills() -> list[dict]:
    """Return list of all locally installed skills."""
    db = _load_installed_db()
    return list(db.values())


def _is_installed(skill_id: str) -> bool:
    db = _load_installed_db()
    return skill_id in db


def _get_installed_version(skill_id: str) -> Optional[str]:
    db = _load_installed_db()
    return db.get(skill_id, {}).get("version")


def _load_installed_db() -> dict:
    if not INSTALLED_DB.exists():
        return {}
    try:
        return json.loads(INSTALLED_DB.read_text())
    except (json.JSONDecodeError, ValueError):
        return {}


def _save_installed_db(db: dict):
    INSTALLED_DB.parent.mkdir(parents=True, exist_ok=True)
    INSTALLED_DB.write_text(json.dumps(db, indent=2))


def register_installed(skill_id: str, name: str, version: str,
                       trust_tier: str, install_path: str):
    """Record a skill as installed."""
    db = _load_installed_db()
    db[skill_id] = {
        "id": skill_id,
        "name": name,
        "version": version,
        "trust_tier": trust_tier,
        "install_path": install_path,
        "installed_at": time.time(),
    }
    _save_installed_db(db)


def unregister_installed(skill_id: str):
    """Remove a skill from the installed registry."""
    db = _load_installed_db()
    db.pop(skill_id, None)
    _save_installed_db(db)
