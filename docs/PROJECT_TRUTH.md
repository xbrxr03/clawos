# ClawOS — Project Truth
## Version 0.1.0 Prototype | March 2026

> **Historical document.** This was written in March 2026 during initial design.
> The file tree and session plan below reflect the original intended structure, not the
> current codebase. For current canonical architecture see `docs/ARCHITECTURE_CURRENT.md`.
> WhatsApp/gatewayd was planned here but was never shipped — those paths do not exist.
> Model defaults have changed: Tier A uses qwen2.5:3b, not gemma3:4b (fixed in v0.1.1).

---

## One sentence definition

ClawOS is a preconfigured, low-RAM, local-first agent OS that boots into a
working AI environment — with policy-gated tools, workspace isolation, memory,
voice, and optional OpenClaw — on consumer hardware, offline, free.

---

## What ClawOS is

- Linux-based (Ubuntu LTS) bootable OS image
- Preconfigured for CPU-first / low-RAM use
- Ships with TWO runtimes: Claw Core (default) + OpenClaw (optional)
- Local-first: all data on device, no cloud, no API keys
- Safe: every tool call gated through policyd
- Voice: Whisper STT + Piper TTS, offline
- Dashboard: operations console at :7070
- One-command startup, first-run wizard, opinionated defaults

## What ClawOS is NOT (v0.1)

- Not a full desktop environment rewrite
- Not a robotics platform
- Not a multi-user enterprise system
- Not a cloud SaaS
- Not "OpenClaw bundled into Linux" — OpenClaw is an optional app layer

---

## Two runtimes

### Claw Core (default)
- Our native Python agent with native Ollama function calling
- Works on 8GB RAM, qwen2.5:3b, CPU-only
- 61/61 tests passing
- 4-layer memory (PINNED + WORKFLOW + ChromaDB + FTS5 + HISTORY)
- Merkle audit trail, lifecycle hooks, asyncio.Event per call
- Voice via voiced

### OpenClaw (optional, installed on request)
- Node.js, 430K lines, full ecosystem, 13,700+ skills
- Pre-configured for Ollama offline (no API keys, no cloud)
- Pre-patched with known Linux fixes (auth-profiles bug, etc.)
- Config: openclaw.json points at localhost:11434, api: openai-completions
- Needs qwen2.5:7b or better (needs tool calling support)
- Installed via: clawctl openclaw install (or: ollama launch openclaw)
- Started via: clawctl openclaw start

### Runtime selection
First-run wizard asks:
  "Choose your runtime"
  [1] Claw Core — fast, low RAM, always works (recommended)
  [2] OpenClaw — full ecosystem, needs 16GB+ free RAM
  [3] Both — Claw Core default, OpenClaw available
Can switch later: clawctl runtime set [core|openclaw|both]

---

## Hardware targets

| Tier | Hardware | RAM | Claw Core | OpenClaw |
|------|----------|-----|-----------|----------|
| A    | 8GB mini PC | 8GB | ✅ default | ❌ too heavy |
| B    | ROG Ally, 16GB laptop | 16GB | ✅ default | ✅ optional |
| C    | 32GB+ workstation | 32GB+ | ✅ | ✅ recommended |

Primary dev hardware: ROG Ally RC71L (Tier B, balanced profile)

---

## Canonical internal flow (Claw Core)

```
User input (CLI / Voice / Dashboard)
  → agentd (task queue)
  → context_builder (SOUL + AGENTS + memory recall)
  → modeld (Ollama inference)
  → tool request
  → policyd (ALLOW / DENY / QUEUE)
  → toolbridge (execute)
  → event bus (broadcast to dashboard)
  → response synthesis
  → output (same channel as input)
```

---

## Service boot order

1. policyd  — must exist before any action
2. memd     — memory before agent starts
3. modeld   — model before agent starts
4. toolbridge
5. agentd
6. voiced   (optional)
7. clawd    — orchestration, hardware detection, scheduler
8. dashd    — observes everything

---

## Project file tree (canonical)

