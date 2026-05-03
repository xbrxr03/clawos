# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Skill Installer — downloads, verifies, and installs skills from ClawHub.

Install flow:
  1. Fetch skill metadata from ClawHub registry
  2. Download zip archive to temp dir
  3. Extract and validate skill.yaml structure
  4. Ed25519 signature check (required for clawos_verified, warning for community)
  5. Run sandbox smoke test (import check only)
  6. Move to ~/.clawos/skills/{skill_id}/
  7. Register in installed_skills.json

Uninstall: delete skill dir + deregister.
"""
import hashlib
import json
import logging
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger("skill_installer")

from clawos_core.constants import CLAWOS_DIR

SKILLS_DIR = CLAWOS_DIR / "skills"


def install_skill(
    skill_id: str,
    force: bool = False,
    allow_community: bool = True,
    progress_cb: Optional[Callable[[str], None]] = None,
    bypass_typosquat_check: bool = False,
) -> dict:
    """
    Install a skill from ClawHub.
    Returns {ok: bool, skill_id: str, trust_tier: str, error: str}
    """
    from skills.marketplace.registry import (
        get_skill_detail, register_installed, _is_installed
    )
    from skills.marketplace.verifier import (
        verify_skill_yaml, verify_signature, check_trust_tier,
        check_typosquatting,
    )

    def _progress(msg: str):
        log.info(f"[install:{skill_id}] {msg}")
        if progress_cb:
            progress_cb(msg)

    # ── 0. Typosquatting check ───────────────────────────────────────────────
    if not bypass_typosquat_check:
        is_suspicious, warning = check_typosquatting(skill_id)
        if is_suspicious:
            _progress(warning)
            # Raise so callers (clawctl + dashboard) can prompt for confirmation
            raise ValueError(f"TYPOSQUAT_WARNING: {warning}")

    # ── 1. Check already installed ───────────────────────────────────────────
    if _is_installed(skill_id) and not force:
        return {"ok": False, "skill_id": skill_id, "trust_tier": "",
                "error": f"Skill '{skill_id}' is already installed. Use --force to reinstall."}

    # ── 2. Fetch metadata ────────────────────────────────────────────────────
    _progress(f"Fetching metadata for '{skill_id}' from ClawHub...")
    detail = get_skill_detail(skill_id)
    if detail is None:
        return {"ok": False, "skill_id": skill_id, "trust_tier": "",
                "error": f"Skill '{skill_id}' not found on ClawHub."}

    trust_tier = detail.get("trust_tier", "community")
    download_url = detail.get("download_url", "")

    if trust_tier == "community" and not allow_community:
        return {"ok": False, "skill_id": skill_id, "trust_tier": trust_tier,
                "error": f"Skill '{skill_id}' is community-tier (unverified). "
                         f"Use --allow-community to install anyway."}

    if not download_url:
        return {"ok": False, "skill_id": skill_id, "trust_tier": trust_tier,
                "error": f"No download URL for '{skill_id}'."}

    # ── 3. Download to temp dir ──────────────────────────────────────────────
    _progress(f"Downloading '{detail['name']}' ({trust_tier})...")
    with tempfile.TemporaryDirectory(prefix="clawos_skill_") as tmpdir:
        tmp_path = Path(tmpdir)
        zip_path = tmp_path / f"{skill_id}.zip"

        try:
            req = urllib.request.Request(
                download_url,
                headers={"User-Agent": "ClawOS-SkillInstaller/1.0"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                zip_path.write_bytes(resp.read())
        except (OSError, ConnectionRefusedError, TimeoutError) as e:
            return {"ok": False, "skill_id": skill_id, "trust_tier": trust_tier,
                    "error": f"Download failed: {e}"}

        # ── 4. Extract ───────────────────────────────────────────────────────
        _progress("Extracting...")
        extract_dir = tmp_path / "extracted"
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                # Security: prevent path traversal in zip
                for name in zf.namelist():
                    if name.startswith("/") or ".." in name:
                        return {"ok": False, "skill_id": skill_id, "trust_tier": trust_tier,
                                "error": f"Zip contains suspicious path: {name}"}
                zf.extractall(extract_dir)
        except zipfile.BadZipFile:
            return {"ok": False, "skill_id": skill_id, "trust_tier": trust_tier,
                    "error": "Download is not a valid zip file."}

        # Find the skill root (may be nested one level)
        skill_root = _find_skill_root(extract_dir)
        if skill_root is None:
            return {"ok": False, "skill_id": skill_id, "trust_tier": trust_tier,
                    "error": "Extracted zip does not contain skill.yaml"}

        # ── 5. Validate skill.yaml ───────────────────────────────────────────
        _progress("Validating skill structure...")
        valid, reason, skill_meta = verify_skill_yaml(skill_root)
        if not valid:
            return {"ok": False, "skill_id": skill_id, "trust_tier": trust_tier,
                    "error": f"Invalid skill: {reason}"}

        # ── 6. Signature verification ────────────────────────────────────────
        signature = detail.get("signature")
        if trust_tier == "clawos_verified" and signature:
            _progress("Verifying Ed25519 signature...")
            sig_valid, sig_reason = verify_signature(skill_root, signature)
            if not sig_valid:
                return {"ok": False, "skill_id": skill_id, "trust_tier": trust_tier,
                        "error": f"Signature verification failed: {sig_reason}. "
                                 f"Refusing to install — skill may have been tampered with."}
            _progress(f"✓ Signature valid")
        elif trust_tier == "community":
            _progress(f"⚠ Community skill — no ClawOS signature. Installing with caution.")

        # ── 7. Sandbox smoke test ────────────────────────────────────────────
        _progress("Running sandbox check...")
        sandbox_result = _sandbox_smoke_test(skill_root, skill_meta)
        if not sandbox_result["ok"]:
            return {"ok": False, "skill_id": skill_id, "trust_tier": trust_tier,
                    "error": f"Sandbox check failed: {sandbox_result['error']}"}

        # ── 8. Install to skills dir ─────────────────────────────────────────
        _progress(f"Installing to {SKILLS_DIR}/{skill_id}...")
        install_path = SKILLS_DIR / skill_id
        if install_path.exists():
            shutil.rmtree(install_path)
        shutil.copytree(skill_root, install_path)

        # Write metadata
        meta_file = install_path / "_clawos_meta.json"
        meta_file.write_text(json.dumps({
            "skill_id": skill_id,
            "name": detail.get("name", skill_id),
            "version": detail.get("version", "latest"),
            "trust_tier": trust_tier,
            "signature": signature,
            "installed_from": "clawhub",
        }, indent=2))

    # ── 9. Register ──────────────────────────────────────────────────────────
    register_installed(
        skill_id=skill_id,
        name=detail.get("name", skill_id),
        version=detail.get("version", "latest"),
        trust_tier=trust_tier,
        install_path=str(SKILLS_DIR / skill_id),
    )
    _progress(f"✓ '{detail['name']}' installed successfully ({trust_tier})")

    return {
        "ok": True,
        "skill_id": skill_id,
        "name": detail.get("name", skill_id),
        "version": detail.get("version", "latest"),
        "trust_tier": trust_tier,
        "install_path": str(SKILLS_DIR / skill_id),
        "error": "",
    }


def uninstall_skill(skill_id: str) -> dict:
    """Remove an installed skill."""
    from skills.marketplace.registry import unregister_installed, _is_installed
    if not _is_installed(skill_id):
        return {"ok": False, "error": f"Skill '{skill_id}' is not installed."}

    install_path = SKILLS_DIR / skill_id
    if install_path.exists():
        shutil.rmtree(install_path)

    unregister_installed(skill_id)
    return {"ok": True, "skill_id": skill_id, "error": ""}


def install_local(skill_dir: str, skill_id: Optional[str] = None) -> dict:
    """
    Install a skill from a local directory (dev mode).
    No signature required, marked as trust_tier='local'.
    """
    from skills.marketplace.verifier import verify_skill_yaml
    from skills.marketplace.registry import register_installed

    src = Path(skill_dir).expanduser().resolve()
    if not src.exists():
        return {"ok": False, "skill_id": skill_id or "", "trust_tier": "local",
                "error": f"Path not found: {skill_dir}"}

    valid, reason, meta = verify_skill_yaml(src)
    if not valid:
        return {"ok": False, "skill_id": skill_id or "", "trust_tier": "local",
                "error": f"Invalid skill: {reason}"}

    sid = skill_id or meta.get("name", src.name)
    dest = SKILLS_DIR / sid
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)

    register_installed(
        skill_id=sid,
        name=meta.get("name", sid),
        version=meta.get("version", "dev"),
        trust_tier="local",
        install_path=str(dest),
    )
    return {"ok": True, "skill_id": sid, "trust_tier": "local", "error": ""}


def _find_skill_root(extract_dir: Path) -> Optional[Path]:
    """Find the directory containing skill.yaml (may be nested one level)."""
    if (extract_dir / "skill.yaml").exists():
        return extract_dir
    for child in extract_dir.iterdir():
        if child.is_dir() and (child / "skill.yaml").exists():
            return child
    return None


def _sandbox_smoke_test(skill_dir: Path, skill_meta: dict) -> dict:
    """
    Minimal sandbox check: parse the entry file for obvious bad imports.
    Does not execute — just AST-scans for blocked module usage.
    """
    entry_name = skill_meta.get("entry", "entry.py")
    entry_path = skill_dir / entry_name
    if not entry_path.exists():
        return {"ok": False, "error": f"Entry file not found: {entry_name}"}

    try:
        import ast
        source = entry_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(entry_path))
    except SyntaxError as e:
        return {"ok": False, "error": f"Syntax error in {entry_name}: {e}"}

    from skills.marketplace.sandbox import BLOCKED_MODULES
    blocked_found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                base = alias.name.split(".")[0]
                if base in BLOCKED_MODULES:
                    blocked_found.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                base = node.module.split(".")[0]
                if base in BLOCKED_MODULES:
                    blocked_found.append(node.module)

    if blocked_found:
        return {"ok": False,
                "error": f"Blocked imports detected: {', '.join(blocked_found)}. "
                          f"This skill attempts to bypass the sandbox."}

    return {"ok": True, "error": ""}
