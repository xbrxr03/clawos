# Production Guide

ClawOS now ships with safer network defaults:

- `dashd` binds to `127.0.0.1` by default.
- `dashd` requires authentication by default.
- `a2ad` binds to `127.0.0.1` by default.
- `a2ad` keeps mDNS discovery off by default.
- Any attempt to bind `dashd` or `a2ad` publicly without the required auth is forced back to loopback.

## Dashboard

The dashboard token is read from:

- `CLAWOS_DASHBOARD_TOKEN`, if set.
- Otherwise `~/clawos/config/dashboard.token`.

To use the browser dashboard:

1. Start ClawOS normally.
2. Open `http://127.0.0.1:7070`.
3. Paste the dashboard token into the login prompt.

To expose the dashboard beyond localhost, keep auth enabled and set:

```yaml
dashboard:
  host: "0.0.0.0"
  auth_required: true
```

## A2A

Remote A2A access is intentionally opt-in.

To expose `a2ad` on the network, set both a non-loopback host and a bearer token:

```yaml
a2a:
  host: "0.0.0.0"
  auth_token: "replace-with-a-long-random-token"
  mdns_enabled: true
```

If `a2a.host` is public and `a2a.auth_token` is empty, ClawOS falls back to `127.0.0.1`.

## Recommended Operator Checklist

Before calling a machine "production-ready", verify:

1. `clawctl status` shows the expected services running.
2. `http://127.0.0.1:7070/api/health` returns `status: ok`.
3. The dashboard login works and websocket updates arrive after login.
4. `a2ad` is either loopback-only or protected by a bearer token.
5. CI is green on both `ubuntu-latest` and `macos-14`.

## Tests

The current production-hardening tests cover:

- dashboard auth and websocket snapshot behavior
- dashboard fail-safe bind behavior
- A2A auth enforcement
- A2A fail-safe bind behavior

Run them with:

```bash
pytest tests/system/test_dashd_security.py tests/system/test_a2a_security.py
```

For the broader repo validation path, including frontend and direct acceptance scripts, run:

```bash
python scripts/verify_repo.py
```
