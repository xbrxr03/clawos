# ClawOS Architecture Deep Analysis

## Overview
**ClawOS** is a comprehensive, self-hosted AI agent operating system that transforms a spare PC into a private "JARVIS" — a voice-enabled, memory-persistent AI assistant with 29+ built-in workflows, running entirely offline.

---

## Philosophy & Design Principles

1. **Privacy-First**: Zero cloud dependencies, zero API keys required, fully local
2. **One-Command Install**: `curl | bash` simplicity despite complex internals
3. **Hardware-Aware**: Detects RAM/CPU/GPU and auto-selects appropriate models
4. **Modular Architecture**: Service-oriented design with clear boundaries
5. **Democratized AI**: Makes local agentic AI accessible to non-technical users

---

## Core Architecture

### Service Mesh (Microservices)
ClawOS runs as a constellation of specialized services:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           USER INTERFACES                              │
├─────────────┬──────────────┬──────────────┬──────────────┬──────────────┤
│  Terminal   │   Voice      │  Dashboard   │   WhatsApp   │   Browser    │
│  (clawos)   │  ("Hey Claw")│  (:7070)     │   (bridge)   │  (OMI/Agent) │
└──────┬──────┴──────┬───────┴──────┬───────┴──────┬───────┴──────┬───────┘
       │             │              │              │              │
       └─────────────┴──────────────┴──────────────┴──────────────┘
                                   │
                         ┌─────────┴─────────┐
                         │    agentd         │  ← Task queue + session manager
                         │  (Agent Manager)  │
                         └─────────┬─────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
       ┌──────┴──────┐    ┌────────┴────────┐   ┌──────┴──────┐
       │   Nexus     │    │   OpenClaw      │   │  SmolAgents │
       │ (ReAct)     │    │ (pi-mono core)  │   │   etc.      │
       │             │    │                 │   │             │
       └──────┬──────┘    └────────┬────────┘   └─────────────┘
              │                    │
              └────────┬───────────┘
                       │
              ┌────────┴────────┐
              │    policyd      │  ← Permission gate (every tool call)
              │  (Policy Engine)│
              └────────┬────────┘
                       │
       ┌───────────────┼───────────────┐
       │               │               │
┌──────┴──────┐ ┌──────┴──────┐ ┌──────┴──────┐
│  memd       │ │ toolbridge  │ │   braind    │
│ (14-layer   │ │ (tool exec) │ │ (knowledge  │
│  memory)    │ │             │ │   graph)    │
└─────────────┘ └─────────────┘ └─────────────┘
       │               │               │
       └───────────────┼───────────────┘
                       │
              ┌────────┴────────┐
              │    llmd         │  ← LiteLLM proxy (unified endpoint)
              │ (Model Router)  │
              └────────┬────────┘
                       │
              ┌────────┴────────┐
              │     Ollama      │  ← Local inference
              │  (qwen2.5 etc)  │
              └─────────────────┘
