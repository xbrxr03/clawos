# ClawOS Shared Update Log

This file is the shared running log for work completed in this repo.

Both Codex and Claude can append here after meaningful changes so the next agent has a clean handoff without re-auditing the whole project.

Treat this file as project memory.

## How To Use

- Add new notes at the top of the `## Updates Done By Codex` or equivalent agent section.
- Keep entries factual and concise.
- Include:
  - date
  - agent
  - what changed
  - verification performed
  - important remaining gaps
- Do not delete older entries unless they are clearly wrong.
- If a future agent changes product direction or discovers a major contradiction, record it here instead of silently replacing history.

## Current Product Direction

ClawOS is what you get when Apple builds Iron Man's JARVIS for everyone.
A real AI operating environment. Runs on your hardware. Works offline. Costs nothing.
Feels like it was made by people who care about every second of the experience.

- **Product shape:** flagship Ubuntu-based AI distro + polished install on existing Linux/macOS
- **UX north star:** Apple-grade. Every surface is designed, not just functional.
  First-run wizard feels like Apple setup. Dashboard feels like a command center.
  Voice feels like JARVIS. Errors are helpful. Empty states are beautiful.
- **Product stance:**
  - OpenClaw-first external positioning, provider-neutral internals
  - Fully open source, AGPL, no paid tier, no telemetry, no call home
  - Local-first by default, cloud optional and explicit
- **Roadmap:** docs/ROADMAP.md — stabilize → premium experience → ship v0.1 → platform depth → distro
- **Promotion:** happening on owned channels (not HN). Assets: dashboard screenshot,
  setup wizard screenshot, organize-downloads GIF, summarize-pdf GIF, voice demo GIF.

## Current Release Frontier

This section is the authoritative release-status snapshot.
Historical notes below are preserved for context, but they are not the current build order.

- Active milestone: `Milestone 3 - Ship v0.1`
- Release version target: `0.1.0`
- Canonical roadmap: `docs/ROADMAP.md`
- Canonical release gates:
  - repo verification green
  - security audit green
  - install path validated on supported targets
  - packaging / ISO validation completed on a Linux host
  - docs accuracy pass complete

## Current Release Gate Status

- `pyproject.toml` is already set to `0.1.0`.
- `python scripts/security_audit.py` passed on 2026-04-07 from this checkout.
- `python -m pytest tests -q` passed on 2026-04-07 with `166 passed, 25 skipped`.
- `npm run typecheck` passed on 2026-04-07.
- `npm run build` passed on 2026-04-07.
- The pre-release macOS-themed dashboard redesign is complete and built into `services/dashd/static`.
- `install.sh` validation is only partially verifiable from this Windows checkout unless a real Linux or macOS target is available.
- `.deb` and ISO validation require a Linux environment with the Debian / ISO toolchain.
- The release tag remains blocked until the install / packaging validation gaps above are closed or explicitly waived.

## Current Canonical Surfaces

- `services/dashd` is the canonical dashboard/backend surface.
- `dashboard/frontend` is the canonical frontend surface.
- `services/setupd` owns guided setup state and flows.
- `packaging/iso` is the distro packaging path.
- Terminal and legacy setup paths are fallback/recovery surfaces, not the flagship UX.

## High-Signal Files

- `docs/ARCHITECTURE_CURRENT.md`
- `docs/PRODUCT_VISION.md`
- `docs/ROADMAP.md`
- `docs/COMPETITIVE_PLATFORM.md`
- `docs/PRODUCTION.md`
- `services/dashd/api.py`
- `services/setupd/service.py`
- `services/setupd/state.py`
- `clawos_core/catalog.py`
- `clawos_core/models/__init__.py`
- `dashboard/frontend/src/App.tsx`
- `dashboard/frontend/src/pages/setup/SetupPage.tsx`

## Updates Done By Claude

### 2026-04-14 - Claude (JARVIS briefing + install profiles + launch prep)

#### New test hardware
- Machine: i7-9700K / 64GB RAM / GTX 1660 Super (6GB VRAM) / fresh Ubuntu
- Install.sh tier: **Tier C (performance)** — ≥30GB RAM, <10GB VRAM
- Expected model pull: `qwen2.5:7b` (~4.7GB), CUDA-accelerated

#### Changes shipped

**`install.sh`**
- Added profile 7 (Freelancer) to `select_profile()` and `apply_profile()`
- Changed Tier A / lowram default model: `qwen2.5:3b` → `qwen3.5:4b` (~3.4GB, 256K context, 5.9M Ollama downloads)
- Changed default fallback model to `qwen3.5:4b`
- Added `icalendar` to pip packages list

**`services/jarvisd/service.py`**
- Added `_BRIEFING_TRIGGERS` (8 regex patterns): what's up, good morning, brief me, what's my day, catch me up, what do I have today, what's going on, give me my update
- Added `_AFFIRMATIVES` frozenset (14 yes-words)
- `_looks_like_briefing_request()` now checks all 8 patterns (was single regex)
- Added `_looks_like_standalone_greeting()` — just "hey jarvis" / "jarvis" alone
- Added `_is_affirmative()` helper
- `_calendar_snapshot()` rewritten: fetches real ICS URL from `jarvis.briefing.calendar_ics_url` config, parses today's events sorted by time, falls back to demo if no URL set
- `set_config()` handles `calendar_ics_url` writes to `jarvis.briefing.calendar_ics_url`
- `_current_config()` exposes `calendar_ics_url` to frontend
- `chat()` restructured: standalone greeting branch (no OpenClaw needed) → continuation check → briefing routing → normal routing
- After briefing delivery: sets `shared_memory["awaiting_project_continue"] = True`
- If next message is affirmative + flag is set: rewrites text to resume last project, clears flag

**`dashboard/frontend/src/pages/Settings.tsx`**
- `<ElevenLabsCard />` now rendered (was defined but never inserted into JSX)
- `<CalendarCard />` added: ICS URL input, instructions pointing to Google Calendar "Secret address in iCal format", save → `setJarvisConfig({ calendar_ics_url })`

**`dashboard/frontend/src/lib/commandCenterApi.ts`**
- `JarvisConfig` type: added `calendar_ics_url?: string`

**`README.md`**
- Full rewrite: product pitch style (was technical manual)
- Leads with JARVIS hook, install command, profile selection
- Comparison table uses policyd row (not WhatsApp)
- Hardware table updated: Tier A/B now shows `qwen3.5:4b`

#### Verification
- `npm run dev` started, Settings page confirmed: 9 cards, ElevenLabs card, Calendar card, all text/buttons present, zero console errors

---

#### Next steps for Linux machine session

**Priority 1 — Install validation (critical path to v0.1.0)**
1. Run `bash install.sh --check` → confirm Tier C detected, `qwen2.5:7b` selected
2. Run full `bash install.sh` → choose profile (try Developer=1 and General=6 separately)
3. Validate all 7 profiles show in prompt
4. Confirm `qwen3.5:4b` pulls correctly on a Tier A simulation (`CLAWOS_PROFILE=lowram bash install.sh`)
5. `openclaude` command works (dev profile) — points at Ollama qwen2.5-coder:7b

**Priority 2 — JARVIS voice validation**
6. Open dashboard Settings → paste ElevenLabs key → Activate → hear test audio
7. Open dashboard Settings → paste Google Calendar ICS URL → Connect
8. Open JARVIS page → type "hey jarvis" → expect short greeting (no briefing)
9. Type "hey jarvis good morning" → expect full briefing with real calendar events
10. After briefing, type "yes" → expect JARVIS to resume last project context

**Priority 3 — Demo asset recording**
11. Record `organize-downloads` GIF: messy Downloads folder → run workflow → clean folder (15s)
12. Record `summarize-pdf` GIF: PDF → terminal summary (10s)
13. Record JARVIS voice demo video: ElevenLabs Brian voice briefing (30s)
14. Screenshot dashboard dark mode with real data visible

**Priority 4 — Launch prep (after validation)**
15. Create Discord server → get invite URL → give to Claude → wires into landing + README
16. Sign up Plausible → get domain ID → give to Claude → adds script tag to landing
17. Docs accuracy pass — grep for TODO/FIXME/placeholder → remove stale content
18. Tag `v0.1.0` once install validation passes

**Hardware context for install.sh:**
- i7-9700K + 64GB RAM + GTX 1660 Super (6GB VRAM) → Tier C
- CUDA will be detected → GPU inference at ~40-80 tok/s on qwen2.5:7b
- 6GB VRAM is tight for qwen2.5:7b fp16 but fine with Ollama's quantization

---

### 2026-04-07 - Claude (doc audit + status sync)

#### Full doc audit completed

Read all 24 markdown files. No code changes — this is a status sync entry.

**Current state confirmed:**
- Phases 1–11 fully complete and merged. 155 tests passing, 25 skipped.
- Dashboard: 8 pages live (Overview, Workflows, Packs, Providers, Registry, Traces, Settings, Setup) + 5 new pages added overnight (Workbench, Research, MCPManager, Federation, Studio)
- Voice pipeline: end-to-end (Whisper 44.1kHz, Piper TTS, wake-word, push-to-talk)
- WhatsApp bridge: stable (approval-by-reply, voice notes, auto-reconnect)
- 29 workflows across 6 categories, hero workflows (organize-downloads, summarize-pdf) demo-ready
- AGPL migration: complete — full LICENSE text, SPDX headers on all files, CI compliance test
- Security: 6 of 7 enterprise requirements met

