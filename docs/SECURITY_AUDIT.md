# Security Audit Guide

ClawOS now has a dedicated security-audit entrypoint alongside the broader repo verifier:

```bash
python scripts/security_audit.py
```

That audit currently checks four things:

1. Static scans for risky execution patterns in product code:
   - `shell=True`
   - `tempfile.mktemp(...)`
   - `exec(open(...))`
   - `curl ... | sh` or `curl ... | bash` installer paths
2. `python -m pip check`
3. `pip-audit` against the declared Python dependency groups in [pyproject.toml](/C:/Users/Abrxr%20Hxbib/.codex/worktrees/2291/clawos_github/pyproject.toml)
4. `npm audit --omit=dev` for the command-center frontend in [dashboard/frontend](/C:/Users/Abrxr%20Hxbib/.codex/worktrees/2291/clawos_github/dashboard/frontend)

## Notes

- The Python vulnerability scan is run against the repo's declared dependency groups, not whatever happens to be installed globally on the machine.
- The frontend audit only checks production dependencies.
- This script is intended to be reproducible locally and in CI; it complements [docs/VERIFICATION.md](/C:/Users/Abrxr%20Hxbib/.codex/worktrees/2291/clawos_github/docs/VERIFICATION.md), which covers the broader correctness and UX gates.
