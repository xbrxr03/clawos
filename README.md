# ClawOS v0.1.1

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Status](https://img.shields.io/badge/status-v0.1.1-green.svg)](https://github.com/xbrxr03/clawos)

> **Local AI agent for your laptop. One curl command. No cloud. No API keys. No telemetry.**

---

## ⚡ What is ClawOS?

ClawOS is a **local-first AI agent** that runs on your existing machine — no cloud required, no API keys, no monthly bill.

Bring your own agent brain — **Nexus** (built-in), **OpenClaw**, or any framework with plugin hooks. It combines local LLMs via [Ollama](https://ollama.com) with a powerful agent runtime to give you:

- 🤖 **Your own AI agent** — runs 100% offline on your hardware
- 🗣️ **Voice activation** — "Hey Claw" wakes your agent
- 🔒 **Zero telemetry** — nothing leaves your machine, ever
- 🎨 **Beautiful dashboard** — control everything from your browser
- ⚡ **Fast and private** — local inference, no network latency

---

## 🎬 Demos

**60-second demo:** [Watch on YouTube](https://youtube.com/...) *(coming soon)*

---

## 🚀 Quick Start

### Option 1: Install on Your Existing Machine (Recommended)

```bash
# One command, 2 minutes, your AI is ready
curl -fsSL https://install.clawos.io | bash

# Start services
clawctl start

# Check health
clawctl health
```

### Option 2: Bootable ISO (Dedicated Machine)

For a clean machine or dedicated AI appliance:

```bash
# Download and flash to USB
sudo dd if=clawos-0.1.0-amd64.iso of=/dev/sdX bs=4M status=progress

# Boot from USB → First-run wizard → Done.
```

---

## 💻 Hardware Requirements

| Tier | RAM | Hardware | Experience |
|------|-----|----------|------------|
| **A** | 8GB | Old laptops, mini PCs | Claw Core (gemma3:4b) |
| **B** | 16GB | Modern laptops, desktops | + Larger models (qwen2.5:7b) |
| **C** | 32GB+ | Workstations, gaming PCs | Large models, fast inference |

**Minimum:** x86_64 CPU, 8GB RAM, 20GB storage  
**Recommended:** 16GB+ RAM, SSD storage

---

## ✨ Key Features

### 🌅 Morning Briefing
Say "Hey Claw" and get a spoken summary of your day: calendar, weather, tasks, and news.

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
│  Voice │ Web Dashboard │ CLI                        │
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

[AGPL-3.0](LICENSE) — Free to use, modify, and distribute.

---

## 🙏 Acknowledgments

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
