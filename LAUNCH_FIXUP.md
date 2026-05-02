# ClawOS — Launch Fix-up Brief (Agent Brief #2)

> **Read this whole file before doing anything.** Then read `LAUNCH_PLAN.md`
> for the foundational context (vision, architecture, conventions). This
> brief is a corrective overlay — it tells you what the previous agent
> shipped, what it got wrong, and exactly what to fix to get to a real
> launchable state.

---

## 0. Read this first

A previous agent was given `LAUNCH_PLAN.md` (covering Phases 1–7) and
delivered a partial pass that it self-declared "ALL PHASES COMPLETE" and
tagged as `v0.1.0`. The engineering work it did is mostly real and good.
The problem is what it **didn't** do, and a few things it changed that
shouldn't have changed. **Do not redo its good work. Do fix its gaps and
revert its product-story drift.**

Run these to see the lay of the land:

```bash
git log --oneline a82e83f..HEAD       # commits since the original Nexus loop
git show v0.1.0 --stat                # what got tagged
cat LAUNCH_BLOCKERS.md                # the previous agent's self-report
cat README.md                         # the regressed README — read this carefully
```

---

## 1. What the previous agent shipped (KEEP, do not rebuild)

| Artifact | Status |
|----------|--------|
| `services/reminderd/` (port 7087) | Real, FastAPI, SQLite, lifespan handlers |
| `services/waketrd/` (port 7088) | Real, bridges voiced wake → morning briefing |
| `tools/calendar/import_ics.py` | Real, 331 lines, ICS importer with SQLite |
| `tests/integration/test_reminderd.py`, `test_waketrd.py`, `test_calendar.py` | 7 pass, 5 skip — green |
| `clawctl demos`, `clawctl health` subcommands | Real |
| FastAPI lifespan migration (`clawos_core/fastapi_lifespan.py`) | Real |
| `packaging/iso/build_iso.sh` + Calamares config + chroot install | Real, but see Section 4 |
| `scripts/validate_install.sh` | Real |
| `RELEASE_NOTES_v0.1.0.md` | Mostly fine — minor tweaks needed |
| `v0.1.0` git tag | Keep it. Ship fixes as `v0.1.1`. Do not rewrite history. |
| `PORT_REMINDERD=7087`, `PORT_WAKETRD=7088` in `clawos_core/constants.py` | Keep |

The 60 unit tests from `tests/unit/test_agent_*.py` still pass. The
12 integration tests still pass. Don't touch them unless you change the
behaviour they test.

---

## 2. Locked decisions for THIS prompt — DO NOT relitigate

These are the corrections to the previous agent's drift. Don't reopen them.

| Decision | Choice |
|----------|--------|
| **Primary install method** | `curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh \| bash` — same as `LAUNCH_PLAN.md`. The agent pivoted to "bootable ISO is the headline." That's wrong. ISO is an OPTIONAL secondary distribution. |
| **Product framing** | "Local AI agent for your existing machine." NOT "bootable Linux distro." A user keeps their existing OS and adds JARVIS — they don't wipe their laptop. |
| **Wake word** | "Hey Claw" — the codebase uses this. The README says "Hey JARVIS" — that's wrong, fix the README, not the code. |
| **WhatsApp / Telegram** | **Removed earlier in the project. The README adding them back is a regression.** Strip every mention. |
| **OpenClaw skills count** | The README says "13,700+ community skills." That's OpenClaw's number, not ClawOS's, and OpenClaw is one of several optional brain choices in the wizard. Drop the inflated claim. Say honestly: "Bring your own agent brain (OpenClaw, Hermes, or use the built-in Nexus)." |
| **Telemetry** | Still zero. Forever. |
| **Launch order** | Linux v1.0 first → macOS v1.1 fast-follow. Same as before. |
| **Version after this fixup** | `v0.1.1`. Tag once everything in Section 5 is green. |
| **Tauri overlay** | Must be rebuilt and bundled in the v0.1.1 release — the previous agent did not do this. |
| **Demo videos** | **Required for launch.** The previous agent skipped them. They are non-negotiable for HN/PH. |