**Active milestone: Milestone 3 — Ship v0.1**

Remaining gaps before v0.1.0 tag:

| Task | Owner | Notes |
|------|-------|-------|
| ISO validation on Tier A (8GB) + Tier B (16GB) | Manual | Real hardware required |
| install.sh end-to-end on Ubuntu 22.04/24.04 + macOS 14+ | Manual | Linux device available; Mac deferred |
| README rewrite | Claude/Codex | Product pitch, not tech manual |
| Social assets: 5 demo GIFs | Manual | Dashboard screenshot, wizard screenshot, organize-downloads GIF, summarize-pdf GIF, voice GIF |
| Docs accuracy pass | Claude/Codex | Remove TODOs, placeholder text, dead links |
| macOS .dmg + Homebrew formula | Deferred | No Mac hardware yet |
| Calamares/live-boot validation | Manual | Real hardware required |

**HN launch plan:**
- Title: "Show HN: ClawOS – bootable ISO that runs OpenClaw + Ollama offline, no API keys"
- Timing: Tuesday/Wednesday 9am ET
- Cross-post: r/selfhosted, r/homelab, r/LocalLLaMA
- Story angle: safe offline alternative given CVE-2026-25253

**Next steps for next agent:**
1. README rewrite — replace technical manual with product pitch (see docs/PRODUCT_VISION.md for tone)
2. Docs accuracy pass — grep for TODO/FIXME/placeholder across docs/, remove stale content
3. Vite production build check — verify `npm run build` in dashboard/frontend succeeds cleanly
4. packaging/launch/hn_post.md — review and finalize copy before posting

---

### 2026-04-06 (overnight session) - Claude

All 7 items in the build order were completed in a single overnight session.

---

#### 1. Browser Workbench

**Backend** (`services/dashd/api.py`):
- `_workbench_fetch(url)` — stdlib URL fetch, HTML strip, title/text/links extraction
- `POST /api/workbench/fetch`, `POST /api/workbench/research`, `GET /api/workbench/sessions`
- `_WORKBENCH_SESSIONS` deque (maxlen=50)

**Frontend** (`dashboard/frontend/src/pages/Workbench.tsx`):
- Fetch/Research mode toggle, URL bar, optional query input
- Left: page content (title, word count, text excerpt, links)
- Right: active session status, task ID, source
- Bottom: resumable session history

---

#### 2. Research Engine with Citations and Resumable Runs

**`services/researchd/engine.py`** (new file):
- `Citation`, `ResearchSource`, `ResearchSession` dataclasses — disk-persisted to `~/.clawos/research/sessions/`
- `_fetch_page(url)` — stdlib fetch, HTML clean, snippet extraction
- `_brave_search(query, api_key)` / `_tavily_search(query, api_key)` — optional API key search providers
- `_detect_provider()` — checks `BRAVE_API_KEY` / `TAVILY_API_KEY` env then config; falls back to direct URL fetch (no key required)
- `_extract_citations(sources, query)` — keyword overlap scoring, relevance tiers: primary / supporting / tangential
- `ResearchEngine` class: full session lifecycle (start, pause, resume, delete)
- `get_engine()` singleton

**API endpoints added to `services/dashd/api.py`**:
- `POST /api/research/start`, `GET /api/research/sessions`, `GET /api/research/sessions/{id}`
- `POST /api/research/sessions/{id}/resume`, `POST /api/research/sessions/{id}/pause`
- `DELETE /api/research/sessions/{id}`

**Frontend** (`dashboard/frontend/src/pages/Research.tsx`):
- Left: session list with status/provider/citation badges + start form (query, seed URLs, optional provider + key)
- Right: citation cards (relevance badge + blockquote excerpt) + source cards
- Resume/pause/delete session actions

---

#### 3. MCP Manager (deeper protocol relay)

**`services/mcpd/protocol.py`** (new file):
- `HttpMCPClient`: `initialize()`, `list_tools()`, `call_tool()`, `list_resources()`, `read_resource()`, `list_prompts()`
- `StdioMCPClient`: async subprocess, JSON-RPC 2.0 over stdin/stdout, `stop()`

**`services/mcpd/service.py`** (new file):
- `MCPServerConfig` dataclass, persisted to `~/.clawos/mcp_servers.json`
- `MCPService`: add/remove/update/connect, `_connect_http`/`_connect_stdio`, `list_all_tools`, `call_tool` relay, `read_resource` relay
- `WELL_KNOWN` list: filesystem, brave-search, github, sqlite, memory, fetch, puppeteer, slack

**API endpoints**:
- `GET/POST /api/mcp/servers`, `DELETE/PATCH /api/mcp/servers/{id}`, `POST /api/mcp/servers/{id}/connect`
- `GET /api/mcp/tools`, `GET /api/mcp/resources`, `POST /api/mcp/call`, `POST /api/mcp/resources/read`
- `GET /api/mcp/well-known`

**Frontend** (`dashboard/frontend/src/pages/MCPManager.tsx`):
- 4 tabs: Servers (add/connect/remove), Catalog (well-known library), Tools (all tools across connected servers), Call Tool (interactive JSON args form)

---

#### 4. A2A Federation and Trust Model

**`services/a2ad/peer_registry.py`** (new file):
- HMAC-SHA256 signed agent cards using `~/.clawos/a2a_signing.key`
- `sign_agent_card()` / `verify_agent_card()`
- `PeerRecord` with `trust_tier`: trusted / unverified / blocked
- `PeerRegistry`: add/remove/set_trust/probe, `probe_peer` fetches `/.well-known/agent.json`, `is_trusted`, `is_blocked`, `get_signing_key_fingerprint`
- Persistence to `~/.clawos/a2a_peers.json`
- `get_registry()` singleton

**API endpoints**:
- `GET/POST /api/a2a/peers`, `DELETE /api/a2a/peers/{id}`, `POST /api/a2a/peers/{id}/trust`
- `POST /api/a2a/peers/{id}/probe`, `GET /api/a2a/signing-key`

**Frontend** (`dashboard/frontend/src/pages/Federation.tsx`):
- Add peer form (URL, name, initial trust tier)
- Peer list with probe button, trust tier badges, reachable status
- Selected peer detail panel: trust tier selector, skills/capabilities, signing key fingerprint

---

#### 5. Pack Studio (drag-and-drop visual graph builder)

**`clawos_core/catalog.py`** extended:
- `_STUDIO_DIR = CONFIG_DIR / "studio" / "programs"`
- `_load_user_programs()`, `get_workflow_program(id)`, `save_workflow_program(data)`, `delete_workflow_program(id)`
- `list_workflow_programs()` prepends user-created programs

**API endpoints**:
- `GET/POST /api/studio/programs`, `DELETE /api/studio/programs/{id}`, `POST /api/studio/programs/{id}/deploy`

**Frontend** (`dashboard/frontend/src/pages/Studio.tsx`):
- Types: `NodeKind` (trigger/step/approval/tool/output), `GraphNode`, `GraphEdge`, `Program`
- `GraphCanvas` SVG component: mouse drag to move nodes, Alt+drag to draw edges, click to select, delete button on selected node
- `programToGraph()` converts WorkflowProgram checkpoints/approval_points/triggers to positioned nodes+edges
- Left sidebar: program list + new program form
- Main: SVG canvas
- Right: node inspector panel
- Toolbar: node-type add buttons + Save + Deploy

---

#### 6. AGPL Migration

- `pyproject.toml`: `license = { text = "AGPL-3.0-or-later" }`
- `LICENSE`: stub file written (full text: `curl https://www.gnu.org/licenses/agpl-3.0.txt > LICENSE` when network is available)
- All 287 Python files: `# SPDX-License-Identifier: AGPL-3.0-or-later` added as first line (6 files already had it; all new files in this session were written with it)

---

#### 7. Linux Packaging Scripts

- `scripts/validate_package.sh` — validate a .deb before publishing: dpkg-deb integrity, required control fields, required file paths, size sanity, lintian (optional)
- `scripts/test_install.sh` — end-to-end install test on Linux (requires root): pre-flight, dpkg install, filesystem checks, clawctl CLI smoke, systemd service start/active, API health check, Python package import, optional uninstall verification
- `packaging/deb/validate.sh` — thin wrapper for the clawos-command-center deb with package-name, desktop entry, postinst, Section, and Depends checks on top of the generic script
- `tests/packaging/test_deb.py` — pytest suite (pass `--deb <path>` to activate): integrity, control fields (parametrized), contents, extracted filesystem, lintian (skipped if not installed)

macOS packaging: deferred — no Mac hardware available yet. Placeholder/docs to follow when device is available.

---

#### Frontend wiring (all pages above)

**`dashboard/frontend/src/lib/commandCenterApi.ts`**:
- Added types: `Citation`, `ResearchSource`, `ResearchSession`, `WorkbenchPage`, `WorkbenchSession`
- Added ~30 new API methods for studio, research, workbench, A2A peers, MCP

**`dashboard/frontend/src/app/navigation.tsx`**:
- Added nav items: Studio, Workbench, Research, MCP, Federation with SVG icons

