# ClawOS Current Architecture

## Purpose

ClawOS is best understood as a local-first agent platform with service-shaped modules, not a fully distributed microservice mesh. The codebase contains multiple generations of the product at once, so this document names the canonical path that works today and the legacy pieces that should be treated as secondary.

## Canonical Runtime Path

1. User input enters through `nexus`, `clawctl`, dashboard APIs, WhatsApp, or A2A.
2. `agentd` owns task submission, session reuse, and the local HTTP API.
3. `AgentRuntime` builds context, chooses tools, and talks to Ollama.
4. `toolbridge` runs tools after a `policyd` check.
5. `memd` provides memory, workspace context, and optional RAG.
6. `dashd` observes the event bus and exposes the dashboard API.

```text
input/channel -> agentd -> AgentRuntime -> policyd -> toolbridge -> local system
                              |                |
                              |                -> audit log + approvals
                              -> memd / skilld / ragd
                              -> Ollama
```

## Canonical Components

- `services/agentd/service.py`: queue, session cache, direct chat, local API.
- `runtimes/agent/runtime.py`: active reasoning loop and Ollama integration.
- `services/toolbridge/service.py`: filesystem, web, shell, memory, and system tools.
- `services/policyd/service.py`: permission checks, approval queue, audit integration.
- `services/memd/service.py`: memory layers, FTS, optional vector and knowledge helpers.
- `services/dashd/api.py`: canonical dashboard API and WebSocket event stream.
- `clawos_core/`: shared constants, IDs, models, event bus, and utilities.

## Supporting Components

- `services/modeld/service.py`: model inventory, health, profile selection, and VRAM helpers.
- `services/gatewayd/service.py`: WhatsApp bridge and peer delegation entry points.
- `services/a2ad/service.py`: agent card, peer discovery, and A2A API.
- `workflows/`: prompt-driven workflows on top of the core runtime.
- `openclaw_integration/`: installer and configuration bridge for the OpenClaw ecosystem.

## Non-Canonical Or Legacy Surfaces

- `dashboard/backend/` is a legacy dashboard backend. `services/dashd/api.py` should be treated as the canonical dashboard service.
- `clients/dashboard/index.html` is the dashboard frontend currently served by `dashd`.
- `modeld` is not the hot-path inference gateway today. `AgentRuntime` calls Ollama directly.
- Many `services/*/main.py` files are process wrappers around in-process modules, not independent network services with strong contracts.

## Contract Rules

- Submit tasks to `agentd` via `/submit`. `/tasks` exists as a legacy compatibility route.
- Use `intent` for new task payloads. `task` is accepted for backwards compatibility.
- `shell.restricted` is the canonical shell tool. `shell.run` is accepted as a compatibility alias.
- Destructive workflows must go through `policyd` approval.
- `DEFAULT_WORKSPACE` from `clawos_core/constants.py` is the canonical default workspace value.

## Repository Shape

- `clawos_core/`: primitives and shared types.
- `services/`: long-lived service modules and APIs.
- `runtimes/`: the active agent loop.
- `clients/`: user-facing interfaces and daemon entrypoints.
- `workflows/`: prebuilt jobs, mostly prompt-defined.
- `configs/`, `systemd/`, `setup/`, `bootstrap/`: install and runtime support.
- `content_factory_skill/`: separate sidecar project, not part of the core runtime path.

## Immediate Cleanups Still Needed

- Pick one dashboard stack and delete or archive the other.
- Route inference through one clearly documented gateway, or explicitly document that `AgentRuntime` talks to Ollama directly.
- Tighten auth on dashboard and A2A endpoints.
- Replace prompt-only workflows with deterministic helpers for the highest-value jobs.
