# SPDX-License-Identifier: AGPL-3.0-or-later
"""
clawctl skill — ClawHub skill marketplace commands.

  clawctl skill search [query]   — search ClawHub
  clawctl skill install <id>     — install a skill
  clawctl skill remove <id>      — remove an installed skill
  clawctl skill list             — list installed skills
  clawctl skill verify <path>    — verify Ed25519 signature of a local skill
  clawctl skill local <path>     — install from local path (dev)
  clawctl skill sign <path>      — sign a skill (requires CLAWOS_SIGN_KEY)
"""
import sys


def run_search(query: str, page: int = 1):
    """Search ClawHub for skills."""
    print(f"🔍 Searching ClawHub: '{query or '(all skills)'}' ...")
    try:
        from skills.marketplace.registry import search_skills
        result = search_skills(query=query, page=page, limit=20)
    except (ImportError, ModuleNotFoundError) as e:
        print(f"  ✗ Search error: {e}", file=sys.stderr)
        return

    if "error" in result and result["error"]:
        print(f"  ⚠  {result['error']}")

    skills = result.get("results", [])
    if not skills:
        print("  No skills found.")
        return

    print(f"\n  Found {result['total']} skills (page {page}):\n")
    for s in skills:
        tier_icon = "✓" if s["trust_tier"] == "clawos_verified" else "~"
        installed = " [installed]" if s.get("installed") else ""
        print(f"  {tier_icon} {s['id']:<30} {s['name']:<25} {s['trust_tier']}{installed}")
        if s.get("description"):
            print(f"    {s['description'][:80]}")

    if result.get("has_more"):
        print(f"\n  More results available — use --page {page+1}")


def run_install(skill_id: str, force: bool = False, allow_community: bool = True):
    """Install a skill from ClawHub."""
    print(f"📦 Installing skill '{skill_id}' from ClawHub...")
    try:
        from skills.marketplace.installer import install_skill
        result = install_skill(
            skill_id=skill_id,
            force=force,
            allow_community=allow_community,
            progress_cb=lambda msg: print(f"  → {msg}"),
        )
    except ValueError as e:
        err = str(e)
        if "TYPOSQUAT_WARNING:" in err:
            warning = err.replace("TYPOSQUAT_WARNING:", "").strip()
            print(f"\n  {warning}\n")
            try:
                import click
                if not click.confirm("Install anyway?", default=False):
                    print("Aborted.")
                    return
            except ImportError:
                ans = input("Install anyway? [y/N] ").strip().lower()
                if ans != "y":
                    print("Aborted.")
                    return
            # Retry with typosquat check bypassed (user confirmed)
            from skills.marketplace.installer import install_skill as _install_skill
            result = _install_skill(
                skill_id=skill_id, force=force,
                allow_community=allow_community,
                progress_cb=lambda msg: print(f"  → {msg}"),
                bypass_typosquat_check=True,
            )
        else:
            print(f"  ✗ Install error: {e}", file=sys.stderr)
            return
    except (OSError, subprocess.SubprocessError, RuntimeError) as e:
        print(f"  ✗ Install error: {e}", file=sys.stderr)
        return

    if result["ok"]:
        tier = result["trust_tier"]
        tier_label = "✓ ClawOS verified" if tier == "clawos_verified" else "⚠ Community (unverified)"
        print(f"\n  ✓ Installed: {result.get('name', skill_id)} v{result.get('version', '?')}")
        print(f"    Trust: {tier_label}")
        print(f"    Path: {result.get('install_path', '')}")
    else:
        print(f"\n  ✗ Install failed: {result['error']}", file=sys.stderr)
        sys.exit(1)


def run_remove(skill_id: str):
    """Remove an installed skill."""
    print(f"🗑  Removing skill '{skill_id}'...")
    try:
        from skills.marketplace.installer import uninstall_skill
        result = uninstall_skill(skill_id)
    except (ImportError, ModuleNotFoundError) as e:
        print(f"  ✗ Remove error: {e}", file=sys.stderr)
        return

    if result["ok"]:
        print(f"  ✓ Removed '{skill_id}'")
    else:
        print(f"  ✗ {result['error']}", file=sys.stderr)