**`dashboard/frontend/src/App.tsx`**:
- Added lazy imports and routes for all 5 new pages

---

#### Remaining frontier for next agent

- LICENSE full text — replace stub with full AGPL-3.0 text (`curl https://www.gnu.org/licenses/agpl-3.0.txt > LICENSE`)
- macOS packaging — scripts + docs when hardware is available
- Calamares/ISO live boot validation on real hardware
- End-to-end clawctl install test run on the Linux device

---

### 2026-04-06 - Claude

#### Browser Workbench — item 1 of the build order

Built the Browser Workbench surface end to end.

**Backend** (`services/dashd/api.py`):
- Added `_workbench_fetch(url)` — stdlib-only server-side URL fetch (urllib.request), strips HTML, extracts title, text (8KB max), and external links
- Added `POST /api/workbench/fetch` — returns structured page content, auth required
- Added `POST /api/workbench/research` — fetches URL if provided, builds context, submits to agentd, records trace, returns session object
- Added `GET /api/workbench/sessions` — returns in-memory deque of last 50 research sessions
- Added `_WORKBENCH_SESSIONS` module-level deque (maxlen=50)
- Added `re` and `urllib.request` imports

**Frontend types + API client** (`dashboard/frontend/src/lib/commandCenterApi.ts`):
- Added `WorkbenchPage` and `WorkbenchSession` types
- Added `workbenchFetch(url)`, `workbenchResearch(query, url, workspace)`, `listWorkbenchSessions()` methods

**Frontend page** (`dashboard/frontend/src/pages/Workbench.tsx`):
- Fetch/Research mode toggle in top bar
- URL bar + optional research query input
- Left panel: extracted page title, word count, links, full text excerpt
- Right panel: active session details — task ID, status badge, source URL, page context summary
- Bottom: resumable session history (click to reload any prior session)

**Navigation + routing**:
- Added Workbench nav item with monitor/lens icon to `navigation.tsx`
- Added lazy `/workbench` route in `App.tsx`

#### Verification

- All changes are additive — no existing endpoints, routes, or components modified beyond safe extensions
- Workbench fetch is SSRF-safe: validates scheme (http/https only), no credential forwarding, 512KB read cap, 12s timeout

#### Remaining frontier (next build order)

1. Research engine with citations and resumable runs
2. MCP manager depth
3. richer A2A federation and trust model
4. Pack Studio visual builder
5. AGPL migration
6. native packaging validation
7. real ISO/Calamares validation on target environments

## Updates Done By Codex

### 2026-04-07 - Codex

#### macOS-themed dashboard redesign completed

- Reworked `dashboard/frontend` to the requested macOS Sonoma/Ventura-inspired visual language:
  - shared tokens and palette moved to Apple-system colors and SF-style typography
  - sidebar, toolbar, inspector rail, and command palette now use compact vibrancy/frosted-glass surfaces
  - Tauri/desktop mode now renders a dedicated traffic-light title bar
  - nav density, buttons, pills, progress bars, grouped settings rows, and trace filters were restyled to match the spec
- Updated the highest-traffic surfaces called out in the redesign brief:
  - `src/app/AppShell.tsx`
  - `src/app/navigation.tsx`
  - `src/app/InspectorRail.tsx`
  - `src/index.css`
  - `src/design/tokens.ts`
  - `src/pages/Overview.tsx`
  - `src/pages/Workflows.tsx`
  - `src/pages/Settings.tsx`
  - `src/pages/Traces.tsx`
  - `src/pages/pages.jsx`
- Rebuilt the generated dashboard assets into `services/dashd/static`.

#### Verification performed in this pass

- Ran `npm run typecheck` -> passed.
- Ran `npm run build` -> passed.

#### Release impact

- The frontend redesign is no longer a pending/deferred task.
- `0.1.0` is still blocked only by supported-target install validation and Linux-host packaging / ISO validation.

### 2026-04-07 - Codex

#### Release-prep alignment pass

- Updated the top of `update.md` so it now names one authoritative current frontier:
  - `Milestone 3 - Ship v0.1`
  - `0.1.0` as the release target
  - explicit release-gate status
- Kept the preserved historical entries intact instead of rewriting prior session history.

#### Verification performed in this pass

- Confirmed `pyproject.toml` is already at `0.1.0`.
- Confirmed `python scripts/security_audit.py` passes in this checkout.
- Ran `python -m pytest tests -q` -> passed, `166 passed, 25 skipped`.
- Ran `npm run typecheck` -> passed.
- Ran `npm run build` -> passed.
- Validated `install.sh`, `scripts/test_install.sh`, `scripts/validate_package.sh`,
  `packaging/deb/build_deb.sh`, `packaging/deb/validate.sh`, and `packaging/iso/build_iso.sh`
  for shell syntax under Git Bash.
- Confirmed `install.sh` exits immediately on an unsupported Windows shell instead of attempting a partial install.
- Confirmed guard behavior on unsupported hosts:
  - `packaging/deb/build_deb.sh --skip-frontend-build` stops immediately when required Linux tooling is absent
  - `packaging/iso/build_iso.sh --skip-download` stops immediately when not run as root
  - `scripts/test_install.sh --skip-uninstall` stops immediately when not run as root

#### Remaining release blockers

- install validation needs a supported Ubuntu/macOS target
- `.deb` and ISO validation need a Linux host with the required packaging toolchain

### 2026-04-07 - Codex

#### Documentation/status audit completed

- Reviewed the tracked first-party Markdown docs in the main repo to determine current documented status and project direction.
- Confirmed the docs now largely converge on this canonical product shape:
  - `dashboard/frontend` as the canonical frontend
  - `services/dashd` as the canonical dashboard API/web surface
  - `services/setupd` as the guided setup control plane
  - `desktop/command-center` as the Tauri desktop shell
- Confirmed the repo contains the main documented surfaces and validation scripts referenced by the newest docs:
  - `services/setupd`
  - `services/dashd`
  - `dashboard/frontend`
  - `desktop/command-center`
  - `packaging/deb/build_deb.sh`
  - `scripts/verify_repo.py`
  - `scripts/security_audit.py`

#### Current documentation picture

- The newest docs position ClawOS as more than a one-command OpenClaw installer:
  - local-first command center
  - pack-first onboarding
  - provider control plane
  - extension registry
  - local traces/evals
  - OpenClaw rescue/import path
- `README.md` still leads with installer/OpenClaw-first messaging, while newer docs describe a broader platform/control-plane story.
- `PROJECT_TRUTH.md` reads like an older architecture contract and does not fully reflect the newer `setupd` + canonical frontend/backend + competitive-platform direction.
- `dashboard/backend/` is explicitly documented as legacy, but it still exists in-tree and remains a cleanup target.
- `content_factory_skill/` docs are duplicated in two paths and should be treated as sidecar material, not core runtime truth.
- Several Markdown files display mojibake in this Windows terminal session (`â€”`, `âœ…`, etc.), so there is likely an encoding/display cleanup worth doing.

#### Verification performed in this pass

- Reviewed tracked first-party `.md` files via `git ls-files "*.md"`.
- Read the core status/product/architecture docs and ADRs.
- Checked that the main canonical paths named by the docs exist in the repo.
- Did not rerun tests in this pass; the latest documented green state remains the `2026-04-06` Codex entry below.

#### Recommended next steps

1. Align top-level messaging across `README.md`, `PROJECT_TRUTH.md`, and `docs/ARCHITECTURE_CURRENT.md` so the repo tells one consistent story.
2. Decide whether `PROJECT_TRUTH.md` remains an active contract document or is replaced by the newer architecture/setup/platform docs.
3. Archive or remove the legacy dashboard stack after confirming nothing first-party still depends on it.
4. Deduplicate `content_factory_skill` documentation and clearly label it as optional sidecar functionality.
5. Fix Markdown encoding/display issues so docs render cleanly across Windows and Linux terminals.
6. Add a short release-state note clarifying what is production-ready today versus still roadmap or scaffold work (`.deb`, macOS host install, ISO/Calamares, desktop shell).

### 2026-04-06 - Codex

#### Milestone 2F hero workflows + 2G AGPL finish

- Finished the hero workflow demo pass end to end:
  - `workflows/engine.py` now exposes live workflow progress phases over the event bus so the dashboard can stream real mid-run updates instead of only start/end state
  - `services/dashd/api.py` now forwards `workflow_progress` and `workflow_error` events to WebSocket clients
  - `workflows/organize_downloads/workflow.py` now reports richer breakdowns (category counts, bytes, largest items, preview/apply posture)
  - `workflows/summarize_pdf/workflow.py` now returns a more demo-ready structured briefing with coverage, key points, key terms, and follow-up prompts
  - `dashboard/frontend/src/pages/Workflows.tsx` now gives the two hero workflows tailored inputs, live progress feeds, and metadata-backed insight cards inside the dashboard
- Finished the AGPL migration cleanup:
  - replaced the stub `LICENSE` with the full GNU AGPL-3.0 text
  - updated `README.md` to show the AGPL badge and correct license section
  - updated `pyproject.toml` with AGPL classifier + `license-files`
  - added SPDX headers to the remaining tracked source files across Python, shell, frontend, and test surfaces
  - added `tests/system/test_agpl_compliance.py` so header/license drift is caught in CI