---

## 3. The README regressions — fix these first

`README.md` was rewritten by the previous agent and contains explicit
regressions. **Open `README.md` and fix each of the following:**

1. **Line ~19 — `13,700+ community skills`** → replace with: `Bring your
   own agent brain — Nexus (built-in), OpenClaw, or any framework with
   plugin hooks.`
2. **Line ~23 — `WhatsApp/Telegram integration`** → DELETE this bullet
   entirely. We don't have those integrations and we removed the WhatsApp
   code earlier in the project.
3. **Line ~116 — architecture diagram includes `WhatsApp │ Telegram`** →
   remove those columns from the ASCII diagram.
4. **Line ~235 — `OpenClaw — The original 13,700+ skill ecosystem`** →
   change to: `OpenClaw — Optional power-user agent brain.`
5. **Wake word references** — search for `Hey JARVIS` in the README and
   replace with `Hey Claw` (the actual phrase voiced uses).
6. **Demo section** — the README currently says "Watch on YouTube *(coming
   soon)*". You're going to record those videos in Section 5 — replace the
   placeholder with the real URLs once you have them.
7. **Headline framing** — the current README leads with "Flash a USB. Boot.
   Your AI agent is running locally." That's the ISO story. Reframe the
   headline to: "Local AI agent for your laptop. One curl command. No
   cloud. No API keys. No telemetry." Lead with the curl install. Make
   the ISO an Option 2.

After fixing, sanity-check:
```bash
grep -i "whatsapp\|telegram\|13.700\|13,700\|hey jarvis" README.md
# should print nothing
```

---

## 4. Distribution model — restore curl|bash as primary

The plan was `curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh | bash`. The previous
agent built a full bootable ISO instead and made it the primary install
path. **The ISO is fine as an optional distribution. It is NOT the primary
install path.** Most users want to add JARVIS to their existing machine,
not wipe their laptop.

What to do:

1. **Verify `bash install.sh` still works** on a clean Ubuntu 24.04 box.
   The previous agent didn't test this end-to-end after its changes.
   Track every break and fix inline. This is now Phase 1 of `LAUNCH_PLAN.md`
   and is non-negotiable.
2. **Wire `reminderd` and `waketrd` into `install.sh`** — they exist but
   nothing starts them on a fresh install. Specifically:
   - Add systemd unit files: `systemd/clawos-reminderd.service`,
     `systemd/clawos-waketrd.service`. Match the pattern of existing units.
   - Add their service names to the `ALL_UNITS` list (or wherever
     `install.sh` registers daemons for autostart).
   - Verify they start with `systemctl --user start clawos-reminderd
     clawos-waketrd` after install.
3. **Add the install URL** — register `install.clawos.io` (Cloudflare
   Worker / pages redirect / nginx 301 to the GitHub raw URL of
   `install.sh`). Document the setup in `docs/INSTALL_URL_SETUP.md` so
   the human can rotate the underlying URL without breaking installs.
4. **Build distribution packages** — AppImage + .deb + AUR `PKGBUILD`,
   downloadable from the GitHub Releases page for `v0.1.1`. The ISO is
   listed below them as an optional install for "dedicated machine" users.

---

## 5. Demo path verification (required, not optional)

The previous agent's `clawctl demos` subcommand exists but I have no
evidence the demos actually work end-to-end with a live LLM. Verify every
demo on the dev box:

### 5.1 Morning briefing
```bash
clawctl demos morning-briefing
```
Should: gather time + weather + calendar + reminders + memory in parallel,
synthesize via qwen2.5:7b, speak via Piper. **Must work fully offline
(weather degrades to [OFFLINE] gracefully).**

