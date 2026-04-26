# ClawOS Roadmap — To The Finish Line



> Canonical roadmap. Supersedes `docs/STABILIZATION_ROADMAP.md`.

> Updated: 2026-04-07 by Codex.
> Nothing from the Codex PRs is omitted — each item is sequenced correctly.



---



## North Star



Ship ClawOS v0.1 as a product that feels like Apple built Iron Man's JARVIS for everyone.

Polish before features. Infrastructure before experience. Experience before platform depth.



---



## Current State (2026-04-26)



- Phases 1-11 merged. `python -m pytest tests -q` now passes with `206 passed`. Security audit green.
- 29 workflow modules across 6 categories.

- 24 services: a2ad, agentd, braind, clawd, dashd, frameworkd, jarvisd, llmd,
  mcpd, memd, metricd, modeld, omid, picoclawd, policyd, ragd, researchd, scheduler,
  secretd, setupd, skilld, toolbridge, voiced.

- Dashboard: Overview, Workflows, Packs, Providers, Registry, Traces, Settings, Setup.

- Competitive platform primitives: UseCasePack, ProviderProfile, ExtensionManifest,

  WorkflowProgram, TraceRecord, OpenClawImportManifest — all wired in catalog.py.

- CLI: clawctl with packs, providers, extensions, wf, benchmark, rescue openclaw, skill, framework, omi, ace, license, project.

- Wave 1 Packs defined: daily-briefing-os, coding-autopilot, sales-meeting-operator,

  chat-app-command-center.

- A2A: agent card, peer discovery, task delegation API.

- OpenClaw rescue path implemented.

- Stabilization is materially cleaner now: the legacy dashboard stack is gone, auth is tightened,

  the top-10 workflows are deterministic, and the first-party contracts are cleaner.

- Milestone 2 is complete: the premium shell/design-system pass, setup wizard rebuild,
  dashboard polish, voice path, hero workflows, and AGPL migration are all in place.
- Additional command-center surfaces are already shipped in-tree: Workbench, Research,
  MCP Manager, Federation, and Studio.
- Remaining debt is mostly release-facing: install validation on supported targets,
  `.deb` validation on a Linux builder, ISO / real-hardware validation, release assets,
  and a final docs accuracy pass.


---



## Milestone 1 — Stabilize



**Goal:** Eliminate structural debt so every future session builds on solid ground.

**Definition of done:** 150+ tests passing, security green, one dashboard stack, contract-clean.



### 1A. Kill the legacy dashboard stack

- Archive `dashboard/backend/` — it is documented as legacy in ARCHITECTURE_CURRENT.md.

- Canonical: `services/dashd/api.py` + `dashboard/frontend/`.

- Remove all imports and references that cross into the legacy backend.

- Update docs that still point to the old stack.



### 1B. Auth hardening

- Tighten auth on `dashd` endpoints — no unauthenticated access to sensitive routes in production.

- Tighten auth on `a2ad` endpoints — A2A peer trust model should require explicit allow-listing.

- Session token rotation on setup completion.

- Document the auth posture in `docs/SECURITY_AUDIT.md`.



### 1C. Top-10 workflow hardening

Replace prompt-only implementations with deterministic helpers for the 10 highest-value workflows:

`organize-downloads`, `summarize-pdf`, `repo-summary`, `pr-review`, `write-readme`,

`disk-report`, `log-summarize`, `changelog`, `find-duplicates`, `clean-empty-dirs`.



Each of these must:

- Succeed 100% of the time on supported platforms without an LLM available.

- Fail clearly with a helpful message on unsupported platforms.

- Have platform metadata set correctly (linux/macOS/windows).

- Have a regression test.



### 1D. Contract alignment

- All first-party callers use `/submit` with `intent` field.

- `shell.restricted` is the canonical shell tool everywhere.

- Destructive workflow gating through policyd is verified by test.

- Remove dead compatibility shims that are no longer needed.



### 1E. Test floor

- 150+ tests, all green.

- Add regression tests covering: agentd contract, workflow gating, tool aliases, auth rejection.

- `python -m pytest tests` + `python scripts/security_audit.py` both pass after every change.



---



## Milestone 2 — Premium Experience



**Goal:** Make ClawOS feel like Apple built it.

**Definition of done:** Every surface passes the premium quality bars in PRODUCT_VISION.md.



### 2A. Design system enforcement

- `docs/FIGMA_SYSTEM.md` is the law. Every component uses it.

- Audit all frontend pages against the design system.

- Fix any inconsistent spacing, color, typography, or animation.

- Every page has a designed empty state — not a blank screen.

- Transitions are animated. Loading is skeleton, not spinner.



### 2B. First-run wizard — Apple-grade

The setup wizard (setupd + SetupPage.tsx) is the product's first impression.



- Step 1: Welcome screen. Brand identity. One button: "Begin Setup".