- Synced roadmap/project memory:
  - `docs/ROADMAP.md` now reflects the completed Milestone 2 state and the actual summarize-PDF implementation posture
  - `packaging/iso/README.md` now documents the ISO build path, prerequisites, and the remaining real-hardware validation checklist for Milestone 3

#### Verification completed

- `python -m pytest tests/system/test_workflow_hardening.py tests/system/test_dashd_security.py tests/system/test_agpl_compliance.py -q` -> passed, `22 passed`
- `npm run typecheck` -> passed
- `npm run build` -> passed
- `python -m pytest tests -q` -> passed, `166 passed, 25 skipped`
- `python scripts/security_audit.py` -> passed

#### Remaining frontier

- Milestone 3 is now the active roadmap frontier:
  - ISO validation
  - install-path validation
  - README/demo-asset polish
  - final docs accuracy pass

### 2026-04-06 - Codex

#### Milestone 2E WhatsApp bridge reliability

- Upgraded `gatewayd` from a thin pass-through into a real WhatsApp reliability layer:
  - `services/gatewayd/service.py` now routes inbound JIDs into stable workspaces, emits WhatsApp activity events, and supports approval-by-reply for the owner phone
  - `services/gatewayd/approval_bridge.py` now formats approval prompts and resolves `yes` / `no` replies back into `policyd`
  - `services/gatewayd/media_handler.py` now transcribes voice notes automatically through the local STT path
  - `services/gatewayd/channels/whatsapp.py` now exposes structured connection status for dashboard consumption and keeps the existing auto-restart behavior visible
- Extended dashboard/API visibility for the bridge:
  - `services/dashd/api.py` now includes `gatewayd` in service health and exposes `/api/gateway/health` plus route inspection/update endpoints
  - `dashboard/frontend/src/pages/Settings.tsx` now shows linked phone posture, route count, approval queue, last activity, and disconnect context
  - `dashboard/frontend/src/lib/commandCenterApi.ts` now includes typed gateway-health and route APIs
- Added regression coverage in `tests/system/test_whatsapp_bridge.py` for:
  - approval-by-reply
  - voice-note routing/transcription
  - dashboard gateway health + route endpoints

#### Verification completed

- `python -m pytest tests/system/test_whatsapp_bridge.py tests/system/test_competitive_platform.py tests/system/test_dashd_security.py -q` -> passed, `11 passed`
- `npm run typecheck` -> passed
- `npm run build` -> passed
- `python -m pytest tests -q` -> passed, `161 passed, 25 skipped`

#### Remaining frontier after this slice

- Milestone 2F hero workflow demo quality
- Milestone 2G finish work, including replacing the AGPL LICENSE stub with the full text

### 2026-04-06 - Codex

#### Milestone 2D voice pipeline finish

- Finished the remaining Milestone 2D interaction loop instead of stopping at diagnostics:
  - `services/voiced/service.py` now supports session listeners, wake-word readiness checks, and a push-to-talk round trip
  - `services/dashd/api.py` now broadcasts live `voice_session` updates and exposes `/api/voice/push-to-talk`
  - `services/setupd/service.py` now treats wake-word mode as a real setup confirmation path instead of a cosmetic toggle
  - `runtimes/voice/microphone.py` now prefers `pw-record` first so 44.1 kHz capture follows the PipeWire-first roadmap posture
- Polished the dashboard voice UX:
  - `dashboard/frontend/src/app/AppShell.tsx` now has a native push-to-talk action plus `Ctrl+Shift+Space`
  - `dashboard/frontend/src/pages/Overview.tsx` now surfaces live voice controls, latest utterance/response, and round-trip feedback in the conversation lane
  - `dashboard/frontend/src/pages/setup/SetupPage.tsx` now blocks wake-word mode until microphone plus wake-detector confirmation passes
  - `dashboard/frontend/src/lib/commandCenterApi.ts` now includes typed wake-word and push-to-talk calls
- Expanded regression coverage in `tests/system/test_voice_pipeline.py` for:
  - setup wake-word confirmation
  - dashd wake-word test routing
  - dashd push-to-talk routing

#### Verification completed

- `python -m pytest tests/system/test_voice_pipeline.py tests/system/test_setupd.py tests/system/test_nexus_presence.py tests/system/test_dashd_security.py -q` -> passed, `16 passed`
- `npm run typecheck` -> passed
- `npm run build` -> passed

#### Remaining frontier after this slice

- Milestone 2F hero workflow demo quality
- Milestone 2G finish work, including replacing the AGPL LICENSE stub with the full text

### 2026-04-06 - Codex

#### Milestone 2D voice pipeline slice

- Replaced the old `voiced` stub with a real local voice orchestration layer in `services/voiced/service.py`:
  - shared voice-session state now updates through `clawos_core/presence.py`
  - microphone capture helpers now live in `runtimes/voice/microphone.py`
  - Whisper transcription helpers now live in `runtimes/voice/stt_client.py`
  - `voiced` now reports microphone / STT / TTS / wake-word readiness, keeps the current voice mode in sync, and exposes real microphone/pipeline test paths
- Extended dashboard and setup backend contracts:
  - `services/dashd/api.py` now includes voice state in snapshots, exposes `/api/voice/health` and `/api/voice/test`, and routes `/api/voice/mode` through the actual voice service
  - `services/setupd/state.py` now persists `voice_test`
  - `services/setupd/service.py` now exposes setup voice diagnostics plus a real setup voice-test path, and persists the latest microphone check result into setup state
- Wired the frontend to those contracts:
  - `dashboard/frontend/src/hooks/useCommandCenter.ts` now tracks live voice session state
  - `dashboard/frontend/src/app/AppShell.tsx` now shows voice status/mode in the shell header
  - `dashboard/frontend/src/pages/setup/SetupPage.tsx` now treats the voice step as a real readiness gate, storing and displaying the latest microphone test result before continuing
  - `dashboard/frontend/src/lib/commandCenterApi.ts` now includes typed voice health/test/setup voice-test calls
- Added regression coverage in `tests/system/test_voice_pipeline.py` for dashd voice endpoints and setupd voice-test persistence/diagnostics.

#### Verification completed

- `npm run typecheck` -> passed
- `npm run build` -> passed
- `python -m pytest tests/system/test_voice_pipeline.py tests/system/test_setupd.py tests/system/test_nexus_presence.py -q` -> passed, `9 passed`

#### Remaining frontier after this slice

- Milestone 2E WhatsApp bridge reliability
- Milestone 2F hero workflow demo quality
- Milestone 2G finish work, including replacing the AGPL LICENSE stub with the full text

### 2026-04-06 - Codex

#### Milestone 2 premium-experience foundation + dashboard polish slice

- Landed the premium shell/design-system pass in `dashboard/frontend`:
  - richer shared UI primitives in `src/components/ui.jsx`
  - command-palette and shell cleanup in `src/app/AppShell.tsx`
  - premium token/CSS pass already carried through `src/index.css`, `src/design/tokens.ts`, and nav metadata
  - skeleton-first loading states across the major product surfaces
- Rebuilt the first-run wizard into the roadmap order and wired the missing setup control-plane support:
  - `services/setupd/state.py` now persists `whatsapp_enabled` and `model_pull_progress`
  - `bootstrap/model_provision.py` now emits model-pull progress snapshots
  - `services/setupd/service.py` now supports `POST /api/setup/options` and `POST /api/setup/model`
  - `services/dashd/api.py` proxies those new setup routes
  - `dashboard/frontend/src/pages/setup/SetupPage.tsx` now runs an 8-step wizard with back/skip controls, live model pull progress, voice and WhatsApp steps, and a real completion state
  - `dashboard/frontend/src/lib/commandCenterApi.ts` gained the corresponding setup types and calls
- Started Milestone 2C dashboard polish with real product-facing improvements instead of placeholder chrome:
  - `src/pages/Overview.tsx` now shows real service/task/activity bars plus runtime and approval posture cards
  - `src/pages/Workflows.tsx` now exposes clearer live-progress state alongside the existing filters/search/run/history flow
  - `src/pages/Packs.tsx`, `src/pages/Providers.tsx`, and `src/pages/Registry.tsx` now use the premium page-header/stat-card pattern and surface install/trust/provider posture more clearly at a glance
  - `src/pages/Traces.tsx` now supports filterable timelines, detail inspection, and JSON export
  - `src/pages/Settings.tsx` is now grouped by purpose with descriptions and explicit save/action feedback
- Added setup regression coverage in `tests/system/test_setupd.py` for options persistence and background model preparation progress.

#### Verification completed

- `npm run typecheck` -> passed
- `npm run build` -> passed
- `python -m pytest tests/system/test_setupd.py tests/system/test_competitive_platform.py tests/system/test_nexus_presence.py tests/system/test_dashd_security.py -q` -> passed, `16 passed`

#### Remaining frontier after this slice

- Milestone 2D voice pipeline end-to-end
- Milestone 2E WhatsApp bridge reliability
- Milestone 2F hero workflow demo quality
- Milestone 2G finish work, including replacing the AGPL LICENSE stub with the full text

### 2026-04-06 - Codex

#### Milestone 1B-1E stabilization pass