```

---

## Services Deep Dive

### 1. **agentd** — Agent Lifecycle Manager
- **Purpose**: Task queue management, session persistence, workspace isolation
- **Key Features**:
  - One session per workspace_id (cached/reused)
  - VRAM guard for Tier D (GPU) machines — prevents OOM
  - Kizuna integration — enriches intents with brain context, writes back learnings
  - Task states: QUEUED → RUNNING → COMPLETED/FAILED

### 2. **policyd** — Permission Gate
- **Purpose**: Every tool call passes through here. No exceptions.
- **Risk Scoring**: Each tool has a risk score (fs.delete=70, shell.restricted=45, etc.)
- **Thresholds**:
  - Score < TOOL_SCORE_QUEUE (15): Auto-allow
  - Score ≥ 15: Queued for approval
  - Score ≥ 70: Requires explicit human approval
- **Security Features**:
  - Path validation (blocked paths: ~/.ssh, /etc, etc.)
  - URL validation (blocks localhost, metadata.google.internal, etc.)
  - Prompt injection scanning
  - Merkle-chained audit log (tamper-evident)
  - Hook registry (BeforeToolCall / AfterToolCall)

### 3. **memd** — Memory Service (14 Layers)
Based on taosmd (Temporal Agent Operating System Memory Daemon):

| Layer | Storage | Purpose |
|-------|---------|---------|
| 1 | PINNED.md | Human-editable durable facts (always injected) |
| 2 | WORKFLOW.md | Current task state |
| 3 | ChromaDB | Semantic vector search |
| 4 | SQLite FTS5 | Keyword search |
| 5 | HISTORY.md | Activity log |
| 6 | taosmd Archive | Long-term archival |
| 7 | Temporal Knowledge Graph | Time-aware entity relationships |
| 8 | Vector Memory | Dense embeddings |
| 9 | SOUL.md | Agent personality |
| 10 | AGENTS.md | Operating instructions |
| 11 | IDENTITY.md | Public name/channel persona |
| 12 | LEARNED.md | ACE self-improving loop extractions |
| 13 | HEARTBEAT.md | Periodic check configuration |
| 14 | RAG index | Document retrieval |

**Lifecycle**: ADD → UPDATE → DELETE → NOOP (prevents bloat)
**Async writes**: Agent loop never blocks on memory

### 4. **toolbridge** — Tool Execution
- **Policy-gated**: All calls route through policyd
- **Available Tools**:
  - `fs.read/write/list/delete/search` — File operations
  - `web.search/fetch` — Web access
  - `shell.restricted` — Allowlisted shell commands
  - `memory.read/write/delete` — Memory operations
  - `system.info` — System metrics
  - `workspace.create/inspect` — Workspace management
  - `browser.open/read/click/type/screenshot` — Playwright automation
- **Agent Tool Filtering**: Only inject granted tools into system prompt (30-60% token reduction)

### 5. **skilld** — Skill Loader
- **Format**: OpenClaw-compatible SKILL.md packages
- **Search Paths**: `~/.claw/skills/` (priority) → `~/.openclaw/skills/`
- **Scoring**: BM25 relevance — injects only relevant skills per turn
- **Pinned Skills**: Always injected (bypasses scoring)
- **Limits**: Max 3 non-pinned skills per turn, 3 pinned max

### 6. **braind** — Knowledge Brain (Kizuna)
- **Purpose**: 3D knowledge graph with temporal awareness
- **Features**:
  - GraphRAG retrieval
  - Automatic expansion from agent outputs
  - Gap detection and research triggers
  - Significance filtering

### 7. **voiced** — Voice Pipeline
- **Wake Word**: "Hey Jarvis" (openWakeWord)
- **STT**: OpenAI Whisper (local)
- **TTS**: Piper (offline) or ElevenLabs (optional)
- **Modes**: wake_word, push_to_talk, off

### 8. **llmd** — LiteLLM Proxy
- Unified OpenAI-compatible endpoint
- Routes to Ollama (local) or configured providers
- Port: 11500

### 9. **dashd** — Dashboard Service
- React frontend (17 pages)
- WebSocket real-time updates
- Setup wizard
- Port: 7070

### 10. **Other Services**
- **setupd**: First-run configuration wizard
- **clawd**: Core ClawOS daemon coordination
- **frameworkd**: Framework Store (9 frameworks, one-click install)
- **mcpd**: Model Context Protocol server management
- **ragd**: Document RAG pipeline
- **metricd**: OTel token tracking
- **a2ad**: Agent-to-Agent protocol federation
- **omid**: OMI (BasedHardware) ambient AI integration
- **picoclawd**: Tier A ARM edge runtime
- **secretd**: Credential management
- **researchd**: Autonomous research engine

---

## Runtime Architecture

### Nexus (ReAct Agent)
The native ClawOS agent runtime:

```python
# Core loop
for iteration in range(MAX_ITERATIONS):
    response = call_llm(messages)
    parsed = parse_response(response)
    
    if "final_answer" in parsed:
        return parsed["final_answer"]
    elif "action" in parsed:
        result = await toolbridge.run(parsed["action"], ...)
        messages.append({"role": "user", "content": f"Observation: {result}"})
