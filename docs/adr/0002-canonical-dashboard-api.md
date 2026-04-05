# ADR 0002: Canonical Dashboard API

- Status: Accepted
- Date: 2026-04-05

## Decision

`services/dashd` is the only dashboard-facing API and web-serving surface.

It is responsible for:

- serving the built Command Center frontend
- browser session/auth handling
- websocket snapshot/event stream
- proxying or composing setup/runtime data for the frontend

## Consequences

- `dashboard/backend` is legacy only and must not receive new features.
- frontend build artifacts are published into `services/dashd/static`.
- desktop shells may call lower-level services directly, but browser clients talk to `dashd`.
