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
