# ClawOS Shared Update Log

This file is the shared running log for work completed in this repo.

Both Codex and Claude append here after meaningful changes so the next agent
has a clean handoff without re-auditing the whole project.

Treat this file as project memory.

> **Note:** earlier entries (2026-03 through 2026-04-07) were removed in commit
> `7739cf1` ("chore: repo polish pre-HN-launch") and preserved only in git
> history. Run `git show 9b0f577:update.md` to read the last snapshot before
> deletion. This file was resurrected 2026-04-19 to continue the internal
> handoff log.

## How To Use

- Add new notes at the top of the `## Updates Done By Claude` (or equivalent
  agent) section.
- Keep entries factual and concise. Include:
  - date
  - agent
  - what shipped (with commit SHAs)
  - what's pending (with file paths and estimates)
  - verification performed
  - gaps / context notes
- Do not delete older entries unless they are clearly wrong.
- If a future agent changes product direction or discovers a major
  contradiction, record it here instead of silently replacing history.

## Current Canonical Surfaces

- `services/dashd` — dashboard/backend surface (FastAPI, loopback 7070)
- `services/setupd` — guided setup state + flows (port 7084)
- `dashboard/frontend` — React 18 + Vite 5 + TypeScript 5.8 SPA
- `install.sh` — one-shot installer entry point
- `frameworks/` — framework registry + installer + runner
- `memd` — 14-layer memory substrate

## Updates Done By Claude

### 2026-04-19 — Claude (setup wizard React rewrite + kimi-k2.5 launch CTA + session plan)

#### Shipped this session

