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
3. `pip-audit` against the declared Python dependency groups in `pyproject.toml`
4. `npm audit --omit=dev` for the command-center frontend in `dashboard/frontend`

## Auth Posture

- `services/dashd/api.py` uses a separate browser session secret for cookies; the cookie value is not the raw dashboard bearer token.
- Setup-only dashboard routes accept `X-ClawOS-Setup: 1` only on loopback and only until setup completion is recorded.
- Completing setup rotates the dashboard session secret to invalidate any setup-era browser session.
- `services/a2ad/service.py` requires both bearer auth and an explicit trusted peer URL for remote task ingress.
- `services/gatewayd/service.py` refuses outbound A2A delegation to blocked or untrusted peers.

## Notes

- The Python vulnerability scan is run against the repo's declared dependency groups, not whatever happens to be installed globally on the machine.
- The frontend audit only checks production dependencies.
- This script is intended to be reproducible locally and in CI; it complements `docs/VERIFICATION.md`, which covers the broader correctness and UX gates.
