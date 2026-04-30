# ClawOS v0.1.0 Release Notes

**Release Date:** 2026-04-30  
**Codename:** "Iron Foundation"

---

## 🎉 What's New

ClawOS v0.1.0 is the first public release of the open-source AI operating system. This release includes the core infrastructure, three flagship demos, and a complete CLI toolchain.

---

## ✨ Major Features

### 🤖 Three Flagship Demos

1. **Morning Briefing** (`clawctl demos morning-briefing`)
   - Voice-activated: "Hey JARVIS" wakes the system
   - Spoken summary of calendar, weather, and tasks
   - Bridge between voiced and Nexus via waketrd service

2. **Essay Editor** (`clawctl demos essay-editor`)
   - Clipboard-aware grammar checking
   - 5 writing styles: formal, casual, academic, concise, engaging
   - Grammar check → Style rewrite → Copy back workflow

3. **Approval Popup** (`clawctl demos approval-test`)
   - Human-in-the-loop for sensitive operations
   - Tauri-based floating window
   - Policy engine integration

### 🏗️ New Services

- **reminderd** (port 7087) — Desktop notification daemon
- **waketrd** (port 7088) — Wake word trigger bridge
- Both services include full HTTP API + integration tests

### 📅 Calendar System

- ICS file importer (`tools/calendar/import_ics.py`)
- SQLite storage with UPSERT semantics
- Tracks event source for traceability
- Command: `python -m tools.calendar.import_ics <file.ics>`

### 🛠️ CLI Improvements

- `clawctl demos` — Run any of the three flagship demos
- `clawctl health` — Real-time service health dashboard
- Services: dashd, clawd, agentd, memd, policyd, modeld, voiced, desktopd, reminderd, waketrd

### 🧪 Testing

- 12 integration tests (all passing)
- Unit tests for calendar importer
- Service API tests for reminderd and waketrd

---

## 📦 Installation

### Option 1: Bootable ISO

Download `clawos-0.1.0-amd64.iso` from the releases page, flash to USB, and boot.

```bash
sudo dd if=clawos-0.1.0-amd64.iso of=/dev/sdX bs=4M status=progress
```

### Option 2: Install Script

```bash
curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh | bash
```

---

## 🔧 Hardware Support

| Tier | RAM | Recommended Models |
|------|-----|-------------------|
| A | 8GB | gemma3:4b |
| B | 16GB | qwen2.5:7b |
| C | 32GB+ | qwen2.5:14b+ |

---

## 🐛 Known Issues

- FastAPI lifespan deprecation warnings (fixed in Phase 3)
- Some legacy tests have import errors (braind, sandboxd - non-critical)
- Desktop screenshot/keyboard/mouse requires display connection

---

## 🔒 Security

- Policy engine enforces human approval for sensitive operations
- All services run on localhost only
- AGPL-3.0 license ensures openness

---

## 📊 Stats

- **Services:** 10 daemons
- **Integration Tests:** 12 (100% passing)
- **Commits:** 12 since inception
- **Lines of Code:** ~50,000

---

## 🙏 Thanks

Special thanks to the OpenClaw community and the Ollama team for making local AI accessible.

---

## 🚀 Next Steps

- Milestone 4: Platform Depth (Wave 1 Packs, Research Engine, MCP Manager)
- Milestone 5: True Distro (Calamares installer, auto-updates)

See [ROADMAP.md](docs/ROADMAP.md) for full details.

---

## 📞 Support

- GitHub Issues: https://github.com/xbrxr03/clawos/issues
- Discord: https://discord.gg/clawos

**Happy Clawing! 🤖**