```

**Features**:
- json_repair parsing (handles malformed LLM outputs)
- Token-aware context injection
- 4-layer memory injection
- Skill scoring & injection
- ACE (self-improving) loop
- Session continuity (morning briefing)
- RAG context injection

---

## Workflows (29 Built-in)

| Category | Workflows |
|----------|-----------|
| **Files** | organize_downloads, clean_empty_dirs, find_duplicates, bulk_rename, folder_summary |
| **Documents** | summarize_pdf, pdf_to_notes, merge_pdfs, extract_tables, csv_summary, csv_to_report, sql_to_csv |
| **Developer** | pr_review, changelog, write_readme, repo_summary, log_summarize, json_explorer, find_todos, port_scan |
| **Content** | batch_summarize, rewrite, proofread, caption_images, meeting_notes |
| **System** | disk_report, backup_check, process_report, daily_digest |

**Workflow Engine Features**:
- Platform-gated (macOS/Linux specific)
- Destructive operation policy gating
- Progress streaming via WebSocket
- Timeout handling
- Agent dependency injection

---

## Configuration System

### Hardware Profiles (Auto-Detected)
| Profile | RAM | GPU | Default Model |
|---------|-----|-----|---------------|
| Tier A (lowram) | 8GB | No | qwen2.5:3b |
| Tier B (balanced) | 16GB | No | qwen2.5:7b |
| Tier C (performance) | 32GB+ | No | qwen2.5:14b |
| Tier D (gaming) | Any | 10GB+ VRAM | qwen2.5:7b (GPU) |

### User Personas (Setup Wizard)
1. Developer — OpenClaude + qwen2.5-coder
2. Creator — Content workflows + daily briefing
3. Business — Lead research, reports, scheduling
4. Student — Summarize lectures, research wiki, proofread
5. Teacher — Lesson planning, curriculum wiki, scheduling
6. General — Balanced setup
7. Freelancer — Proposals, client research, outreach, invoicing

---

## Security Architecture

| Feature | Implementation |
|---------|---------------|
| RBAC | Workspace-scoped permissions |
| Tool Gating | policyd evaluates every call |
| Audit Trail | Merkle-chained, tamper-evident logs |
| Human Approval | Queue for sensitive operations |
| Kill Switch | Real-time action termination |
| Credential Isolation | secretd, no API keys in agent context |
| Supply Chain | Ed25519 skill signing, sandbox execution |
| Prompt Injection | Scanner integrated into policyd |
| Path Security | Blocked paths, workspace containment |
| URL Security | Private IP/metadata blocking |

---

## File Structure

```
~/clawos/
├── config/
│   ├── clawos.yaml          # Main config
│   └── skills/              # Installed skills
├── workspace/
│   └── nexus_default/       # Default workspace
│       ├── PINNED.md
│       ├── HISTORY.md
│       ├── SOUL.md
│       ├── AGENTS.md
│       └── ...
├── services/                # Service daemons
├── voice/                   # Piper voice models
├── logs/                    # Service logs
└── brain/                   # Knowledge graph DB

~/.claw/                     # Claw Core files
~/.openclaw/                 # OpenClaw compatibility
```

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.10+ |
| Async | asyncio |
| Web Framework | FastAPI (services), React (dashboard) |
| Database | SQLite (FTS5), ChromaDB (vectors) |
| ML Inference | Ollama |
| Default Models | Qwen2.5 series (3b/7b/14b) |
| Embeddings | nomic-embed-text |
| Reranking | cross-encoder/ms-marco-MiniLM-L-6-v2 |
| STT | OpenAI Whisper |
| TTS | Piper (local), ElevenLabs (optional) |
| Wake Word | openWakeWord |
| Voice | WebRTC, VAD |
| Packaging | systemd (Linux), launchd (macOS) |
| License | AGPL-3.0-or-later |

---

## Key Innovations

1. **taosmd**: 14-layer memory architecture with temporal knowledge graphs
2. **Kizuna**: GraphRAG brain with automatic expansion
3. **Hardware-Aware Install**: Auto-detects and configures for user's machine
4. **Framework Store**: One-click install of 9 different agent frameworks
5. **Policy Engine**: Fine-grained permission control with audit trails
6. **Session Continuity**: Morning briefings from session state
7. **A2A Federation**: Multi-instance agent communication
8. **Skill Marketplace**: Signed, sandboxed skill distribution

---

## Development Status

| Feature | Status |
|---------|--------|
| Core Runtime | ✅ Complete |
| Voice Pipeline | ✅ Complete |
| Dashboard | ✅ Complete |
| Workflows (29) | ✅ Complete |
| Memory System | ✅ Complete |
| Policy Engine | ✅ Complete |
| Framework Store | ✅ Complete |
| A2A Federation | ✅ Complete |
| Skill Marketplace | ✅ Complete |
| Bootable ISO | 🚧 Planned (v0.1.1) |

---

## Analysis Notes

This is an extremely mature, production-ready system. The architecture shows deep thinking about:

1. **Scalability**: Service-oriented design allows independent scaling
2. **Security**: Defense in depth at every layer
3. **User Experience**: One-command install despite complexity
4. **Privacy**: True local-first, no cloud dependencies
5. **Extensibility**: Plugin architecture via skills and frameworks

The codebase (~200+ Python files, 110 service files) represents a serious engineering effort. The combination of taosmd memory, Kizuna brain, policyd security, and hardware-aware provisioning creates a genuinely unique product in the local AI space.