```
clawos/
├── PROJECT_TRUTH.md          ← you are here
├── README.md
├── LICENSE
├── pyproject.toml
├── Makefile
├── .env.example
│
├── configs/
│   ├── defaults.yaml         ← base all profiles inherit from
│   ├── lowram.yaml           ← 8-16GB, gemma3:4b, voice off
│   ├── balanced.yaml         ← 16-32GB, gemma3:4b, voice on (ROG Ally)
│   ├── performance.yaml      ← 32GB+, larger model
│   ├── desktop.yaml          ← Desktop edition overrides
│   └── server.yaml           ← Server/headless overrides
│
├── clawos_core/              ← shared primitives, imported by all services
│   ├── __init__.py
│   ├── constants.py          ← VERSION, paths, ports, model names
│   ├── config/
│   │   ├── loader.py         ← load + merge yaml configs
│   │   └── schema.py         ← pydantic config models
│   ├── events/
│   │   └── bus.py            ← asyncio event bus (pub/sub)
│   ├── models/
│   │   └── __init__.py       ← Task, Session, AuditEntry, ToolCall, Decision
│   ├── logging/
│   │   └── audit.py          ← Merkle-chained audit writer
│   └── util/
│       ├── ids.py            ← task_id(), session_id(), entry_id()
│       ├── time.py           ← now_iso(), now_stamp()
│       ├── paths.py          ← workspace_path(), pinned_path(), etc.
│       └── jsonx.py          ← json_repair wrapper + safe_parse()
│
├── bootstrap/                ← one-time machine setup (run once at install)
│   ├── bootstrap.py          ← main entry: runs all steps in order
│   ├── hardware_probe.py     ← detect RAM, GPU, audio, CPU → tier
│   ├── profile_selector.py   ← auto-select lowram/balanced/performance
│   ├── workspace_init.py     ← create dirs, PINNED/SOUL/AGENTS/HEARTBEAT
│   ├── model_provision.py    ← ollama pull + verify
│   ├── memory_init.py        ← init SQLite FTS5 + ChromaDB
│   ├── tools_init.py         ← register default tool grants per profile
│   ├── permissions_init.py   ← write initial policy config
│   └── service_enable.py     ← enable + start systemd user services
│
├── setup/
│   ├── first_run/
│   │   ├── wizard.py         ← main wizard controller, screen sequencer
│   │   ├── state.py          ← WizardState, persistence
│   │   └── screens/
│   │       ├── welcome.py
│   │       ├── hardware_profile.py
│   │       ├── runtime_choice.py   ← Claw Core / OpenClaw / Both
│   │       ├── workspace_setup.py
│   │       ├── voice_setup.py
│   │       ├── model_setup.py
│   │       ├── whatsapp_setup.py   ← QR scan
│   │       ├── policy_setup.py
│   │       └── summary.py
│   └── repair/
│       ├── doctor.py
│       ├── fixes.py
│       └── diagnostics.py
│
├── runtimes/
│   ├── agent/                ← Claw Core agent loop
│   │   ├── runtime.py        ← main ReAct loop (was jarvis.py)
│   │   ├── context_builder.py← system prompt + memory injection
│   │   ├── parser.py         ← json_repair response parser
│   │   ├── prompts.py        ← SYSTEM_PROMPT, _build_user_message()
│   │   ├── session_store.py  ← workspace → session cache
│   │   └── retries.py        ← retry logic, backoff
│   ├── voice/
│   │   ├── stt_client.py     ← Whisper at 44100Hz via pipewire
│   │   ├── tts_client.py     ← Piper TTS lessac-medium
│   │   ├── microphone.py     ← audio capture, silence detection
│   │   ├── wakeword.py       ← OpenWakeWord "Hey Claw"
│   │   └── runtime.py        ← push-to-talk + always-on pipeline
│   └── scheduler/
│       ├── scheduler.py      ← cron + interval job runner
│       ├── jobs.py           ← job registry, HEARTBEAT.md parser
│       └── persistence.py    ← SQLite job store
│
├── services/                 ← long-running systemd daemons
│   ├── policyd/
│   │   ├── service.py        ← permission gate, hooks, audit
│   │   ├── rules.py          ← TOOL_SCORES, BLOCKED_PATHS
│   │   ├── approvals.py      ← ApprovalRequest, asyncio.Event
│   │   ├── main.py
│   │   └── health.py
│   ├── memd/
│   │   ├── service.py        ← 4-layer memory manager
│   │   ├── lifecycle.py      ← ADD/UPDATE/DELETE/NOOP
│   │   ├── fts_store.py      ← SQLite FTS5
│   │   ├── vector_store.py   ← ChromaDB
│   │   ├── ranking.py        ← merge + deduplicate recall
│   │   ├── main.py
│   │   └── health.py
│   ├── toolbridge/
│   │   ├── service.py        ← tool dispatch
│   │   ├── registry.py       ← ALL_TOOL_DESCRIPTIONS, filtering
│   │   ├── dispatcher.py     ← route to tool modules
│   │   ├── sandbox.py        ← workspace isolation, allowlist
│   │   ├── main.py
│   │   └── health.py
│   ├── agentd/
│   │   ├── service.py        ← task queue, session manager
│   │   ├── handlers.py       ← handle_chat, handle_task, handle_voice
│   │   ├── main.py
│   │   └── health.py
│   ├── modeld/
│   │   ├── service.py        ← model profiles, routing
│   │   ├── ollama_client.py  ← chat, pull, list, health
│   │   ├── embeddings_client.py
│   │   ├── main.py
│   │   └── health.py
│   ├── voiced/
│   │   ├── service.py
│   │   ├── main.py
│   │   └── health.py
│   ├── clawd/
│   │   ├── service.py        ← orchestration, hardware detect, scheduler
│   │   ├── main.py
│   │   └── health.py
│   ├── dashd/
│   │   ├── api.py            ← all REST routes
│   │   ├── websocket.py      ← ConnectionManager, broadcast
│   │   ├── frontend.py       ← embedded single-file HTML dashboard
│   │   ├── main.py
│   │   └── health.py
│   └── gatewayd/             ← message routing (WhatsApp → agentd → WhatsApp)
│       ├── service.py
│       ├── session_router.py ← contact → workspace mapping
│       ├── media_handler.py  ← voice notes → STT, images
│       ├── approval_bridge.py← WhatsApp reply → approve/deny
│       ├── channels/
│       │   ├── base.py       ← BaseChannel interface
│       │   └── whatsapp.py   ← whatsapp-web.py bridge
│       ├── main.py
│       └── health.py
│
├── adapters/                 ← pluggable backends
│   ├── models/
│   │   ├── base.py
│   │   └── ollama_adapter.py
│   ├── memory/
│   │   ├── base.py
│   │   ├── chroma_adapter.py
│   │   └── sqlite_adapter.py
│   ├── audio/
│   │   ├── base.py
│   │   ├── whisper_adapter.py
│   │   └── piper_adapter.py
│   ├── audit/
│   │   ├── base.py
│   │   └── jsonl_adapter.py
│   └── policy/
│       └── local_policy_adapter.py  ← was policyd_client.py
│
├── tools/                    ← callable tools the agent uses
│   ├── __init__.py
│   ├── registry.py           ← register all tools
│   ├── filesystem/
│   │   ├── read_file.py
│   │   ├── write_file.py
│   │   ├── list_dir.py
│   │   └── search.py
│   ├── shell/
│   │   ├── run_command.py    ← allowlisted execution
│   │   └── safe_exec.py
│   ├── web/
│   │   ├── search.py         ← DuckDuckGo + offline fallback
│   │   ├── fetch.py
│   │   └── download.py
│   ├── system/
│   │   ├── disk_info.py
│   │   ├── process_info.py
│   │   ├── services.py
│   │   └── network_info.py
│   ├── workspace/
│   │   ├── create.py
│   │   └── inspect.py
│   └── dev/
│       ├── git_status.py
│       └── project_scan.py
│
├── clawctl/                  ← user-facing CLI: clawctl <command>
│   ├── __init__.py
│   ├── main.py               ← Click entry point
│   ├── commands/
│   │   ├── start.py
│   │   ├── stop.py
│   │   ├── restart.py
│   │   ├── status.py
│   │   ├── logs.py
│   │   ├── doctor.py
│   │   ├── config.py
│   │   ├── model.py
│   │   ├── workspace.py
│   │   ├── voice.py
│   │   ├── whatsapp.py
│   │   └── openclaw.py       ← install/start/stop/status OpenClaw
│   └── ui/
│       ├── banner.py         ← ASCII art, ClawOS identity
│       └── formatting.py     ← tables, progress bars, status icons
│
├── clients/
│   ├── cli/
│   │   ├── repl.py           ← interactive text chat
│   │   └── commands.py       ← /memory /pin /reset slash commands
│   ├── dashboard/
│   │   └── index.html        ← single-file dashboard (no build step)
│   └── voice/
│       └── push_to_talk.py
│
├── openclaw_integration/     ← OpenClaw optional layer
│   ├── installer.py          ← npm install + configure for Ollama offline
│   ├── config_gen.py         ← generate pre-patched openclaw.json
│   ├── fixes.py              ← apply known Linux fixes (auth-profiles bug)
│   ├── launcher.py           ← start/stop/status OpenClaw gateway
│   └── openclaw.json.template← pre-configured for Ollama, offline mode
│
├── data/
│   ├── prompts/
│   │   ├── system.txt        ← base system prompt
│   │   ├── soul.txt          ← default SOUL.md template
│   │   ├── agents.txt        ← default AGENTS.md template
│   │   ├── heartbeat.txt     ← default HEARTBEAT.md template
│   │   └── tooluse.txt
│   └── presets/
│       ├── policies/
│       │   └── default.json
│       └── workspaces/
│           └── default/
│               ├── PINNED.md
│               ├── SOUL.md
│               └── AGENTS.md
│               └── HEARTBEAT.md
│
├── packaging/
│   ├── systemd/
│   │   ├── clawos-policyd.service
│   │   ├── clawos-memd.service
│   │   ├── clawos-modeld.service
│   │   ├── clawos-toolbridge.service
│   │   ├── clawos-agentd.service
│   │   ├── clawos-voiced.service
│   │   ├── clawos-clawd.service
│   │   ├── clawos-dashd.service
│   │   └── clawos-gatewayd.service
│   ├── install/
│   │   ├── install.sh
│   │   ├── postinstall.sh
│   │   └── uninstall.sh
│   └── iso/
│       ├── build_iso.sh
│       └── preseed.cfg
│
├── tests/
│   ├── unit/
│   │   ├── test_core.py
│   │   ├── test_memory.py
│   │   ├── test_policy.py
│   │   └── test_tools.py
│   ├── integration/
│   │   ├── test_agent_pipeline.py
│   │   ├── test_memory_pipeline.py
│   │   ├── test_voice_pipeline.py
│   │   └── test_whatsapp_bridge.py
│   └── system/
│       ├── test_phase1.py       ← 56/56 passing (migrated)
│       ├── test_phase3_4.py     ← dashd + clawd (migrated)
│       └── test_full_stack.py   ← end-to-end all services
│
└── scripts/
    ├── dev_boot.sh             ← start all services for dev
    ├── run_local_stack.sh
    ├── seed_workspace.sh       ← seed PINNED/SOUL/AGENTS defaults
    └── benchmark_models.sh
```