### 5.2 Essay-to-editor
```bash
clawctl demos essay-editor
```
OR drive it through the agent directly:
```bash
clawos
> write me a 1000 word essay about AI ethics and paste it into the text editor
```
Should: 4 tool calls in one batch (write_text → set_clipboard → open_app →
paste_to_app), essay appears in gedit, JARVIS confirms verbally.

### 5.3 Approval popup
```bash
clawctl demos approval-test
```
Should: trigger a sensitive tool, **floating popup appears on screen**
(not in the dashboard tab), Y/N keyboard works, decision flows back to the
runtime.

**Critical: rebuild the Tauri binary before testing this.** The overlay
commands (`show_approval_overlay`, `hide_approval_overlay`) were added in
`a82e83f` but the desktop binary needs rebuilding for them to be exposed.
```bash
cd desktop/command-center
npm install
npm run tauri build
```

### 5.4 Quirky combo
```bash
clawos
> set volume to 30 and play spotify
```
Should: two tools chained, runs in <3s.

For each demo, **document what works, what's flaky, what's broken** in
`docs/DEMOS.md`. If a demo is flaky, **fix the tool description in
`runtimes/agent/tool_schemas.py`** — the LLM follows the schema description
closely. Better descriptions > more tools.

---

## 6. The hard launch deliverables (where the previous agent dropped the ball)

### 6.1 `docs/DEMOS.md`
Write this file. For each of the 4 demos: exact phrasing, expected tool
calls, expected timing, expected reply. This file is what gets read aloud
in the demo videos.

### 6.2 Demo videos (4 × 60s)
**Required for launch. The previous agent skipped these.**

Use `peek` (Linux GIF recorder) or `obs-studio` (full video). Record:
1. Morning briefing — show Wi-Fi disabled in corner to prove offline
2. Essay-to-editor — show the essay appearing live in gedit
3. Approval popup — show the floating window over a real desktop
4. Quirky combo — "set volume + play spotify"

Encode each to:
- MP4 (for landing page, Twitter)
- GIF ≤8MB (for README, GitHub)

Save originals + GIFs to `docs/media/demos/`. Reference them in the README
hero section.

### 6.3 Landing page
- Audit `landing/`. Whatever framework it uses (React / static HTML),
  polish it.
- Hero matches the README: "Local AI agent for your laptop. One curl
  command. No cloud. No API keys. No telemetry."
- Embed all 4 demo videos.
- Big install command (copyable).
- "Zero telemetry. Verify it yourself." badge linked to the no-telemetry
  proof in the codebase.
- CTA: GitHub stars + install command.

### 6.4 HN submission text
File: `docs/LAUNCH/hn_submission.md`. Title format:
`Show HN: ClawOS – local-first JARVIS that runs on your laptop`
Body: 150 words max, link to GitHub, link to landing, three demo GIFs
embedded.

### 6.5 ProductHunt copy
File: `docs/LAUNCH/producthunt.md`. Tagline (60 chars max), description
(260 chars max), 5 gallery images (the demo GIFs + screenshots).

### 6.6 Twitter launch thread
File: `docs/LAUNCH/twitter_thread.md`. 6-tweet thread:
1. Hook + 1 demo GIF + install command
2. The vision (1 paragraph)
3. Demo 2 (essay-to-editor GIF)
4. Demo 3 (approval popup GIF)
5. "Zero telemetry, fully offline" + tech stack
6. Star us + install link

---

## 7. Production hardening (Phase 3 from `LAUNCH_PLAN.md` — also skipped)

Do this BEFORE tagging `v0.1.1`.

### 7.1 Error handling sweep
Walk every tool in `runtimes/agent/tools/`. For each, identify failure
modes (network down, file not found, permission denied). Make sure each
returns `[ERROR] ...` or `[OFFLINE] ...` strings, never raises out of
`dispatch_tool`. Run through:
```bash
# kill ollama mid-conversation
killall ollama
# agent should reply "I'm offline right now" not crash
```

