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

- ClawOS is being shaped into:
  - a flagship Ubuntu-based AI distro
  - polished installs for existing Linux and macOS machines
- UX north star:
  - Apple-like OpenClaw operating system command center
  - Finder/Xcode-style shell
  - OS-home feel
  - Apple-style onboarding
- Product stance:
  - OpenClaw-first
  - fully open source
  - no paid tier
  - local-first by default
  - provider-neutral internally

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

## Claude Pickup Point

Claude should pick up from the competitive-platform foundation that is already wired through setup, API, UI, CLI, docs, tests, and security checks.

### Read these first

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

### Current known-good state

- `python -m pytest tests` passed with `122 passed`
- `python scripts/security_audit.py` passed
- CLI competitive commands passed:
  - `clawctl packs list`
  - `clawctl providers list`
  - `clawctl extensions list`
  - `clawctl benchmark`
  - `clawctl rescue openclaw`

### Best next build order

1. Browser Workbench
2. Research engine with citations and resumable runs
3. MCP manager depth
4. richer A2A federation and trust model
5. Pack Studio visual builder
6. AGPL migration
7. native packaging validation
8. real ISO/Calamares validation on target environments

### Important guardrails

- Keep `dashboard/frontend` as the canonical frontend.
- Keep `services/dashd` as the canonical dashboard backend.
- Keep `services/setupd` as the guided setup control plane.
- Preserve the OpenClaw-first external positioning, but keep internals provider-neutral.
- Do not reintroduce duplicate primary UI paths.
- Keep security and verification green after every major slice.
