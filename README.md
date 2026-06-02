<div align="center">

# 🦀 ClawOS

**Your laptop. Your AI. Your rules.**

The JARVIS-style AI agent that runs 100% on your hardware —  
voice activation, multi-step tool use, 7-layer memory, approval gates, zero cloud.

[![CI](https://github.com/xbrxr03/clawos/actions/workflows/ci.yml/badge.svg)](https://github.com/xbrxr03/clawos/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: AGPL-3.0+](https://img.shields.io/badge/license-AGPL%203.0+-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Telemetry: zero](https://img.shields.io/badge/telemetry-zero-brightgreen)](#-zero-telemetry)
[![Tests: 553 passing](https://img.shields.io/badge/tests-553%20passing-brightgreen)](https://github.com/xbrxr03/clawos/actions)
[![Stars](https://img.shields.io/github/stars/xbrxr03/clawos?style=social)](https://github.com/xbrxr03/clawos/stargazers)

**[Install in 2 minutes](#-quick-start)** · **[See it in action](#-see-it-in-action)** · **[Read the docs](docs/)** · **[Join the discussion](https://github.com/xbrxr03/clawos/discussions)**

</div>

---

## Why ClawOS?

> **Ollama gave you a local model. ClawOS gives you a local agent.**

ChatGPT runs in the cloud. Jan is a chat wrapper. OpenWebUI is a UI layer.  
ClawOS is a **full agent OS** — it talks, it does, it remembers, and it asks before it acts.

| | ClawOS | Odysseus | Open WebUI | Jan |
|:---|:---:|:---:|:---:|:---:|
| **Voice activation** | ✅ "Hey Claw" | ❌ | ❌ | ❌ |
| **Approval gates** | ✅ Native popup | ❌ Shell access | ❌ | ❌ |
| **Agent workflows** | ✅ 29 built-in | ✅ Skills | ❌ | ❌ |
| **Multi-agent (A2A)** | ✅ Agent mesh | ❌ Single agent | ❌ | ❌ |
| **7-layer memory** | ✅ Knowledge graph | ⚠️ Flat vectors | ⚠️ Flat vectors | ⚠️ Flat |
| **Bootable ISO** | ✅ Flash & go | ❌ | ❌ | ❌ |
| **Model manager** | ✅ Cookbook | ✅ Cookbook | ✅ | ✅ |
| **Deep research** | ✅ Citation tracking | ✅ | ❌ | ❌ |
| **Model compare** | ✅ Side-by-side | ✅ Compare | ❌ | ❌ |
| **Notes** | ✅ Markdown + tags | ✅ | ❌ | ❌ |
| **Calendar** | ✅ iCal export | ✅ | ❌ | ❌ |
| **Email** | ✅ IMAP + SMTP | ✅ | ❌ | ❌ |
| **PWA / Mobile** | ✅ Installable | ✅ | ❌ | ⚠️ |
| **Self-hosted** | ✅ Zero cloud | ✅ | ✅ | ✅ |
| **Zero telemetry** | ✅ [Verify it](#-zero-telemetry) | ✅ | ✅ | ✅ |

---

## ✨ See it in action

### 🗣️ Voice Activation — "Hey Claw, good morning"
Say the wake word and hear a synthesized briefing: time, weather, calendar, reminders, what you worked on yesterday. Five tool calls fire in parallel. Fully offline.

```
You: "Hey Claw, good morning"
Claw: 🔊 "Good morning. It's Tuesday, June 3rd, 72°F and clear.
       You have 3 meetings today, starting with standup at 10.
       Yesterday you pushed 4 commits to ClawOS and closed issue #66.
       Reminder: dentist appointment Thursday."
```

### ⚡ Multi-Step Workflows
"Organize my downloads" — 6-tool chain, zero intervention:
1. Scan downloads folder
2. Classify files by type
3. Create category folders
4. Move files
5. Generate summary
6. Report what was done

```bash
clawctl run organize-downloads
```

### 🛡️ Approval Gates — It asks before it acts
When the agent wants to run a shell command, delete a file, or close an app — a native floating popup appears. You approve or deny. Every time.

> **This is the #1 differentiator.** Other local AI tools give shell access with no guard. ClawOS respects your authority.

### 🧠 7-Layer Memory — It actually remembers you
Not a goldfish chatbot. ClawOS persists across sessions with structured intelligence:

| Layer | What | Example |
|:------|:-----|:--------|
| Pinned facts | Things it should always know | "I prefer dark mode" |
| Semantic recall | Vector search over conversations | ChromaDB + fastembed |
| Full-text search | Keyword search across all history | FTS5 |
| Knowledge graph | Entities and relations | "Abrar → works_on → ClawOS" |
| Archive | Old conversations, compressed | Time-decay compression |
| ACE learnings | Self-improving corrections | "When I said X, user corrected to Y" |
| Workflow state | Active task progress | Multi-step task context |

---

## 🚀 Quick start

```bash
curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh | bash
```

The installer takes ~2 minutes. Walks you through a 9-step browser wizard — hardware detection, model pull, voice setup, permissions. When done, your dashboard opens at `http://localhost:7070`.

```bash
clawctl health    # verify everything's running
clawctl start     # start all services
clawctl logs      # tail service output
```

### One-command manual install

```bash
git clone https://github.com/xbrxr03/clawos.git
cd clawos
pip install -e ".[dev]"
clawctl bootstrap  # interactive setup wizard
```

### Bootable ISO

Got an old laptop? Flash ClawOS onto it and dedicate it to being your JARVIS:

```bash
sudo dd if=clawos-amd64.iso of=/dev/sdX bs=4M status=progress
```

---

## ⚡ Features

<details>
<summary><b>🗣️ Voice — Talk to your computer</b></summary>

- **Wake word**: "Hey Claw" activates listening — no button needed
- **Push-to-talk**: Hold a key, speak, release
- **Whisper STT**: Local speech-to-text, zero cloud
- **Piper TTS**: Local text-to-speech, natural-sounding
- **Morning briefing**: Wake up to a voiced summary of your day

```bash
clawctl demos morning-briefing    # try it now
```
</details>

<details>
<summary><b>🤖 Agent — It does things, not just chats</b></summary>

- **Native function calling**: qwen2.5 with Ollama-native tool use
- **Dynamic model routing**: 3b for quick tasks → 7b for reasoning → coder for code
- **31 built-in tools**: Shell, files, web search, calendar, reminders, clipboard, screenshot...
- **29 built-in workflows**: Organize downloads, summarize PDFs, bulk rename, daily digests...
- **Agent mesh (A2A)**: Multiple agents coordinate on complex tasks

```bash
clawctl run organize-downloads    # built-in workflow
clawctl submit "Research Rust vs Go"   # agent task
```
</details>

<details>
<summary><b>🛡️ Security — It asks before it acts</b></summary>

- **Policy engine**: Every tool call goes through policyd
- **Approval popup**: Sensitive actions trigger a native Tauri window — approve or deny
- **Workspace sandbox**: File ops can't escape `~/clawos/workspace/`
- **Shell allowlist**: Only approved binaries; blocks `python3 -c <code>` injection
- **Merkle audit trail**: Tamper-proof execution log
- **No SSRF**: Web search blocks private/loopback IPs

Every action is logged. Every sensitive action requires your approval. You are always in control.
</details>

<details>
<summary><b>🧠 Memory — 7 layers of remembering</b></summary>

- **Pinned facts** — permanent knowledge ("I prefer dark mode")
- **Semantic recall** — ChromaDB + fastembed vector search
- **Full-text search** — FTS5 keyword search across all history
- **Knowledge graph** — entities and relations via braind
- **Archive** — compressed old conversations
- **ACE learnings** — self-improving corrections from feedback
- **Workflow state** — multi-step task context persistence

```bash
clawctl memory search "what did I work on last week"
clawctl memory pin "I prefer dark mode"
```
</details>

<details>
<summary><b>🎨 Dashboard — Full control panel</b></summary>

- **React SPA** at `http://localhost:7070`
- **Workflows**: Browse, configure, and run 29 built-in workflows
- **Packs**: Install curated skill packs
- **Traces**: Watch agent reasoning in real-time
- **Brain**: Inspect knowledge graph, search memory
- **Settings**: Models, voice, permissions, auth — all in one place
- **Mobile-responsive**: Works on phone and tablet (PWA coming)
</details>

<details>
<summary><b>📖 Cookbook — Hardware-aware model recommendations</b></summary>

- **Auto-detect**: Scans CPU, RAM, GPU vendor/VRAM/compute capability
- **Smart scoring**: 25 models ranked for your exact hardware
- **One-command serve**: `clawctl cookbook serve` — picks the best model, pulls, and starts it
- **Tier system**: A (8GB), B (16GB), C (32GB+) — never recommend what won't fit

```bash
clawctl cookbook scan          # detect your hardware
clawctl cookbook recommend    # top 10 models for your rig
clawctl cookbook serve         # auto-pick + start the best model
```
</details>

<details>
<summary><b>🔬 Deep Research — Multi-source research with citations</b></summary>

- **Search providers**: Brave API, Tavily API, or direct URL fetch
- **Citation tracking**: Sources ranked primary/supporting/tangential
- **Session persistence**: Research sessions saved to disk, resumable
- **Agent integration**: Build research intent for agentd synthesis

```bash
clawctl research start "quantum computing applications 2026"
clawctl research list
clawctl research get <session-id>
```
</details>

<details>
<summary><b>⚖️ Compare — Side-by-side model evaluation</b></summary>

- **Parallel execution**: Ask multiple models the same question simultaneously
- **Per-model metrics**: Tokens/sec, total tokens, response time
- **Auto-detect running models**: No config needed if Ollama is running

```bash
clawctl compare "Explain attention mechanisms" --models llama3:8b,qwen2.5:7b
```
</details>

<details>
<summary><b>📝 Notes + Calendar + Email — Productivity suite</b></summary>

- **Notes**: Markdown with YAML front matter, tags, full-text search
- **Calendar**: Event management, date range filtering, **iCal export** for external calendars
- **Email**: IMAP inbox reader + SMTP sender, works with your existing account
- **PWA**: Install ClawOS on your phone — offline support, push to home screen

```bash
clawctl research start "..."   # deep research
# Notes, Calendar, and Email available via dashboard at localhost:7070
```
</details>

<details>
<summary><b>🔌 Bring your own brain</b></summary>

- **Nexus** (built-in) — default agent runtime, optimized for local
- **OpenClaw** — drop-in power-user agent framework
- **Any MCP-compatible** — plugin hooks for custom brains
- **Ollama** — local model serving (qwen2.5, llama3, mistral, phi3...)
- **OpenAI-compatible APIs** — cloud fallback if you want it (optional)
</details>

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

## 🏗️ Architecture

> 📊 [Interactive Mermaid diagram](docs/ARCHITECTURE_DIAGRAM.md) — renders natively on GitHub.

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

**Core daemons** (10 critical at runtime, 29 total):

| Daemon | Port | What it does |
|:-------|:-----|:-------------|
| `dashd` | 7070 | Dashboard API + SPA |
| `clawd` | 7071 | Core orchestrator |
| `agentd` | 7072 | Agent runtime + task queue |
| `memd` | 7073 | 7-layer memory |
| `policyd` | 7074 | Approval engine + audit log |
| `modeld` | 7075 | Model lifecycle management |
| `voiced` | 7079 | Whisper + Piper voice pipeline |
| `desktopd` | 7080 | Input automation (clipboard, paste, screenshot) |
| `braind` | 7082 | Knowledge graph engine |
| `a2ad` | 7083 | Agent-to-agent mesh protocol |

<details>
<summary><b>Full service list (29 daemons)</b></summary>

| Daemon | Port | What it does |
|:-------|:-----|:-------------|
| dashd | 7070 | Dashboard API + SPA |
| clawd | 7071 | Core orchestrator |
| agentd | 7072 | Agent runtime + task queue |
| memd | 7073 | 7-layer memory |
| policyd | 7074 | Approval engine + audit log |
| modeld | 7075 | Model lifecycle management |
| metricd | 7076 | Metrics collection |
| mcpd | 7077 | MCP tool server |
| observd | 7078 | Observability |
| voiced | 7079 | Whisper + Piper voice pipeline |
| desktopd | 7080 | Input automation |
| agentd_v2 | 7081 | Next-gen agent runtime |
| braind | 7082 | Knowledge graph |
| a2ad | 7083 | Agent-to-agent mesh |
| sandboxd | 7085 | Sandbox execution |
| visuald | 7086 | Visual processing |
| reminderd | 7087 | Desktop notifications |
| waketrd | 7088 | Wake word → briefing bridge |
</details>

---

## 🔒 Zero telemetry — verify it yourself

No analytics. No error reporting. No usage stats. No phone-home. Run this:

```bash
grep -rn "posthog\|sentry\|google-analytics\|mixpanel\|amplitude" \
  --include="*.py" --include="*.ts" --include="*.tsx" .
# returns nothing
```

The only network calls ClawOS makes: Ollama (localhost), DuckDuckGo (web search), wttr.in (weather), your RSS feeds. All optional. All disableable.

---

## 🛠️ Development

```bash
git clone https://github.com/xbrxr03/clawos.git
cd clawos
pip install -e ".[dev]"

# Run tests (no live LLM needed)
pytest tests/ -q

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
└── tests/                  # 479 unit + integration tests
```

---

## 📚 Documentation

| Doc | What's inside |
|:----|:--------------|
| [Demos walk-through](docs/DEMOS.md) | Exact phrasing and expected output for each demo |
| [Architecture overview](docs/ARCHITECTURE_CURRENT.md) | How the pieces fit together |
| [Architecture diagram](docs/ARCHITECTURE_DIAGRAM.md) | Mermaid diagram of system and request flow |
| [CLI reference](docs/CLI_REFERENCE.md) | All `clawctl` commands, flags, and examples |
| [API reference](docs/API_REFERENCE.md) | Service endpoints and contracts |
| [Security audit](docs/SECURITY_AUDIT.md) | Threat model and mitigations |
| [Product vision](docs/PRODUCT_VISION.md) | Where we're headed |
| [Roadmap](docs/ROADMAP.md) | Milestones and current status |

---

## ⭐ Star this repo

If you want local AI that actually **does things** — not just chat — star ClawOS and follow the progress.

Every star tells us: *build this faster.*

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

This project is licensed under the [GNU Affero General Public License v3 or later (AGPL-3.0-or-later)](LICENSE). Forks must remain open source.

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