### 7.2 Daemon health + auto-restart
- `systemd/*.service` files: verify `Restart=always`, `RestartSec=5`.
- `services/dashd/api.py /api/health` reports each daemon's true status.
- Add reminderd + waketrd to the health endpoint.

### 7.3 Security pass
- Re-read `services/toolbridge/service.py` `SHELL_ALLOWLIST`.
  `python3` allows `-c <code>` — restrict to script paths inside workspace.
- `runtimes/agent/tools/system.py` `_SHELL_ALLOW` mirrors this — keep in
  sync. Better: import from one canonical module.
- `runtimes/agent/tools/files.py` `_resolve()` — write a test that asserts
  `read_file({"path": "../../../etc/passwd"})` returns `[ERROR]` and never
  reads the file. Add to `tests/unit/test_agent_tools.py`.
- `runtimes/agent/tools/web.py` — verify httpx redirects can't reach
  internal IPs (SSRF guard).

### 7.4 Logging
- Structured JSON logs to `~/clawos/logs/{daemon}.log`.
- 10MB rotation, 5 files retained (`RotatingFileHandler`).
- Secret redaction via existing `services/memd/taosmd/secret_filter.py`
  if the API fits.
- `clawctl logs [daemon]` tail-with-colour subcommand.

---

## 8. Order of operations

Execute in this order. Don't reorder unless you hit a hard block.

1. **README fixes** (Section 3) — half a day. Most embarrassing if it
   ships as-is.
2. **Daemon wiring** (Section 4.2) — half a day. Reminderd/waketrd not
   autostarting is a "we shipped a feature that doesn't run" bug.
3. **Install verification on clean Ubuntu** (Section 4.1) — 1 day.
   This is the foundation. Until you've run `bash install.sh` end-to-end
   on a fresh box, everything else is theoretical.
4. **Tauri overlay rebuild** (Section 5.3) — 2 hours. Without this, the
   approval-popup demo doesn't actually work.
5. **Demo verification** (Section 5) — 1 day. Each demo runs reliably
   end-to-end.
6. **Production hardening** (Section 7) — 2 days. Error sweep + security
   pass + logging.
7. **Distribution packages** (Section 4.4) — 1 day. AppImage + .deb +
   AUR + install URL.
8. **Demo videos + landing page** (Section 6) — 2 days. The actual
   marketing artifacts.
9. **HN / ProductHunt / Twitter copy** (Section 6.4-6.6) — 0.5 day.
10. **Tag `v0.1.1` and ship** — 0.5 day. Build release artifacts, upload
    to GitHub Releases, submit to HN at 8AM EST Tuesday.

**Total: ~9 days from now to actual launch.**

---

## 9. What NOT to do

- **Do not** pivot the product story again. The product is "local AI
  agent for your existing machine." Not a Linux distro, not a SaaS,
  not a "JARVIS marketplace."
- **Do not** add new features. The scope is fixing what's broken and
  finishing the launch prep. New features go in v0.2.
- **Do not** rewrite working code that has tests. Read first, change
  surgically.
- **Do not** delete the `v0.1.0` tag or rewrite history. Ship `v0.1.1`.
- **Do not** add WhatsApp, Telegram, or any cloud integrations.
- **Do not** add telemetry, even opt-in. Zero forever.
- **Do not** declare "ALL PHASES COMPLETE" until every checkbox in
  Section 11 is verifiably green.

---

## 10. When to ask the human

- Before pushing to `main` (always)
- Before tagging `v0.1.1`
- If you find that `install.sh` is fundamentally broken in a way that
  needs design input (not just bug fixes)
- If the LLM behaviour for a demo is consistently wrong despite tweaking
  the tool schemas — may need to swap the model recommendation
- If the Tauri overlay can't be made to behave on Wayland — may need
  a fallback strategy

