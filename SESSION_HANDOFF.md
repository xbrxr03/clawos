# Session Handoff — ClawOS Launch Push

> Living doc updated at the end of each session so the next agent picks
> up with full context, no reconstruction required.

**Last updated:** 2026-05-01
**Current state:** v0.1.1 tagged, polish complete, **active live-install
debugging on user's Linux dev box.**

---

## TL;DR for the next agent

ClawOS is days away from a Linux v1.0 launch. The codebase is
"testing-ready" — every code-only task in the plan is done. The work
right now is **the human running `bash install.sh` on their actual
Linux machine and surfacing real-world failures for inline fixing.**

If you're picking up mid-stream, **first thing:** ask the user what
state the install is in. They might be debugging Phase 1-6 of the
clean-wipe-then-reinstall sequence in the prior session.

---

## Read these in order

1. **`LAUNCH_PLAN.md`** — the original 7-phase product+launch plan.
   Section 2 ("the product vision") is the lodestar. If a decision
   feels ambiguous, it answers it.
2. **`LAUNCH_FIXUP.md`** — written after the first launch agent's
   drift. Tells you what NOT to redo and what's already real.
3. **This file** — current session-by-session state.
4. **`LAUNCH_CHECKLIST.md`** — the human-only tasks list.

You don't need to re-read `LAUNCH_BLOCKERS.md` — it's a historical
artifact from the previous agent's premature "ALL PHASES COMPLETE"
declaration. Kept in repo for context, not for guidance.

---

## What's been built and shipped

### Code-complete (in main, both v0.1.0 and v0.1.1 tagged)

- **Native Nexus agent loop** with native Ollama function calling, 4-tier
  priority pipeline (memory fast-path → confirmation → deterministic
  intent → LLM with tools), dynamic 3b/7b/coder routing
- **31 tools** across 8 modules (system, desktop, compose, files,
  knowledge, productivity, workflows, web). Linux primary, macOS
  branches present, Windows deferred.
- **reminderd** (port 7087) — desktop notification daemon
- **waketrd** (port 7088) — wake-word → morning-briefing bridge
- **Calendar ICS importer** at `tools/calendar/import_ics.py`
- **Tauri floating approval overlay** (rebuilt for v0.1.1)
- **Distribution scripts**: AppImage, .deb, AUR PKGBUILD, ISO builder
- **clawctl doctor** extended to check the new daemons + tool-registry
  coherence
- **Dashboard frontend rebuilt** (compiled bundle matches source TSX
  fixes — no more "ReAct loop" or "13,700+ skills" leaks)
- **Launch copy** drafted: `docs/LAUNCH/{hn_submission,producthunt,
  twitter_thread}.md`
- **Release notes** for both v0.1.0 and v0.1.1
- **CONTRIBUTING.md** with the hard "no telemetry" line
- **README** rewritten — accurate, no false claims

### Tests
- 61/61 unit pass (`tests/unit/test_agent_*.py`)
- 7/12 integration pass (5 skip — require live services)
- All shell scripts pass `bash -n`
- All critical Python compiles
- Tool registry: 31 schemas == 31 dispatchers, no orphans

### Recent commit log (newest first)

```
d66aee3 feat(openclaw): prefer ollama launch openclaw over npm install
93621b3 chore(polish): pre-test polish pass — frontend rebuild + doctor extension
2aacea0 fix(audit): close v0.1.1 launch gaps from thorough audit pass
4e0911e docs(launch): polish audit pass — accurate README, honest demos, real release notes
186e68b chore(version): bump to v0.1.1
dec0d12 feat(demos): complete all 4 demos with videos/GIFs    [previous agent — videos were placeholders, deleted in 4e0911e]
9f11234 fix(demos): essay editor + add demo videos/GIFs       [previous agent — same]
6d6e31f docs(launch): HN, ProductHunt, Twitter copy
ce5bda8 feat(dist): AppImage, AUR, install URL docs
830e7c1 feat(logging): structured JSON + rotation + clawctl logs
```

---

## Locked decisions — DO NOT relitigate

These are settled. If a user request seems to reopen one, ask them
directly before changing direction.

