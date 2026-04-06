# SPDX-License-Identifier: AGPL-3.0-or-later
"""clawctl doctor — run diagnostics."""


def run(fix: bool = False):
    from setup.repair.doctor import run_all
    results = run_all()
    if fix:
        _auto_fix(results)


def _auto_fix(results: list[dict]):
    failed = [r for r in results if not r["ok"] and r.get("fix")]
    if not failed:
        return
    print("  ── Auto-fix ────────────────────────────────────\n")
    import subprocess
    for r in failed:
        fix = r["fix"]
        label = r["label"]
        # Only safe non-destructive fixes
        if fix.startswith("mkdir"):
            subprocess.run(["bash", "-c", fix])
            print(f"  ✓  Fixed: {label}")
        elif fix.startswith("pip install"):
            print(f"  Running: {fix}")
            subprocess.run(["bash", "-c", fix])