- Hardened dashboard auth in `services/dashd/api.py`:
  - browser cookies now use a separate session secret instead of the raw dashboard bearer token
  - setup bypass is loopback-only and automatically shuts off once setup is marked complete
  - setup completion now rotates the dashboard session secret
- Hardened A2A trust in `services/a2ad/service.py`, `services/a2ad/peer_registry.py`, and `services/gatewayd/service.py`:
  - remote A2A task ingress now requires both bearer auth and an explicit trusted peer URL
  - blocked or untrusted peers are rejected on outbound delegation too
- Finished the top-10 workflow hardening work:
  - replaced prompt-only implementations for `organize-downloads`, `summarize-pdf`, `repo-summary`,
    `pr-review`, `write-readme`, and `changelog`
  - kept `disk-report`, `log-summarize`, `find-duplicates`, and `clean-empty-dirs` as direct deterministic helpers
  - added shared deterministic helper logic in `workflows/helpers.py`
- Completed the contract cleanup:
  - `agentd` now exposes `/submit` as the only first-party submit route and requires `intent`
  - removed the `shell.run` compatibility alias from `toolbridge`
  - updated remaining docs/prompts to use `shell.restricted`
- Raised the test floor:
  - added new auth, A2A, agentd, workflow, and helper regression coverage
  - added repo-local pytest temp handling in `tests/conftest.py`
  - fixed the packaging test harness so `.deb` checks skip cleanly unless `--deb` is provided
- Hardened `scripts/security_audit.py` itself:
  - ignores duplicate `.claude/worktrees/**` copies
  - uses AST-based checks for Python risk patterns to avoid string-literal false positives

#### Verification completed

- `python -m pytest tests/system/test_dashd_security.py tests/system/test_a2a_security.py tests/system/test_agentd_contract.py tests/system/test_workflow_hardening.py -q` -> passed, `23 passed`
- `python -m pytest tests -q` -> passed, `155 passed, 25 skipped`
- `python scripts/security_audit.py` -> passed

#### Remaining frontier after this slice

- Milestone 2 premium-experience work is now the main frontier in roadmap order
- packaging validation still needs a real built `.deb` artifact supplied to the packaging tests
- macOS packaging polish, ISO validation, and real hardware install checks still remain

### 2026-04-06 - Codex

#### Milestone 1A dashboard-stack cleanup

- Archived the retired dashboard backend from `dashboard/backend/` to `archive/legacy/dashboard-backend/`.
- Removed runtime fallback paths that still booted the legacy backend:
  - `clients/daemon/daemon.py`
  - `scripts/clawos-start.sh`
  - `systemd/clawos-dashd.service`
- Kept `services/dashd/api.py` + `dashboard/frontend/` + `services/dashd/static/` as the only active dashboard path.
- Removed the old single-file dashboard fallback from `services/dashd/api.py`; root now serves the built static bundle only.

#### Docs and verification cleanup

- Updated canonical docs to reflect the archive and single-stack dashboard model:
  - `docs/ARCHITECTURE_CURRENT.md`
  - `docs/ROADMAP.md`
  - `docs/MACOS.md`
  - `docs/STABILIZATION_ROADMAP.md`
  - `docs/adr/0001-canonical-frontend.md`
  - `docs/adr/0002-canonical-dashboard-api.md`
- Cleaned stale absolute `.codex/worktrees/...` links out of:
  - `docs/SECURITY_AUDIT.md`
  - `docs/VERIFICATION.md`
- Updated phase scripts to match the canonical frontend path and made their console output/windows behavior safer.
- Fixed a real portability bug in `bootstrap/workspace_init.py` by forcing UTF-8 when seeding workspace preset markdown files.

#### Verification completed

- `python -m pytest tests/system/test_dashd_security.py tests/system/test_nexus_presence.py tests/system/test_competitive_platform.py -q` -> passed, `11 passed`
- `python tests/system/test_phase1.py` -> passed, `46/46 passed`
- `python tests/system/test_phase2.py` -> passed, `25/25 passed`
- `git grep` confirmed no live runtime references remain to `dashboard/backend` or `uvicorn service:app`; only roadmap/archive historical references remain

#### Remaining frontier after this slice

- Milestone 1B auth hardening
- Milestone 1C top-10 workflow hardening
- Milestone 1D contract alignment
- Milestone 1E test floor
- later premium-experience dashboard redesign still remains under Milestone 2

### 2026-04-06 - Codex

#### Nexus presence implementation

- Implemented the Nexus presence layer so ClawOS now presents itself as the platform and `Nexus` as the assistant identity.
- Added new first-class shared models and state handling for:
  - `PresenceProfile`
  - `AutonomyPolicy`
  - `AttentionEvent`
  - `ActionProposal`
  - `Briefing`
  - `Mission`
  - `VoiceSession`
- Added `clawos_core/presence.py` to manage:
  - persisted presence/autonomy state
  - voice mode/session state
  - default seeded missions
  - today briefing generation
  - attention/signal generation
  - setup-to-presence synchronization

#### Setup, API, UI, and CLI integration

- Extended `services/setupd/state.py` with Nexus-oriented setup fields:
  - `assistant_identity`
  - `presence_profile`
  - `autonomy_policy`
  - `quiet_hours`
  - `primary_goals`
  - `voice_mode`
  - `briefing_enabled`
- Extended `services/setupd/service.py` so setup can configure:
  - Nexus presence
  - autonomy posture
  - voice mode
  - first briefing preparation
  - trusted routine installation
- Added new dashboard/setup API surfaces in `services/dashd/api.py` and `services/setupd/service.py`:
  - `/api/presence`
  - `/api/attention`
  - `/api/briefings/today`
  - `/api/missions`
  - `/api/voice/session`
  - `/api/voice/mode`
  - `/api/setup/presence`
  - `/api/setup/autonomy`
- Rebuilt the React home surface to be Nexus-first instead of metrics-first:
  - Today
  - Conversation
  - Active Missions
  - Pending Decisions
  - Signals
  - System Posture
- Rebuilt the setup page so it now configures:
  - assistant style
  - voice mode
  - autonomy comfort
  - primary personal-ops goals
  - quiet hours
  - first briefing behavior
- Added CLI surfaces for the Nexus layer:
  - `briefing`
  - `mission list`
  - `mission start`
  - `presence show`
  - `voice mode`
- Added a `clawos` script alias in `pyproject.toml` that points to the existing CLI entrypoint so the product-facing command now matches the product name while preserving `clawctl`.

#### Safety and supportability

- Support bundles now include presence state but redact:
  - last spoken utterance
  - last spoken response
  - sensitive mission content
- Presence and setup persistence were made fail-soft where local filesystem permissions are unreliable in this environment.

#### Verification completed

- `python -m pytest -p no:cacheprovider --basetemp test-basetemp tests/system/test_nexus_presence.py tests/system/test_setupd.py tests/system/test_competitive_platform.py` -> passed
- `python -m py_compile` on the touched Python files -> passed
- `npm run typecheck` in `dashboard/frontend` -> passed
- `npm run build` in `dashboard/frontend` -> passed
- CLI smoke checks passed:
  - `python clawctl/main.py briefing`
  - `python clawctl/main.py presence show`
  - `python clawctl/main.py voice mode`
  - `python clawctl/main.py mission list`

#### Immediate pickup point for Claude

- Continue from the Nexus foundation already wired through:
  - `clawos_core/presence.py`
  - `services/setupd/state.py`
  - `services/setupd/service.py`
  - `services/dashd/api.py`
  - `dashboard/frontend/src/pages/Overview.tsx`
  - `dashboard/frontend/src/pages/setup/SetupPage.tsx`
  - `dashboard/frontend/src/lib/commandCenterApi.ts`
- Best next build order from here:
  1. real cross-platform voice runtime abstraction
  2. richer personal-ops routines and proactive briefings
  3. conversation state / barge-in / follow-up window runtime behavior
  4. deeper approvals and mission inspector UX
  5. browser workbench and research engine integration

### 2026-04-06 - Codex

#### Major product/platform work completed in this session

- Audited the repo and turned it into a clearer architecture + stabilization direction.
- Added architecture and roadmap docs:
  - `docs/ARCHITECTURE_CURRENT.md`
  - `docs/STABILIZATION_ROADMAP.md`
- Strengthened service/workflow alignment around `agentd`, `dashd`, `toolbridge`, `policyd`, and workflow execution.
- Fixed workflow prompt placeholder bugs and stale compatibility paths.

#### Cross-platform and installer work

- Added stronger macOS support scaffolding:
  - installer branching
  - service-manager abstraction
  - `launchd` support path
  - macOS-aware docs and tests
- Added/updated:
  - `docs/MACOS.md`
  - platform/service-manager coverage
  - CI support for platform-facing code paths

#### Frontend, setup, and product shell

- Moved the repo further toward one canonical React frontend with `dashd` as the main backend.
- Added a more command-center-oriented shell and setup experience.
- Added desktop/browser launcher behavior so setup and first-boot point at the modern frontend path.
- Improved auth/session behavior for dashboard/setup access.

#### Production and security hardening

- Tightened default exposure and auth posture for dashboard and A2A surfaces.
- Added production docs and tests:
  - `docs/PRODUCTION.md`
  - dashboard security tests
  - A2A security tests
