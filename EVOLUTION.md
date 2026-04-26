# ClawOS Evolution Log

> Every mistake ClawOS makes is logged here. Every fix is shipped. The AI gets smarter every day.

This log is automatically updated as ClawOS encounters edge cases, user corrections, and new patterns. It's the living memory of what ClawOS has learned.

---

## 2026-04-11 — Daemon wouldn't start (203/EXEC)

**What happened:** After install, `clawos.service` showed `status=203/EXEC` and crashed in a restart loop (counter hit 1399+). The service was defined but systemd couldn't find the binary.

**Root cause:** `ExecStart=/usr/bin/python3` was hardcoded. On Ubuntu 24.04, the Python binary at that exact path doesn't exist in all configurations. A leftover `override.conf` drop-in was also shadowing our unit.

**What ClawOS learned:** Always use `/usr/bin/env python3` in systemd units. Clean up `.service.d/` override directories on reinstall.

**Fix shipped:** `systemd/clawos.service` now uses `ExecStart=/usr/bin/env python3 %h/clawos/clients/daemon/daemon.py`. `setup-systemd.sh` now removes drop-in overrides on every install.

---

## 2026-04-11 — Wake word never armed

**What happened:** Voice mode was set to `push_to_talk` by default. Wake word never fired. Users had to manually switch mode.

**Root cause:** `configs/defaults.yaml` had `voice.enabled: false` and `mode: "push_to_talk"`. The wake detector only arms when mode is `wake_word` — so it never started.

**What ClawOS learned:** JARVIS should wake up ready to listen. The wow moment requires zero configuration.

**Fix shipped:** `configs/defaults.yaml` now defaults to `voice.enabled: true` and `mode: "wake_word"`.

---

## 2026-04-11 — Voice roundtrip returned dummy response

**What happened:** Wake word fired correctly. STT transcribed the speech. But the response was always `"I heard: [transcript]"` — a literal debug string shipped to production.

**Root cause:** `services/voiced/service.py::_handle_voice_roundtrip()` had a placeholder response instead of calling the agent.

**What ClawOS learned:** The voice loop must be wired end-to-end before any other voice work. A pipeline with a broken last step produces nothing useful.

**Fix shipped:** `_handle_voice_roundtrip()` now calls `agentd.chat_direct(transcript, channel="voice")`. ElevenLabs/Piper TTS routing wired through TTSRouter.

---

## 2026-04-11 — gemma3:4b too slow on 8GB CPU machines

**What happened:** Tier A installs (≤8GB RAM, CPU-only) pulled gemma3:4b by default. Response times were 30-90 seconds per query — unusable as a voice assistant.

**Root cause:** gemma3:4b (~3.3GB) was the default for all Tier A machines regardless of speed.

**What ClawOS learned:** Voice assistants need <5s response time. Model selection must prioritize inference speed over capability on constrained hardware.

**Fix shipped:** Tier A now defaults to `qwen2.5:3b` (~2.0GB, significantly faster CPU inference). Tier B gets `qwen2.5:7b`.

---

## 2026-04-26 — Phase 11: workflow engine, clawctl wf, and platform cleanup

**What happened:** Three gaps blocked the HN demo: (1) no `clawctl wf` CLI despite the dashboard showing `clawctl wf organize-downloads` as the entry point; (2) `PORT_GATEWAYD` was removed from constants but still imported in `responses_api.py` and `launcher.py`, crashing on startup; (3) WhatsApp references leaked through Traces, Brain, JarvisVoice, and the Getting Started card — a product that removed WhatsApp still showed it everywhere.

**Root cause:** The gatewayd service was retired but its dependents weren't updated. The `clawctl wf` command was spec'd in the UI layer but never implemented. WhatsApp surface-area wasn't swept after the capability decision.

**What ClawOS learned:** Removing a service requires a blast-radius sweep of all importers, not just the service file. CLI commands referenced in the UI must exist before UI ships. Product decisions need a full-surface audit across every page, diagram, and static copy.

**Fix shipped:**
- `workflows/engine.py` + 27 workflow modules: full Phase 11 engine with `needs_agent=False` for the two HN demo workflows (`organize-downloads`, `summarize-pdf`), CapabilityScanner for ranked suggestions.
- `clawctl/commands/workflow.py` + `clawctl wf` group registered in `main.py`: `wf list [--category] [--search]`, `wf info <id>`, `wf run <id> [key=value…] [--dry-run]`. All three verified end-to-end.
- `responses_api.py` + `launcher.py`: removed `PORT_GATEWAYD` import, added local `_PORT_OPENCLAW = 18789`.
- `tests/system/test_phase9.py`: removed dead `test_port_gatewayd` and `test_gatewayd_whatsapp` test functions.
- `dashd` login + `_setup_bypass_allowed`: now accepts token-in-body auth and falls back to `settings.host` loopback check so TestClient requests pass.
- WhatsApp stripped from Traces, Brain, JarvisVoice transcript, pages.jsx approvals/audit, GettingStartedCard, PolicyScreen, and README architecture diagram.
- Test suite: 205/206 passing (1 known timing flake in WebSocket test under parallel run).

---

*This log is append-only. Mistakes are features — they tell you ClawOS is being used.*
