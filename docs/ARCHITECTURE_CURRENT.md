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
- `clawos_core/`: shared constants, IDs, models, event bus, platform, service-manager, and utilities.

## Supporting Components

- `services/modeld/service.py`: model inventory, health, profile selection, and VRAM helpers.
- `services/gatewayd/service.py`: WhatsApp bridge and peer delegation entry points.
- `services/a2ad/service.py`: agent card, peer discovery, and trusted-peer A2A API.
- `workflows/`: a mix of agent-backed prompts and direct Python helpers with platform metadata.
- `openclaw_integration/`: installer and configuration bridge for the OpenClaw ecosystem.

## Non-Canonical Or Legacy Surfaces

- `archive/legacy/dashboard-backend/` preserves the retired dashboard backend for reference only.
- `clients/dashboard/index.html` is a retired single-file dashboard snapshot and is not served by `dashd`.
- `modeld` is not the hot-path inference gateway today. `AgentRuntime` calls Ollama directly.
- Many `services/*/main.py` files are process wrappers around in-process modules, not independent network services with strong contracts.

## Contract Rules

- Submit tasks to `agentd` via `/submit`.
- Use `intent` for task payloads across first-party callers.
- `shell.restricted` is the canonical shell tool everywhere.
- Destructive workflows must go through `policyd` approval.
- `DEFAULT_WORKSPACE` from `clawos_core/constants.py` is the canonical default workspace value.

## Repository Shape

- `clawos_core/`: primitives and shared types.
- `services/`: long-lived service modules and APIs.
- `runtimes/`: the active agent loop.
- `clients/`: user-facing interfaces and daemon entrypoints.
- `workflows/`: prebuilt jobs and helper-backed workflows.
- `configs/`, `systemd/`, `setup/`, `bootstrap/`, `scripts/`: install and runtime support.

## Immediate Cleanups Still Needed

- Route inference through one clearly documented gateway, or explicitly document that `AgentRuntime` talks to Ollama directly.
- Keep dashboard setup-bypass limited to pre-completion, loopback-only setup flows.
- Keep trusted-peer allow-listing enforced for remote A2A task ingress.