| Decision | Choice | Source |
|----------|--------|--------|
| Primary install method | `curl -fsSL https://install.clawos.io \| bash` | `LAUNCH_PLAN.md` Section 3 |
| Telemetry | **Zero. Forever.** | User's repeated emphasis, `LAUNCH_PLAN.md` |
| Launch OS | Linux v1.0, macOS v1.1 | User Apr 30 message |
| Primary local model | qwen2.5:7b-instruct (FAST: 3b, CODER: coder:7b) | Research: 93% F1 tool calling, native Hermes format works with Ollama |
| Tool calling format | Native Ollama function calling | NOT ReAct JSON — that was the old loop, replaced in `a82e83f` |
| Wake word | "Hey Claw" | Code uses this; README must reflect this |
| OpenClaw role | Optional power-user agent brain, not required | Wizard offers "Configure later" |
| WhatsApp/Telegram in our marketing | NO | These are OpenClaw features, not ClawOS — surface only when discussing OpenClaw |
| Distribution channels for v1.0 | AppImage + .deb + AUR + ISO | Skip Homebrew until macOS v1.1 |
| Wizard step count | 9 | `dashboard/frontend/src/pages/setup/SetupPage.tsx` STEPS |
| Version after current fixes | v0.1.1 (tagged) | Don't rewrite v0.1.0 history |

---

## What changed this session

### Major

1. **Frontend rebuilt** — the previous fixup pass corrected source TSX
   files but the compiled bundle in `services/dashd/static/assets/` was
   stale. Rebuilt; new asset hashes; "ReAct loop" / "13,700+ skills"
   leaks gone from what users actually see.

2. **`clawctl doctor` extended** — now checks ports 7080 (desktopd),
   7087 (reminderd), 7088 (waketrd) plus agent tool registry
   coherence. Catches "added a tool but forgot the dispatcher" bugs.

3. **Brain.tsx knowledge graph node fixed** — was labeling Nexus as
   "ReAct loop"; now "agent loop". Standalone "ReAct paper" node kept
   (academic reference, not our loop).

