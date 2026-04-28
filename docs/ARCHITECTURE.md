# ClawOS Architecture

High-level architecture overview of the ClawOS system.

## Overview

ClawOS is a modular AI operating system composed of microservices that work together to provide a cohesive AI development and deployment platform.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Interfaces                          │
├─────────────┬─────────────┬─────────────┬───────────────────────┤
│   clawctl   │   Web UI    │   VS Code   │      API Clients      │
│   (CLI)     │   (dashd)   │  (Extension)│      (SDK)            │
└──────┬──────┴──────┬──────┴──────┬──────┴───────────┬───────────┘
       │             │             │                  │
       └─────────────┴─────────────┴──────────────────┘
                          │
       ┌──────────────────┼──────────────────┐
       │                  │                  │
┌──────▼──────┐  ┌────────▼────────┐  ┌─────▼──────┐
│   clawd     │  │     dashd       │  │   a2ad     │
│  (Core API) │  │  (Dashboard)    │  │  (A2A)     │
└──────┬──────┘  └────────┬────────┘  └─────┬──────┘
       │                  │                  │
       └──────────────────┼──────────────────┘
                          │
       ┌──────────────────┼──────────────────┐
       │                  │                  │
┌──────▼──────┐  ┌────────▼────────┐  ┌─────▼──────┐
│   policyd   │  │     memd        │  │  metricd   │
│  (Policy)   │  │   (Memory)      │  │ (Metrics)  │
└──────┬──────┘  └────────┬────────┘  └─────┬──────┘
       │                  │                  │
       └──────────────────┼──────────────────┘
                          │
       ┌──────────────────┼──────────────────┐
       │                  │                  │
┌──────▼──────┐  ┌────────▼────────┐  ┌─────▼──────┐
│   modeld    │  │     mcpd        │  │  observd   │
│   (Models)  │  │    (MCP)        │  │(Observability)│
└──────┬──────┘  └────────┬────────┘  └─────┬──────┘
       │                  │                  │
       └──────────────────┼──────────────────┘
                          │
       ┌──────────────────┼──────────────────┐
       │                  │                  │
┌──────▼──────┐  ┌────────▼────────┐  ┌─────▼──────┐
│   agentd    │  │    agentd_v2    │  │   voiced   │
│   (Agents)  │  │  (Multi-Agent)  │  │  (Voice)   │
└──────┬──────┘  └────────┬────────┘  └─────┬──────┘
       │                  │                  │
       └──────────────────┼──────────────────┘
                          │
       ┌──────────────────┼──────────────────┐
       │                  │                  │
┌──────▼──────┐  ┌────────▼────────┐  ┌─────▼──────┐
│  desktopd   │  │     braind      │  │  sandboxd  │
│  (Desktop)  │  │  (2nd Brain)    │  │ (Sandbox)  │
└─────────────┘  └─────────────────┘  └────────────┘
       │                  │                  │
       └──────────────────┼──────────────────┘
                          │
              ┌───────────▼────────────┐
              │     Skill System       │
              │  (code, notebooks,    │
              │   visual, etc.)       │
              └───────────┬──────────┘
                          │
       ┌──────────────────┼──────────────────┐
       │                  │                  │
┌──────▼──────┐  ┌────────▼────────┐  ┌─────▼──────┐
│   Ollama    │  │     Browser     │  │   Files    │
│   (Local)   │  │   (Playwright)  │  │   (FS)     │
└─────────────┘  └─────────────────┘  └────────────┘
```

## Service Architecture

### Communication Patterns

1. **HTTP/REST**: Primary API communication
2. **WebSocket**: Real-time updates (dashd, visuald)
3. **gRPC**: Internal service communication (planned)
4. **A2A**: Agent-to-agent protocol
5. **MCP**: Model context protocol

### Service Discovery

Services register with the core (clawd) on startup:

```python
# Service registration
clawd.register_service(
    name="modeld",
    port=7075,
    health_endpoint="/health",
    capabilities=["llm", "embeddings"]
)
```

## Core Components

### 1. Policy Engine (policyd)

**Responsibility**: Security and access control

**Features**:
- Action approval based on security rings
- Budget enforcement
- Rate limiting
- Audit logging

**Data Flow**:
```
Request → Policy Check → Action Ring → Execute → Log
              ↓
         Approve/Deny
```

### 2. Memory Service (memd)

**Responsibility**: Session and context persistence

**Storage Types**:
- Short-term: Session context
- Long-term: User preferences
- Vector: Semantic search

**Architecture**:
```
┌─────────────┐
│   API Layer │
└──────┬──────┘
       │
┌──────▼──────┐
│    Cache    │ ← Redis/In-memory
└──────┬──────┘
       │
