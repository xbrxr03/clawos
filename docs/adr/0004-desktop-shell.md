# ADR 0004: Desktop Shell

- Status: Accepted
- Date: 2026-04-05

## Decision

ClawOS uses Tauri as the desktop shell for Command Center and Setup.

The shell provides:

- launch-on-login integration
- native notifications
- file/system reveal helpers
- service lifecycle actions
- support bundle handoff

## Consequences

- Electron is not used.
- browser mode remains supported, but desktop is the flagship surface.
- a single frontend codebase is shared across web and desktop.
