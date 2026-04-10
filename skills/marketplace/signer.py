# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Skill Signer — developer tool for signing ClawOS skills with Ed25519.
Used by the ClawOS team to create clawos_verified signatures.

Usage (team only):
    clawctl skill sign ./my-skill/

Generates a base64 Ed25519 signature over the skill package hash.
The private key must be set via CLAWOS_SIGN_KEY env var (hex-encoded).
"""
import base64
import logging
import os
from pathlib import Path
from typing import Optional

log = logging.getLogger("skill_signer")


def sign_skill(skill_dir: Path, private_key_hex: Optional[str] = None) -> dict:
    """
    Sign a skill package with Ed25519.
    Returns {ok: bool, signature: str, skill_hash: str, error: str}

    private_key_hex: 32-byte hex private key scalar.
                     If None, reads from CLAWOS_SIGN_KEY env var.
    """
    key_hex = private_key_hex or os.environ.get("CLAWOS_SIGN_KEY", "")
    if not key_hex:
        return {"ok": False, "signature": "", "skill_hash": "",
                "error": "No signing key — set CLAWOS_SIGN_KEY env var"}

    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError:
        return {"ok": False, "signature": "", "skill_hash": "",
                "error": "cryptography library not installed — pip install cryptography"}

    try:
        key_bytes = bytes.fromhex(key_hex.strip())
        private_key = Ed25519PrivateKey.from_private_bytes(key_bytes)
    except Exception as e:
        return {"ok": False, "signature": "", "skill_hash": "",
                "error": f"Invalid private key: {e}"}

    from skills.marketplace.verifier import compute_skill_hash, verify_skill_yaml

    # Validate skill structure first
    valid, reason, _ = verify_skill_yaml(skill_dir)
    if not valid:
        return {"ok": False, "signature": "", "skill_hash": "",
                "error": f"Invalid skill structure: {reason}"}

    skill_hash = compute_skill_hash(skill_dir)
    message = skill_hash.encode("utf-8")

    try:
        sig_bytes = private_key.sign(message)
        sig_b64 = base64.b64encode(sig_bytes).decode("ascii")
        log.info(f"Signed skill {skill_dir.name} (hash={skill_hash[:16]}...)")
        return {
            "ok": True,
            "signature": sig_b64,
            "skill_hash": skill_hash,
            "error": "",
        }
    except Exception as e:
        return {"ok": False, "signature": "", "skill_hash": "",
                "error": f"Signing failed: {e}"}


def generate_keypair() -> dict:
    """
    Generate a new Ed25519 keypair for skill signing.
    Returns {private_key_hex: str, public_key_hex: str}
    Run this once to bootstrap the signing infrastructure.
    """
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError:
        return {"error": "cryptography library not installed — pip install cryptography"}

    private_key = Ed25519PrivateKey.generate()
    pub_key = private_key.public_key()

    private_bytes = private_key.private_bytes_raw()
    public_bytes = pub_key.public_bytes_raw()

    return {
        "private_key_hex": private_bytes.hex(),
        "public_key_hex": public_bytes.hex(),
        "note": "Store private key securely. Embed public key in verifier.py CLAWOS_PUBLIC_KEY_HEX.",
    }
