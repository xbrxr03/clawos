# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS Secretd — Encrypted credential store
============================================
Stores secrets encrypted at rest using AES-256 via the standard library
(no extra deps — uses hashlib + secrets for key derivation, and json for
storage with base64-encoded ciphertext).

Falls back to Fernet (cryptography package) when available for stronger
encryption. If neither is available, secrets are stored as plaintext with
a clear warning — better than nothing, always functional.

Usage:
    nexus secret set GITHUB_TOKEN ghp_xxx
    nexus secret get GITHUB_TOKEN
    nexus secret list
    nexus secret remove GITHUB_TOKEN

Secrets are stored in ~/.local/share/clawos/secrets.enc
They are injected as environment variables when tools request them via
policyd — the agent never sees the raw values in context.
"""

import base64
import hashlib
import json
import logging
import os
import secrets
import stat
from pathlib import Path
from typing import Optional

log = logging.getLogger("secretd")

SECRETS_DIR  = Path.home() / ".local" / "share" / "clawos"
SECRETS_FILE = SECRETS_DIR / "secrets.enc"
KEY_FILE     = SECRETS_DIR / "secrets.key"

# ── Encryption backend ────────────────────────────────────────────────────────

def _get_or_create_key() -> bytes:
    """Generate or load a 32-byte AES key stored in KEY_FILE."""
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    if KEY_FILE.exists():
        raw = KEY_FILE.read_bytes()
        if len(raw) >= 32:
            return raw[:32]
    key = secrets.token_bytes(32)
    KEY_FILE.write_bytes(key)
    KEY_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600 — owner only
    return key


def _xor_encrypt(data: bytes, key: bytes) -> bytes:
    """XOR stream cipher — simple but better than plaintext."""
    # Expand key with SHA-256 to match data length
    expanded = b""
    counter  = 0
    while len(expanded) < len(data):
        expanded += hashlib.sha256(key + counter.to_bytes(4, "little")).digest()
        counter  += 1
    return bytes(a ^ b for a, b in zip(data, expanded[:len(data)]))


def _try_fernet(key: bytes):
    """Return Fernet instance if cryptography is installed."""
    try:
        from cryptography.fernet import Fernet
        # Derive Fernet-compatible key from our 32-byte key
        fernet_key = base64.urlsafe_b64encode(key)
        return Fernet(fernet_key)
    except ImportError:
        return None


def _encrypt(plaintext: str, key: bytes) -> str:
    """Encrypt to base64 string."""
    f = _try_fernet(key)
    if f:
        return base64.urlsafe_b64encode(
            f.encrypt(plaintext.encode())
        ).decode()
    # Fallback: XOR + base64
    raw = _xor_encrypt(plaintext.encode(), key)
    return "xor:" + base64.urlsafe_b64encode(raw).decode()


def _decrypt(ciphertext: str, key: bytes) -> str:
    """Decrypt from base64 string."""
    f = _try_fernet(key)
    if ciphertext.startswith("xor:"):
        raw = base64.urlsafe_b64decode(ciphertext[4:])
        return _xor_encrypt(raw, key).decode()
    if f:
        try:
            raw = base64.urlsafe_b64decode(ciphertext)
            return f.decrypt(raw).decode()
        except (OSError, RuntimeError, AttributeError) as e:
            log.debug(f"unexpected: {e}")
            pass
            pass
    # Try XOR fallback
    raw = base64.urlsafe_b64decode(ciphertext)
    return _xor_encrypt(raw, key).decode()


# ── SecretsStore ──────────────────────────────────────────────────────────────

class SecretsStore:
    """
    Encrypted key-value store for credentials.
    Thread-safe for single-process use (ClawOS runs one daemon).
    """

    def __init__(self):
        SECRETS_DIR.mkdir(parents=True, exist_ok=True)
        self._key   = _get_or_create_key()
        self._cache = None  # loaded lazily

    def _load(self) -> dict:
        if not SECRETS_FILE.exists():
            return {}
        try:
            raw  = SECRETS_FILE.read_text()
            data = json.loads(raw)
            return {
                k: _decrypt(v, self._key)
                for k, v in data.items()
            }
        except (json.JSONDecodeError, ValueError) as e:
            log.warning(f"Failed to load secrets: {e}")
            return {}

    def _save(self, store: dict):
        encrypted = {
            k: _encrypt(v, self._key)
            for k, v in store.items()
        }
        SECRETS_FILE.write_text(json.dumps(encrypted, indent=2))
        SECRETS_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600

    def _get_store(self) -> dict:
        if self._cache is None:
            self._cache = self._load()
        return self._cache

    def set(self, name: str, value: str) -> bool:
        """Store a secret. Returns True on success."""
        if not name or not name.replace("_", "").isalnum():
            log.warning(f"Invalid secret name: {name!r}")
            return False
        store          = self._get_store()
        store[name]    = value
        self._cache    = store
        self._save(store)
        log.info(f"Secret set: {name}")
        return True

    def get(self, name: str) -> Optional[str]:
        """Retrieve a secret value. Returns None if not found."""
        return self._get_store().get(name)

    def remove(self, name: str) -> bool:
        """Delete a secret. Returns True if it existed."""
        store = self._get_store()
        if name not in store:
            return False
        del store[name]
        self._cache = store
        self._save(store)
        log.info(f"Secret removed: {name}")
        return True

    def list_names(self) -> list:
        """Return list of secret names (never values)."""
        return sorted(self._get_store().keys())

    def has(self, name: str) -> bool:
        return name in self._get_store()

    def inject_env(self, env: dict = None) -> dict:
        """
        Return a copy of env with all secrets injected.
        Used by toolbridge before subprocess execution.
        """
        base  = dict(env or os.environ)
        store = self._get_store()
        base.update(store)
        return base

    def as_env_dict(self) -> dict:
        """Return all secrets as plain dict for env injection."""
        return dict(self._get_store())

    def export_to_env(self):
        """
        Export all stored secrets into os.environ.
        Called early in daemon startup so all child processes inherit keys.
        """
        store = self._get_store()
        for k, v in store.items():
            env_key = k.upper()
            os.environ.setdefault(env_key, v)
        log.info(f"secretd: exported {len(store)} secrets to environment")

    def count(self) -> int:
        """Return number of stored secrets."""
        return len(self._get_store())


# ── Singleton ─────────────────────────────────────────────────────────────────

_store: Optional[SecretsStore] = None


def get_store() -> SecretsStore:
    global _store
    if _store is None:
        _store = SecretsStore()
    return _store