┌──────▼──────┐
│  Persistent │ ← SQLite/DuckDB
└─────────────┘
```

### 3. Model Service (modeld)

**Responsibility**: LLM abstraction and routing

**Provider Abstraction**:
```
┌─────────────┐
│  Model API  │
└──────┬──────┘
       │
   ┌───┴───┐
   │       │
┌──▼──┐ ┌──▼──┐
│Ollama│ │OpenAI│
└──────┘ └──────┘
```

## Agent Architecture

### Single Agent (agentd)

**Components**:
- Prompt builder
- Tool selector
- Executor
- Memory manager

**Execution Flow**:
```
Input → Parse Intent → Select Tools → Execute → Format Output
            ↓              ↓
       Retrieve Context  Call MCP/Skills
```

### Multi-Agent (agentd_v2)

**Coordinator Pattern**:
```
┌─────────────┐
│ Coordinator │
└──────┬──────┘
       │
   ┌───┼───┐
   │   │   │
┌──▼┐ ┌▼┐ ┌▼┐
│A1 │ │A2│ │A3│  (Specialized agents)
└───┘ └──┘ └──┘
```

### A2A Protocol (a2ad)

**Discovery**:
- mDNS for local network
- Registry for cloud

**Communication**:
- Agent cards for capabilities
- Task delegation
- Result streaming

## Knowledge Architecture

### Second Brain (braind)

**Layers**:
1. **Ingestion**: Extract entities from text
2. **Storage**: Graph database + vector store
3. **Retrieval**: Semantic + structured search
4. **Synthesis**: Pattern discovery

**Data Model**:
```
Entity ──[relation]──→ Entity
  │                      │
  └────[has memory]─────┘
```

## Security Architecture

### Security Rings

```
Ring 0: Policy Engine (trusted)
Ring 1: User Data (sensitive)
Ring 2: External Data (untrusted)
Ring 3: System Changes (dangerous)
Ring 4: Destructive (requires approval)
```

### Approval Flow

```
Action Request
     ↓
Security Check → Block/Allow
     ↓
Budget Check → Insufficient funds?
     ↓
User Confirmation (if required)
     ↓
Execute + Audit Log
```

## Workflow Architecture

### Durable Workflows (durabled)

**Features**:
- State persistence
- Resume on failure
- Parallel execution
- Scheduling

**State Machine**:
```
Pending → Running → Completed
              ↓
         Failed → Retry
```

### Visual Workflows (visuald)

**Node Types**:
- Data nodes (input/output)
- Process nodes (transform)
- Agent nodes (AI)
- Control nodes (condition, loop)

**Execution**:
```
Compile → Topological Sort → Execute Nodes → Collect Results
```

## Data Flow Examples

### Chat with Tools

```
User Input
    ↓
clawd receives
    ↓
agentd processes intent
    ↓
mcpd selects tools
    ↓
Execute tools (browser, shell, etc.)
    ↓
Collect results
    ↓
modeld generates response
    ↓
Return to user
```

### Code Review

```
Developer runs: clawctl code review file.py
    ↓
Code Companion indexes file
    ↓
braind retrieves related knowledge
    ↓
LSP analyzes code structure
    ↓
modeld reviews with context
    ↓
Return suggestions
```

### Multi-Agent Task

```
Task: "Build a web scraper"
    ↓
agentd_v2 coordinator analyzes
    ↓
Delegate to:
  - Architect: Design structure
  - Coder: Implement
  - Reviewer: Check code
    ↓
Aggregate results
    ↓
Return final code
```

## Deployment Patterns

### Monolithic (Development)

All services in one process:
```bash
./scripts/dev_boot.sh --full
```

### Microservices (Production)

Each service as separate container:
```yaml
# docker-compose.yml
services:
  clawd:
    image: clawos/clawd
  modeld:
    image: clawos/modeld
  # ...
```

### Edge (Minimal)

Core only, external AI:
```bash
./scripts/dev_boot.sh --core
```

## Scaling Considerations

### Horizontal Scaling

- **stateless services**: Easy to replicate (modeld, mcpd)
- **stateful services**: Need coordination (memd, braind)
- **single-node services**: Reconsider architecture (policyd)

### Caching Strategy

```
L1: In-memory (per-service)
L2: Redis (shared)
L3: Persistent store
```

### Load Balancing

```
┌─────────┐
│  Nginx  │
└────┬────┘
     │
 ┌───┴───┐
 │       │
┌▼┐     ┌▼┐
│S1│     │S2│
└──┘     └──┘
```

## Future Architecture

### Planned Components

1. **clawd_v2**: Rust-based core for performance
2. **Distributed Brain**: Federated knowledge graph
3. **Edge Runtime**: WASM-based skills
4. **FHE Support**: Fully homomorphic encryption

### Research Directions

- LLM-native operating systems
- Agent swarm coordination
- Continuous learning
- Quantum-safe cryptography

---

**Last Updated**: 2026-04-27
**Version**: 0.1.0-beta
