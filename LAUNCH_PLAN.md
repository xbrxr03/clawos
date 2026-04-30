# ClawOS — MVP Launch Plan (Agent Brief)

> **Read this whole file before doing anything.** It's a self-contained brief
> for the coding agent driving ClawOS from current state to v1.0 launch on
> Linux, then v1.1 on macOS. The brief assumes you have shell, file edit,
> and git access in this repo, and a Linux dev box you can SSH into.

---

## 1. Mission

Take ClawOS from "code-complete native agent loop" to **public launch on
Hacker News + ProductHunt + Twitter** with three flagship demos that make
people say *"I didn't know offline AI could do this on my own laptop."*

**Linux v1.0 first. macOS v1.1 fast-follow.** Total target: ~11 days for
Linux launch, ~4 days for macOS follow-up.

---

## 2. The product vision (so you make the right judgment calls)

ClawOS is **a local-first OS layer that turns any agent brain (qwen2.5:7b
locally, OpenClaw optionally) into a JARVIS-style personal AI assistant.**
Runs entirely on the user's hardware. No cloud. No API keys. No telemetry.

Two parallel tracks:

1. **Nexus** — the native ClawOS agent loop. The default JARVIS experience.
   Native Ollama function calling on qwen2.5:7b-instruct. Already built,
   needs hardening.
2. **OpenClaw integration** — for power users who want a more capable agent
   brain. The setup wizard recommends it. **Out of scope for this launch
   plan** — that's the next sprint after v1.0 ships.

The user must be able to:
- Install with one curl command
- Walk through a 9-step browser wizard
- Say "good morning" and get a JARVIS-voiced briefing of their day
- Say "write me a 1000-word essay about AI ethics and paste it into the editor"
  and have it actually happen
- Get a floating popup when the agent wants to do something sensitive
- Open apps, control volume, set reminders — all by voice or text
- Have it work fully offline

The competitive frame: **Ollama gave you a local model. We're giving you a
local AGENT.** Memory, voice, system control, multi-step tool use — all
offline, all on your hardware.

---

## 3. Locked decisions — DO NOT RELITIGATE

These are settled. Don't propose alternatives unless you discover a fatal
problem:

| Decision | Choice | Why |
|----------|--------|-----|
| Primary local model | `qwen2.5:7b-instruct` | 93% F1 on tool calling, native Hermes format works with Ollama |
| Code-task model | `qwen2.5-coder:7b` | Superior code/file/shell quality |
| Fast model | `qwen2.5:3b` | <1.5s on consumer hardware |
| Tool calling format | Native Ollama function calling | NOT ReAct JSON — that was the old loop |
| Telemetry | **ZERO**. Ever. | Brand promise + matches Ollama/Bun/Tauri positioning |
| Launch OS | Linux first, macOS v1.1 | Cuts code-signing complexity from v1.0 |
| Wake-word phrase | "Hey Claw" (already in voiced) | Don't change |
| OpenClaw integration | Out of scope for this plan | Next sprint |
| Windows | Out of scope, deferred | Far future |
| Distribution channels for v1.0 | AppImage + .deb + AUR | Skip Homebrew (macOS phase) |
| Wizard step count | 9 (already in `dashboard/frontend/src/pages/setup/SetupPage.tsx`) | Don't add steps |

---

## 4. Current state — what's already built (do NOT rebuild)

The recent commit `a82e83f feat(nexus): native Ollama tool-calling agent
loop with full JARVIS stack` shipped the Nexus core. Read `git show a82e83f`
for the full diff, but in summary:

### Native agent loop (`runtimes/agent/`)
- `runtime.py` — main runtime with 4-tier priority pipeline (memory fast-path
  → confirmation → deterministic intent → LLM with native tools)
