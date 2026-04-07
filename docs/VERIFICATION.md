# Verification Guide

ClawOS now has a single verification entrypoint for the main local quality gates:

```bash
python scripts/verify_repo.py
```

For security-focused checks, run:

```bash
python scripts/security_audit.py
```

That command runs, in order:

1. `py_compile` across tracked Python files
2. `pytest tests`
3. direct `tests/system/test_phase*.py` acceptance scripts
4. frontend `npm run ci` in `dashboard/frontend`

## Useful Variants

Skip the frontend checks:

```bash
python scripts/verify_repo.py --skip-frontend
```

Skip direct phase scripts:

```bash
python scripts/verify_repo.py --skip-phase-scripts
```

Run with a specific Python or npm executable:

```bash
python scripts/verify_repo.py --python-bin python3.11 --npm-bin npm
```

## Notes

- The verifier will run `npm ci` automatically if `dashboard/frontend/node_modules` is missing.
- Packaging `.deb` tests are part of `pytest tests`, but they skip unless you provide `--deb /path/to/package.deb`.
- Direct phase scripts are executed with `PYTHONUTF8=1` to keep output stable across platforms.
- CI also runs the main frontend and Python suites, but this script is the fastest way to reproduce the full local validation path before shipping.
- The dedicated security audit is documented in `docs/SECURITY_AUDIT.md`.