---

## Migration map (old files → new structure)

| Old file | New location |
|----------|-------------|
| banner.py | clawctl/ui/banner.py |
| jarvis.py | runtimes/agent/runtime.py |
| memory_service.py | services/memd/service.py |
| policyd.py | services/policyd/service.py |
| policyd_client.py | adapters/policy/local_policy_adapter.py |
| toolbridge.py | services/toolbridge/service.py |
| voice_service.py | services/voiced/service.py + adapters/audio/ |
| dashd.py | services/dashd/api.py + main.py |
| clawd.py | services/clawd/service.py |
| test_phase1.py | tests/system/test_phase1.py |
| test_phase3_4.py | tests/system/test_phase3_4.py |
| clawos-*.service | packaging/systemd/ |

---

## Session build plan

| Session | Deliverable |
|---------|------------|
| S1 | Full tree + all core files + migrated services + test suite passing |
| S2 | Bootstrap + first-run wizard + clawctl CLI |
| S3 | WhatsApp gatewayd + heartbeat scheduler |
| S4 | OpenClaw integration layer (install + configure + fixes) |
| S5 | Packaging + bootable ISO |

---

## Key rules for every file written

1. Always import from clawos_core — never hardcode constants
2. Every service has main.py + service.py + health.py
3. Every tool call goes through policyd — no exceptions
4. All paths use clawos_core/util/paths.py helpers
5. All IDs use clawos_core/util/ids.py helpers
6. json_repair wrapper in jsonx.py — never raw json.loads on LLM output
7. Async writes for memory — never block the agent loop
8. Tests must run without a live LLM (unit/integration) and with one (--e2e)