- `intents.py` — pure-regex intent classifier, 8 intents
- `router.py` — picks 3b/7b/coder dynamically
- `tool_schemas.py` — 31 tool JSON schemas for native Ollama function calling
- `briefing.py` — morning briefing with parallel tool gather
- `voice_entry.py` — `speak_morning_briefing()` and `voice_chat_once()` helpers
- `cache.py` — TTL cache for time-stable tools
- `context_budget.py` — 2000-token priority-ordered context assembly
- `tools/` — 31 tools across 8 modules:
  - `system.py` — open_app, focus_window, close_app, set_volume, get_volume,
    system_stats, run_command
  - `desktop.py` — clipboard, paste, type, screenshot (wraps desktopd HTTP API)
  - `compose.py` — write_text using a second LLM call
  - `files.py` — read/write/list/open_file, open_url
  - `knowledge.py` — remember, recall, pin_fact (memd wrappers)
  - `productivity.py` — reminders (SQLite), get_time, get_weather (wttr.in,
    cached), get_calendar_events (local ICS), get_news (RSS, cached)
  - `workflows.py` — list/run for the 28 existing workflows
  - `web.py` — DuckDuckGo search

### Approval overlay
- `desktop/command-center/src-tauri/src/main.rs` — `show_approval_overlay`
  and `hide_approval_overlay` Tauri commands, borderless always-on-top
- `dashboard/frontend/src/overlays/ApprovalOverlay.tsx` — the React component
- `dashboard/frontend/src/main.tsx` — overlay route detection
- `dashboard/frontend/src/hooks/useCommandCenter.ts` — auto-shows overlay on
  `approval_pending` event when running inside Tauri

### Existing services you should USE, not rebuild
- `services/memd/service.py` — 7-layer memory: PINNED, WORKFLOW, ChromaDB,
  FTS5, archive, KG, LEARNED. Public API: `MemoryService.build_context_block`,
  `remember_async`, `recall`, `add_to_graph`, `query_graph`, `run_ace_loop`
- `services/policyd/service.py` — `PolicyEngine` with approval queue.
  `evaluate(tool, target, task_id, ws_id, granted_tools, content)` returns
  Decision (ALLOW / DENY / QUEUE). `decide_approval(req_id, approve)` resolves
  queued requests. `get_pending_approvals()` lists them.
- `services/voiced/service.py` — `VoiceService` + `run_voice_session(agent,
  stt_fn, tts_fn, tray)`. Whisper STT + Piper TTS already wired.
- `services/skilld/service.py` — `SkillLoader` with BM25 matching against
  SKILL.md files in `~/.claw/skills` and `~/.openclaw/skills`
- `services/desktopd/main.py` — HTTP API on port 7080 for cross-platform
  input automation. Already imports pyautogui/pynput/PIL.
- `services/dashd/api.py` — exposes `GET /api/approvals` and `POST
  /api/approve/{request_id}` (used by the Tauri overlay polling)
- `workflows/engine.py` — workflow engine, 28 workflows registered
- `services/setupd/service.py` — setup wizard backend
- `clawos_core/platform.py` — `is_linux()`, `is_macos()`, `is_windows()`,
  `homebrew_prefix()`, `ram_snapshot_gb()`

### Tests already passing (60)
- `tests/unit/test_agent_intents.py`
- `tests/unit/test_agent_router.py`
- `tests/unit/test_agent_tools.py`
- `tests/unit/test_agent_briefing.py`
- `tests/unit/test_agent_platform_coverage.py`
- `tests/unit/test_agent_polish.py`

Run the agent test suite: `python -m pytest tests/unit/test_agent_*.py -q`

---

## 5. Current state — what's broken or missing (your work)

### Verified gaps
1. **Install hasn't been re-run** since OpenClaw was ripped from `install.sh`.
   It SHOULD work but is unverified on a clean box.
2. **Reminders never fire** — they sit in `~/.clawos/reminders.db` with a
   `due_at` column but nothing watches it. No notification daemon.
3. **Wake-word → morning briefing** — voiced has `run_voice_session(agent,
   ...)` and `voice_entry.speak_morning_briefing()` exists, but they're
   not wired together. Saying "good morning" via voice doesn't trigger
   the briefing today.
4. **Tauri overlay** — Rust source ships but the binary needs rebuilding
   (`npm run tauri build` inside `desktop/command-center/`) to register
   the new `show_approval_overlay` command.
5. **`run_workflow` tool** assumes the workflows engine has `run`/`execute`/
   `invoke` methods. Defensive code, but unverified against the real
   `WorkflowEngine` API.
6. **Calendar tool** reads `~/.clawos/calendars/*.ics` but there's no
   importer to populate it. Empty by default.
