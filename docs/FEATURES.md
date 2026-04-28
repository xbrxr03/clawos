# ClawOS Feature Overview

Complete list of all implemented features in ClawOS.

## Table of Contents

1. [Core Services](#core-services)
2. [AI Services](#ai-services)
3. [Agent Framework](#agent-framework)
4. [Developer Tools](#developer-tools)
5. [Knowledge Management](#knowledge-management)
6. [Security Features](#security-features)
7. [Observability](#observability)
8. [CLI Commands](#cli-commands)

---

## Core Services

### Dashboard Service (dashd) - Port 7070
- Service health monitoring dashboard
- Real-time metrics display
- System resource usage
- Service control interface
- WebSocket updates

### Core API (clawd) - Port 7071
- Central API gateway
- Request routing
- Authentication/authorization
- Rate limiting
- API versioning

### Memory Service (memd) - Port 7073
- Session memory storage
- Context persistence
- Memory search
- TTL-based expiration
- Key-value operations

### Policy Service (policyd) - Port 7074
- Permission-based access control
- Policy engine with rule evaluation
- Budget tracking per workspace
- Action approval workflows
- Audit logging

---

## AI Services

### Model Service (modeld) - Port 7075

**Features:**
- Multi-model support (Ollama, OpenAI, Anthropic)
- Model registry and metadata
- Cost tracking per request
- Fallback model selection
- Request routing

**Supported Models:**
- Ollama (local): llama3.2, qwen2.5-coder, mistral, etc.
- OpenAI: gpt-4, gpt-3.5-turbo
- Anthropic: claude-3-opus, claude-3-sonnet

### MCP Protocol (mcpd) - Port 7077

**Features:**
- Model Context Protocol implementation
- Tool registry with JSON schema
- Resource management
- Prompt templating
- Multi-transport support (stdio, HTTP, WebSocket)

**Built-in Tools:**
- `browser_navigate` - Web page navigation
- `browser_click` - Element interaction
- `browser_extract` - Data extraction
- `shell_exec` - Command execution
- `shell_script` - Script execution
- `read_file` - File reading
- `write_file` - File writing

### Voice Pipeline (voiced) - Port 7079

**Features:**
- Text-to-Speech (TTS)
- Speech-to-Text (STT)
- Voice activity detection
- Audio file processing
- Multiple voice models
- Real-time streaming

**Providers:**
- Piper (local TTS)
- System TTS (espeak, say)
- Whisper (STT)

---

## Agent Framework

### Agent Service (agentd) - Port 7072

**Features:**
- Simple agent execution
- Skill invocation
- Task queuing
- Result storage
- Basic multi-step workflows

### Multi-Agent Framework (agentd_v2) - Port 7081

**Features:**
- Multi-agent coordination
- Agent roles and personas
- Collaboration protocols
- Task delegation
- Result aggregation
- Conflict resolution

**Agent Types:**
- Researcher - Information gathering
- Coder - Code generation
- Reviewer - Code review
- Architect - System design
- QA - Testing and validation

### A2A Protocol (a2ad) - Port 7083

**Features:**
- Agent-to-Agent protocol
- Service discovery
- Agent cards
- Task delegation
- Cross-node communication
- Mesh networking

---

## Developer Tools

### Code Companion - Port 7080

**Features:**
- Local coding agent
- LSP integration (planned)
- Code review
- Refactoring suggestions
- Documentation generation
- Test generation
- Symbol indexing
- Vector search over codebase

**Languages Supported:**
- Python
- JavaScript/TypeScript
- Go
- Rust
- More via tree-sitter

### Secure Sandbox (sandboxd_v2) - Port 7085

**Features:**
- E2B-inspired secure execution
- Containerized execution
- Resource limits (CPU, memory, time)
- Network isolation
- Filesystem sandboxing
- Multi-language support

**Supported Languages:**
- Python
- Node.js
- Bash

### DevOps Notebooks

**Features:**
- Executable markdown
- Multi-language cells
- Variable passing
- Output capture
- Export to scripts
- Session persistence

**Cell Languages:**
- Bash
- Python
- Node.js
- SQL

### Visual Workflow Builder (visuald) - Port 7086

**Features:**
- ComfyUI-style node editor
- Drag-and-drop interface
- Visual data flow
- Real-time execution
- Node library
- Workflow templates

**Node Types:**
- Input/Output
- Process
- Agent
- Skill
- Condition
- Loop
- Merge/Split
- Delay

---

## Knowledge Management

### Second Brain (braind) - Port 7082

**Features:**
- Knowledge graph with entities and relations
- Semantic memory with vector search
- Timeline-based memory
- Pattern discovery
- Insight generation
- Auto-suggested questions

**Entity Types:**
- Person
- Concept
- Project
- Event
- Document

**Relations:**
- knows
- part_of
- related_to
- caused_by
- depends_on

---

## Security Features

### Security Module (clawos_core/security.py)

**Features:**
- Input validation and sanitization
- Path traversal protection
- Code injection detection
- Rate limiting
- Security context management
- Audit logging

### Action Security Rings

**Ring 0** - System Core:
- Policy decisions
- Budget checks
- Audit logging

**Ring 1** - User Data:
- File system access
- Personal data
- Configuration

**Ring 2** - External Data:
- Web browsing
- API calls
- Network access

**Ring 3** - System Changes:
- Package installation
- Service management
- System configuration

**Ring 4** - Destructive:
- File deletion
- Data modification
- Irreversible actions

---

## Observability

### Metrics Service (metricd) - Port 7076

**Features:**
- Prometheus-compatible metrics
- Request latency tracking
- Token usage tracking
- Cost per operation
- Custom metrics support

### Observability Service (observd) - Port 7078

**Features:**
- Distributed tracing
- Structured logging
- Event correlation
- Performance monitoring
- Alert management

---

## CLI Commands

### System Commands

| Command | Description |
|---------|-------------|
| `clawctl status` | Show all service health |
| `clawctl start [svc]` | Start services |
| `clawctl stop [svc]` | Stop services |
| `clawctl restart [svc]` | Restart services |
| `clawctl logs [svc]` | Show service logs |
| `clawctl doctor [--fix]` | Run diagnostics |

### AI Commands

| Command | Description |
|---------|-------------|
| `clawctl model list` | List installed models |
| `clawctl model pull <name>` | Pull a model |
| `clawctl model remove <name>` | Remove a model |
| `clawctl model default <name>` | Set default model |

### Agent Commands

| Command | Description |
|---------|-------------|
| `clawctl agent run <name>` | Run agent |
| `clawctl agent list` | List agents |
| `clawctl a2a peers` | List discovered peers |
| `clawctl a2a delegate <task>` | Send task to peer |

### Workflow Commands

| Command | Description |
|---------|-------------|
| `clawctl wf list` | List workflows |
| `clawctl wf run <id>` | Run workflow |
| `clawctl wf info <id>` | Show workflow details |

### Code Commands

| Command | Description |
|---------|-------------|
| `clawctl code index` | Index codebase |
| `clawctl code query <q>` | Search code |
| `clawctl code review <file>` | Review code |
| `clawctl code test <symbol>` | Generate tests |

### Knowledge Commands

| Command | Description |
|---------|-------------|
| `clawctl brain entity <name>` | Create entity |
| `clawctl brain search <query>` | Search knowledge |
| `clawctl brain timeline` | View timeline |
| `clawctl brain insights` | Show insights |

### Sandbox Commands

| Command | Description |
|---------|-------------|
| `clawctl sandbox create` | Create sandbox |
| `clawctl sandbox execute <id> <file>` | Run code |
| `clawctl sandbox list` | List sandboxes |
| `clawctl sandbox destroy <id>` | Destroy sandbox |

### Notebook Commands

| Command | Description |
|---------|-------------|
| `clawctl notebook new <name>` | Create notebook |
| `clawctl notebook run <file>` | Execute notebook |
| `clawctl notebook export <file>` | Export to script |

### Visual Workflow Commands

| Command | Description |
|---------|-------------|
| `clawctl visual create <name>` | Create workflow |
| `clawctl visual open` | Open editor |
| `clawctl visual run <id>` | Execute workflow |

---

## Feature Matrix

| Feature | Status | Gap # |
|---------|--------|-------|
| MCP Integration | ✅ Complete | #1 |
| Local Coding Agent | ✅ Complete | #2 |
| Voice Pipeline | ✅ Complete | #3 |
| Browser Automation | ✅ Complete | #4 |
| Security Governance | ✅ Complete | #5 |
| Action Caching | ✅ Complete | #6 |
| Agent Framework | ✅ Complete | #7 |
| Workflow Orchestration | ✅ Complete | #8 |
| Second Brain | ✅ Complete | #9 |
| Observability | ✅ Complete | #10 |
| Secure Code Execution | ✅ Complete | #11 |
| Desktop Computer Use | ✅ Complete | #12 |
| DevOps Notebooks | ✅ Complete | #13 |
| Visual Workflow Builder | ✅ Complete | #14 |

---

## Port Allocation

| Port | Service | Category |
|------|---------|----------|
| 7070 | dashd | Core |
| 7071 | clawd | Core |
| 7072 | agentd | Agent |
| 7073 | memd | Core |
| 7074 | policyd | Core |
| 7075 | modeld | AI |
| 7076 | metricd | Observability |
| 7077 | mcpd | AI |
| 7078 | observd | Observability |
| 7079 | voiced | AI |
| 7080 | desktopd | Tools |
| 7081 | agentd_v2 | Agent |
| 7082 | braind | Tools |
| 7083 | a2ad | Agent |
| 7085 | sandboxd | Tools |
| 7086 | visuald | Tools |

---

**Last Updated**: 2026-04-27
**Version**: 0.1.0-beta
