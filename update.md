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