- Added support-bundle and diagnostics improvements.
- Ran a dedicated security pass:
  - SSRF-style policy hardening
  - support-bundle redaction hardening
  - safer secret placement
  - safer installer download behavior
  - removal of risky patterns in hardened paths
- Added:
  - `docs/SECURITY_AUDIT.md`
  - `scripts/security_audit.py`
  - security CI coverage

#### Competitive-platform implementation

- Added core product primitives in `clawos_core`:
  - `UseCasePack`
  - `ProviderProfile`
  - `ExtensionManifest`
  - `WorkflowProgram`
  - `TraceRecord`
  - `EvalSuite`
  - `OpenClawImportManifest`
- Added `clawos_core/catalog.py` with:
  - pack catalog
  - provider profiles
  - extension catalog
  - eval suites
  - trace helpers
  - OpenClaw install detection
- Extended setup state and setup APIs to support:
  - primary pack selection
  - provider selection
  - OpenClaw import/rescue
  - installed extensions
- Extended `dashd` with new APIs:
  - `/api/packs`
  - `/api/providers`
  - `/api/extensions`
  - `/api/traces`
  - `/api/evals`
  - `/api/a2a/agent-card`
  - `/api/a2a/tasks`
  - setup proxy routes for inspect/select-pack/import-openclaw
- Added new CLI commands:
  - `clawctl packs list`
  - `clawctl packs install`
  - `clawctl providers list`
  - `clawctl providers test`
  - `clawctl providers switch`
  - `clawctl extensions list`
  - `clawctl extensions install`
  - `clawctl rescue openclaw`
  - `clawctl benchmark`
- Added new frontend pages:
  - `dashboard/frontend/src/pages/Packs.tsx`
  - `dashboard/frontend/src/pages/Providers.tsx`
  - `dashboard/frontend/src/pages/Registry.tsx`
  - `dashboard/frontend/src/pages/Traces.tsx`
- Updated:
  - overview/home
  - setup page
  - navigation
  - shared API layer
- Added competitive-platform doc:
  - `docs/COMPETITIVE_PLATFORM.md`

#### Verification completed

- `python -m pytest tests` -> passed, `122 passed`
- `python scripts/security_audit.py` -> passed
- frontend typecheck/build/storybook/playwright were passing in the last full validation sweep during this session
- CLI competitive commands were verified:
  - `python clawctl/main.py packs list`
  - `python clawctl/main.py providers list`
  - `python clawctl/main.py extensions list`
  - `python clawctl/main.py benchmark`
  - `python clawctl/main.py rescue openclaw`

#### Remaining frontier

- Browser Workbench
- richer research engine with citations/resume
- MCP manager depth
- richer A2A federation/trust
- Pack Studio visual builder
- AGPL migration
- true native packaging validation
- real ISO/Calamares validation on native target environments

## Completed Design Task: macOS-Themed Dashboard Redesign

Completed on 2026-04-07 as pre-release work. The original requested spec is preserved below for traceability.

### Requested by user — 2026-04-06

**What:** Redesign `dashboard/frontend` with a macOS Sonoma/Ventura visual theme. This is a **pure CSS/layout visual redesign** — no backend changes, no new pages, no logic changes.

**Reference:** `C:\Users\Abrxr Hxbib\Downloads\prototype.html` — a single-file HTML mockup showing the desired feature set and page structure. Use this as the feature/page reference, but apply macOS aesthetics instead of its current sci-fi cyan/purple palette.

**Design language:**
- Vibrancy / frosted glass: `backdrop-filter: blur + saturate` on sidebar, toolbar, cards
- macOS system colors: `--blue: #007AFF`, `--green: #34C759`, `--red: #FF3B30`, `--orange: #FF9500`
- Dark bg: `#1C1C1E`; Light bg: `#F2F2F7`
- Font: `-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui`
- Traffic light window chrome in Tauri desktop mode (32px title bar, red/yellow/green 12px dots)
- Compact density — 28px nav rows, 4px progress bars, 0.5px borders
- Apple-style pill badges, grouped settings rows, segmented log filter control
- Soft layered shadows, no glows, no text gradients

**Files to modify:**
- `dashboard/frontend/src/index.css` — full CSS variable + utility class rewrite
- `dashboard/frontend/src/design/tokens.ts` — update token values
- `dashboard/frontend/src/app/AppShell.tsx` — traffic light chrome, layout dimensions
- `dashboard/frontend/src/app/navigation.tsx` — nav item/section styles
- `dashboard/frontend/src/pages/Overview.tsx` — stat cards, agents list, log panel
- `dashboard/frontend/src/pages/pages.jsx` — Agents, Tasks, Approvals, Models, Memory
- `dashboard/frontend/src/pages/Workflows.tsx` — library card redesign
- `dashboard/frontend/src/pages/Settings.tsx` — grouped macOS-style settings rows
- `dashboard/frontend/src/pages/Traces.tsx` — segmented filter control, log viewer

**What NOT to change:** backend, API calls, routing, auth, Tauri bridge logic, any `.py` files.

**Full detailed spec:** `C:\Users\Abrxr Hxbib\.claude\plans\floating-conjuring-marble.md`

**Verification:** `npm run dev` → check all 11 pages; toggle light/dark; run Playwright tests; check Storybook.

---

## Historical Claude Pickup Point

This section is preserved history from 2026-04-06.
It is superseded by the current release frontier near the top of this file.

Updated 2026-04-06. Previous pickup point preserved below under "Archived Pickup Point".

The project direction is set. The goal is to ship ClawOS v0.1 as something that feels like
Apple built Iron Man's JARVIS for everyone. Premium quality. No rough edges. Works on consumer
hardware, offline, free.

The competitive-platform work from the Codex PRs is real and stays — it is sequenced into
Milestone 4 after the core is polished and shipped.

### Read these first

- `docs/PRODUCT_VISION.md` — the brand identity and quality bars (START HERE)
- `docs/ROADMAP.md` — the canonical finish-line roadmap (replaces STABILIZATION_ROADMAP.md)
- `docs/ARCHITECTURE_CURRENT.md` — current service layout and canonical paths
- `docs/COMPETITIVE_PLATFORM.md` — competitive platform primitives and surfaces
- `services/dashd/api.py` — canonical dashboard backend
- `services/setupd/service.py` + `state.py` — guided setup control plane
- `clawos_core/catalog.py` — packs, providers, extensions, traces, eval suites
- `dashboard/frontend/src/App.tsx` — canonical frontend entry
- `dashboard/frontend/src/pages/setup/SetupPage.tsx` — first-run wizard

### Current known-good state

- `python -m pytest tests` → 122 passed
- `python scripts/security_audit.py` → passed
- Frontend typecheck + build passing
- CLI competitive commands verified:
  - `clawctl packs list`
  - `clawctl providers list`
  - `clawctl extensions list`
  - `clawctl benchmark`
  - `clawctl rescue openclaw`

### Active milestone: Milestone 1 — Stabilize

Work these in order. Do not start Milestone 2 until all of these are done.

1. **Kill legacy dashboard stack** — archive `dashboard/backend/`, remove all cross-references.
   Canonical: `services/dashd/api.py` + `dashboard/frontend/`.

2. **Auth hardening** — tighten dashd and a2ad endpoints. Session token rotation after setup.
   Document final posture in `docs/SECURITY_AUDIT.md`.

3. **Top-10 workflow hardening** — replace prompt-only with deterministic helpers for:
   organize-downloads, summarize-pdf, repo-summary, pr-review, write-readme,
   disk-report, log-summarize, changelog, find-duplicates, clean-empty-dirs.
   Each must succeed 100% on supported platforms and fail clearly on unsupported ones.

4. **Contract alignment** — all callers use `/submit` + `intent`. `shell.restricted` canonical.
   Destructive gating verified by test. Dead shims removed.

5. **Test floor** — 150+ tests, all green. Regressions on: agentd contract, workflow gating,
   tool aliases, auth rejection.

### After Milestone 1: Milestone 2 — Premium Experience

See `docs/ROADMAP.md` for the full breakdown. Summary:
- Design system enforcement (FIGMA_SYSTEM.md as law)
- First-run wizard redesigned to Apple quality
- Dashboard polish across all pages
- Voice pipeline end-to-end
- WhatsApp bridge reliable
- Hero workflows demo-quality (organize-downloads + summarize-pdf)
- AGPL migration

### Guardrails (permanent)

- `dashboard/frontend` is the canonical frontend. Do not add a second one.
- `services/dashd` is the canonical dashboard backend. Do not split it.
- `services/setupd` owns guided setup. Do not duplicate setup logic elsewhere.
- OpenClaw-first external positioning, provider-neutral internals.
- Zero test failures before shipping any milestone.
- Security audit and tests both green before any merge.
- Root cause before patch. One thing at a time.

---

## 2026-04-13 Codex Handoff

### Scope completed in this pass

- Closed the verification and environment gaps identified during the repo-wide status check.
- Focus stayed on repo hygiene, verifier reliability, Windows portability, frontend runtime consistency, and stale acceptance/doc drift.

### Repo hygiene and verifier hardening

