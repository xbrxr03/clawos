# ClawOS

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Status](https://img.shields.io/badge/status-v0.1.1-green.svg)](https://github.com/xbrxr03/clawos/releases)
[![Telemetry: zero](https://img.shields.io/badge/telemetry-zero-brightgreen.svg)](#zero-telemetry)

> **Local AI agent for your laptop. One curl command. No cloud. No API keys. No telemetry.**

ClawOS turns your existing Linux machine into a JARVIS-style personal AI
assistant. Voice activation, multi-step tool use, system control, memory —
all running locally on your hardware via [Ollama](https://ollama.com).

```bash
curl -fsSL https://install.clawos.io | bash
```

---

## ⚡ What it does

- 🤖 **Native agent loop** — qwen2.5:7b with native Ollama function calling, parallel tool execution, dynamic model routing
- 🗣️ **Voice activation** — "Hey Claw" wakes the agent. Whisper for STT, Piper for TTS
- 🔒 **Zero telemetry** — nothing leaves your machine, ever. Verify it yourself in the source
- 🧠 **7-layer memory** — pinned facts, semantic recall, knowledge graph, ACE self-improving learnings
- 🛡️ **Human-in-the-loop** — sensitive actions (file delete, shell commands) trigger a floating approval popup
- 🎨 **Beautiful dashboard** — full SPA at `http://localhost:7070`
- 🔌 **Bring your own brain** — Nexus (built-in), OpenClaw, or any framework with plugin hooks

---

## 🎬 Demos

> Demo videos: **not yet recorded.** Placeholder slots reserved at
> `docs/media/demos/` for v0.1.2. The demos run live today — see
> [docs/DEMOS.md](docs/DEMOS.md) for exact phrasing and expected output.

**Try them yourself after install:**

```bash
clawctl demos morning-briefing       # parallel tool gather + Piper voice
clawctl demos essay-editor           # multi-step: write → clipboard → editor
clawctl demos approval-test          # floating popup for sensitive ops
```

---

## 🚀 Quick start

### Recommended: install on your existing Linux

```bash
curl -fsSL https://install.clawos.io | bash
clawctl health
```

The installer takes ~2 minutes on a warm system. Walks you through a 9-step
browser wizard (hardware detection, profile, model pull, voice setup,
permissions). When done your dashboard opens at `http://localhost:7070`.

### Alternative: bootable ISO (dedicated machine)

For a clean machine or AI appliance, flash the ISO and boot from USB:

```bash
sudo dd if=clawos-amd64.iso of=/dev/sdX bs=4M status=progress
```

The ISO ships with the same setup wizard pre-installed. Useful for old
laptops you want to dedicate to JARVIS.

---

## 💻 Hardware tiers

| Tier | RAM | Recommended model | Experience |
|------|-----|-------------------|------------|
| **A** | 8 GB | qwen2.5:3b | Basic — works on old laptops, mini PCs |
| **B** | 16 GB | qwen2.5:7b | Full — multi-step tool use, fast briefings |
| **C** | 32 GB+ | qwen2.5:7b + qwen2.5-coder:7b | Power — coder model for file/shell tasks |

**Minimum:** x86_64 CPU, 8 GB RAM, 20 GB storage, Linux (Ubuntu 22.04+, Fedora 39+, Arch). NVIDIA GPU optional but accelerates inference.

macOS support: arriving in v0.2 (most platform code is already in place).

---

## ✨ Flagship demos

### 🌅 Morning briefing
Say *"Hey Claw, good morning"* and get a spoken briefing of your day:
time, weather, calendar, reminders, and what you were working on yesterday.
Five tool calls fire in parallel; qwen2.5:7b synthesizes; Piper voices it.
Fully offline-capable — weather/news degrade gracefully if you're disconnected.

### 📝 Multi-step composition
Tell the agent *"Write me a 1000-word essay about AI ethics and paste it
into the text editor"* and watch the four-tool chain execute: `write_text`
generates the content, `set_clipboard` copies it, `open_app` launches
gedit, `paste_to_app` drops it in. The agent confirms with *"Done. Your
essay's in the editor — 1,024 words."*

### 🛡️ Floating approval popup
When the agent wants to do something sensitive (`run_command`, `write_file`,
`close_app`), a borderless always-on-top window appears over your desktop
with the proposed action and Approve/Deny buttons. Y/N keyboard shortcuts.
Built on Tauri, native to each OS — not a browser tab.

### ⚡ Quirky combos
*"Set volume to 30 and play Spotify"*, *"What's eating my CPU?"*,
*"Screenshot my screen and save it to today's folder"*. Two- or three-tool
chains run in 2-3 seconds. The intent classifier catches 60-70% of
real inputs before the LLM ever fires.

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

**Core daemons** (29 microservices total, ~10 critical at runtime):
- `dashd:7070` — dashboard API
- `agentd` — agent runtime
- `voiced` — Whisper + Piper voice pipeline
- `memd` — 7-layer memory (PINNED, ChromaDB, FTS5, KG, archive, LEARNED, WORKFLOW)
- `policyd` — approval engine + audit log
- `reminderd:7087` — desktop notifications
- `waketrd:7088` — wake word → briefing bridge
- `desktopd:7080` — input automation (clipboard, paste, type, screenshot)
- `skilld` — BM25 skill retrieval
- `workfd` — 28+ built-in workflows

---

## <a id="zero-telemetry"></a>🔒 Zero telemetry — verify it yourself

We don't collect anything. There's no analytics SDK, no error reporting,
no usage stats, no phone-home. Run this to verify:

```bash
grep -rn "posthog\|sentry\|google-analytics\|mixpanel\|amplitude" \
  --include="*.py" --include="*.ts" --include="*.tsx" .
# returns nothing
```

The only network calls ClawOS makes are: Ollama (localhost), DuckDuckGo
(only when you call `web_search`), wttr.in (only when you call
`get_weather`), RSS feeds you've configured. All optional. All disableable.

---

## 🛠️ Development

```bash
git clone https://github.com/xbrxr03/clawos.git
cd clawos
pip install -e ".[dev]"

# Run agent unit tests (60 tests, no live LLM)
pytest tests/unit/test_agent_*.py -q

# Boot dev services
bash scripts/dev_boot.sh --full

# Service health
clawctl health

# Tail any daemon's logs
clawctl logs dashd
```

---

## 📁 Project structure

```
clawos/
├── runtimes/agent/         # Nexus agent loop
│   ├── runtime.py          # 4-tier priority pipeline
│   ├── intents.py          # deterministic regex classifier
│   ├── router.py           # 3b/7b/coder model router
│   ├── tool_schemas.py     # 31 tool JSON Schemas
│   ├── briefing.py         # morning briefing
│   └── tools/              # 8 tool modules (Linux+macOS)
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

- [Demos walk-through](docs/DEMOS.md)
- [Architecture overview](docs/ARCHITECTURE_CURRENT.md)
- [API reference](docs/API_REFERENCE.md)
- [Security audit](docs/SECURITY_AUDIT.md)
- [Product vision](docs/PRODUCT_VISION.md)

---

## 🔐 Security

- **Policy engine** — every tool call gated; sensitive ops queue for human approval
- **Workspace sandbox** — file ops can't escape `~/clawos/workspace/`
- **Shell allowlist** — `run_command` restricted to safe binaries; tightened to block `python3 -c <code>` injection
- **Merkle audit trail** — tamper-proof execution log in policyd
- **No SSRF** — `web_search` blocks private/loopback IPs

See [SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md).

---

## 🤝 Contributing

Contributions welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
git checkout -b feature/my-feature
git commit -m "feat: add awesome feature"
git push origin feature/my-feature
# Open PR
```

---

## 📜 License

[AGPL-3.0](LICENSE) — free to use, modify, and distribute. Forks must
remain open source.

---

## 🙏 Acknowledgments

- **[Ollama](https://ollama.com)** — local LLM serving
- **[Qwen team](https://github.com/QwenLM)** — qwen2.5 models
- **[Piper](https://github.com/rhasspy/piper)** — local TTS
- **[OpenClaw](https://github.com/openclaw)** — optional power-user agent brain

---

## 📞 Community

- 🐛 [Issues](https://github.com/xbrxr03/clawos/issues)
- 💬 Discussions on the GitHub repo

> **The future of AI is local, private, and yours to control.**
