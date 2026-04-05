# ADR 0003: Setup Platform

- Status: Accepted
- Date: 2026-04-05

## Decision

ClawOS setup is implemented as a reusable local platform named `setupd`.

`setupd` owns:

- machine inspection
- install/apply planning
- resumable setup execution
- progress events
- diagnostics and repair hooks
- persisted `SetupState`

## Consequences

- terminal and GTK setup flows become fallback/recovery paths.
- distro first boot, Linux host install, and macOS host install all target the same backend contract.
- bootstrap primitives remain useful, but are no longer the primary user-facing entrypoint.