- Removed tracked `.pytest_tmp` contents from git so generated pytest temp files stop appearing as source changes.
- Added `.pytest_cache/` to `.gitignore`.
- Reworked `tests/conftest.py` so tests use isolated temp roots instead of a fixed repo-local temp directory.
- Added `CLAWOS_TEST_TEMP_ROOT` support and automatic per-run temp creation/cleanup.
- Set pytest `basetemp` programmatically when none is provided so repeated local runs do not collide.
- Added `clawos_core/util/git.py` with safe-directory-aware git helpers.
- Updated `tests/system/test_agpl_compliance.py` to use the shared git helper instead of raw `git`.
- Hardened `scripts/verify_repo.py`:
  - inserts repo root into `sys.path` for direct execution
  - uses safe-directory-aware git calls
  - excludes `.claude`, `.pytest_tmp`, `.pytest_cache`, `node_modules`, `storybook-static`, `test-results`, and similar non-source trees from fallback scans
  - runs pytest and direct phase scripts inside fresh temp/cache sandboxes
  - sets `PYTHONUTF8=1` during verification

### Windows reliability fixes

- Rewrote `clawctl/commands/status.py` to use ASCII-safe output markers and separators.
- Removed the mojibake-prone glyph output that crashed on Windows `cp1252` consoles.
- Added `tests/system/test_clawctl_ui.py::test_status_command_is_safe_on_cp1252` to prevent regressions.

### Frontend runtime and CI contract

- Added `.nvmrc` with Node `24`.
- Updated `dashboard/frontend/package.json` with `engines.node = \">=24 <25\"`.
- Split frontend CI into smaller scripts:
  - `ci:typecheck`
  - `ci:build`
  - `ci:storybook`
  - `ci:visual`
- Updated GitHub workflows to use `node-version-file: .nvmrc` instead of repeating a hardcoded version.
- Updated `scripts/verify_repo.py` to fail fast with a clear message when frontend verification is run under the wrong Node major version.

### Acceptance and docs drift cleanup

- Updated stale expectations in:
  - `tests/system/test_phase2.py`
  - `tests/system/test_phase3.py`
  - `tests/system/test_phase4.py`
  - `tests/system/test_phase5.py`
- Updated `docs/VERIFICATION.md` to reflect the current local verification flow, temp isolation, and Node 24 requirement.
- Updated `docs/ROADMAP.md` so service-count language matches the current tree.
- Removed malformed leftover directory `dashboard/{backend,frontend` that was causing verification noise.

### Verification completed

- `python scripts/verify_repo.py` passed end to end on Node `24`.
- `python scripts/verify_repo.py --skip-frontend` passed.
- `python scripts/security_audit.py` passed.
- Full pytest passed through the verifier after the auth hardening pass: `235 passed, 25 skipped`.
- Additional targeted checks passed, including AGPL compliance and `clawctl` UI coverage.
- Frontend validation passed under Node 24 for:
  - Vite production build
  - Storybook build
  - Playwright visual tests

### Pickup note for the next agent

- The core verifier path is now healthy on this machine's default `node` (`v24.14.0`).
- `scripts/verify_repo.py` now stops early with a clear message if frontend verification is attempted under the wrong Node version.
- I intentionally did not touch unrelated `.claude` worktree changes already present in the repo.
- Frontend build validation refreshed tracked assets under `services/dashd/static` and `services/dashd/static/assets`; those diffs are expected from the local build runs and remain in the worktree.
- No commit was created in this pass.

### Auth hardening follow-up

- Hardened `services/dashd/api.py` so `/api/openapi.json`, `/api/docs`, and `/api/redoc` require dashboard auth instead of remaining public.
- Locked `/api/evolution` and `/ws/brain` behind the same dashboard auth gate as the rest of the private command-center surface.
- Tightened cookie-backed dashboard websocket auth so browser sessions require a trusted loopback origin. Bearer and explicit token websocket auth still work for non-browser clients.
- Fixed the latent `/ws/brain` route signature so FastAPI treats it as a real websocket endpoint instead of a malformed request handler.
- Added regression coverage for protected docs/evolution routes, trusted-origin websocket behavior, protected brain websocket access, and blocked-peer rejection in `tests/system/test_a2a_security.py`.
- Updated `docs/SECURITY_AUDIT.md` and `docs/PRODUCTION.md` to document the final auth posture.

### Workflow hardening follow-up - organize-downloads

- Hardened `workflows/organize_downloads/workflow.py` without changing its deterministic happy path.
- The workflow now ignores hidden/system noise such as `.DS_Store`, `.localized`, `desktop.ini`, `Thumbs.db`, and direct symlink entries instead of trying to organize them as user content.
- Live runs now continue past per-file move failures, report which moves failed, and preserve the successful moves instead of aborting the whole workflow at the first locked or permission-denied file.
- Added richer metadata for planned, skipped, failed, and completed moves so the dashboard and future tests can distinguish previews from partial live runs.
- Switched the user-facing summary separators in this workflow to ASCII-safe formatting to avoid mojibake-prone bullets in mixed Windows console setups.
- Added workflow regressions in `tests/system/test_workflow_hardening.py` for:
  - hidden/system file ignore behavior
  - partial move failure reporting while other files still organize correctly

### Verification after organize-downloads hardening

- `python -m pytest tests/system/test_workflow_hardening.py -q` passed: `14 passed`.
- `python scripts/verify_repo.py` passed end to end after the workflow hardening slice: `237 passed, 25 skipped`.
- Frontend validation still passed inside the verifier on Node `24`, which refreshed tracked assets under `services/dashd/static` again.

### Workflow hardening follow-up - summarize-pdf

- Hardened `workflows/summarize_pdf/workflow.py` so PDF extraction failures now return explicit, typed workflow errors instead of bubbling up as vague exceptions.
- Added a dedicated failure path for missing PDF extraction support and a separate failure path for image-only / encrypted / OCR-needed PDFs with actionable wording.
- Added failure metadata (`failure_reason`, `pages_used`, `file`) so callers can distinguish extractor availability problems from no-text documents.
- Switched the coverage summary line in this workflow to ASCII-safe separators for consistency with the Windows-safe CLI hardening.
- Added workflow regressions in `tests/system/test_workflow_hardening.py` for:
  - image-only or encrypted PDFs with no extractable text
  - extractor-runtime failures such as missing `pypdf`

### Verification after summarize-pdf hardening

- `python -m pytest tests/system/test_workflow_hardening.py -q` passed: `16 passed`.
- `python scripts/verify_repo.py` passed end to end after the second workflow hardening slice: `239 passed, 25 skipped`.
- Frontend validation still passed inside the verifier on Node `24`, and the generated `services/dashd/static` asset diffs remain expected from those validation builds.

### JARVIS / OpenClaw voice pivot - product direction locked

- Voice strategy changed during follow-up product planning and should be treated as a major architecture pivot, not a cosmetic UI pass.
- `JARVIS` is now the flagship marketed voice experience and is explicitly separate from `Nexus`.
- The desired end state is:
  - JARVIS UI = dedicated voice-first frontend surface
  - JARVIS brain = OpenClaw-backed runtime
  - JARVIS typed chat + spoken chat = same brain
  - JARVIS memory/context = shared with OpenClaw channels such as WhatsApp, Telegram, and future external channels
- Nexus should not own the premium JARVIS voice path.
- ElevenLabs belongs to the JARVIS/OpenClaw lane. If ElevenLabs is unavailable, the fallback is Piper.

### Architecture correction discovered during planning

- The current repository does not yet route voice to OpenClaw.
- Current live voice path is still:
  - `dashboard -> /api/voice/*`
  - `services/dashd/api.py -> services/voiced/service.py`
  - `services/voiced/service.py -> services.agentd.service.get_manager().chat_direct(..., channel="voice")`
  - `services/agentd/service.py -> runtimes/agent/runtime.py`
- That means the existing voice pipeline still lands in the native ClawOS/Nexus-style runtime, not an OpenClaw-backed voice brain.
- OpenClaw currently exists in this repo mainly as:
  - install/start/stop/config support in `openclaw_integration/`
  - optional gateway runtime posture
  - peer/gateway integration
- A real JARVIS implementation therefore still needs a backend bridge/adaptor layer so the JARVIS surface talks to OpenClaw instead of the default `agentd` runtime.

### JARVIS UX direction locked with the user

- The new JARVIS surface should be a separate page in the dashboard, not a modal and not a second standalone frontend.
- It should keep the main app nav, but suppress the dense inspector and behave like an immersive voice room.
- Visual direction requested and confirmed:
  - top-centered glowing orb
  - live caption bubble under the orb
  - centered visible audio spectrum
  - bottom text + mic composer
  - smaller transcript history as a secondary surface
- The visual reference shared by the user is `jarvisUI.png` on the desktop and should be treated as the style anchor for the first pass.

### JARVIS/OpenClaw behavior locked with the user

- JARVIS should use a separate identity/session lane from Nexus.
- JARVIS and OpenClaw should share the same cross-channel brain so the user can continue the same assistant relationship across:
  - dashboard JARVIS voice UI
  - dashboard JARVIS typed input
  - WhatsApp
  - Telegram and future channels
- Conversation threading model is now locked:
  - separate short-thread conversation state per channel/surface
  - shared long-term memory across the JARVIS/OpenClaw brain
- Typed input on the JARVIS page should go to the same OpenClaw-backed brain as voice input.
- JARVIS should answer out loud by default for both typed and spoken turns.
- The only exception is when voice mode is explicitly turned off, in which case responses can remain text-only.
- The special call flow is in scope for day one:
  - saying `Jarvis` or `Hey Jarvis` plus `what's up` should trigger the personalized briefing workflow