4. **Ollama announced first-class OpenClaw support** (April 30, 2026
   blog: https://ollama.com/blog/openclaw). New install path is
   `ollama launch openclaw`. Implications:
   - Updated `openclaw_integration/installer.py` to try
     `_install_via_ollama_launch()` first, npm fallback
   - Added `_ollama_supports_launch()` probe (looks for "launch" in
     `ollama --help`)
   - FrameworkScreen subtitle reframed: "OpenClaw — now first-class
     in Ollama (`ollama launch openclaw`)"
   - **Implication for v0.2:** the OpenClaw plugin work after launch
     becomes higher leverage — Ollama is investing in OpenClaw as an
     ecosystem, so a "ClawOS upgrades OpenClaw with memory + voice +
     JARVIS persona" plugin lands in a now-blessed ecosystem.

5. **Audit pass found and fixed:**
   - Reminderd + waketrd unit files were installed but never enabled
     by `setup-systemd.sh` — would sit dormant after install. Fixed:
     they're now individually enabled at user login.
   - AUR `PKGBUILD` had `pkgver=0.1.0` while VERSION constant was
     `0.1.1`. Bumped.
   - README linked to non-existent `CONTRIBUTING.md`. Created.

### Minor / housekeeping

- 8 fake placeholder demo videos (all identical MD5) deleted from
  `docs/media/demos/`. Replaced with `README.md` explaining what
  needs to live there + recording targets.
- Twitter Tweet 3 contradicted itself (described both grammar checker
  AND essay generator). Now describes the essay-to-editor chain
  consistently.
- `RELEASE_NOTES_v0.1.1.md` written (was missing).

---

## What's actively in flight

**The user is debugging a clean install on their Linux dev box right
now.** Hardware: 64GB RAM, no GPU. They wiped:
- Old Ollama (binary, models, systemd unit)
- Old OpenClaw (npm global, config dir, gateway)
- Old ClawOS (runtime, data, wrappers, units)
- A stray `~/.clawos_dev_env` file

They're proceeding through Phase 6 (the actual `bash install.sh` run)
and pinging me with errors as they surface.

**If a new session opens mid-debug:**
- Ask what the latest error/state is
- Don't assume the install completed
- The wipe sequence is in the prior session's last assistant turn —
  ~6 phases (stop services → remove OpenClaw → remove Ollama → remove
  ClawOS → sanity check → reinstall)

---

## Hardware context

| Box | RAM | Accel | Use |
|-----|-----|-------|-----|
| Linux dev box | 64 GB | CPU only | Primary v1.0 testing + launch |
| M4 Mac mini | 16 GB unified | Metal | macOS v1.1 testing (later) |

On Linux CPU-only, qwen2.5:7b runs ~5-15 tok/s. Morning briefing ≈
6-12 s (vs 4 s with GPU). Essay-to-editor demo ≈ 30 s for 1000 words
(vs 12-15 s). Acceptable for testing and demo recording.

On M4 Metal, expect comparable or faster than the Linux box despite
fewer cores — Metal acceleration in Ollama is excellent.

---

## Plan from here (what comes next)

### This week — finish Linux v1.0 launch

The 7 human-only tasks in `LAUNCH_CHECKLIST.md`:

1. ✅ **In progress:** install verification on Linux
2. **Pending:** set up `install.clawos.io` redirector
3. **Pending:** record 4 real demo videos (placeholder slot in
   `docs/media/demos/`)
4. **Pending:** build + upload AppImage / .deb to GitHub Release v0.1.1
5. **Pending:** schedule HN / PH / Twitter
6. **Pending:** day-of monitoring

### Next sprint — OpenClaw plugin

After launch lands. The original "make Nexus's stack work for OpenClaw
users via plugin hooks" goal. Now higher leverage given Ollama's
endorsement of OpenClaw. Multi-day work.

Target: `~/.openclaw/plugins/clawos/` that hooks into:
- `bootstrap` — initialize memd, braind, policyd
- `before_prompt_build` — assemble context (intent → PINNED + recall
  + Kizuna + LEARNED) → prependSystemContext
- `agent_turn_prepare` — one-turn injections (WORKFLOW.md, session
  resume briefing)
- `afterTurn` — async ACE + memory write-back + Kizuna expand
- `precompact-extract` — archive conversation before OpenClaw
  truncates

### v0.2 — macOS

After v0.1.x launch is in users' hands. Most platform code is in place
(every platform-aware tool has `is_macos()` branches). Needs:
- End-to-end demo verification on macOS Sonoma + Sequoia
- Tauri overlay behavior on macOS Spaces
- Code signing + notarization (user has Apple Dev cert ready)
- Homebrew formula
- macOS demo videos

---

## Working agreements with this user

These have surfaced repeatedly and matter:

- **Be honest about what's tested vs theoretical.** The previous agent
  declared "ALL PHASES COMPLETE" when ~30% was done; that broke trust.
  Don't do that. Check actual state, report honestly, flag uncertainty.
- **Don't pivot the product story without authorization.** The previous
  agent silently changed ClawOS from "local agent for your machine" to
  "bootable Linux distro" — wrong. The product is local agent first;
  ISO is optional secondary.
- **Don't add features.** Scope is fixing what's broken and finishing
  the launch. New features go in v0.2.
- **Push only when explicitly told.** Default behavior is commit
  locally and surface the result.
- **Use `clawctl doctor` as a smoke test.** It's substantial and
  catches a lot of common issues.
- **Fix-as-you-go is preferred over audit-then-fix.** When debugging
  the live install, fix the root cause inline.

---

## Files / paths the next agent will touch most

| Purpose | Path |
|---------|------|
| Agent runtime | `runtimes/agent/runtime.py` |
| Tool schemas | `runtimes/agent/tool_schemas.py` |
| Tool dispatchers | `runtimes/agent/tools/` |
| Setup wizard | `dashboard/frontend/src/pages/setup/` |
| Wizard backend | `services/setupd/service.py` |
| New daemons | `services/reminderd/`, `services/waketrd/` |
| OpenClaw integration | `openclaw_integration/installer.py` |
| Install script | `install.sh` |
| Daemon orchestrator | `clients/daemon/daemon.py` |
| Service start chain | `scripts/clawos-start.sh` |
| systemd registration | `scripts/setup-systemd.sh` |
| Doctor checks | `setup/repair/doctor.py` |
| CLI surface | `clawctl/main.py`, `clawctl/demos.py` |
| Tauri overlay | `desktop/command-center/src-tauri/src/main.rs` |
| Approval UI | `dashboard/frontend/src/overlays/ApprovalOverlay.tsx` |

---

## When you finish a session

Update this file with:
- New `**Last updated:**` date
- Anything you shipped (append to "What's been built")
- Anything actively in flight (replace the section)
- Anything blocking
- Anything you decided that should be locked

Commit + push so the next session inherits the latest state.
