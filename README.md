# ClawOS

> Take any spare PC and turn it into a private JARVIS. Voice, 29+ automations, a living knowledge brain — all running locally on your hardware, answering to no one.
>
> [![License: AGPL v3+](https://img.shields.io/badge/License-AGPL%20v3%2B-1f6feb.svg)](LICENSE)

```bash
curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh | bash
```

One command. Your spare PC becomes a private AI assistant — voice, automation engine, and personal knowledge base. No subscriptions. No cloud. No API keys required.

---

## What ClawOS is — and isn't

ClawOS is a **curated installation and orchestration layer**. We built the glue, the install experience, and several original services. We did not build everything.

| Component | Built by | Notes |
|-----------|---------|-------|
| **Nexus** agent loop | ✅ ClawOS | Our native ReAct runtime |
| **Jarvis** voice layer | ✅ ClawOS | Wake word, STT/TTS wiring, personality |
| Dashboard + workflow engine | ✅ ClawOS | 17-page React UI, 29 workflows |
| Memory system (memd) | ✅ ClawOS | 14-layer persistent memory (taosmd) |
| Policy engine (policyd) | ✅ ClawOS | Merkle audit, approval queue |
| OMI integration (omid) | ✅ ClawOS | Ambient AI capture + command detection |
| Framework Store (frameworkd) | ✅ ClawOS | 9 agent frameworks, one-click install |
| Scheduler, toolbridge, A2A | ✅ ClawOS | Original services |
| **Ollama** (model server) | [Ollama project](https://ollama.com) | Not ours — MIT licensed |
| **OpenClaw** (optional runtime) | [OpenClaw](https://openclaw.ai) | Not ours — we pre-configure it for offline use |
| **OMI** (ambient AI) | [BasedHardware](https://github.com/BasedHardware/omi) | Not ours — optional macOS app or wearable |
| Whisper STT | [OpenAI](https://github.com/openai/whisper) | Speech-to-text (MIT) |
| Piper TTS | [Rhasspy project](https://github.com/rhasspy/piper) | Text-to-speech (MIT) |
| ChromaDB | [Chroma](https://www.trychroma.com) | Vector memory (Apache 2.0) |
| CrossEncoder reranking | [sentence-transformers](https://github.com/UKPLab/sentence-transformers) | MS MARCO MiniLM-L-6-v2 (Apache 2.0) |

OpenClaw is an optional component you can install *through* ClawOS. If you already run OpenClaw yourself, ClawOS is a curated setup layer on top of that — not a competing product.

> **Full absorption log**: See [ABSORPTION.md](ABSORPTION.md) for every external project,
> repo, algorithm, and research pattern that ClawOS integrates — with links, licenses, and
> what each one does.

---

## Honest performance expectations

> **Before you install**: Local models on consumer hardware are meaningfully slower and less capable than cloud APIs. A `qwen2.5:3b` on 16GB RAM will not match GPT-4 on complex multi-step agentic tasks. You will get worse results on hard reasoning problems and longer chains.
>
> ClawOS trades performance for privacy and zero ongoing cost. For many use cases that tradeoff is correct. For others it isn't. Know which one you are.

**What works well locally:** chat, summaries, file organisation, voice reminders, daily briefings, simple automations, document Q&A.

**What struggles locally:** complex multi-tool chains, code generation for large projects, nuanced reasoning, tasks that need a 70B+ model to succeed reliably.

---

## Per-device capability guide

| Device | RAM | Recommended model | What works | What won't |
|--------|-----|-------------------|-----------|-----------|
| Raspberry Pi 5 / ARM 8GB | 8GB | `qwen2.5:1.5b` | Q&A, voice, reminders | Agentic chains, code gen |
| ROG Ally / laptop 16GB | 16GB | `qwen2.5:3b` | Chat, voice, simple tasks | Complex multi-step pipelines |
| Mini PC / MacBook 16GB | 16GB | `qwen2.5:7b` | Most tasks, good quality | Very long context tasks |
| Workstation 32GB+ | 32GB+ | `qwen2.5:14b+` | Full agentic use | Nothing (this is the target) |
| GPU rig (RTX 3080+) | Any+10GB VRAM | `qwen2.5:7b` GPU | Fast, solid quality | Large context (32k+) |

---

## Why this exists

Most people who try to run a local AI assistant give up. The setup takes hours. The defaults are wrong. The models are poorly matched to the hardware. Nothing talks to each other.

ClawOS is a single installer that detects your hardware, picks the right model, wires up voice, memory, workflows, and a dashboard, and hands you a working system.

---

## Who it's for

The one-line installer provisions the machine, opens the browser, and the setup wizard asks you one question there:

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

Pick your persona in the setup wizard. ClawOS pre-configures the right workflows and the final model provisioning for you.

The **Developer** persona gets **OpenClaude** pre-wired to Ollama — Claude Code's interface, your hardware, zero API bill.

---

## What you get

- **JARVIS voice** — wake word ("Hey Claw"), Whisper STT, Piper TTS offline. Plug in your ElevenLabs key once for cinematic voice.
- **OpenClaude** — open-source Claude Code, pre-configured for offline Ollama. Dev profile only. No subscription.
- **Framework Store** — install any AI agent framework from a store UI: SmolAgents, AgentZero, PocketFlow, NullClaw, Langroid, and more.
- **Nexus Brain** — 3D knowledge graph. Drop a ZIP of notes, watch your personal knowledge base build itself.
- **29 one-command workflows** — organize downloads, summarize PDFs, review PRs, disk reports, daily digest, and more. Run any from the terminal: `clawctl wf list` · `clawctl wf run organize-downloads --dry-run`
- **Proactive ambient intelligence** — ClawOS watches in the background. "82% disk full." "Brain found a new connection." Surfaces what matters before you ask.
- **Session continuity** — wake up your device and JARVIS briefs you on where you left off. No re-explaining context.
- **policyd** — every tool call gated, audited, and logged before it runs. Human approval queue for sensitive ops.
- **Dashboard** — 17-page React UI at `:7070`. Tasks, approvals, models, memory, audit log, workflows, brain graph.
- **Smart model routing** — lightweight models for simple tasks, full models for complex ones.
- **MCP Manager** — connect any Model Context Protocol server, visual UI.
- **A2A Federation** — link multiple ClawOS instances on your network.

---

## Agent Runtimes & Framework Store

ClawOS ships with a full agent runtime ecosystem and a store to install more.

**Built-in runtimes:**

| Runtime | Tiers | What it is |
|---|---|---|
| **Nexus** | All | Native Python ReAct agent. Always-on, CPU-capable, 4-layer persistent memory, skill loader, A2A federation. |
| **PicoClaw** | Tier A (ARM) | Lightweight runtime from [Sipeed](https://github.com/sipeed/picoclaw). Auto-activated on Raspberry Pi and ARM hardware — no configuration required. |

**Install any framework from the store:**

| Framework | Description |
|---|---|
| **OpenClaw** | 13,700+ community skills, multi-channel. `clawctl framework install openclaw` |
| **SmolAgents** | HuggingFace code-based agent, 30% fewer LLM calls |
| **AgentZero** | Self-correcting, tool creation, computer use |
| **PocketFlow** | 100-line LLM framework, zero deps, MCP support |
| **NullClaw** | Stateless, ephemeral, pure function execution |
| **ZeroClaw** | Rust implementation, ultra-lightweight |
| **NanoClaw** | ~500 TypeScript lines, minimal footprint |
| **Langroid** | Multi-agent message-passing, built-in local LLM support |
| **OpenAI Agents SDK** | Provider-agnostic, 100+ LLM support |
| **Hermes Agent** | Nous Research self-improving agent — persistent cross-session memory, MCP integration, autonomous skill loops. _Coming post-v0.1._ |

Every framework routes through a shared LiteLLM proxy — one Ollama backend, any framework on top. OpenClaw itself is built on [pi-mono](https://github.com/badlogic/pi-mono) (MIT) — when it's the active framework, pi's 4-tool core (read/bash/edit/write) drives the agent loop.

---

## How it works

```
You (Terminal / Voice / Dashboard / App)
         |
      agentd   ← task queue + session manager
         |
    frameworkd  ← active framework routing (Nexus / OpenClaw / SmolAgents / ...)
         |
      llmd     ← LiteLLM proxy — unified OpenAI-compatible endpoint
         |
      Ollama   ← local inference, no cloud, no API keys
         |
     policyd   ← every tool call checked before it runs
         |
   toolbridge  ← files, web, shell, memory
         |
       memd    ← temporal knowledge graph + hybrid RRF memory
```

Every action goes through `policyd`. Sensitive operations pause for your approval. Nothing talks to the internet unless you explicitly allow it. A tamper-evident Merkle-chained audit log records every action taken on your machine.

---

## Security

| Requirement | Status |
|---|---|
| Agent-level RBAC with scoped permissions | ✅ |
| Runtime permission check before every tool call | ✅ |
| Immutable Merkle-chained audit trail | ✅ |
| Human-in-loop approval for sensitive actions | ✅ |
| Kill switch — terminate agent actions in real time | ✅ |
| Credential isolation — no API keys in agent context | ✅ |
| Skill supply-chain: name similarity check on install | ✅ |

---

## vs. other local AI setups

> Ollama runs models. ClawOS runs agents.

| | Just Ollama | Open WebUI | AnythingLLM | Leon | ClawOS |
|---|---|---|---|---|---|
| One-command install | No | Partial | Partial | No | **Yes** |
| Hardware-aware model selection | No | No | No | No | **Yes** |
| Voice pipeline (offline) | No | No | No | Partial | **Yes** |
| Dashboard UI | No | Yes | Yes | No | **Yes** |
| Built-in workflows | No | No | No | Partial | **Yes (29)** |
| Persistent memory | No | No | Partial | No | **Yes (14 layers)** |
| Proactive ambient alerts | No | No | No | No | **Yes** |
| Knowledge brain + graph | No | No | No | No | **Yes** |
| Human approval queue | No | No | No | No | **Yes** |
| Session continuity (morning briefing) | No | No | No | No | **Yes** |
| Framework store (install any agent runtime) | No | No | No | No | **Yes** |
| Signed skill marketplace | No | No | No | No | **Yes** |

*Note: OpenClaw is not in this comparison because ClawOS includes OpenClaw as an optional installable component.*

---

## Memory architecture (taosmd)

Most local AI tools have one memory layer — a vector database. ClawOS has 14, layered by function:

| Layer | Storage | Purpose |
|-------|---------|---------|
| 1 | `PINNED.md` | Human-editable durable facts — always injected into every prompt |
| 2 | `WORKFLOW.md` | Current task state and in-progress context |
| 3 | ChromaDB | Semantic vector search across past conversations |
| 4 | SQLite FTS5 | Keyword search for exact recall |
| 5 | `HISTORY.md` | Activity log and session summaries |
| 6 | taosmd Archive | Long-term archival with decay-resistant storage |
| 7 | Temporal knowledge graph | Time-aware entity relationships |
| 8 | Vector memory | Dense embeddings for similarity retrieval |
| 9 | `SOUL.md` | Agent personality and behaviour shaping |
| 10 | `AGENTS.md` | Operating instructions and capability boundaries |
| 11 | `IDENTITY.md` | Public name and channel persona |
| 12 | `LEARNED.md` | ACE self-improving loop — extractions from past corrections |
| 13 | `HEARTBEAT.md` | Periodic check configuration |
| 14 | RAG index | Document retrieval from ingested files |

The write lifecycle is ADD → UPDATE → DELETE → NOOP to prevent bloat. Memory writes are async — the agent loop never blocks on them.

---

## Requirements

- Ubuntu 24.04, Debian 12, Raspberry Pi OS, or macOS 14+ (Apple Silicon first, Intel best-effort)
- 8GB RAM minimum (16GB recommended for useful agentic tasks)
- 10GB free disk space
- Internet on first run only (pulls models, then fully offline)

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
- [x] Framework Store — install any AI agent framework from dashboard UI
- [x] LiteLLM proxy — unified model endpoint for all frameworks
- [x] Session continuity — JARVIS picks up where you left off
- [x] Temporal memory — knowledge graph + hybrid RRF retrieval
- [ ] **Bootable ISO** — flash and boot, no install needed (v0.1.1)

---

## License

ClawOS is licensed under the **GNU Affero General Public License v3 or later (AGPL-3.0-or-later)**. See [LICENSE](LICENSE) for the full text.

ClawOS is not affiliated with OpenClaw or Anthropic. OpenClaw and Ollama remain their own independently licensed upstream projects. Links to original projects are provided throughout this README.

---

*Built for people who wanted a local AI assistant that actually works. [github.com/xbrxr03/clawos](https://github.com/xbrxr03/clawos)*