Don't ask for: small refactors, README wording, dependency adds with
clear justification, fixes you can verify yourself.

---

## 11. Definition of done — `v0.1.1` ships when

### Sanity
- [ ] `grep -i "whatsapp\|telegram\|13.700\|13,700\|hey jarvis" README.md`
      prints nothing
- [ ] README hero leads with `curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh | bash`
- [ ] Wake word everywhere is "Hey Claw"

### Install + autostart
- [ ] `bash install.sh` completes cleanly on fresh Ubuntu 24.04 in <120s
- [ ] After install, `systemctl --user list-units 'clawos-*'` shows
      reminderd + waketrd running
- [ ] `install.clawos.io` resolves and serves `install.sh`

### Demos
- [ ] All 4 demos in `docs/DEMOS.md` run reliably on the dev box
- [ ] Tauri overlay window appears on screen during `clawctl demos
      approval-test`
- [ ] Each demo has a 60s recorded video in `docs/media/demos/`
- [ ] Each demo has a GIF ≤8MB in `docs/media/demos/`
- [ ] All 4 demo GIFs are embedded in the README

### Production
- [ ] Killing any single daemon doesn't crash the agent loop
- [ ] `tests/unit/test_agent_tools.py` includes a workspace-escape test
      that passes
- [ ] `clawctl logs [daemon]` works
- [ ] No tool ever raises an exception out of `dispatch_tool` (verify
      by running through every demo with `OLLAMA_HOST=http://invalid:1`)

### Distribution
- [ ] AppImage built and uploaded to GitHub Releases for `v0.1.1`
- [ ] `.deb` built and uploaded
- [ ] AUR `PKGBUILD` submitted as `clawos-bin`
- [ ] ISO builder still works (regression check on the previous agent's
      work)

### Marketing
- [ ] Landing page (`landing/`) finished, polished, all demos embedded
- [ ] `docs/LAUNCH/hn_submission.md` drafted
- [ ] `docs/LAUNCH/producthunt.md` drafted
- [ ] `docs/LAUNCH/twitter_thread.md` drafted

### Release
- [ ] `RELEASE_NOTES_v0.1.1.md` written
- [ ] `git tag v0.1.1` exists and is pushed
- [ ] GitHub Release created with all artifacts attached
- [ ] Human has explicitly said "ship it"

---

## 12. Quick reference — file paths you'll touch most

```
README.md                                   # primary fix target
install.sh                                  # add reminderd/waketrd autostart
systemd/clawos-reminderd.service            # NEW (mirror an existing unit)
systemd/clawos-waketrd.service              # NEW
docs/DEMOS.md                               # NEW
docs/media/demos/                           # NEW (videos + GIFs)
docs/LAUNCH/hn_submission.md                # NEW
docs/LAUNCH/producthunt.md                  # NEW
docs/LAUNCH/twitter_thread.md               # NEW
docs/INSTALL_URL_SETUP.md                   # NEW
RELEASE_NOTES_v0.1.1.md                     # NEW
landing/                                    # polish
desktop/command-center/                     # rebuild Tauri binary
runtimes/agent/tools/                       # error handling sweep
services/toolbridge/service.py              # tighten shell allowlist
services/dashd/api.py                       # add reminderd/waketrd to /api/health
clawctl/                                    # add `clawctl logs` subcommand
tests/unit/test_agent_tools.py              # add workspace-escape test
```

---

## 13. Final notes

- The previous agent made a habit of self-declaring completion when work
  was not actually verifiable. **Don't do that.** Every checkbox in
  Section 11 must be a thing you have actually run and seen succeed —
  not a thing you wrote code for.
- If you can't verify something on the dev box (e.g. demo video recording
  needs human hands), explicitly note "needs human" and surface it.
- The launch is real and time-sensitive. The vision in `LAUNCH_PLAN.md`
  Section 2 still applies. Re-read it if you're about to make a judgment
  call.

Ship it properly this time.
