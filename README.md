<div align="center">

# ClawOS

**Your laptop. Your AI. Your rules.**

A JARVIS-style AI assistant that runs entirely on your machine —  
voice activation, multi-step tool use, 7-layer memory, zero cloud.

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Telemetry: zero](https://img.shields.io/badge/telemetry-zero-brightgreen.svg)](#zero-telemetry)

[Install in 2 minutes](#-quick-start) · [Watch the demos](#-see-it-in-action) · [Read the docs](docs/) · [Join the discussion](https://github.com/xbrxr03/clawos/discussions)

</div>

---

## Why ClawOS?

**Ollama gave you a local model. ClawOS gives you a local agent.**

Most local AI tools are chatbots in a terminal. ClawOS is different:

- 🗣️ **Talk to it** — "Hey Claw, good morning" and it gives you a voiced briefing of your day
- ⚡ **It does things** — "Write me a 1000-word essay and paste it into my editor" — and it actually happens
- 🛡️ **It asks first** — sensitive actions trigger a floating approval popup before execution
- 🔒 **Nothing leaves your machine** — zero telemetry, zero cloud, zero API keys. [Verify it yourself.](#zero-telemetry)
- 🧠 **It remembers** — 7-layer memory that persists across sessions, not a goldfish chatbot
- 💰 **It's free** — runs on Ollama, on your hardware. No subscription, no token counting, no surprises

> *ClawOS is what you'd get if Apple built Iron Man's JARVIS and gave it away for free.*

---

## ✨ See it in action

### 🌅 Morning Briefing
Say *"Hey Claw, good morning"* and hear a synthesized briefing — time, weather, calendar, reminders, and what you worked on yesterday. Five tool calls fire in parallel. Fully offline-capable.

```bash
clawctl demos morning-briefing
```

### 📝 Multi-Step Composition
*"Write me a 1000-word essay about AI ethics and paste it into the text editor."* Watch the 4-tool chain execute: write → clipboard → open editor → paste. Done in seconds.

```bash
clawctl demos essay-editor
```

### 🛡️ Floating Approval Popup
When the agent wants to run a shell command, delete a file, or close an app — a borderless always-on-top window appears. You approve or deny. Built on Tauri, native to your OS.

```bash
clawctl demos approval-test
```

> 🎬 **Demo videos coming in v0.1.2** — see [docs/DEMOS.md](docs/DEMOS.md) for exact phrasing and expected output. Try them yourself after install!

---

## 🚀 Quick start

```bash
curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh | bash
```

The installer takes ~2 minutes. Walks you through a 9-step browser wizard — hardware detection, model pull, voice setup, permissions. When done, your dashboard opens at `http://localhost:7070`.

```bash
clawctl health    # verify everything's running
```

### Bootable ISO

Got an old laptop? Flash ClawOS onto it and dedicate it to being your JARVIS:

```bash
sudo dd if=clawos-amd64.iso of=/dev/sdX bs=4M status=progress
```

---

## 💻 Hardware tiers

| Tier | RAM | Model | Experience |
|:----:|:---:|:-----|:-----------|
| **A** | 8 GB | qwen2.5:3b | Basic — works on old laptops, mini PCs |
| **B** | 16 GB | qwen2.5:7b | Full — multi-step tool use, fast briefings |
| **C** | 32 GB+ | qwen2.5:7b + qwen2.5-coder:7b | Power — coder model for file/shell tasks |

**Minimum:** x86_64 CPU, 8 GB RAM, 20 GB storage, Linux (Ubuntu 22.04+, Fedora 39+, Arch).  
NVIDIA GPU optional but accelerates inference.  
macOS support arriving in v0.2.

---

## ⚡ What's inside

| | |
|:---|:---|
| 🤖 **Native agent loop** | qwen2.5:7b with native Ollama function calling, parallel tool execution, dynamic model routing (3b → 7b → coder) |
| 🗣️ **Voice activation** | "Hey Claw" wake word. Whisper STT, Piper TTS. Push-to-talk mode. |
| 🧠 **7-layer memory** | Pinned facts, semantic recall (ChromaDB), full-text search, knowledge graph, archive, ACE self-improving learnings, workflow state |
| 🛡️ **Human-in-the-loop** | Sensitive actions trigger a native approval popup. You say yes or no. Every time. |
| 🎨 **Dashboard** | Full React SPA at :7070. Workflows, packs, traces, memory, settings — all in one place. |
| 🔌 **Bring your own brain** | Nexus (built-in), OpenClaw, or any framework with plugin hooks |
| 📦 **28 built-in workflows** | Summarize PDFs, organize downloads, bulk rename, daily digests, and more |
| 🛠️ **31 tools** | System control, file ops, web search, reminders, calendar, desktop automation |

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────┐
│                   User Interfaces                         │
│       Voice  │  Web Dashboard  │  CLI  │  Tauri Overlay  │
└─────────────────────────┬─────────────────────────────────┘
                          │
       ┌──────────────────┼──────────────────┐
       │                  │                  │
   ┌───▼────┐    ┌────────▼─────────┐   ┌────▼─────┐
   │ voiced │    │   Nexus Agent    │   │ Services │
   │  STT   │    │ (4-tier pipeline)│   │  memd    │
   │  TTS   │    │  ┌────────────┐  │   │  policyd │
   │  wake  │    │  │  Policy    │  │   │  workfd  │
   └───┬────┘    │  │  Engine    │  │   │  skilld  │
       │        │  └────────────┘  │   │  desktopd│
       │        └──────────────────┘   └──────────┘
       │
   ┌───▼─────────────────────────────────────────────┐
   │              Local Models (Ollama)               │
   │  qwen2.5:3b · qwen2.5:7b · qwen2.5-coder:7b     │
   └──────────────────────────────────────────────────┘
```

**Core daemons** (29 microservices, ~10 critical at runtime):

| Daemon | Port | What it does |
|:-------|:-----|:-------------|
| `dashd` | 7070 | Dashboard API |
| `agentd` | — | Agent runtime |
| `voiced` | — | Whisper + Piper voice pipeline |
| `memd` | 7073 | 7-layer memory |
| `policyd` | 7074 | Approval engine + audit log |
| `desktopd` | 7080 | Input automation (clipboard, paste, screenshot) |
| `reminderd` | 7087 | Desktop notifications |
| `waketrd` | 7088 | Wake word → briefing bridge |
| `skilld` | — | BM25 skill retrieval |
| `workfd` | — | 28+ built-in workflows |

---

## <a id="zero-telemetry"></a>🔒 Zero telemetry — verify it yourself

No analytics. No error reporting. No usage stats. No phone-home. Run this:

```bash
grep -rn "posthog\|sentry\|google-analytics\|mixpanel\|amplitude" \
  --include="*.py" --include="*.ts" --include="*.tsx" .
# returns nothing
```

The only network calls ClawOS makes: Ollama (localhost), DuckDuckGo (web search), wttr.in (weather), your RSS feeds. All optional. All disableable.

---

## 🔐 Security

- **Policy engine** — every tool call gated; sensitive ops queue for human approval
- **Workspace sandbox** — file ops can't escape `~/clawos/workspace/`
- **Shell allowlist** — `run_command` restricted to safe binaries; blocks `python3 -c <code>` injection
- **Merkle audit trail** — tamper-proof execution log in policyd
- **No SSRF** — `web_search` blocks private/loopback IPs

See [SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md).

---

## 🛠️ Development

```bash
git clone https://github.com/xbrxr03/clawos.git
cd clawos
pip install -e ".[dev]"

# Run tests (no live LLM needed)
pytest tests/unit/test_agent_*.py -q

# Boot dev services
bash scripts/dev_boot.sh --full

# Check health
clawctl health

# Tail logs
clawctl logs dashd
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## 📁 Project structure

```
clawos/
├── runtimes/agent/         # Nexus agent loop (4-tier pipeline)
│   ├── runtime.py          #   Priority pipeline: memory → confirm → intent → LLM
│   ├── intents.py          #   Deterministic regex classifier
│   ├── router.py           #   3b/7b/coder dynamic model router
│   ├── tool_schemas.py     #   31 tool JSON schemas for Ollama function calling
│   ├── briefing.py         #   Morning briefing
│   └── tools/              #   8 tool modules (Linux + macOS)
├── services/               # 29 daemons (FastAPI + SQLite)
├── workflows/              # 28 built-in workflows
├── desktop/command-center/ # Tauri shell + approval overlay
├── dashboard/frontend/     # React SPA
├── clawctl/                # CLI
├── packaging/              # AppImage, .deb, AUR, ISO
└── tests/                  # 60 unit + integration
```

---

## 📚 Documentation

| Doc | What's inside |
|:----|:--------------|
| [Demos walk-through](docs/DEMOS.md) | Exact phrasing and expected output for each demo |
| [Architecture overview](docs/ARCHITECTURE_CURRENT.md) | How the pieces fit together |
| [API reference](docs/API_REFERENCE.md) | Service endpoints and contracts |
| [Security audit](docs/SECURITY_AUDIT.md) | Threat model and mitigations |
| [Product vision](docs/PRODUCT_VISION.md) | Where we're headed |
| [Roadmap](docs/ROADMAP.md) | Milestones and current status |

---

## ⭐ Star this repo

If you want local AI that actually *does things* — not just chat — star ClawOS and follow the progress. macOS support and demo videos coming soon.

**⭐ Star = "I want this on my machine"**

---

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
git checkout -b feature/my-feature
git commit -m "feat: add awesome feature"
git push origin feature/my-feature
# Open a PR
```

---

## 📜 License

[AGPL-3.0](LICENSE) — free to use, modify, and distribute. Forks must remain open source.

---

## 🙏 Acknowledgments

- **[Ollama](https://ollama.com)** — local LLM serving
- **[Qwen team](https://github.com/QwenLM)** — qwen2.5 models
- **[Piper](https://github.com/rhasspy/piper)** — local TTS
- **[OpenClaw](https://github.com/openclaw)** — optional power-user agent brain

---

<div align="center">

**The future of AI is local, private, and yours to control.**

[Get started](#-quick-start) · [Read the docs](docs/) · [Join the discussion](https://github.com/xbrxr03/clawos/discussions)

</div>