Two commits on `feat/setup-react-wizard`, opened as PR #40
(https://github.com/xbrxr03/clawos/pull/40):

1. **`04eef9b`** — feat(setup): React 9-screen wizard + framework picker, retire GTK flow
   - Replaces legacy GTK first-run wizard (13 files deleted under `setup/first_run/`)
     with React wizard served by setupd
   - 9 screens: Welcome → Hardware → Profile → Runtimes → Framework → Model →
     Voice → Policy → Summary
   - Framework picker plumbing end-to-end: `selected_framework` field on
     `SetupState`, `/api/setup/frameworks` endpoint on setupd (tier-filtered via
     `FrameworkRegistry.list_for_tier(profile_id)`), dashd proxy of the same
     endpoint, new `FrameworkScreen.tsx` with compatible-first sort and
     disabled-with-reason for incompatible entries
   - `install.sh` reverted from qwen3.5 → qwen2.5 (see "Model strategy note" below)
   - 47 files, +5,104 / −1,952

2. **`3241850`** — feat(setup): surface `ollama launch openclaw` + kimi-k2.5 CTA on done state
   - Post-apply "Welcome home" state now includes a zero-friction JARVIS launch block
   - Copy-to-clipboard button writes `ollama launch openclaw --model kimi-k2.5:cloud`
     with a "Copied ✓" pulse for 1.6 s
   - Sub-text explains the three credit tiers: free Ollama credits → Ollama Pro →
     bring-your-own-key (Anthropic / OpenAI / OpenRouter)
   - Positions JARVIS as "your AI Butler" in copy (see "Branding note" below)

Verification: `npx tsc --noEmit` clean for the frontend. Backend imports verified.
No runtime end-to-end test on a fresh install yet — do that before merging PR #40.

#### Still pending (scoped, not in PR #40)

1. **Framework `_apply()` wiring** — ~30 min
   - FrameworkScreen persists `state.selected_framework` but
     `SetupService._apply()` in `services/setupd/service.py` (line 640) doesn't
     consume it. Picking smolagents today is cosmetic.
   - Hook point: between the identity-memory pin (line 693) and voice-pipeline
     prep (line 694). Call `frameworks.installer.install(name, progress_cb)`.
   - Installer API confirmed at `frameworks/installer.py:180` — takes `name`,
     optional `progress` callback; returns `bool`.
   - Don't forget to broadcast a progress line via `self._log(...)` so the
     Summary's apply progress shows the framework install stage.

2. **Landing page plan** — ~15 min
   - Plan file: `.claude/plans/steady-forging-peacock.md`
   - 4 edits to both `landing/index.html` AND `website/index.html` (identical
     files, must stay in sync):
     - Line ~543: hero subtitle rewrite → lead with 14-layer memory
       ("OpenClaw agents forget. ClawOS doesn't.")
     - Line ~675: Framework Store feature card → append "Hermes Agent coming soon"
     - Line ~947: architecture diagram footer → append pi-mono (MIT) attribution
     - After line ~1053: add an 8th FAQ `<details>` block answering the blast-radius
       / sandbox-paradox question (policyd risk-scoring, approval gates, one-click
       stop)
   - Verify via Website Preview (port 7100, `.claude/launch.json`)
   - Vercel auto-deploys on push to main

3. **Embedded JARVIS terminal — Option A (zero-terminal launch)** — ~2-3 h
   - Full Codex hand-off prompt drafted this session and delivered to user
   - Files:
     - **New:** `services/dashd/pty_ws.py` — FastAPI WebSocket `/ws/jarvis`,
       cross-platform PTY (`ptyprocess` on unix, `pywinpty` on Windows),
       hardcoded `JARVIS_CMD = ["ollama", "launch", "openclaw", "--model",
       "kimi-k2.5:cloud"]` (never interpolated)
     - **New:** `dashboard/frontend/src/components/JarvisTerminalModal.tsx` —
       xterm.js modal with FitAddon + WebLinksAddon (clickable OAuth URL)
     - **New:** `dashboard/frontend/src/components/LaunchJarvisButton.tsx` —
       "⚡ Launch JARVIS" button for Overview page
     - **Edit:** `dashboard/frontend/src/pages/Overview.tsx` — mount button
       prominently (hero section, near `<GettingStartedCard />`)
     - **Edit:** `services/dashd/api.py` — call `pty_ws.register(app)` after app
       init; reuse existing session auth helper
     - **Deps:** `ptyprocess>=0.7` (non-Windows), `pywinpty>=2.0` (Windows),
       `@xterm/xterm`, `@xterm/addon-fit`, `@xterm/addon-web-links`
   - Single commit target, do-not-push directive so human reviews before shipping
   - Unlocks the headline "60 seconds to JARVIS" demo

#### Model strategy note (why qwen2.5, not qwen3.5)

Ollama's registry ships qwen3.5 with the Qwen3 Hermes JSON parser template,
but the model was trained to emit Qwen3-Coder XML — tool calls print as plain
text (often inside unclosed `<think>` blocks) instead of executing.

Tracked upstream (all open as of 2026-04-19):

- Ollama #14745, #14493
- llama.cpp #20837
- QwenLM/Qwen3.5 #12
- HF template issue, OpenClaw #32916, ZeroClaw #3079

A 7-line comment above the `MODEL=` case block in `install.sh` records this so
future agents know why we held. Revisit after Ollama ships the renderer/parser fix.

#### Demo plan (two product goals, credit-constrained shoot order)

**Goal 1 — Democratize agentic AI.** Default path: kimi-k2.5 via Ollama Cloud
(free credits cover casual use). Power users: Ollama Pro. Heavy users: BYO key
(Anthropic / OpenAI / OpenRouter). The Summary CTA surfaces the `ollama launch`
command today; after Option A ships, clicking `⚡ Launch JARVIS` in the
dashboard embeds the TUI in-browser. Zero-terminal UX.

Goal 1 is ~90% shootable today. Fully shootable post-Option-A.

**Goal 2 — Show value to non-tech users.** Daily morning briefing + profile-driven
personalization. Currently only a `briefing_enabled` toggle; no engine. Full
spec for the butler-tone pipeline:

1. News-source adapter (RSS / API → one of the 27 Phase 11 workflows)
2. Calendar OAuth (Google + iCloud minimum — hardest piece)
3. Briefing composer (LLM prompt): butler greeting → general headlines →
   profile-filtered news → profile briefing (kid schedule for parents,
   calendar + priority emails for solopreneurs, assignments + class schedule
   for students) → outro with an open question ("want me to draft a reply to
   the contractor?")
4. TTS pipeline: Piper free tier, ElevenLabs for the "premium butler" feel in
   demos

Estimated 2–3 weeks of build. Phase 11 territory. Not a weekend job.

**Shoot order once Option A lands:**

Tier 1 (highest ROI):
- "60 seconds to JARVIS" end-to-end demo (install.sh → wizard → bring online →
  dashboard → Launch JARVIS → chat) — Reddit / r/LocalLLaMA gold
- Wizard polish walkthrough (90 sec screen-record of all 9 screens with VO)
- "Click, see JARVIS" (15-sec cut-down of just the button → TUI → first message)

Tier 2 (supporting narrative):
- memd recall across restart (counters "agents forget" critique)
- policyd + audit chain (Merkle write visible in `~/.clawos/audit.log`)
- "Own your stack" — provider dropdown switching local qwen2.5 / kimi-k2.5 cloud
  / BYO key, three modes in one UI

Not yet shootable:
- Framework switching (wiring deferred — picker is cosmetic until task 1 lands)
- Daily briefing (engine doesn't exist — Goal 2 territory)
- Profile-driven personalization (no downstream consumer of `ui.user_profile`)
- End-to-end voice conversation (Piper/ElevenLabs install variance too high
  for unrehearsed takes)

Pre-shoot checklist:
- Dry-run install on a fresh VM first
- Pre-authenticate Ollama Cloud on the recording machine so the OAuth redirect
  doesn't break flow
- Have a standalone terminal recording of OpenClaw running as backup footage
- Test JARVIS greeting (Piper TTS fires on "Open dashboard" click — silent-fails
  if Piper missing)
- Record 1440p or 4K so terminal text stays sharp on mobile crops

#### Branding note (JARVIS framing)

r/LocalLLaMA publicly mocks the bare "JARVIS" framing as movie-reference cringe.
Compromise landed this session: keep "JARVIS" in product copy but pair with
"your AI Butler" so the vibe reads as high-end assistant, not fan-fiction.

Applied in Summary CTA: *"JARVIS, your AI Butler. Copy this command to bring
your agent online:"*

Extend this framing to:
- `landing/index.html` + `website/index.html` hero + FAQ (Thursday pass)
- README.md tagline if it still references JARVIS in isolation
- Any future marketing copy

#### Handoff state

- Branch `feat/setup-react-wizard` is pushed and matches origin
- Local `main` is 2 commits ahead of `origin/main` — same commits that are in
  the PR; will fast-forward on next pull after PR #40 merges
- No uncommitted work on tracked files. `.claude/settings.local.json`,
  `.claude/worktrees/`, `.claude/skills/` are local-only and gitignored
- Todo list carried over: framework `_apply()` wiring, landing page plan,
  embedded JARVIS terminal (Option A via Codex)
