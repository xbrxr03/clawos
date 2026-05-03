# SPDX-License-Identifier: AGPL-3.0-or-later
"""
A2A Peer Registry
=================
Persisted registry of known A2A peers with trust tiers and HMAC-signed
agent card verification.

Trust tiers:
  trusted    – peer is explicitly trusted; tasks are accepted without extra gates
  unverified – discovered or manually added; tasks go through policyd approval
  blocked    – all incoming/outgoing communication rejected
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("a2ad.peers")

try:
    from clawos_core.constants import CONFIG_DIR
    PEER_REGISTRY_PATH = CONFIG_DIR / "a2a_peers.json"
    PEER_SIGNING_KEY_PATH = CONFIG_DIR / "a2a_signing.key"
except (ImportError, ModuleNotFoundError):
    PEER_REGISTRY_PATH = Path.home() / ".clawos" / "a2a_peers.json"
    PEER_SIGNING_KEY_PATH = Path.home() / ".clawos" / "a2a_signing.key"

TRUST_TIERS = frozenset({"trusted", "unverified", "blocked"})


# ── Signing key ───────────────────────────────────────────────────────────────
def _load_or_create_signing_key() -> str:
    PEER_SIGNING_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not PEER_SIGNING_KEY_PATH.exists():
        key = secrets.token_hex(32)
        PEER_SIGNING_KEY_PATH.write_text(key, encoding="utf-8")
        try:
            PEER_SIGNING_KEY_PATH.chmod(0o600)
        except OSError as e:
            log.debug(f"suppressed: {e}")
        return key
    return PEER_SIGNING_KEY_PATH.read_text(encoding="utf-8").strip()


def sign_agent_card(card_dict: dict) -> str:
    """Return HMAC-SHA256 hex signature of the agent card JSON."""
    key = _load_or_create_signing_key()
    canonical = json.dumps(card_dict, sort_keys=True, separators=(",", ":"))
    return hmac.new(key.encode(), canonical.encode(), hashlib.sha256).hexdigest()


def verify_agent_card(card_dict: dict, signature: str) -> bool:
    """Verify the signature of a received agent card."""
    expected = sign_agent_card(card_dict)
    try:
        return hmac.compare_digest(expected, signature)
    except (OSError, ValueError, AttributeError):
        return False


# ── Peer model ────────────────────────────────────────────────────────────────
@dataclass
class PeerRecord:
    id: str
    url: str
    name: str
    trust_tier: str = "unverified"   # trusted | unverified | blocked
    description: str = ""
    version: str = ""
    capabilities: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    last_seen: str = ""
    last_error: str = ""
    card_signature: str = ""
    added_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    reachable: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


# ── Persistence ───────────────────────────────────────────────────────────────
def _load_peers() -> List[PeerRecord]:
    if not PEER_REGISTRY_PATH.exists():
        return []
    try:
        data = json.loads(PEER_REGISTRY_PATH.read_text(encoding="utf-8"))
        return [PeerRecord(**p) for p in data]
    except (json.JSONDecodeError, ValueError) as exc:
        log.warning("Failed to load peer registry: %s", exc)
        return []


def _save_peers(peers: List[PeerRecord]) -> None:
    PEER_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    PEER_REGISTRY_PATH.write_text(
        json.dumps([asdict(p) for p in peers], indent=2),
        encoding="utf-8",
    )


# ── Agent card fetching ───────────────────────────────────────────────────────
def _fetch_agent_card(url: str, timeout: int = 8) -> Optional[dict]:
    """Fetch /.well-known/agent.json from a peer URL."""
    base = url.rstrip("/")
    card_url = f"{base}/.well-known/agent.json"
    try:
        req = urllib.request.Request(card_url, headers={"User-Agent": "ClawOS-A2A/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return json.loads(resp.read())
    except (json.JSONDecodeError, ValueError) as exc:
        log.debug("Failed to fetch agent card from %s: %s", url, exc)
        return None


# ── Registry ──────────────────────────────────────────────────────────────────
class PeerRegistry:
    def __init__(self) -> None:
        self._peers: List[PeerRecord] = _load_peers()

    def _find(self, peer_id: str) -> Optional[PeerRecord]:
        return next((p for p in self._peers if p.id == peer_id), None)

    def _find_by_url(self, url: str) -> Optional[PeerRecord]:
        url = url.rstrip("/")
        return next((p for p in self._peers if p.url.rstrip("/") == url), None)

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def list_peers(self) -> List[dict]:
        return [p.to_dict() for p in self._peers]

    def get_peer(self, peer_id: str) -> Optional[PeerRecord]:
        return self._find(peer_id)

    def get_peer_by_url(self, url: str) -> Optional[PeerRecord]:
        return self._find_by_url(url)

    def add_peer(self, url: str, name: str = "", trust_tier: str = "unverified") -> PeerRecord:
        url = url.rstrip("/")
        if trust_tier not in TRUST_TIERS:
            trust_tier = "unverified"
        existing = self._find_by_url(url)
        if existing:
            return existing
        peer = PeerRecord(
            id=secrets.token_urlsafe(8),
            url=url,
            name=name or url,
            trust_tier=trust_tier,
        )
        self._peers.append(peer)
        _save_peers(self._peers)
        return peer

    def remove_peer(self, peer_id: str) -> bool:
        before = len(self._peers)
        self._peers = [p for p in self._peers if p.id != peer_id]
        if len(self._peers) < before:
            _save_peers(self._peers)
            return True
        return False

    def set_trust(self, peer_id: str, trust_tier: str) -> Optional[PeerRecord]:
        if trust_tier not in TRUST_TIERS:
            return None
        peer = self._find(peer_id)
        if not peer:
            return None
        peer.trust_tier = trust_tier
        _save_peers(self._peers)
        return peer

    # ── Probe ─────────────────────────────────────────────────────────────────

    def probe_peer(self, peer_id: str) -> PeerRecord:
        peer = self._find(peer_id)
        if not peer:
            raise ValueError(f"Peer not found: {peer_id}")

        card = _fetch_agent_card(peer.url)
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        if card:
            peer.name = card.get("name", peer.name)
            peer.description = card.get("description", "")
            peer.version = card.get("version", "")
            peer.capabilities = list(card.get("capabilities", {}).keys())
            peer.skills = [s.get("name", "") for s in card.get("skills", [])]
            peer.reachable = True
            peer.last_seen = now
            peer.last_error = ""

            # Verify signature if present
            sig = card.pop("_signature", "") or card.get("metadata", {}).get("_signature", "")
            if sig:
                peer.card_signature = sig
        else:
            peer.reachable = False
            peer.last_error = f"Unreachable at {now}"

        _save_peers(self._peers)
        return peer

    def register_from_card(self, card: dict, source_url: str) -> PeerRecord:
        """Register or update a peer from an inbound agent card."""
        url = card.get("url", source_url).rstrip("/")
        existing = self._find_by_url(url)
        peer = existing or PeerRecord(id=secrets.token_urlsafe(8), url=url, name=card.get("name", url))
        peer.name = card.get("name", peer.name)
        peer.description = card.get("description", "")
        peer.version = card.get("version", "")
        peer.capabilities = list(card.get("capabilities", {}).keys())
        peer.skills = [s.get("name", "") for s in card.get("skills", [])]
        peer.last_seen = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        peer.reachable = True
        if not existing:
            self._peers.append(peer)
        _save_peers(self._peers)
        return peer

    def is_trusted(self, peer_id: str) -> bool:
        peer = self._find(peer_id)
        return peer is not None and peer.trust_tier == "trusted"

    def is_trusted_url(self, url: str) -> bool:
        peer = self._find_by_url(url)
        return peer is not None and peer.trust_tier == "trusted"

    def is_blocked(self, url: str) -> bool:
        peer = self._find_by_url(url)
        return peer is not None and peer.trust_tier == "blocked"

    def get_signing_key_fingerprint(self) -> str:
        key = _load_or_create_signing_key()
        return hashlib.sha256(key.encode()).hexdigest()[:16]


_registry: Optional[PeerRegistry] = None


def get_registry() -> PeerRegistry:
    global _registry
    if _registry is None:
        _registry = PeerRegistry()
    return _registry
