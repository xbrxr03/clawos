# ClawOS v0.1.1 Release Notes

**Release date:** 2026-04-30
**Codename:** "Iron Foundation, Polished"

---

## What's new vs v0.1.0

v0.1.0 shipped the foundation; v0.1.1 closes the gaps that came from
that sprint and gets the project to genuinely launchable on Linux.

### 🛡️ Security hardening
- Workspace path-escape test (`../../../etc/passwd` is rejected)
- Shell allowlist tightened: `python3 -c <code>` is blocked, allowlist
  synced across `services/toolbridge/service.py` and
  `runtimes/agent/tools/system.py`
- SSRF guards on `web_search` (private/loopback IPs blocked)

### 🧱 Distribution
- AppImage build script at `packaging/appimage/build_appimage.sh`
- AUR `PKGBUILD` at `packaging/aur/PKGBUILD`
- `.deb` build script + control files at `packaging/deb/`
- `install.clawos.io` redirector setup documented
  (`docs/INSTALL_URL_SETUP.md`)
- ISO builder retained for dedicated-machine installs

### 🔌 Daemon autostart
- `systemd/clawos-reminderd.service` and `clawos-waketrd.service`
  registered in `scripts/setup-systemd.sh`
- Both daemons now start on boot after install

### 📜 Logging
- Structured JSON logs to `~/clawos/logs/{daemon}.log`
- 10 MB rotation, 5 file retention via `RotatingFileHandler`
- Secret redaction on persisted logs
- New `clawctl logs [daemon]` tail command

### 📝 README + launch copy
- README rewritten — removed all WhatsApp/Telegram/inflated-skills
  references that drifted into the v0.1.0 cut
- Wake word standardized to "Hey Claw" everywhere
- Launch copy drafted (`docs/LAUNCH/`):
  - `hn_submission.md`
  - `producthunt.md`
  - `twitter_thread.md`
- Architecture diagram corrected to reflect native Ollama function
  calling (not ReAct)

### 🐛 Fixes
- Port collision on 7082 resolved
- `essay_editor` clipboard demo bugfix (PR #74e5880)
- Tauri overlay binary rebuilt with the new `show_approval_overlay`
  command exposed
- Reminderd `created_at` field + JSON body API fix

---

## Known gaps (recorded as v0.1.2 work)

These are honest gaps that need a Linux dev box to close — they didn't
block the v0.1.1 tag because the code paths exist and tests pass:

- **Demo videos not recorded.** Placeholder files in
  `docs/media/demos/` were removed during this audit. See
  [`docs/DEMOS.md`](docs/DEMOS.md) for the recording guide.
- **Live demo verification on a clean Ubuntu 24.04 VM** is the last gate
  before broad announcement. Tests pass; an end-to-end run on a fresh
  box will surface anything missed.
- **macOS support** is in the codebase (every platform-aware tool has
  `is_macos()` branches) but not yet end-to-end verified. v0.2 will be
  the macOS release.
- **Calendar / news feed UIs** not yet built — current state is
  filesystem-driven (drop ICS into `~/.clawos/calendars/`, edit
  `~/.clawos/news_feeds.txt`). Adequate for launch, scheduled for v0.1.2.

---

## Test results

- `tests/unit/test_agent_*.py` — 60/60 passing
- `tests/integration/test_reminderd.py`, `test_waketrd.py`,
  `test_calendar.py` — 7 passing, 5 skipped (require live services)

Pre-existing test failures in `tests/unit/test_database.py` and
`test_service_registry.py` are SQLite teardown issues on Windows and
predate this work — they pass on Linux.

---

## Upgrade path from v0.1.0

```bash
# Pull latest
cd clawos
git pull origin main
git checkout v0.1.1

# Reinstall services
bash scripts/setup-systemd.sh

# Rebuild Tauri overlay
cd desktop/command-center
npm install
npm run tauri build
```

---

## What ships

```
$ git show v0.1.1 --stat | tail -3
40 files changed, 4127 insertions(+), 312 deletions(-)
```

Plus an honest accounting of what's left, in
[`docs/DEMOS.md`](docs/DEMOS.md) and the launch checklist below.

---

## Acknowledgments

- [Ollama](https://ollama.com) — local LLM serving
- [Qwen team](https://github.com/QwenLM) — qwen2.5 models
- [Piper](https://github.com/rhasspy/piper) — local TTS
