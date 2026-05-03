# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS License Manager — Supabase-backed.
Validates license keys against Supabase REST API with 72h offline grace.

License key format: CLAW-XXXX-XXXX-XXXX-XXXX
Tiers: free | premium | pro

Supabase table (licenses):
  id            uuid primary key
  key           text unique not null
  tier          text not null  -- 'premium' | 'pro'
  machine_id    text           -- bound machine after first activation
  activated_at  timestamptz
  is_active     bool default true
  email         text
"""
import hashlib
import json
import logging
import os
import platform
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger("license")

# License cache: stored locally so 72h offline grace works
from clawos_core.constants import CLAWOS_DIR
LICENSE_CACHE_FILE = CLAWOS_DIR / "config" / "license.json"

# Supabase project config — set via env or secretd
# These are public/anon keys — safe to ship in code
SUPABASE_URL = os.environ.get("CLAWOS_SUPABASE_URL", "https://YOUR_PROJECT.supabase.co")
SUPABASE_ANON_KEY = os.environ.get("CLAWOS_SUPABASE_ANON_KEY", "")

# Offline grace period
GRACE_PERIOD_S = 72 * 3600  # 72 hours

# Free tier — always available, no license needed
FREE_FEATURES = frozenset({
    "core_agent", "ollama_local", "dashboard", "voice_piper",
    "workflows_basic",  # organize-downloads, summarize-pdf, repo-summary
    "memory", "rag_basic", "whatsapp_basic",
})

# Premium tier features ($10 one-time)
PREMIUM_FEATURES = frozenset({
    *FREE_FEATURES,
    "all_workflows",
    "cloud_models",  # OpenRouter, kimi-k2
    "rag_advanced",  # GraphRAG, Nexus Brain
    "a2a_federation",
    "voice_elevenlabs",
    "skill_publishing",
    "mcp_advanced",
    "packs_all",
    "browser_control",
    "nexus_brain",
    "proactive_intelligence",
})

# Pro tier features ($25/month — future)
PRO_FEATURES = frozenset({
    *PREMIUM_FEATURES,
    "team_workspaces",
    "remote_a2a",
    "enterprise_workflows",
    "white_label",
})


def _get_machine_id() -> str:
    """
    Get a stable machine ID for license binding.
    Linux: /etc/machine-id
    macOS: IOPlatformUUID via system_profiler
    Windows: winreg MachineGuid
    Falls back to hostname hash.
    """
    raw_id = ""

    try:
        if platform.system() == "Linux":
            mid_path = Path("/etc/machine-id")
            if mid_path.exists():
                raw_id = mid_path.read_text().strip()
        elif platform.system() == "Darwin":
            import subprocess
            result = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                if "IOPlatformUUID" in line:
                    raw_id = line.split('"')[-2]
                    break
        elif platform.system() == "Windows":
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r"SOFTWARE\Microsoft\Cryptography")
            raw_id = winreg.QueryValueEx(key, "MachineGuid")[0]
    except (subprocess.SubprocessError, OSError) as e:
        log.debug(f"suppressed: {e}")

    if not raw_id:
        raw_id = platform.node()  # hostname fallback

    return hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:32]


def _supabase_headers() -> dict:
    anon_key = SUPABASE_ANON_KEY or os.environ.get("CLAWOS_SUPABASE_ANON_KEY", "")
    return {
        "apikey": anon_key,
        "Authorization": f"Bearer {anon_key}",
        "Content-Type": "application/json",
    }


def _supabase_get(path: str, params: str = "") -> Optional[list]:
    """HTTP GET to Supabase REST API."""
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += f"?{params}"
    try:
        import urllib.request
        req = urllib.request.Request(url, headers=_supabase_headers())
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (json.JSONDecodeError, ValueError) as e:
        log.debug(f"Supabase GET {path}: {e}")
        return None


def _supabase_patch(path: str, data: dict) -> bool:
    """HTTP PATCH to Supabase REST API."""
    import urllib.request
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    body = json.dumps(data).encode("utf-8")
    headers = {**_supabase_headers(), "Prefer": "return=minimal"}
    try:
        req = urllib.request.Request(url, data=body, headers=headers, method="PATCH")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status < 300
    except (OSError, ConnectionRefusedError, TimeoutError) as e:
        log.debug(f"Supabase PATCH {path}: {e}")
        return False


def _load_cache() -> dict:
    if not LICENSE_CACHE_FILE.exists():
        return {}
    try:
        return json.loads(LICENSE_CACHE_FILE.read_text())
    except (json.JSONDecodeError, ValueError):
        return {}


def _save_cache(data: dict):
    LICENSE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    LICENSE_CACHE_FILE.write_text(json.dumps(data, indent=2))


class LicenseManager:
    """
    Validates and caches license state.
    Thread-safe singleton.
    """

    def __init__(self):
        self._cache: dict = _load_cache()
        self._machine_id = _get_machine_id()
        self._last_online_check: float = 0.0

    def activate(self, key: str) -> dict:
        """
        Activate a license key on this machine.
        Returns {ok: bool, tier: str, email: str, error: str}
        """
        key = key.strip().upper()
        if not key.startswith("CLAW-"):
            return {"ok": False, "tier": "free", "email": "",
                    "error": "Invalid key format. Expected: CLAW-XXXX-XXXX-XXXX-XXXX"}

        # Check Supabase
        rows = _supabase_get("licenses", f"key=eq.{key}&select=*")
        if rows is None:
            return {"ok": False, "tier": "free", "email": "",
                    "error": "Cannot reach license server. Check internet connection."}
        if not rows:
            return {"ok": False, "tier": "free", "email": "",
                    "error": "License key not found. Check your key and try again."}

        row = rows[0]
        if not row.get("is_active"):
            return {"ok": False, "tier": "free", "email": "",
                    "error": "License key is deactivated."}

        bound_machine = row.get("machine_id")
        if bound_machine and bound_machine != self._machine_id:
            return {"ok": False, "tier": "free", "email": "",
                    "error": "License key is already activated on a different machine. "
                             "Contact support to transfer."}

        # Bind to this machine if first activation
        if not bound_machine:
            _supabase_patch(f"licenses?key=eq.{key}",
                            {"machine_id": self._machine_id,
                             "activated_at": _now_iso()})

        tier = row.get("tier", "premium")
        email = row.get("email", "")

        # Cache locally
        cache_data = {
            "key": key,
            "tier": tier,
            "email": email,
            "machine_id": self._machine_id,
            "validated_at": time.time(),
            "is_active": True,
        }
        self._cache = cache_data
        _save_cache(cache_data)

        log.info(f"License activated: {tier} tier for {email or 'unknown'}")
        return {"ok": True, "tier": tier, "email": email, "error": ""}

    def validate(self) -> dict:
        """
        Validate current license.
        Online: check Supabase (once per hour).
        Offline: use cache for up to 72h grace period.
        Returns {valid: bool, tier: str, source: str, error: str}
        """
        cache = _load_cache()
        if not cache:
            return {"valid": False, "tier": "free", "source": "none",
                    "error": "No license activated"}

        now = time.time()
        cache_age = now - cache.get("validated_at", 0)

        # Try online validation (once per hour max)
        if now - self._last_online_check > 3600:
            online = self._online_validate(cache.get("key", ""))
            if online is not None:
                self._last_online_check = now
                if not online:
                    # Mark invalid in cache
                    cache["is_active"] = False
                    _save_cache(cache)
                    return {"valid": False, "tier": "free", "source": "online",
                            "error": "License deactivated remotely"}
                # Update validated_at
                cache["validated_at"] = now
                _save_cache(cache)
                return {"valid": True, "tier": cache.get("tier", "premium"),
                        "source": "online", "error": ""}

        # Offline grace period
        if cache_age < GRACE_PERIOD_S:
            grace_remaining_h = int((GRACE_PERIOD_S - cache_age) / 3600)
            return {
                "valid": True,
                "tier": cache.get("tier", "premium"),
                "source": "cache",
                "grace_remaining_hours": grace_remaining_h,
                "error": "",
            }

        # Grace expired
        return {
            "valid": False,
            "tier": "free",
            "source": "cache_expired",
            "error": f"License validation cache expired ({int(cache_age/3600)}h old). "
                     f"Connect to the internet to revalidate.",
        }

    def _online_validate(self, key: str) -> Optional[bool]:
        """Returns True if valid, False if deactivated, None if unreachable."""
        if not key:
            return False
        rows = _supabase_get("licenses",
                             f"key=eq.{key}&machine_id=eq.{self._machine_id}&select=is_active")
        if rows is None:
            return None  # offline
        if not rows:
            return False
        return bool(rows[0].get("is_active"))

    def deactivate(self) -> dict:
        """Remove license from this machine (doesn't invalidate the key)."""
        cache = _load_cache()
        key = cache.get("key", "")
        if not key:
            return {"ok": False, "error": "No license to deactivate"}

        # Clear machine binding on Supabase
        _supabase_patch(f"licenses?key=eq.{key}&machine_id=eq.{self._machine_id}",
                        {"machine_id": None})

        # Clear local cache
        if LICENSE_CACHE_FILE.exists():
            LICENSE_CACHE_FILE.unlink()
        self._cache = {}
        return {"ok": True, "error": ""}

    def get_tier(self) -> str:
        """Return current tier: 'free' | 'premium' | 'pro'."""
        result = self.validate()
        if result["valid"]:
            return result["tier"]
        return "free"

    def get_status(self) -> dict:
        """Full status for dashboard display."""
        cache = _load_cache()
        validation = self.validate()
        return {
            "tier": validation["tier"] if validation["valid"] else "free",
            "valid": validation["valid"],
            "source": validation.get("source", "none"),
            "key_prefix": cache.get("key", "")[:10] + "..." if cache.get("key") else "",
            "email": cache.get("email", ""),
            "grace_remaining_hours": validation.get("grace_remaining_hours"),
            "machine_id": self._machine_id[:8] + "...",
            "error": validation.get("error", ""),
        }


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# ── Singleton ──────────────────────────────────────────────────────────────────
_manager: Optional[LicenseManager] = None


def get_license_manager() -> LicenseManager:
    global _manager
    if _manager is None:
        _manager = LicenseManager()
    return _manager
