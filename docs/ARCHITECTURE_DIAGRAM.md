# ClawOS Architecture Diagram

> Diagram-as-code version of the architecture. Renders natively on GitHub.
> For the full architecture narrative, see [ARCHITECTURE_CURRENT.md](ARCHITECTURE_CURRENT.md).

## System Overview

```mermaid
graph TD
    subgraph UI["User Interfaces"]
        voice["🎤 Voice<br/>(voiced)"]
        web["🌐 Web Dashboard<br/>(dashd :7070)"]
        cli["⌨️ CLI<br/>(clawctl)"]
        tauri["🖥️ Tauri Overlay<br/>(desktopd :7080)"]
        a2a["🤝 A2A Peers<br/>(a2ad)"]
    end

    subgraph Agent["Nexus Agent Runtime"]
        agentd["agentd<br/>Task Queue + Sessions"]
        runtime["AgentRuntime<br/>Reasoning Loop"]
        policy["Policy Engine<br/>(policyd :7074)"]
        agentd --> runtime --> policy
    end

    subgraph Tools["Tool Bridge"]
        toolbridge["toolbridge"]
        fs["fs.read/write/list"]
        webtools["web.fetch/search"]
        shell["shell.restricted"]
        desktoptools["desktop.clipboard/paste/screenshot"]
        toolbridge --> fs
        toolbridge --> webtools
        toolbridge --> shell
        toolbridge --> desktoptools
    end

    subgraph Memory["Memory System"]
        memd["memd :7073<br/>7-Layer Memory"]
        ragd["ragd<br/>RAG + Vector"]
        braind["braind<br/>Knowledge Graph"]
        memd --> ragd
        memd --> braind
    end

    subgraph Services["Supporting Services"]
        skilld["skilld<br/>Skill Retrieval"]
        reminderd["reminderd :7087<br/>Notifications"]
        waketrd["waketrd :7088<br/>Wake Word Bridge"]
        modeld["modeld<br/>Model Inventory"]
        workfd["workfd<br/>28+ Workflows"]
    end

    subgraph Models["Local Models"]
        ollama["Ollama<br/>:11434"]
        qwen3b["qwen2.5:3b"]
        qwen7b["qwen2.5:7b"]
        qwencoder["qwen2.5-coder:7b"]
        ollama --> qwen3b
        ollama --> qwen7b
        ollama --> qwencoder
    end

    voice -->|"STT/TTS/wake"| agentd
    web -->|"REST + WS"| agentd
    cli -->|"clawctl"| agentd
    tauri -->|"input automation"| agentd
    a2a -->|"peer tasks"| agentd

    runtime -->|"tool calls"| toolbridge
    policy -->|"approval gate"| toolbridge

    runtime -->|"context + memory"| memd
    runtime -->|"skill lookup"| skilld
    runtime -->|"run workflow"| workfd
    runtime -->|"model call"| ollama

    waketrd -->|"briefing trigger"| agentd
    reminderd -->|"desktop notify"| tauri
    modeld -->|"model health"| runtime
```

## Request Flow

```mermaid
sequenceDiagram
    participant User
    participant Agentd as agentd
    participant Runtime as AgentRuntime
    participant Policy as policyd
    participant Toolbridge as toolbridge
    participant Memd as memd
    participant Ollama as Ollama

    User->>Agentd: Submit task (voice/CLI/web)
    Agentd->>Runtime: Create/reuse session
    Runtime->>Memd: Load context (7 layers)
    Runtime->>Ollama: Model inference
    Ollama-->>Runtime: Response + tool calls
    Runtime->>Policy: Check tool permissions
    Policy-->>Runtime: Approved / Needs approval
    Runtime->>Toolbridge: Execute approved tools
    Toolbridge-->>Runtime: Tool results
    Runtime->>Ollama: Continue reasoning (if needed)
    Runtime-->>Agentd: Final response
    Agentd-->>User: Result
```

## Daemon Ports

| Daemon | Port | Role |
|:-------|:-----|:-----|
| `dashd` | 7070 | Dashboard API + WebSocket events |
| `memd` | 7073 | 7-layer memory service |
| `policyd` | 7074 | Permission checks + audit |
| `desktopd` | 7080 | Input automation (clipboard, paste, screenshot) |
| `reminderd` | 7087 | Desktop notifications |
| `waketrd` | 7088 | Wake word → briefing bridge |
| `ollama` | 11434 | Local model inference |

> Daemons without a listed port communicate via the in-process event bus, not over HTTP.