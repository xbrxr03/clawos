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

*This log is append-only. Mistakes are features — they tell you ClawOS is being used.*