- Step 2: Hardware detection + profile auto-select. Show what was detected. Confirm.

- Step 3: Pack selection. Visual cards. Brief descriptions. One click.

- Step 4: Provider selection. Local Ollama first. Cloud option visible but not default.

- Step 5: Model pull. Animated progress. "Downloading your AI..." — real progress, real ETA.

- Step 6: Voice setup. Enable or skip. If enabled: mic test, wake word test.

- Step 7: WhatsApp. QR scan or skip. Works or skips cleanly.

- Step 8: Summary. "ClawOS is ready." — show what was configured. Launch dashboard.



Each step must:

- Never fail silently.

- Have a back button.

- Have a skip option where appropriate.

- Show progress (step X of Y).

- Be beautiful on a 1366Ã—768 screen (minimum target).



### 2C. Dashboard polish

- Overview: real data, real graphs, useful at a glance.

- Workflows page: category filter, search, Run button with live WebSocket progress, history.

- Packs page: visual cards, install state, pack details panel.

- Providers page: status indicators (green/yellow/red), test button, switch in-place.

- Registry page: trust tier badges, permission list visible before install.

- Traces page: timeline view, filterable, exportable.

- Settings: grouped logically, every setting has a description, save feedback.

- All pages: consistent header, breadcrumb, keyboard shortcuts documented.



### 2D. Voice pipeline — end-to-end

- Whisper STT at 44100Hz via pipewire. No audio gaps.

- Piper TTS lessac-medium. Smooth playback.

- Wake word "Hey Claw" — OpenWakeWord.

- Push-to-talk as fallback.

- Voice status visible in dashboard header (listening / speaking / idle).

- Voice setup in wizard tests the mic and confirms it works before proceeding.



### 2E. Chat integration — reliable

- Messages route to the correct workspace.

- Tool approval by reply ("yes" / "no").

- Voice notes transcribed automatically.



### 2F. Hero workflow demo quality

The two hero workflows must be demo-perfect for promotional use:

- `organize-downloads`: scans a real Downloads folder, categorizes, moves, shows summary.

  Works in < 2 minutes on Tier B hardware.

- `summarize-pdf`: takes a PDF path, returns a structured summary with key points.

  Works in < 2 minutes on Tier B hardware using local extractive summarization.



Both must work in the dashboard with live WebSocket progress updates.



### 2G. AGPL migration

- Confirm all files carry AGPL-3.0 header or are explicitly excepted.

- Update LICENSE, README badge, pyproject.toml.

- No licensing ambiguity before public release.



Status on 2026-04-26: Milestone 2 complete. Voice, hero workflows, and the AGPL migration are all in place. clawctl wf CLI and Phase 11 workflow engine shipped. Milestone 3 is the active frontier.



---



## Milestone 3 — Ship v0.1



**Goal:** The product is publicly available, documented, and reproducible.

**Definition of done:** Clean install works on target hardware, assets ready for promotion.



### 3A. ISO validated

- Build Ubuntu 24.04 LTS base ISO with ClawOS preinstalled.

- Calamares installer for clean machines.

- Tested on Tier A (8GB mini PC) and Tier B (16GB laptop).

- First boot goes directly to first-run wizard. No terminal required.

- `packaging/iso/build_iso.sh` works end-to-end with documented steps.



### 3B. install.sh validated

- Works on clean Ubuntu 22.04, 24.04.

- Works on macOS 14+ Apple Silicon (as documented in docs/MACOS.md).

- Intel macOS: best-effort, documented.

- Windows: dev checkout only, not a supported install target.

- Every error in install.sh is caught and gives a recovery path.



### 3C. README — the product pitch

The README is the first thing anyone reads. It must:

- Open with the "Apple made JARVIS real" framing in one strong sentence.

- Show a screenshot of the dashboard above the fold.

- Have a "What is this" section that a non-technical person understands.

- Have a "Install in 5 minutes" section that actually works.

- List the hardware requirements clearly.

- Link to PRODUCT_VISION.md for deeper context.

- Have a demo GIF.

- Not be a wall of technical notes.



### 3D. Social assets

Promotional assets for the platforms you're using:

- Dashboard screenshot: dark mode, Overview page, real data showing workflows + activity.

- Setup wizard screenshot: Pack selection step.

- organize-downloads demo GIF: < 15 seconds, shows before/after.

- summarize-pdf demo GIF: < 15 seconds, shows PDF in, structured summary out.

- Voice demo GIF: "Hey Claw..." â†’ response playing — ambient, natural.



All assets: would look at home in an Apple product launch deck.



### 3E. Docs accuracy pass

- ARCHITECTURE_CURRENT.md: reflects final canonical service layout.

- PRODUCTION.md: accurate deployment steps.

- SECURITY_AUDIT.md: reflects current auth posture.

- MACOS.md: accurate for macOS 14+ Apple Silicon.