7. **News feeds** default to BBC + HN. No UI to manage feeds. Users edit
   `~/.clawos/news_feeds.txt` by hand.
8. **No PINNED.md GUI editor** — users can't see/edit what JARVIS remembers
   about them.
9. **No structured logging or log rotation** — daemons log to stdout, no
   `clawctl logs` viewer.
10. **No code signing** — irrelevant for Linux v1.0.
11. **README and landing page are stale** — don't sell the vision.
12. **No demo videos** — needed for HN/PH submission.

### Risks you should investigate early
- Does `install.sh` actually complete on Ubuntu 24.04 today?
- Does the Ollama function-calling API behave as the new `runtime.py` expects?
- Does the Tauri overlay show on Wayland with `always_on_top` behaviour?
- Does `xdotool key ctrl+v` work consistently on GNOME/Wayland (it's known
  to be flaky on Wayland — wtype is the better path there)?
- Does `desktopd` actually start? Check `services/desktopd/main.py` — the
  service has dependencies (pyautogui, pynput) that may need extra setup
  on headless / Wayland systems.

---

## 6. The phased plan

> **Working style:** Fix-as-you-go. Commit after each meaningful change with
> a clear message. Push to `main` only when human approves (ask first). Keep
> changes small and verifiable. Run the existing test suite after each
> non-trivial change.

### Phase 1 — Reality check + ground-truth fixes (2 days)

**Goal:** install + 9-step wizard + the 3 showcase demos all work end-to-end
on a clean Ubuntu 24.04 box.

Steps:

1. SSH to the dev box. `git pull`. Confirm clean state.
2. Run `bash install.sh` from a clean home directory. Track every error,
   warning, missing dependency, broken step. Fix them inline.
3. Open the wizard at `http://localhost:7070/setup`. Walk through every
   screen. Note any broken endpoints, JS errors, missing data, ugly states.
   Fix them inline.