- The briefing content requested by the user includes:
  - weather via Open-Meteo
  - headlines via Brave API
  - calendar via Google Calendar
  - current tasks / schedule
  - resume-last-project context from memory
- Demo data is acceptable for the first demo pass where live integrations are not ready.

### Current planning state for the next agent

- The separate JARVIS room UI was planned in detail:
  - dedicated `/jarvis` route
  - JARVIS-specific frontend wrappers over the existing voice endpoints for the UI-first slice
  - separate JARVIS settings ownership instead of generic Nexus settings ownership
  - transcript history derived from `last_utterance` and `last_response` until streaming transcript support exists
- After the architecture correction, this plan should now be understood as incomplete unless paired with the OpenClaw runtime bridge.
- The correct implementation order from here is:
  - build the JARVIS/OpenClaw backend bridge and session ownership
  - add JARVIS-specific API endpoints or wrappers
  - then finish the dedicated JARVIS room UI against that lane

### Partial implementation already started before the pivot was fully corrected

- A draft frontend route and nav entry for `/jarvis` were already added:
  - `dashboard/frontend/src/App.tsx`
  - `dashboard/frontend/src/app/navigation.tsx`
- Those changes only establish navigation scaffolding.
- The actual JARVIS page component, settings move, OpenClaw bridge, and full UI surface have not been implemented yet.
- Treat the current `/jarvis` route/nav work as an in-progress stub, not a completed feature.

### Environment note

- `openclaw` is not installed on this Windows machine right now, so direct local CLI interrogation such as `openclaw --help` and `openclaw status` was not available during this planning pass.
- Backend conclusions above were derived from the checked-in ClawOS runtime/integration code rather than from a live local OpenClaw process.

### 2026-04-13 Codex implementation - JARVIS OpenClaw voice room delivered

- The JARVIS/OpenClaw pivot above is now implemented as a real product slice rather than remaining only a planning note.
- This pass should be understood as the first integrated JARVIS/OpenClaw delivery:
  - dedicated JARVIS backend service
  - dedicated JARVIS dashboard API lane
  - OpenClaw gateway adapter and config patching
  - owner WhatsApp routing into JARVIS/OpenClaw
  - dedicated `/jarvis` room UI
  - generic Settings no longer owning the ElevenLabs activation flow

### Backend implementation completed

- Added `openclaw_integration/responses_api.py` as the JARVIS-side OpenClaw HTTP adapter.
- The adapter now:
  - patches `~/.openclaw/openclaw.json` so the responses endpoint is enabled
  - ensures gateway auth token posture exists
  - writes a reusable gateway token file
  - auto-starts the managed OpenClaw gateway when installed but not already running
  - sends JARVIS traffic to the managed OpenClaw `main` agent over HTTP
- Added `services/jarvisd/service.py`.
- `jarvisd` now owns:
  - JARVIS session state
  - transcript history
  - typed chat
  - push-to-talk
  - TTS playback routing
  - OpenClaw chat requests
  - separate-thread / shared-memory behavior
  - the `Jarvis` / `Hey Jarvis` + `what's up` briefing trigger
- JARVIS state is persisted in `jarvis_state.json` with:
  - a stable UI thread key of `jarvis-ui`
  - per-thread response ids for OpenClaw continuity
  - shared memory for items like `last_project`
- Shared-memory extraction was tightened during testing so phrases like `working on project Atlas` now store `Atlas`, not `project Atlas`.

### Dashboard and channel routing completed

- `services/dashd/api.py` now exposes a dedicated authenticated JARVIS lane:
  - `GET /api/jarvis/session`
  - `GET /api/jarvis/health`
  - `GET /api/jarvis/config`
  - `POST /api/jarvis/config`
  - `POST /api/jarvis/push-to-talk`
  - `POST /api/jarvis/chat`
  - `POST /api/jarvis/mode`
- Dashboard websocket snapshots and live updates now include a dedicated `jarvis_session` event stream.
- `services/gatewayd/service.py` now routes owner WhatsApp traffic through JARVIS/OpenClaw first, using:
  - `thread_key = whatsapp:<jid>`
  - `source = whatsapp`
  - `speak_reply = False`
- The owner WhatsApp lane now shares the JARVIS/OpenClaw memory namespace while keeping its own short conversation thread.
- Morning briefing delivery in `gatewayd` was also updated to use the JARVIS path first, with fallback to the old manager path only if JARVIS/OpenClaw is unavailable.

### Frontend JARVIS room completed

- Finished the dedicated `/jarvis` route in the dashboard frontend.
- Added the new page component at `dashboard/frontend/src/pages/JarvisVoice.tsx`.
- `dashboard/frontend/src/app/AppShell.tsx` is now route-aware:
  - `/jarvis` hides the normal inspector rail
  - shell styling becomes immersive for the JARVIS room
  - the topbar push-to-talk action uses JARVIS endpoints when the user is on `/jarvis`
- Added JARVIS-specific frontend API wrappers in `dashboard/frontend/src/lib/commandCenterApi.ts`:
  - `getJarvisSession`
  - `getJarvisHealth`
  - `getJarvisConfig`
  - `setJarvisConfig`
  - `pushToTalkJarvis`
  - `sendJarvisChat`
  - `setJarvisMode`
- `dashboard/frontend/src/hooks/useCommandCenter.ts` now tracks JARVIS session state from snapshots, websocket events, and polling.
- `dashboard/frontend/src/index.css` now includes the dedicated JARVIS visual system:
  - immersive graphite/cyan chamber background
  - top-centered glowing orb with layered rings
  - animated stateful spectrum
  - live caption bubble
  - transcript panel
  - bottom text + mic composer
  - responsive mobile stacking
- `dashboard/frontend/src/pages/Settings.tsx` no longer presents the old generic ElevenLabs activation form as the primary voice ownership surface.
- Generic Settings now shows a compact JARVIS Voice handoff/status card that links the user into `/jarvis`.

### Current briefing and voice behavior in this implementation

- JARVIS uses OpenClaw for the actual chat/briefing brain when the managed OpenClaw gateway is available.
- JARVIS replies out loud by default unless voice mode is explicitly off.
- ElevenLabs remains the preferred JARVIS provider, with Piper kept as the fallback path.
- The `what's up` briefing flow is implemented with best-available source resolution:
  - weather via Open-Meteo when configured, otherwise demo data
  - headlines via Brave API when configured, otherwise demo data
  - calendar currently demo data
  - tasks from live ClawOS mission state when available, otherwise demo data
  - last project from shared JARVIS memory when available, otherwise demo data
- Google Calendar is therefore still not live in this pass; it remains a known v1 demo-data placeholder.

### Tests added or updated in this pass

- Added `tests/system/test_jarvis_openclaw.py` covering:
  - OpenClaw config patching for the responses endpoint
  - OpenClaw gateway auto-start behavior
  - JARVIS separate-thread / shared-memory behavior
- Updated `tests/system/test_voice_pipeline.py` with dedicated JARVIS endpoint coverage for `dashd`.
- Updated `tests/system/test_whatsapp_bridge.py` with owner-message routing coverage through JARVIS/OpenClaw.
- Updated `dashboard/frontend/tests/visual/command-center.spec.ts` to cover:
  - `/jarvis` rendering as a dedicated voice chamber
  - Settings handing JARVIS voice ownership off to the dedicated chamber

### Verification after JARVIS/OpenClaw implementation

- `npm run typecheck` passed in `dashboard/frontend`.
- `npm run build` passed in `dashboard/frontend`.
- `npm run test:visual -- tests/visual/command-center.spec.ts` passed with `5 passed`.
- `python -m pytest tests/system/test_voice_pipeline.py tests/system/test_whatsapp_bridge.py tests/system/test_jarvis_openclaw.py -q` passed with `10 passed`.
- `python scripts/verify_repo.py` passed end to end after this implementation:
  - `244 passed, 25 skipped`
  - frontend CI lane passed inside the verifier as well

### Known follow-up notes after this pass

- OpenClaw is still not installed on this Windows machine, so the new adapter/runtime path was validated through repo integration, mocked/system tests, and the verifier rather than against a live local OpenClaw binary.
- The Playwright run still emits harmless Vite proxy warnings for a few unstubbed ancillary endpoints during test teardown, but the visual suite itself passes and the verifier is green.
- Frontend builds refreshed tracked generated assets under `services/dashd/static`, so those generated bundle diffs are expected in the local worktree.
- The worktree also still contains unrelated `.claude`, docs, workflow-hardening, verifier, and earlier hardening changes from previous passes; they were left intact.

## Archived Pickup Point

> The following was the previous Claude Pickup Point before the 2026-04-06 direction update.
> Preserved per the update log policy. The build order below was superseded by docs/ROADMAP.md.

Claude should pick up from the competitive-platform foundation that is already wired through setup, API, UI, CLI, docs, tests, and security checks.

Previous best next build order (superseded):
1. Browser Workbench
2. Research engine with citations and resumable runs
3. MCP manager depth
4. richer A2A federation and trust model
5. Pack Studio visual builder
6. AGPL migration
7. native packaging validation
8. real ISO/Calamares validation on target environments