- COMPETITIVE_PLATFORM.md: updated with current API surface.

- No dead links. No placeholder text. No "TODO" in production docs.



### 3F. v0.1.0 release

- Git tag: `v0.1.0`.

- GitHub release with changelog and asset links.

- pyproject.toml version set to `0.1.0`.

- All tests passing at tag time.



---



## Milestone 4 — Platform Depth



**Goal:** Deliver the competitive platform features Codex built the foundation for.

**Start after:** v0.1.0 is tagged and public.



These are all real, all built on existing foundations, all valuable. Sequenced by user impact:



### 4A. Wave 1 Packs — production-grade

Make all four Wave 1 Packs fully production-grade:

- `daily-briefing-os`: morning digest, calendar summary, news, action items.

- `coding-autopilot`: repo summary, PR review, README generation, TODO tracking.

- `sales-meeting-operator`: meeting notes, CRM updates, follow-up drafts.

- `chat-app-command-center`: WhatsApp/Telegram command routing, smart replies.



Each pack needs: setup path, seeded dashboards, default workflows, provider recommendations,

policy pack, eval suite. Guided by COMPETITIVE_PLATFORM.md Wave 1 spec.



### 4B. Browser Workbench

- Access ClawOS from any browser on the local network, not just :7070.

- Responsive layout that works on mobile (WhatsApp companion use case).

- Progressive Web App manifest so it can be pinned to home screen.

- Auth gate for remote access.



### 4C. Research Engine

- Long-running research tasks with citation tracking.

- Resumable runs (save state, continue after restart).

- Web fetch + local document search combined.

- Results formatted as structured reports with source links.



### 4D. MCP Manager

- Visual manager for MCP tools in the dashboard.

- Install, enable, disable, configure MCP servers from the UI.

- Trust tier displayed. Permission list visible before install.

- Backed by the Registry trust model.



### 4E. Richer A2A Federation

- Multi-agent meshes: ClawOS instances delegating to each other.

- Trust model: explicit allow-list, signed agent cards.

- Federation dashboard: see connected peers, their status, delegated tasks.

- OTEL-native trace export for federated runs.



### 4F. Pack Studio (visual builder)

- Drag-and-drop workflow and pack builder in the dashboard.

- Export as a portable pack manifest.

- Share with the community registry.

- Trust tier: Community by default, upgradeable to Verified by review.



### 4G. Extension ecosystem hardening

- Signed extension packaging.

- Rollback support (revert to previous version).

- Stronger quarantine isolation.

- Extension update notifications in dashboard.



---



## Milestone 5 — True Distro



**Goal:** ClawOS is a first-class Linux distribution, not just an installer.

**Start after:** Platform depth is stable.



- Full Calamares-based installer with hardware detection during install.

- Custom Ubuntu-based ISO with ClawOS branding from boot.

- Auto-update system with rollback.

- Tier A hardware validation on real low-spec devices.

- Server/headless install profile (no display required).

- Optional desktop environment (XFCE or Gnome minimal).



---



## Guardrails (permanent)



These apply to every session, every milestone:



- `dashboard/frontend` is the canonical frontend. Do not add a second one.

- `services/dashd/api.py` is the canonical dashboard backend. Do not split it.

- `services/setupd` owns guided setup state and flows. Do not duplicate setup logic.

- `clawos_core/` is the only place for shared primitives. Never hardcode constants outside it.

- Every tool call goes through policyd. No exceptions.

- Every service has `main.py` + `service.py` + `health.py`.

- All IDs use `clawos_core/util/ids.py`. All paths use `clawos_core/util/paths.py`.

- `json_repair` wrapper in `jsonx.py` — never raw `json.loads` on LLM output.

- Zero test failures before shipping any milestone.

- Root cause before patch. One thing at a time.

- Security audit and test suite both green before any merge.

- OpenClaw-first external positioning, provider-neutral internals.



---



## Build Order Summary



```

NOW      Milestone 3: Ship v0.1
         â””â”€â”€ ISO validated on real hardware
         â””â”€â”€ install.sh validated (Ubuntu + macOS)
         â””â”€â”€ README — the product pitch
         â””â”€â”€ Social assets ready
         â””â”€â”€ Docs accuracy pass
         â””â”€â”€ v0.1.0 release tag

NEXT     Milestone 4: Platform Depth
         â””â”€â”€ Wave 1 Packs production-grade
         â””â”€â”€ Browser Workbench
         â””â”€â”€ Research Engine
         â””â”€â”€ MCP Manager
         â””â”€â”€ Richer A2A Federation
         â””â”€â”€ Pack Studio
         â””â”€â”€ Extension ecosystem hardening

THEN     Milestone 5: True Distro
         â””â”€â”€ Calamares installer
         â””â”€â”€ Custom branded ISO
         â””â”€â”€ Auto-update system
         â””â”€â”€ Tier A validation
```

