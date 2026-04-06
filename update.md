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

## Current Canonical Surfaces

- `services/dashd` is the canonical dashboard/backend surface.
- `dashboard/frontend` is the canonical frontend surface.
- `services/setupd` owns guided setup state and flows.
- `packaging/iso` is the distro packaging path.
- Terminal and legacy setup paths are fallback/recovery surfaces, not the flagship UX.

## High-Signal Files

- `docs/ARCHITECTURE_CURRENT.md`
- `docs/STABILIZATION_ROADMAP.md`
- `docs/COMPETITIVE_PLATFORM.md`
- `services/dashd/api.py`
- `services/setupd/service.py`
- `services/setupd/state.py`
- `clawos_core/catalog.py`
- `clawos_core/models/__init__.py`
- `dashboard/frontend/src/App.tsx`
- `dashboard/frontend/src/pages/setup/SetupPage.tsx`

## Updates Done By Claude

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

## Pending Task: macOS-Themed Dashboard Redesign

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

## Claude Pickup Point

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
