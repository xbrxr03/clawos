# macOS Support

## Target

- Supported install target: macOS 14+.
- Primary hardware target: Apple Silicon.
- Intel Macs are best-effort until they have broader runtime coverage.

## Canonical Path

The macOS install path is now:

1. `install.sh`
2. Homebrew for `git`, `sqlite`, `python`, `node`, and `ollama`
3. `scripts/setup-launchd.sh`
4. `clawctl` for service control and health checks

This is the macOS equivalent of the Linux `systemd` path. The repo should not add a second installer or a second service-manager path for macOS.

## What Works

- `install.sh` branches cleanly between Linux and macOS.
- `clawctl start`, `clawctl status`, `clawctl stop`, and `clawctl logs` use a shared service-manager abstraction.
- `bootstrap/service_enable.py` can install `launchd` agents.
- The top workflow hardening pass now includes direct Python implementations for:
  - `disk-report`
  - `log-summarize`
  - `find-duplicates`
  - `find-todos`
  - `merge-pdfs`
  - `clean-empty-dirs`

## Known Gaps

- `setup/first_run/gtk_wizard.py` is still Linux-oriented and should not be treated as the macOS first-run path.
- PicoClaw is skipped on macOS because the published release binaries are Linux-only.
- OpenClaw gateway support is available, but the Linux path is still more battle-tested than the macOS path.
- The archived dashboard backend under `archive/legacy/dashboard-backend/` is not part of the supported macOS runtime path.

## Verification

After installing on macOS, verify:

```bash
clawctl start
clawctl status
launchctl print gui/$(id -u)/io.clawos.daemon
launchctl print gui/$(id -u)/io.clawos.ollama
nexus workflow run disk-report
nexus workflow run find-todos dir=.
```

If OpenClaw is installed:

```bash
launchctl print gui/$(id -u)/io.clawos.openclaw-gateway
openclaw tui
```
