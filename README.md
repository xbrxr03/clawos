# ClawOS

> Take any spare PC and turn it into a private JARVIS. Voice, 29+ automations, a living knowledge brain — all running locally on your hardware, answering to no one.
>
> [![License: AGPL v3+](https://img.shields.io/badge/License-AGPL%20v3%2B-1f6feb.svg)](LICENSE)

```bash
curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh | bash
```

One command. Your spare PC becomes a private JARVIS — voice assistant, automation engine, and personal AI. No subscriptions. No cloud. No API keys required.

---

## Why this exists

OpenClaw hit 280,000 GitHub stars in six weeks. Most people who tried it gave up.

The setup takes hours. It requires API keys. It costs $300–750/month in tokens. CVE-2026-25253 lets anyone steal your keys in one click.

ClawOS fixes all of that. It runs OpenClaw on your hardware, with your models, for the cost of electricity.

---

## Who it's for

The installer asks you one question:

```
Who is ClawOS for?

  1) Developer    — OpenClaude (open-source Claude Code) + qwen2.5-coder
  2) Creator      — Content workflows + daily briefing
  3) Business     — Lead research, reports, scheduling
  4) Student      — Summarise lectures, research wiki, proofread
  5) Teacher      — Lesson planning, curriculum wiki, scheduling
  6) General      — Balanced setup, good for everything
  7) Freelancer   — Proposals, client research, outreach, invoicing
```

Pick your profile. ClawOS pre-configures the right workflows and models for you.

Developers get **OpenClaude** pre-wired to Ollama — Claude Code's interface, your hardware, zero API bill.

---

## What you get

- **JARVIS voice** — wake word ("Hey Claw"), Whisper STT, Piper TTS offline. Plug in your ElevenLabs key once for cinematic voice.
- **OpenClaude** — open-source Claude Code, pre-configured for offline Ollama. Dev profile only. No subscription.
- **Nexus Brain** — 3D knowledge graph. Drop a ZIP of notes, watch your personal knowledge base build itself.
- **29 one-command workflows** — organize downloads, summarize PDFs, review PRs, disk reports, daily digest, and more.
- **Proactive ambient intelligence** — ClawOS watches in the background. "82% disk full." "Brain found a new connection." Surfaces what matters before you ask.
- **policyd** — every tool call gated, audited, and logged before it runs. Human approval queue for sensitive ops.
- **Dashboard** — 17-page React UI at `:7070`. Tasks, approvals, models, memory, audit log, workflows, brain graph.
- **Smart model routing** — DeepSeek for cheap tasks, Claude for hard ones, Ollama (free) for local coding.
- **MCP Manager** — connect any Model Context Protocol server, visual UI.
- **A2A Federation** — link multiple ClawOS instances on your network.

---

## Why not just run Ollama?

Ollama runs models. ClawOS is what you build *with* Ollama.

| Just Ollama | ClawOS |
|---|---|
| Chat in terminal | Wake word + voice replies |
| One conversation at a time | 29+ background automations |
| No memory | 4-layer persistent memory |
| No dashboard | Full ops console at `:7070` |
| No schedules | Morning briefing at 7am |
| No safety layer | policyd — every call risk-scored, sensitive ops need approval |
| Model only | Model + brain + workflows + voice |

**Ollama is the engine. ClawOS is the car.**

---

## Requirements

- Ubuntu 24.04, Debian 12, Raspberry Pi OS, or macOS 14+ (Apple Silicon first, Intel best-effort)
- 8GB RAM minimum
- 10GB free disk space
- Internet on first run only (pulls models, then fully offline)

The installer automatically detects your hardware and picks the right model:

| Hardware | RAM | Model | Speed |
|---|---|---|---|
| Raspberry Pi 5 / ARM | 8GB | `qwen3.5:4b` | ~3–5 tok/s CPU |
| x86 laptop / mini PC | 8–16GB | `qwen3.5:4b` | ~8–20 tok/s CPU |
| x86 workstation with GPU | 16–32GB | `qwen3.5:4b` | ~40–80 tok/s GPU |
| Gaming rig / workstation | 32GB+ + GPU | `qwen3.5:9b` | ~80+ tok/s GPU |

GPU optional. NVIDIA CUDA and AMD ROCm both supported via Ollama.

## Agent Runtimes

ClawOS ships with a full agent runtime ecosystem — not just one model interface.

| Runtime | Tiers | What it is |
|---|---|---|
| **Nexus** | All | Native Python ReAct agent. Always-on, CPU-capable, 4-layer persistent memory, skill loader, A2A federation. |
| **PicoClaw** | Tier A (ARM) | Lightweight runtime from [Sipeed](https://github.com/sipeed/picoclaw). Auto-activated on Raspberry Pi and ARM hardware — no configuration required. |
| **OpenClaw** | All | 13,700+ community skills. The main agent ecosystem. Activate with `clawctl openclaw install`. |
| **Hermes Agent** | Coming soon | Self-improving agent from [Nous Research](https://github.com/nousresearch/hermes-agent). Persistent cross-session memory, MCP integration, autonomous skill building. |

---

## How it works

```
You (Terminal / Voice / Dashboard)
         |
      agentd   ← task queue + session manager
         |
      Ollama   ← local inference, no cloud, no API keys
         |
     policyd   ← every tool call checked before it runs
         |
   toolbridge  ← files, web, shell, memory
         |
       memd    ← 4-layer memory: PINNED + WORKFLOW + ChromaDB + FTS5
```

Every action goes through `policyd`. Sensitive operations pause for your approval. Nothing talks to the internet unless you explicitly allow it. A tamper-evident Merkle-chained audit log records every action taken on your machine.

---

## Security

ClawOS meets 6 of 7 enterprise security requirements. No other open-source agent project meets more than 3.

| Requirement | Status |
|---|---|
| Agent-level RBAC with scoped permissions | Yes |
| Runtime permission check before every tool call | Yes |
| Immutable Merkle-chained audit trail | Yes |
| Human-in-loop approval for sensitive actions | Yes |
| Kill switch — terminate agent actions in real time | Yes |
| Credential isolation — no API keys in agent context | Yes |

---

## vs. everything else

| | OpenClaw | Leon | khoj | Open WebUI | ClawOS |
|---|---|---|---|---|---|
| One-command install | No | No | No | Partial | **Yes** |
| Fully offline, no API keys | No | No | No | Yes | **Yes** |
| Profile-based setup | No | No | No | No | **Yes** |
| Dashboard UI (17 pages) | No | No | No | Yes | **Yes** |
| 29 built-in workflows | No | Partial | No | No | **Yes** |
| Proactive ambient alerts | No | No | No | No | **Yes** |
| 3D knowledge brain | No | No | No | No | **Yes** |
| Human approval queue | No | No | No | No | **Yes** |
| No safety layer | — | — | — | — | policyd ✓ |
| Signed skill marketplace | Unsafe | No | No | No | **Yes** |
| Voice pipeline (offline) | No | Partial | No | No | **Yes** |
| Zero monthly cost | No | Yes | Partial | Yes | **Yes** |

---

## Build from source

```bash
git clone https://github.com/xbrxr03/clawos
cd clawos
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[full]"
python3 -m bootstrap.bootstrap
clawos
```

Pre-flight check — see what the installer will do before committing:

```bash
bash install.sh --check
```

---

## Remote Ollama

If you have a powerful machine running Ollama on your LAN, point ClawOS at it:

```bash
export OLLAMA_HOST=http://192.168.1.50:11434
curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh | bash
```

Useful for low-power devices like Raspberry Pi 5.

---

## Roadmap

- [x] Core runtime — policyd, memd, toolbridge, agentd, modeld, voiced, metricd
- [x] Voice pipeline — Whisper STT + Piper TTS + wake word
- [x] One-command installer — Ubuntu, Debian, macOS, `--check` pre-flight
- [x] 7 install profiles — Developer, Creator, Business, Student, Teacher, General, Freelancer
- [x] OpenClaude offline — pre-wired to qwen2.5-coder:7b via Ollama, no API keys
- [x] ElevenLabs JARVIS voice — paste your key once in dashboard Settings
- [x] Dashboard — 17-page React UI, WebSocket real-time updates
- [x] 29 offline workflows — files, documents, developer, content, system, data
- [x] Nexus Brain — 3D knowledge graph, ZIP ingestion, GraphRAG retrieval
- [x] Proactive ambient intelligence — suggestions feed, morning briefing
- [x] MCP Manager — visual UI to connect any MCP server
- [x] A2A Federation — Agent-to-Agent protocol, multi-instance networking
- [x] policyd — runtime permission checks, Merkle audit log, kill switch
- [x] Skill Marketplace — Ed25519 signing, sandbox, trust tiers
- [x] PWA — installable on desktop and mobile
- [ ] **Bootable ISO** — flash and boot, no install needed (v0.1.1)

---

## License

AGPL-3.0-or-later. See [LICENSE](LICENSE).

ClawOS is not affiliated with OpenClaw or Anthropic. OpenClaw and Ollama remain MIT-licensed upstream projects.

---

*Built for people who wanted OpenClaw to actually work. [github.com/xbrxr03/clawos](https://github.com/xbrxr03/clawos)*
