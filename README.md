# ClawOS v0.1.0

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Status](https://img.shields.io/badge/status-v0.1.0-green.svg)](https://github.com/xbrxr03/clawos)

> **OpenClaw + Ollama, offline, on any x86 machine.**
> 
> Flash a USB. Boot. Your AI agent is running locally. No API keys. No monthly bill.

---

## ⚡ What is ClawOS?

ClawOS is a **bootable Linux ISO** that turns any x86 machine (laptop, mini PC, old desktop) into a **local AI agent computer**.

It combines the power of [OpenClaw](https://github.com/openclaw) with the simplicity of [Ollama](https://ollama.com) to give you:

- 🤖 **13,700+ community skills** — from file management to web scraping
- 🗣️ **Voice activation** — "Hey JARVIS" wakes your agent
- 🔒 **100% offline** — runs locally, never sends data to the cloud
- 🎨 **Beautiful dashboard** — control everything from your browser
- 📱 **WhatsApp/Telegram integration** — chat with your agent from your phone

---

## 🎬 Demo

```bash
# Flash ClawOS to USB
sudo dd if=clawos-0.1.0-amd64.iso of=/dev/sdX bs=4M status=progress

# Boot from USB → First-run wizard → Done.
```

**60-second demo:** [Watch on YouTube](https://youtube.com/...) *(coming soon)*

---

## 🚀 Quick Start

### Option 1: Bootable ISO (Recommended)

1. **Download** the ISO from [Releases](https://github.com/xbrxr03/clawos/releases)
2. **Flash** to USB: `sudo dd if=clawos-0.1.0-amd64.iso of=/dev/sdX bs=4M`
3. **Boot** from USB on any x86 machine
4. **Follow** the first-run wizard
5. **Done** — dashboard opens at `http://localhost:7070`

### Option 2: Install on Existing Linux

```bash
# Download and run installer
curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh | bash

# Start services
clawctl start

# Check health
clawctl health
```

---

## 💻 Hardware Requirements

| Tier | RAM | Hardware | Experience |
|------|-----|----------|------------|
| **A** | 8GB | Old laptops, mini PCs | Claw Core (gemma3:4b) |
| **B** | 16GB | Modern laptops, desktops | + OpenClaw (qwen2.5:7b) |
| **C** | 32GB+ | Workstations, gaming PCs | Large models, fast inference |

**Minimum:** x86_64 CPU, 8GB RAM, 20GB storage  
**Recommended:** 16GB+ RAM, SSD storage

---

## ✨ Key Features

### 🌅 Morning Briefing
Say "Hey JARVIS" and get a spoken summary of your day: calendar, weather, tasks, and news.

```bash
clawctl demos morning-briefing
```

### 📝 Essay Editor
Copy text from any editor, run grammar check + style rewrite, paste back.

```bash
# Copy text, then:
clawctl demos essay-editor --style concise
```

### 🛡️ Human-in-the-Loop
Sensitive operations (file delete, shell commands) require your approval via floating popup.

```bash
clawctl demos approval-test
```

### 📊 Dashboard
Web interface at `http://localhost:7070`:
- **Overview** — system status, active workflows
- **Workflows** — 29 built-in automations
- **Packs** — skill packs for different personas
- **Settings** — configure providers, voice, memory

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                   User Interfaces                     │
│  Voice │ Web Dashboard │ CLI │ WhatsApp │ Telegram  │
└────────────────────────┬────────────────────────────┘
                         │
    ┌────────────────────┼────────────────────┐
    │                    │                    │
┌───▼───┐   ┌───────────▼────────┐   ┌───────▼──────┐
│ voiced │   │   Nexus Agent     │   │  Services    │
│ Wake   │   │   (ReAct Loop)    │   │  dashboard   │
│ Word   │   │                    │   │  calendar    │
│ TTS/STT│   │   ┌────────────┐   │   │  reminders   │
└───┬───┘   │   │  Policy    │   │   │  policy      │
    │       │   │  Engine    │   │   └──────────────┘
    │       │   └────────────┘   │
    │       └───────────────────┘
    │
┌───▼──────────────────────────────────────────────┐
│                   Local Models                      │
│  gemma3:4b │ qwen2.5:7b │ llama3.2:3b │ Ollama   │
└────────────────────────────────────────────────────┘
```

**Core Services** (10 daemons):
- `dashd:7070` — Dashboard API
- `agentd:7072` — Agent runtime
- `voiced:7079` — Voice pipeline
- `reminderd:7087` — Desktop notifications
- `waketrd:7088` — Wake word bridge
- Plus: clawd, memd, policyd, modeld, desktopd

---

## 🛠️ Development

```bash
# Clone repository
git clone https://github.com/xbrxr03/clawos.git
cd clawos

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest tests/ -q

# Start dev services
bash scripts/dev_boot.sh --full

# Check service health
clawctl health
```

---

## 📁 Project Structure

```
clawos/
├── clawos_core/        # Core constants, utilities
├── services/           # Microservices (10 daemons)
│   ├── dashd/          # Dashboard API
│   ├── agentd/         # Agent runtime
│   ├── voiced/         # Voice pipeline
│   ├── reminderd/      # Notifications
│   └── waketrd/        # Wake word bridge
├── runtimes/           # Agent runtimes (Nexus)
├── tools/              # CLI tools (calendar, etc.)
├── demos/              # Flagship demos
├── dashboard/          # React frontend
├── clawctl/            # CLI commands
├── scripts/            # Install, boot scripts
├── packaging/          # ISO, .deb builds
└── tests/              # Test suite
```

---

## 📚 Documentation

- [Installation Guide](docs/DEPLOYMENT_GUIDE.md)
- [Architecture Overview](docs/ARCHITECTURE_CURRENT.md)
- [API Reference](docs/API_REFERENCE.md)
- [Security Audit](docs/SECURITY_AUDIT.md)
- [Product Vision](docs/PRODUCT_VISION.md)

---

## 🔒 Security

- **Policy Engine** — human approval for sensitive operations
- **Merkle Audit Trail** — tamper-proof execution log
- **Sandboxed Tools** — code runs in restricted environment
- **Local Only** — no data leaves your machine

See [SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md) for details.

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
# Fork, clone, branch
git checkout -b feature/my-feature
git commit -m "feat: add awesome feature"
git push origin feature/my-feature
# Open PR
```

---

## 📜 License

[AGPL-3.0](LICENSE) — Free to use, modify, and distribute. OpenClaw was AGPL, so ClawOS is too.

---

## 🙏 Acknowledgments

- **OpenClaw** — The original 13,700+ skill ecosystem
- **Ollama** — Local LLM management made simple
- **Nous Research** — Hermes models and agent research
- **Claude Code** — Architecture inspiration

---

## 📞 Support

- 💬 [Discord](https://discord.gg/clawos)
- 🐛 [Issues](https://github.com/xbrxr03/clawos/issues)
- 📧 [Email](mailto:hello@clawos.ai)

---

> **"The future of AI is local, private, and yours to control."**
