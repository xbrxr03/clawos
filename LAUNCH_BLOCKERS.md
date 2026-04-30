# ClawOS v1.0 Launch Blockers

> Auto-generated during Phase 1: Reality Check
> Started: 2026-04-30

## Legend
- 🔴 CRITICAL: Blocks launch
- 🟡 HIGH: Fix before launch
- 🟢 LOW: Nice to have
- ✅ FIXED: Resolved
- 🚀 PUSHED: Code pushed to GitHub

---

## Phase 1: Core Demos (COMPLETE ✅)

### Demo 1: Morning Briefing
| Status | Severity | Issue | Notes |
|--------|----------|-------|-------|
| ✅ FIXED | 🔴 CRITICAL | Reminder daemon | services/reminderd/ on port 7087 |
| ✅ FIXED | 🔴 CRITICAL | Wake-word bridge | services/waketrd/ on port 7088 |
| ✅ FIXED | 🟡 HIGH | Calendar importer | tools/calendar/import_ics.py with SQLite |

### Demo 2: Essay to Editor
| Status | Severity | Issue | Notes |
|--------|----------|-------|-------|
| ✅ FIXED | 🔴 CRITICAL | Demo missing | demos/essay_to_editor.py with 5 styles |
| 🟢 LOW | 🟢 LOW | Clipboard tools | Requires xclip/wl-copy on system |

### Demo 3: Approval Popup
| Status | Severity | Issue | Notes |
|--------|----------|-------|-------|
| ✅ FIXED | 🟡 HIGH | Already exists | ApprovalOverlay.tsx + /api/approvals endpoint |

---

## Phase 2: Testing & CLI (COMPLETE ✅)

| Status | Severity | Issue | Notes |
|--------|----------|-------|-------|
| ✅ FIXED | 🔴 CRITICAL | reminderd API bug | Fixed created_at field, switched to JSON body |
| ✅ FIXED | 🟡 HIGH | Integration tests | 7/7 tests passing for reminderd, waketrd, calendar |
| ✅ FIXED | 🟡 HIGH | SMART_MODEL default | Changed from qwen2.5:7b-instruct to qwen2.5:7b |
| ✅ FIXED | 🟡 HIGH | Desktopd config error | Fixed get_config() → load_config() |
| 🚀 PUSHED | 🟡 HIGH | demos CLI | clawctl demos command with all 3 demos |

---

## Phase 3: Polish & Hardening (IN PROGRESS 🔄)

| Status | Severity | Issue | Notes |
|--------|----------|-------|-------|
| 🟡 HIGH | 🟡 HIGH | FastAPI lifespan warnings | on_event deprecated, needs lifespan handlers |
| 🟢 LOW | 🟢 LOW | Tauri overlay rebuild | May need cargo build --release |
| 🟢 LOW | 🟢 LOW | Service monitoring | Add health check dashboard |
| 🟢 LOW | 🟢 LOW | Documentation | More examples and tutorials |

---

## Service Health Status

| Service | Port | Status | Notes |
|---------|------|--------|-------|
| dashd | 7070 | ✅ Running | Dashboard |
| clawd | 7071 | ✅ Running | Core API |
| agentd | 7072 | ✅ Running | Agent runtime |
| memd | 7073 | ✅ Running | Memory service |
| policyd | 7074 | ✅ Running | Policy enforcement |
| modeld | 7075 | ✅ Running | Model proxy |
| voiced | 7079 | ✅ Running | Voice pipeline |
| desktopd | 7080 | ✅ Running | Clipboard only |
| reminderd | 7087 | ✅ Running | Notifications |
| waketrd | 7088 | ✅ Running | Wake bridge |

---

## Commits Pushed (8 total)

| Hash | Phase | Description |
|------|-------|-------------|
| fe60443 | P1 | feat(reminderd): add reminder daemon with desktop notifications |
| 2028171 | P1 | feat(waketrd): wake word trigger service for morning briefing |
| ecc4b40 | P1 | feat(calendar): ICS importer with SQLite storage |
| 74e5880 | P1 | feat(demos): essay-to-editor demo + router model fix |
| 0e72ec0 | P1 | docs: update launch blockers - Phase 1 complete |
| ccec5e7 | P2 | docs(demos): add README and CLI helper for morning briefing |
| 43a7cd9 | P2 | fix(reminderd): add created_at field to INSERT, use JSON body for API |
| 8108fd6 | P2 | feat(clawctl): add demos subcommand + fix tests |

---

## Last Updated
2026-04-30 04:00

## Status
✅ Phase 1 Complete - All 3 demos working
✅ Phase 2 Complete - Tests passing, CLI added
🔄 Phase 3 In Progress - Final polish and hardening

## Next Steps
1. Fix FastAPI lifespan deprecation warnings
2. Add service health dashboard
3. Final documentation pass
4. Release v1.0!
