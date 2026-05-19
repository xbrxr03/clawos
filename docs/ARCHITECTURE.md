# ClawOS Architecture Guide

> How a local-first, zero-cloud AI assistant actually works — from voice wave to tool execution and back.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                           User                                       │
│                     ┌───────┐  ┌─────┐                               │
│                     │ Voice │  │ CLI │                               │
│                     └───┬───┘  └──┬──┘                               │
│                         │        │                                    │
│              ┌──────────▼────────▼──────────┐                        │
│              │        voiced / clawd         │  ← Input services     │
│              └──────────────┬────────────────┘                        │
│                             │                                         │
│              ┌──────────────▼────────────────┐                        │
│              │     Agent Runtime (runtime.py) │  ← Core loop          │
│              │  ┌─────────────────────────┐  │                        │
│              │  │ 1. Memory fast-path      │  │                        │
│              │  │ 2. Confirmation responses │  │                        │
│              │  │ 3. Intent classifier     │  │  ← Regex, no LLM      │
│              │  │ 4. LLM + tool_calls      │  │  ← Ollama native      │
│              │  └─────────────────────────┘  │                        │
│              │         Model Router          │  ← FAST/SMART/CODER   │
│              └──────┬──────┬────────────────┘                        │
│                     │      │                                         │
│          ┌──────────▼┐  ┌──▼───────────┐                             │
│          │   memd     │  │  policyd     │  ← Gate every tool call   │
│          │ (Memory)   │  │ (Approvals)  │                            │
│          └───────────┘  └──┬───────────┘                             │
│                            │                                         │
│              ┌─────────────▼──────────────┐                          │
│              │       toolbridge             │  ← Execute tools       │
│              │  fs · shell · web · memory   │                        │
│              └─────────────┬───────────────┘                          │
│                            │                                         │
│              ┌─────────────▼──────────────┐                          │
│              │   voiced (TTS) → Speaker    │  ← Speak response      │
│              │   dashd → Tauri UI          │  ← Show in dashboard   │
│              └────────────────────────────┘                          │
│                                                                      │
│              ┌──────────────────────────────┐                        │
│              │     Event Bus (pub/sub)       │  ← Wire everything   │
│              └──────────────────────────────┘                        │
└─────────────────────────────────────────────────────────────────────┘
```

ClawOS is a **microservices-style local AI assistant**. Every capability — memory, voice, policy, tools, agent lifecycle — runs as an independent service communicating through an in-process event bus and direct async calls. Nothing leaves the machine.

---

## Components

### Agent Runtime (`runtimes/agent/runtime.py`)

The brain. `AgentRuntime` processes every user turn through a **4-tier priority pipeline**:

1. **Memory fast-path** — Check if the query matches a pinned or high-confidence memory. If yes, return immediately — no LLM call.
2. **Confirmation responses** — Handle "yes", "no", "cancel" prompts from pending approvals or multi-step workflows.
3. **Intent classifier** (`intents.py`) — A pure regex engine that classifies ~60-70% of inputs without hitting the LLM. Intents include `GREETING`, `REMINDER_ADD`, `VOLUME_SET`, `APP_OPEN`, `TIME_QUERY`, `MEMORY_RECALL`, and `LLM_NEEDED` (fallback to model).
4. **LLM with tool_calls** — Sends the conversation history + granted tool schemas to Ollama's native function-calling API. The model decides whether to respond directly or invoke tools.

The runtime is built by `build_runtime()`, which wires up memory, policy, toolbridge, and the model router into a single `AgentRuntime` object per workspace.

### Model Router (`runtimes/agent/router.py`)

Not all tasks need the same model. The router selects between three profiles based on task complexity:

| Profile  | Model              | When used                                    |
|----------|--------------------|----------------------------------------------|
| FAST     | `qwen2.5:3b`       | Greetings, simple Q&A, confirmation responses |
| SMART    | `qwen2.5:7b`       | Multi-step reasoning, tool calls, composition |
| CODER    | `qwen2.5-coder:7b` | Code generation, debugging, shell commands   |

Routing signals come from intent classification (simple intents → FAST) and explicit tool-type detection (shell/code → CODER).

### Memory Service (`services/memd/service.py`)

4-layer memory architecture, each layer serving a different access pattern:

| Layer      | Backend          | Purpose                                              |
|------------|------------------|------------------------------------------------------|
| PINNED     | `PINNED.md` file | Always injected into the system prompt. Key facts, identity, preferences. |
| WORKFLOW   | `WORKFLOW.md` file | Current task state, scratch space. Cleared per session. |
| Semantic   | ChromaDB         | Vector similarity search over past conversations and facts. |
| Keyword    | SQLite FTS5      | Full-text keyword search for exact-term recall.      |

`memd` also hosts taosmd backends for knowledge graph construction, intent classification assist, and secret filtering (PII redaction before LLM context injection).

The `remember()` and `recall()` operations are the two main entry points. `remember()` writes to both ChromaDB and FTS5; `recall()` queries both and merges results by relevance score.

### Policy Engine (`services/policyd/service.py`)

Every tool call passes through `policyd`. No exceptions. The evaluation pipeline:

1. **Before-hooks** — Custom lifecycle hooks can block a tool call before evaluation begins.
2. **Tool grant check** — If the tool isn't in the workspace's granted tool list, it's denied.
3. **Blocked path check** — File operations outside the workspace root are denied.
4. **Blocked URL check** — Local/private network URLs are denied (SSRF protection).
5. **Prompt injection scan** — Tool inputs are scanned for injection patterns. High-severity (score ≥ 8) are denied.
6. **Risk score evaluation** — Each tool has a numeric risk score (e.g., `fs.delete: 70`, `shell.restricted: 45`, `memory.read: 5`). If the score ≥ 50 (`TOOL_SCORE_QUEUE`), the call is queued for **human approval** via an async `asyncio.Event`.
7. **Audit log** — Every decision (ALLOW, DENY, QUEUE) is written to an append-only JSONL audit trail with SHA-256 hash chaining.

Human approval can come from the Tauri dashboard, the CLI, or WhatsApp. If no response arrives within 120 seconds, the call is auto-denied.

### ToolBridge (`services/toolbridge/service.py`)

The tool execution layer. `ToolBridge.run_native()` takes a tool name + args dict from the LLM's `tool_calls` response and:

1. Resolves file paths to absolute (within workspace).
2. Sends the call through `policyd` for gating.
3. Dispatches to either **native tools** (`runtimes/agent/tools/`) or **legacy tools** (the `_execute()` dispatch table).
4. Runs after-hooks for post-execution auditing.

Available tool categories:

- **Filesystem** — `read_file`, `write_file`, `list_files`, `fs.delete`, `fs.search`
- **Shell** — `run_command` (allowlist-gated: `ls`, `git`, `python3`, etc.)
- **Web** — `web_search`, `web.fetch`
- **Memory** — `remember`, `recall`, `pin_fact`, `memory.delete`
- **System** — `system_stats`
- **Workspace** — `workspace.create`, `workspace.inspect`
- **Browser** — `browser.open/read/click/type/screenshot/close/scroll/wait` (Playwright, disabled by default)

### Voice Pipeline (`services/voiced/`, `runtimes/voice/`)

Two paths:

1. **Wake word → STT → Agent → TTS** — Always-listening mode using OpenWakeWord ("Hey Jarvis") with Whisper STT and Piper TTS. Full-duplex voice loop.
2. **Push-to-talk** — Record utterance → Whisper → agent → Piper → speaker. No wake word needed.

`VoiceService` manages microphone selection, recording, VAD (voice activity detection with silence threshold), and speaker output. `voice_entry.py` bridges voice into the agent runtime — `voice_chat_once()` is a single exchange: text → agent → speak → return.

### Agent Lifecycle (`services/agentd/service.py`)

`AgentManager` is the session orchestrator. Key responsibilities:

- **One session per workspace** — Multiple workspaces can run in parallel.
- **VRAM guard** — Before spinning up a new session on Tier D hardware, checks if GPU memory is available via `modeld`.
- **Task queue** — If a workspace session is busy, incoming tasks queue and run sequentially.
- **Channel routing** — Tasks arrive from CLI (`clawd`), voice (`voiced`), dashboard (`dashd`), or A2A protocol. Agentd normalizes them into `Task` objects.

### Service Registry & Manager (`clawos_core/`)

- **`service_registry.py`** — Health-aware service discovery. Each service registers with a TTL heartbeat. Callers get the healthiest instance. Circuit breaker integration trips after 3 failures.
- **`service_manager.py`** — Platform-aware daemon lifecycle. On macOS, generates `launchd` plist files. On Linux, writes `systemd` user unit files. `clawctl start/stop/status` delegates here.

### Event Bus (`clawos_core/events/bus.py`)

Lightweight asyncio pub/sub. All services publish events (task updates, tool calls, approval requests, service heartbeats, chat messages). The dashboard subscribes via WebSocket to render real-time UI.

Event types: `log`, `task_update`, `tool_call`, `approval_request`, `approval_decided`, `service_up`, `service_down`, `heartbeat`, `chat_message`, `whatsapp_message`.

### Daemon (`clients/daemon/daemon.py`)

Headless service runner for systemd/launchd. Starts the full stack — dashboard, setupd, memd, modeld, skilld, agentd — and keeps them alive. Signal handlers for graceful shutdown.

### Bootstrap (`bootstrap/bootstrap.py`)

One-time machine preparation. Idempotent — safe to re-run:

1. **Hardware probe** — Detects RAM, GPU, VRAM, Ollama status.
2. **Profile selection** — Maps hardware to a tier (lowram/balanced/performance/gaming).
3. **Workspace setup** — Creates `~/clawos/` directory tree and seeds the default workspace.
4. **Memory init** — Sets up ChromaDB collections and FTS5 tables.
5. **Policy config** — Writes default permissions.
6. **Model provisioning** — Pulls the recommended Ollama model.

### Dashboard (`services/dashd/`)

Tauri-based desktop UI (or web at `localhost:7070`). Shows real-time agent status, approval popups, conversation history, and memory browser. Subscribes to the event bus via WebSocket.

---

## Data Flow: Voice Command to Action

Here's what happens when a user says **"Hey Claw, what's on my calendar today?"**:

```
1.  Wake word detector (OpenWakeWord) triggers
2.  voiced records audio via microphone (VAD silence detection)
3.  Whisper STT transcribes audio → "What's on my calendar today?"
4.  voiced passes text to agentd → AgentRuntime.chat()
5.  Runtime checks Memory fast-path → no pinned match
6.  Runtime checks Intent classifier → CALENDAR_QUERY intent detected
7.  Router selects SMART model (calendar needs reasoning)
8.  LLM generates tool_call: { "name": "calendar_events", "arguments": { "date": "today" } }
9.  ToolBridge.run_native() resolves args
10. policyd.evaluate() → ALLOW (risk score 15 < 50)
11. Tool executes → returns calendar events
12. LLM generates final response: "You have 3 events today..."
13. voiced pipes response through Piper TTS
14. Audio plays through speaker
15. Event bus publishes: chat_message, tool_call, task_update
```

For a **dangerous command** like "Delete my old backups":

```
Steps 1-8: same flow
9.  ToolBridge → policyd.evaluate("fs.delete", "/backups/old/", ...)
10. Risk score 70 ≥ 50 → QUEUE for human approval
11. policyd emits approval_request event → dashboard shows popup
12. asyncio.Event waits for decision (or 120s timeout)
13. Human approves → ALLOW → tool executes
14. Human denies → DENY → "Permission denied" response
15. Audit trail records: who approved, when, what tool, what target
```

---

## Memory System in Detail

### Layer 1: PINNED (`PINNED.md`)

A plain Markdown file in the workspace root. Always injected into every LLM context at the top of the system prompt. Used for identity, core preferences, and facts the user never wants forgotten.

```markdown
- I prefer dark mode
- My timezone is America/New_York
- Project ClawOS is the highest priority
```

### Layer 2: WORKFLOW (`WORKFLOW.md`)

Task-state scratchpad. The agent writes current goals, in-progress steps, and intermediate results here. Cleared or rotated between sessions. Provides continuity within a single conversation.

### Layer 3: ChromaDB (Semantic)

Embeds all `remember()` inputs using `nomic-embed-text`, stores them in ChromaDB collections. `recall()` vectorizes the query and returns the top-K results by cosine similarity. Handles conceptual queries — "that thing about databases" → finds the memory about PostgreSQL tuning.

### Layer 4: SQLite FTS5 (Keyword)

Traditional full-text search index. Fast exact-term matching. `recall()` queries this in parallel with ChromaDB and merges results. Handles queries like "meeting with Sarah" or "error code 404".

### Secret Filtering

Before any memory content enters the LLM context, `memd` runs a secret filter that redacts API keys, passwords, and tokens. Secrets are never sent to the model, even in local-only mode.

---

## Security Model

### Defense in Depth

ClawOS uses a **layered permission model** — no single point of trust:

1. **Tool grant list** — Each workspace has an explicit set of allowed tools. Not granted = denied.
2. **Risk scoring** — Every tool has a numeric risk score. Scores ≥ 50 require human approval.
3. **Path sandboxing** — File operations are restricted to the workspace directory. Accessing `~/.ssh`, `/etc`, or other sensitive paths is blocked.
4. **URL blocking** — SSRF protection blocks private IPs, localhost, and internal hostnames.
5. **Shell allowlist** — Only pre-approved commands can run. Regex patterns like `^git\s`, `^ls(\s|$)`, `^python3?\s+[^-]`.
6. **Prompt injection scanning** — Tool inputs are scanned for injection patterns. High-severity injections (score ≥ 8) are denied.
7. **Audit trail** — Every policy decision is logged to an append-only JSONL file with SHA-256 hash chaining for tamper evidence.
8. **Before/after hooks** — Extensible lifecycle hooks for custom policy logic (e.g., rate limiting, data loss prevention).

### Human-in-the-Loop

The approval system is **asynchronous and multi-channel**:

- **Dashboard popup** — Tauri window appears, user clicks approve/deny.
- **Terminal prompt** — In interactive mode, `[a]pprove/[d]eny` appears inline.
- **WhatsApp bridge** — Approval requests can be sent via WhatsApp for remote approval.
- **Auto-deny on timeout** — If no response within 120 seconds, the call is denied.

### Zero Telemetry

ClawOS makes **zero network calls** except to local Ollama. No analytics, no phoning home, no crash reports. Verify by searching the codebase — no external URLs, no telemetry SDKs, no tracking pixels.

---

## Design Decisions & Trade-offs

### Local-First, Zero Cloud

**Decision**: Everything runs on the user's machine. Ollama handles inference. No API keys needed.

**Trade-off**: Model quality is limited by local hardware. A 7B parameter model on a Mac mini won't match GPT-4. But the user's data never leaves their machine — no privacy leaks, no subscription costs, no rate limits.

### Regex Intent Classification (No LLM for Simple Inputs)

**Decision**: The intent classifier uses pure regex patterns to handle ~60-70% of inputs without calling the LLM.

**Trade-off**: Less flexible than LLM-based classification, but zero latency and zero cost for greetings, time queries, volume controls, and other deterministic intents. Falls back to LLM for anything complex.

### Microservices Architecture (In-Process)

**Decision**: Services are modular (memd, policyd, toolbridge, voiced, etc.) but run in the same process with async dispatch, not as separate OS processes.

**Trade-off**: No IPC overhead or service discovery complexity, but a crash in one service can take down the whole process. The service manager provides systemd/launchd integration for production reliability.

### Async Approval Queue (Not Blocking)

**Decision**: Policy approvals use `asyncio.Event` — the agent loop awaits the decision, but the event loop keeps running. Other tasks can proceed.

**Trade-off**: More complex than synchronous blocking, but essential for a responsive voice assistant that can't freeze while waiting for approval.

### Hardware-Adaptive Profiles

**Decision**: Four hardware tiers (A through D) automatically selected during bootstrap based on detected RAM, GPU, and VRAM.

| Tier | Hardware              | Model            | Context | Voice | Parallel Agents |
|------|-----------------------|------------------|---------|-------|-----------------|
| A    | CPU-only, ≤8GB RAM    | `gemma3:4b`      | 2048    | No    | 1               |
| B    | x86, 8-16GB RAM      | `qwen2.5:7b`     | 4096    | Yes   | 1               |
| C    | x86, 16-32GB + GPU   | `qwen2.5:7b`     | 8192    | Yes   | 1               |
| D    | 32GB+ RAM, GPU ≥10GB | `qwen2.5:7b`     | 16384   | Yes   | 3               |

Tier D enables parallel agent sessions with VRAM-aware scheduling.

### Ollama Native Function Calling

**Decision**: Use Ollama's native `tool_calls` API instead of parsing LLM output with regex.

**Trade-off**: Requires models that support function calling (Qwen 2.5, Llama 3.1+), but eliminates prompt injection via structured tool invocation and gives reliable argument extraction.

---

## Service Map

| Service   | Port  | Purpose                                      |
|-----------|-------|----------------------------------------------|
| dashd     | 7070  | Dashboard web UI + WebSocket                 |
| clawd     | 7071  | CLI agent interface                           |
| agentd    | 7072  | Agent lifecycle manager                       |
| memd      | 7073  | Memory service (4-layer)                      |
| policyd   | 7074  | Permission gate (risk scoring, approvals)    |
| modeld    | 7075  | Model management + VRAM scheduler             |
| metricd   | 7076  | Token usage tracking + budget enforcement     |
| mcpd      | 7077  | Model Context Protocol server                |
| obserd    | 7078  | Observability (OTel traces)                   |
| voiced    | 7079  | Voice pipeline (STT/TTS/wake word)            |
| desktopd  | 7080  | Desktop integration (Tauri)                   |
| braind    | 7082  | Background reasoning + RAG                   |
| sandboxd  | 7085  | Sandboxed code execution                      |
| a2ad      | 7083  | Agent-to-Agent protocol server                |
| setupd    | 7084  | First-run setup wizard                        |
| visuald   | 7086  | Vision/screen understanding                   |
| reminderd | 7087  | Scheduled reminders                           |
| waketrd   | 7088  | Wake word training                            |
| picoclawd | 18800 | Tier A lightweight agent (Pi/edge devices)   |

All services communicate in-process via the async event bus and direct async function calls. Ports are exposed for external integrations (dashboard, A2A, CLI).

---

## Directory Structure

```
clawos/
├── bootstrap/          # One-time machine setup (hardware probe, profile, model pull)
├── clawos_core/        # Shared library: constants, models, events, config, platform
│   ├── constants.py    # Single source of truth for paths, ports, versions
│   ├── models.py       # Data classes: Task, Session, Decision, AuditEntry, etc.
│   ├── events/bus.py   # Asyncio pub/sub event bus
│   ├── service_registry.py  # Health-aware service discovery
│   ├── service_manager.py   # systemd/launchd lifecycle management
│   └── security.py     # Input validation, rate limiting, pattern detection
├── clients/
│   ├── daemon/          # Headless service runner (systemd/launchd entry point)
│   ├── cli/             # CLI client (clawctl)
│   └── desktop/         # Tauri desktop app
├── runtimes/
│   ├── agent/           # Agent runtime core
│   │   ├── runtime.py   # 4-tier priority pipeline
│   │   ├── router.py    # FAST/SMART/CODER model selection
│   │   ├── intents.py   # Regex intent classifier
│   │   ├── tool_schemas.py  # JSON Schema definitions for tool_calls
│   │   ├── tools/       # Native tool implementations
│   │   ├── briefing.py  # Morning briefing generator
│   │   └── voice_entry.py  # Voice → runtime bridge
│   └── voice/           # Voice pipeline
│       ├── microphone.py    # Audio recording + VAD
│       ├── stt_client.py    # Whisper speech-to-text
│       └── tts.py           # Piper text-to-speech
├── services/
│   ├── agentd/          # Agent lifecycle (session management, VRAM guard)
│   ├── memd/            # 4-layer memory (PINNED, WORKFLOW, ChromaDB, FTS5)
│   ├── policyd/         # Permission gate (risk scoring, human approval, audit)
│   ├── toolbridge/      # Tool execution (policy gating, dispatch, hooks)
│   ├── voiced/          # Voice service (STT/TTS/wake word orchestration)
│   ├── modeld/          # Model management + VRAM scheduling
│   ├── dashd/           # Dashboard (FastAPI + WebSocket)
│   ├── braind/          # Background reasoning + RAG
│   ├── sandboxd/        # Sandboxed execution environment
│   ├── metricd/         # Token usage + budget tracking
│   ├── mcpd/            # Model Context Protocol server
│   ├── a2ad/            # Agent-to-Agent protocol
│   └── ...              # setupd, visuald, reminderd, etc.
├── adapters/
│   ├── policy/          # LocalPolicyAdapter (wraps PolicyEngine)
│   ├── memory/          # Memory adapter for runtime
│   ├── browser/          # Playwright session manager
│   ├── audio/           # Audio device adapters
│   └── models/          # Model adapter (Ollama client)
├── dashboard/           # Frontend (web/Tauri UI)
├── setup/               # First-run setup wizard
└── Makefile             # Build, test, lint, service management
```

---

## Key Files Quick Reference

| File | Purpose |
|------|---------|
| `runtimes/agent/runtime.py` | Agent loop — 4-tier priority pipeline |
| `runtimes/agent/router.py` | Model router — FAST/SMART/CODER |
| `runtimes/agent/intents.py` | Regex intent classifier |
| `runtimes/agent/tool_schemas.py` | JSON Schema definitions for Ollama tool_calls |
| `services/memd/service.py` | 4-layer memory service |
| `services/policyd/service.py` | Permission engine, risk scoring, approval queue |
| `services/toolbridge/service.py` | Tool dispatch, policy gating, hooks |
| `services/agentd/service.py` | Agent lifecycle, VRAM guard, task queue |
| `services/voiced/service.py` | Voice pipeline orchestration |
| `clawos_core/constants.py` | All paths, ports, models, thresholds |
| `clawos_core/events/bus.py` | Async event bus |
| `clawos_core/models.py` | Shared data models |
| `bootstrap/bootstrap.py` | First-run setup |
| `clients/daemon/daemon.py` | Headless service runner |

---

*This document traces the real code — module imports, function signatures, and data flows. When the code changes, update this doc.*