def run_list():
    """List all installed skills."""
    try:
        from skills.marketplace.registry import get_installed_skills
        skills = get_installed_skills()
    except (ImportError, ModuleNotFoundError) as e:
        print(f"  ✗ Error: {e}", file=sys.stderr)
        return

    if not skills:
        print("  No skills installed.")
        print("  Try: clawctl skill search")
        return

    print(f"  Installed skills ({len(skills)}):\n")
    for s in skills:
        tier_icon = "✓" if s.get("trust_tier") == "clawos_verified" else "~"
        print(f"  {tier_icon} {s['id']:<30} {s.get('name', ''):<25} v{s.get('version', '?')} [{s.get('trust_tier', '?')}]")


def run_verify(skill_path: str):
    """Verify Ed25519 signature of a local skill directory."""
    from pathlib import Path
    path = Path(skill_path).expanduser().resolve()
    if not path.exists():
        print(f"  ✗ Path not found: {skill_path}", file=sys.stderr)
        return

    print(f"🔐 Verifying '{path.name}'...")
    try:
        from skills.marketplace.verifier import (
            verify_skill_yaml, compute_skill_hash, verify_signature
        )
        valid, reason, meta = verify_skill_yaml(path)
        if not valid:
            print(f"  ✗ Invalid skill structure: {reason}")
            return

        skill_hash = compute_skill_hash(path)
        print(f"  Skill: {meta.get('name')} v{meta.get('version')}")
        print(f"  Hash:  {skill_hash[:32]}...")

        # Check if there's a _clawos_meta.json with stored signature
        import json
        meta_file = path / "_clawos_meta.json"
        if meta_file.exists():
            stored = json.loads(meta_file.read_text())
            sig = stored.get("signature")
            if sig:
                sig_valid, sig_reason = verify_signature(path, sig)
                if sig_valid:
                    print(f"  ✓ Signature: VALID (ClawOS verified)")
                else:
                    print(f"  ✗ Signature: INVALID — {sig_reason}")
            else:
                print(f"  ~ No signature (community tier)")
        else:
            print(f"  ~ No _clawos_meta.json — community or unsigned skill")
    except (json.JSONDecodeError, ValueError) as e:
        print(f"  ✗ Verify error: {e}", file=sys.stderr)


def run_local(skill_path: str, skill_id: str = ""):
    """Install a skill from a local directory (dev mode)."""
    print(f"📁 Installing local skill from '{skill_path}'...")
    try:
        from skills.marketplace.installer import install_local
        result = install_local(skill_path, skill_id or None)
    except (ImportError, ModuleNotFoundError) as e:
        print(f"  ✗ Error: {e}", file=sys.stderr)
        return

    if result["ok"]:
        print(f"  ✓ Installed '{result['skill_id']}' (local/dev)")
    else:
        print(f"  ✗ {result['error']}", file=sys.stderr)


def run_sign(skill_path: str):
    """Sign a skill package (requires CLAWOS_SIGN_KEY env var)."""
    from pathlib import Path
    path = Path(skill_path).expanduser().resolve()
    if not path.exists():
        print(f"  ✗ Path not found: {skill_path}", file=sys.stderr)
        return

    print(f"✍  Signing '{path.name}'...")
    try:
        from skills.marketplace.signer import sign_skill
        result = sign_skill(path)
    except (ImportError, ModuleNotFoundError) as e:
        print(f"  ✗ Sign error: {e}", file=sys.stderr)
        return

    if result["ok"]:
        print(f"  ✓ Signature: {result['signature']}")
        print(f"  Hash: {result['skill_hash']}")
        print(f"\n  Add this to your skill index or _clawos_meta.json:")
        print(f"    \"signature\": \"{result['signature']}\"")
    else:
        print(f"  ✗ {result['error']}", file=sys.stderr)