4. Trigger each of the three demos manually:
   - **Morning briefing:** call `python -m runtimes.agent.briefing`
     directly first (write a tiny CLI entry if one doesn't exist), then
     trigger via voice if voice is wired.
   - **Essay-to-editor:** start `clawos`, type "write me a 500 word essay
     about cats and paste it into the text editor". Watch what happens.
     Verify the LLM emits the right tool calls.
   - **Approval popup:** trigger a sensitive tool (`run_command "ls"`),
     verify the floating popup appears (rebuild Tauri binary first if
     needed).
5. Output: a `LAUNCH_BLOCKERS.md` checklist at repo root with every issue
   found, sorted by severity. Mark fixed inline as you go.

**Definition of done:** the install + wizard + 3 demos all work without
human intervention on a freshly imaged Ubuntu 24.04 VM. Commit message:
`fix(install,wizard,demos): make end-to-end flow work on clean Ubuntu 24.04`.

### Phase 2 — Demo path completion + the quirky moments (2 days)

**Goal:** add the missing pieces that make the demos feel magical.

#### 2.1 Wake word → morning briefing pipeline
Wire `voice_entry.speak_morning_briefing()` into the wake-word handler
inside `services/voiced/`. When the user says "Hey Claw" then "good morning"
(or any of the morning-briefing intents in `runtimes/agent/intents.py`),
the runtime already routes to `_try_deterministic` → `morning_briefing`.
The actual gap is just confirming voiced calls into the runtime correctly
when wake word fires. Test live, not just in unit tests.

#### 2.2 Reminder daemon
New file: `services/reminderd/` — minimal service that ticks every 30s,
queries `~/.clawos/reminders.db`, fires desktop notifications for due
reminders.
- Linux: `notify-send "Nexus" "{task}"` (with `paplay` for a sound).
- macOS: `osascript -e 'display notification "{task}" with title "Nexus"'`
  (skipped for v1.0, add for v1.1).
- Mark fired reminders `done = 1` in SQLite.
- Register the service with autostart (systemd user unit).

#### 2.3 Quirky "wow" demos
Document and verify these one-liners work:
- "set volume to 30 and play spotify" — two tools chained
- "what's eating my CPU?" — `system_stats` + brief synthesis
- "screenshot my screen and save it to today's folder" — three tools
- "what's on the news?"
- "remember I'm interested in AI safety" → recall in next briefing
- "open my project notes" — fuzzy file find via `list_files` + `open_file`

For each, confirm the LLM consistently emits the right tool calls. If a
demo is flaky, **fix the tool description in `tool_schemas.py`** — the LLM
follows the schema descriptions closely. Better descriptions > more tools.

#### 2.4 Demo scripts file
Create `docs/DEMOS.md` with each demo's: exact phrasing, expected tool
calls, expected timing, expected reply. This is what gets read aloud in
the demo videos.

**Definition of done:** every demo in `docs/DEMOS.md` runs reliably on
the dev box. Reminders fire as desktop notifications. Voice → morning
briefing works.

### Phase 3 — Production hardening (3 days)

**Goal:** nothing crashes the agent loop. Every failure has a graceful
degradation path.

#### 3.1 Error handling sweep
- Read every tool in `runtimes/agent/tools/`. For each, identify failure
  modes (network down, file not found, command not in PATH, permission
  denied). Make sure each returns a `[ERROR] ...` or `[OFFLINE] ...` string
  that the LLM can synthesize from.
- The runtime's tool dispatch already catches exceptions, but verify no
  raised exception propagates past `dispatch_tool` in
  `runtimes/agent/tools/__init__.py`.
- Specifically test: Ollama down (kill `ollama` process mid-conversation),
  ChromaDB locked, disk full, voice device missing.

#### 3.2 Daemon health + auto-restart
- Audit `clawos_core/circuit_breaker.py` — wire it into every cross-service
  HTTP call (currently runtime calls desktopd HTTP, agent calls memd, etc).
- `services/dashd/api.py` `/api/health` should report each daemon's true
  status, not just "I'm up." Walk every daemon's `/health` endpoint.
- Failed daemons surface in the dashboard Overview page with a "restart"
  button.
- systemd unit files in `systemd/` — verify `Restart=always` and reasonable
  `RestartSec=`. If running on macOS later, do the launchd equivalent.

#### 3.3 Resource limits
- Cap ChromaDB at 2GB on disk (rotate old vectors into archive).
- Hard-cap agent loop turn count at MAX_ITERATIONS (already 8, verify it
  triggers the fallback, doesn't infinite-loop).
- `runtimes/agent/runtime.py` — verify `_history` is trimmed properly
  (it uses `MAX_HISTORY * 2`).
- Add a runaway-tool detector: if the same tool is called >5x in one turn
  with the same args, abort and tell the user.

#### 3.4 Security pass
- Re-read `services/toolbridge/service.py` `SHELL_ALLOWLIST` — is anything
  in there exploitable? E.g. `python3` allows arbitrary code via `-c`.
  Tighten: maybe restrict `python3` to require a script path inside the
  workspace.
- `runtimes/agent/tools/system.py` `_SHELL_ALLOW` mirrors this — keep them
  in sync. Better: import the canonical list from one place.
- `runtimes/agent/tools/files.py` `_resolve()` — verify it can't escape
  the workspace via `../../../etc/passwd` style paths. The toolbridge
  resolves before policy check; tools/files.py should also clamp.
- `runtimes/agent/tools/web.py` — DuckDuckGo only. Verify no SSRF via
  redirect to internal IPs. Use `httpx` redirect filter if needed.
- `runtimes/agent/tools/files.py` `open_url` — already restricts to
  http/https. Good.
- Sensitive-tool list (`tool_schemas.SENSITIVE_TOOLS`) currently has
  `close_app`, `write_file`, `run_command`. Should `open_url` be sensitive?
  (Probably no — webbrowser.open is harmless.) Should `set_volume` to 100
  be sensitive at 3am? (Out of scope, fun later idea.)
- Workspace path escape: write a test that asserts `read_file` with
  `../../../etc/passwd` returns `[ERROR]` and never reads the file.

#### 3.5 Structured logging
- Every daemon logs JSON lines to `~/clawos/logs/{daemon}.log`.
- Log rotation: 10MB per file, 5 files retained. Use Python's
  `RotatingFileHandler`.
- Secret redaction: scrub anything matching `api[_-]?key`, `token`, `secret`,
  `password`, `bearer`. Use the existing `services/memd/taosmd/secret_filter.py`
  if its API fits.
- New `clawctl logs [daemon]` subcommand — tail logs in colour.

**Definition of done:** kill any single daemon, agent keeps running,
gracefully tells user what's broken. No exception ever escapes a tool call.
Workspace escape tests pass. `clawctl logs` works.

### Phase 4 — Onboarding gaps (1.5 days)

#### 4.1 Calendar importer
- New file: `tools/calendar_import.py`.
- Two paths:
  - **Google Calendar OAuth** — uses google-auth-oauthlib, stores token in
    `~/.clawos/secrets/google_calendar.json`. Periodically syncs to ICS in
    `~/.clawos/calendars/google.ics`. Refresh every 30 min.
  - **Raw ICS URL** — user pastes a webcal:// or .ics URL, we sync it.
- Wizard integration: add a card on `VoiceScreen` or new `CalendarScreen`
  saying "Connect a calendar so JARVIS can brief you each morning."

#### 4.2 News feeds UI
- New dashboard page: `dashboard/frontend/src/pages/News.tsx`.
- CRUD on `~/.clawos/news_feeds.txt`. Preview top 3 headlines per feed.
- Default feeds shipped: BBC, HN, Verge, Ars Technica.

#### 4.3 Weather location
- Add to setup wizard `VoiceScreen` or `ProfileScreen`: a "Where are you?"
  text field. Defaults to IP geolocation.
- Persist to `memd` PINNED.md as `User location: {city}` so morning
  briefing weather lookup defaults to it.

#### 4.4 PINNED.md GUI editor
- Existing `dashboard/frontend/src/pages/Memory.tsx` may already have parts.
  Audit. If not, add a "Pinned facts" section with edit/delete on each line.
- Backed by memd's `read_pinned` / `append_pinned` / `write_pinned`.
- Big trust win: users see exactly what JARVIS knows about them.

**Definition of done:** new user can connect a calendar in 60 seconds.
News feeds editable from dashboard. Weather location persists. Pinned
memory editable.

### Phase 5 — Distribution & marketing (2 days)

#### 5.1 README rewrite
File: `README.md`. New structure:
1. Hero: one-line tagline ("Local AI agent for your machine. Zero cloud, zero API keys, zero telemetry.")
2. Three demo GIFs at top (created in 5.3)
3. One-line install: `curl -fsSL https://install.clawos.io | bash`
4. "What makes this different" — 4 bullets max
5. "How it works" — diagram (text-art is fine)
6. Roadmap teaser
7. License + community links

#### 5.2 Landing page
- Audit `landing/`. If it's React, polish. If it's static HTML, polish.
- Same hero, same demo GIFs/videos, big install CTA.
- Add a prominent "Zero telemetry. Verify it yourself" badge.

#### 5.3 Demo videos (4 × 60s clips)
1. **Morning briefing** — user says "good morning", JARVIS speaks 4-line
   briefing. Show it's running offline (e.g. Wi-Fi disabled in the corner).
2. **Essay to editor** — user says "write me a 1000 word essay about AI
   ethics and paste it into the text editor", essay appears in gedit, JARVIS
   says "Done. Your essay's in the editor — 1,024 words."
3. **Approval popup** — user says "delete config.json", floating popup
   appears, user clicks Approve, file is deleted.
4. **Quirky combo** — "set volume to 30 and play spotify", instant.

Use `peek` or `obs-studio` to record. Encode to MP4 + GIF (GIF for README,
MP4 for landing/Twitter).

#### 5.4 Stable installer URL
Set up `install.clawos.io` as a redirector to the GitHub raw URL. Cloudflare
Workers or a simple nginx config. Document the setup so the human can rotate
the underlying URL without breaking the install command.

#### 5.5 Linux distribution packages
- **AppImage** — use `appimagetool`. Bundle the venv + binaries. Output
  `ClawOS-x86_64.AppImage` per release.
- **.deb** — use `dpkg-deb` or `fpm`. Test on Ubuntu 22.04 + 24.04.
- **AUR** — write `PKGBUILD`, submit to AUR as `clawos-bin`.
- All three downloadable from the GitHub Releases page.

**Definition of done:** `install.clawos.io` resolves and installs cleanly.
README has 3 demo GIFs above the fold. AppImage runs on a fresh Ubuntu.

### Phase 6 — Pre-launch dry run + ship (0.5 day)

1. Fresh Ubuntu 24.04 VM, never touched ClawOS.
2. Run the install. Time it.
3. Walk through wizard. Time it.
4. Run all 4 demos. Re-record final videos if anything looks off.
5. Tag `v1.0.0`. Push.
6. Build release artifacts (AppImage, .deb). Upload to GitHub Releases.
7. Write HN submission text. Title format: "Show HN: ClawOS – local-first
   JARVIS that runs on your laptop". Submit at 8AM EST Tuesday or Wednesday.
8. Schedule ProductHunt for same day.
9. Twitter thread queued.

**Definition of done:** v1.0.0 tagged, release artifacts up, submitted to
HN.

### Phase 7 — macOS fast-follow (3-4 days, after launch)

Run after v1.0 is in users' hands but BEFORE the launch buzz dies.

1. **Test all demos on macOS Sonoma 14 + Sequoia 15.** Most platform branches
   are already in the tools — verify each one works.
2. **Tauri overlay on macOS** — verify `always_on_top` behaves on macOS
   Spaces, doesn't break full-screen apps.
3. **Code sign + notarize the Tauri binary.** Apple Developer cert ready by
   this point. Use `tauri build --target universal-apple-darwin` for ARM
   + Intel.
4. **Homebrew formula** — `brew tap clawos/tap` + `brew install clawos`.
5. **macOS demo videos** — same 4 demos, recorded on a Mac.
6. **macOS quirks to expect:**
   - Accessibility permissions for input automation (paste/type) require
     user to grant in System Settings → Privacy → Accessibility.
   - `osascript` requires Automation permission for cross-app focus.
   - The setup wizard should detect missing permissions and link to the
     System Settings panel directly (Tauri has APIs for this).
7. Tag `v1.1.0`, ship.

---

## 7. Working conventions

### Commits
- Style: `type(scope): brief description` — match existing repo. Examples:
  - `fix(install): handle missing python3 on Debian 12`
  - `feat(reminderd): notification daemon for due reminders`
  - `refactor(toolbridge): consolidate shell allowlist into single module`
- Trailer: end with `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>`
- Commit small + often. One logical change per commit. Never bundle unrelated
  changes.
- Push to `main` ONLY when the human says so. Otherwise commit locally and
  surface them.

### Tests
- Unit tests in `tests/unit/test_*.py`. Match existing patterns —
  `tests/unit/test_agent_*.py` is the most current style.
- Run `python -m pytest tests/unit/test_agent_*.py -q` after every change
  to runtime/, services/, or adapters/.
- Don't write tests that hit live LLMs. Mock or skip.

### Code style
- Python: stdlib + the deps already in `pyproject.toml`. Don't add new heavy
  deps without strong justification.
- Comments: WHY only, never WHAT. The code already explains what.
- New files: SPDX-License-Identifier header at top, docstring explaining
  the module's role.
- Type hints encouraged but not enforced everywhere — match the surrounding
  file's style.

### Where things live
- New agent tools → `runtimes/agent/tools/{category}.py`
- New tool schemas → `runtimes/agent/tool_schemas.py` + add to `ALL_TOOLS`
  registry. Also register in `runtimes/agent/tools/__init__.py` `NATIVE_TOOLS`.
- New daemons → `services/{daemon}d/` with `main.py`, `service.py`,
  `health.py`, `__init__.py`. Add to systemd units in `systemd/`.
- New dashboard pages → `dashboard/frontend/src/pages/{Page}.tsx`. Register
  in `dashboard/frontend/src/App.tsx` `ShellRoutes`.
- Setup wizard screens → `dashboard/frontend/src/pages/setup/screens/`.
  Order in `SetupPage.tsx` `STEPS` array.

---

## 8. Tools and commands you'll need

### Run the test suite
```bash
python -m pytest tests/unit/test_agent_*.py -q
python -m pytest tests/unit -q              # all unit tests
python -m pytest tests/system -q            # system tests (slower)
```

### Drive the agent from CLI
```bash
clawos                          # interactive REPL with the new runtime
clawctl wf list                 # list workflows
clawctl framework list          # list installed frameworks
clawctl model set qwen2.5:7b    # change the active model
```

### Inspect what's running
```bash
systemctl --user status clawos-dashd clawos-memd clawos-policyd clawos-voiced
journalctl --user -u clawos-dashd -f       # tail logs
curl http://localhost:7070/api/health       # dashd health
curl http://localhost:7070/api/approvals    # pending approvals
```

### Rebuild Tauri overlay
```bash
cd desktop/command-center
npm install
npm run tauri build      # release binary
npm run tauri dev        # dev mode with hot reload
```

### Manual demo trigger (no voice)
```bash
python -c "
import asyncio
from runtimes.agent.runtime import build_runtime
async def main():
    rt = await build_runtime()
    print(await rt.chat('good morning'))
asyncio.run(main())
"
```

---

## 9. When to ask the human

Default behaviour: **just do the thing.** Ask only when:
- A locked decision (Section 3) appears wrong and you want to reopen it
- You need credentials, API keys, or external accounts
- You want to push to `main` (always ask)
- You discover a fundamental architectural issue that changes the plan
- You're about to delete >100 lines of working code

Don't ask when:
- A small refactor would clean things up — just do it
- You discover a tool or test is flaky — fix it
- The README needs better wording — write it
- A dependency needs adding for a small reason — add it, document why

---

## 10. Definition of done — launch criteria

ClawOS v1.0 ships when ALL of these are true:

- [ ] `bash install.sh` completes cleanly on a fresh Ubuntu 24.04 VM in
      under 120 seconds
- [ ] All 9 setup wizard screens render and function without JS errors
- [ ] User can reach "Welcome home" screen end-to-end
- [ ] All 4 flagship demos run reliably (morning briefing, essay-to-editor,
      approval popup, quirky combo)
- [ ] `python -m pytest tests/unit -q` shows 0 failures
- [ ] No exception ever propagates out of a tool call
- [ ] Reminders fire as desktop notifications
- [ ] Daemons survive being killed (auto-restart with backoff)
- [ ] Workspace escape attempts are blocked with a test proving it
- [ ] README has 3 demo GIFs above the fold
- [ ] `install.clawos.io` resolves and installs cleanly
- [ ] AppImage built and uploaded to GitHub Releases for v1.0.0
- [ ] Tag `v1.0.0` exists and is pushed
- [ ] HN submission text drafted in `docs/LAUNCH/hn_submission.md`
- [ ] Twitter thread drafted in `docs/LAUNCH/twitter_thread.md`

ClawOS v1.1 ships when:

- [ ] All 4 demos run on macOS Sonoma + Sequoia
- [ ] Tauri binary code-signed and notarized
- [ ] Homebrew formula published and `brew install clawos` works
- [ ] macOS demo videos recorded
- [ ] Tag `v1.1.0` exists and is pushed

---

## 11. Appendix — useful greps

```bash
# Find all platform-specific code
grep -rn "is_linux\|is_macos\|is_windows" runtimes/ services/ clawos_core/

# Find all tool schemas
grep -n "_tool(" runtimes/agent/tool_schemas.py

# Find all current dashboard routes
grep "Route path" dashboard/frontend/src/App.tsx

# Find all setup wizard steps
grep "Component:" dashboard/frontend/src/pages/setup/SetupPage.tsx

# Find all systemd service units
ls systemd/

# Find every place we touch the Ollama API
grep -rn "ollama.Client\|ollama.chat\|OLLAMA_HOST" runtimes/ services/

# Pending approval API consumers (so you don't break them)
grep -rn "approvals\|approve" services/dashd/ dashboard/frontend/src/

# Existing workflows (so the run_workflow tool stays consistent)
ls workflows/ | grep -v "^_" | grep -v "^\."
```

---

## 12. Final notes

- **The human's vision matters more than this plan.** If you're forced to
  choose between "the plan said X" and "this would clearly serve the
  vision better," choose the vision. The vision is in Section 2.
- **Local-first is religion.** Every decision should preserve "no cloud,
  no API keys, works offline." If a feature requires the cloud to function
  at all, it's wrong.
- **Demos > features.** A polished morning briefing beats a feature-complete
  but flaky one. Cut features to make demos solid.
- **The launch window is short.** HN attention dies in 24 hours.
  ProductHunt in 7 days. The Twitter buzz needs the demo videos to land.
  Optimize for that window, not for some imagined future user.

Good luck. Ship it.
