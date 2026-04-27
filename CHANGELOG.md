# Changelog

All notable changes to ClawOS.

## [0.1.0] - 2026-04-27

### Added

#### MCP Integration (Phase 1 & 2)
- **MCP Client** (`services/toolbridge/mcp_client.py`)
  - StdioTransport for local MCP servers
  - HTTPTransport for remote MCP servers
  - Auto-discovery of 600+ tools
  - Tool execution with result formatting

- **MCP Server** (`services/mcpd/`)
  - FastAPI-based MCP server on port 7077
  - 7 tools: skill_execute, memory_search, memory_save, workflow_run, system_info, list_workflows, list_skills
  - 4 resources: skills, workflows, system/status, memory/{workspace}
  - 2 prompts: daily_briefing, task_planner
  - Full JSON-RPC 2.0 protocol support

- **MCP CLI** (`clawctl/commands/mcp.py`)
  - `clawctl mcp init` - Create default config
  - `clawctl mcp list` - Show configured servers
  - `clawctl mcp add` - Add new server
  - `clawctl mcp test` - Test connections
  - `clawctl mcp discover` - Find available servers

#### Observability Service (observd)
- **Service** (`services/observd/`) on port 7078
  - SQLite-backed storage for LLM calls
  - Token usage tracking (prompt/completion/total)
  - Cost estimation (OpenAI, Anthropic, Google, Ollama)
  - Latency monitoring (avg/min/max/p95)
  - Time-series analytics

- **CLI** (`clawctl/commands/observ.py`)
  - `clawctl observ calls` - View LLM calls
  - `clawctl observ stats` - Aggregate statistics
  - `clawctl observ cost` - Cost breakdown
  - `clawctl observ latency` - Latency analysis
  - `clawctl observ export` - Export to JSON/CSV

#### Durable Workflow Engine
- **Engine** (`workflows/durable_engine.py`)
  - Step-based workflow execution
  - Automatic checkpointing
  - Resume from last completed step
  - Retry with exponential backoff
  - SQLite-backed persistence

- **CLI** (`clawctl/commands/durable.py`)
  - `clawctl durable runs` - List runs
  - `clawctl durable show` - Show details
  - `clawctl durable resume` - Resume failed
  - `clawctl durable cancel` - Cancel running
  - `clawctl durable cleanup` - Remove old runs

#### Code Companion Skill
- **Skill** (`skills/code_companion/`)
  - LSPClient: Language Server Protocol client
    - Python, TypeScript, Rust, Go, Java, C/C++ support
    - Go-to-definition, find references, hover
  - TreeSitterParser: AST-based code understanding
  - CodebaseIndex: Vector index for semantic search

- **CLI** (`clawctl/commands/code.py`)
  - `clawctl code index` - Index codebase
  - `clawctl code search` - Semantic search
  - `clawctl code review` - Find issues
  - `clawctl code test` - Generate tests
  - `clawctl code explain` - Explain code

#### Browser Automation 2.0
- **Skill** (`skills/browser_vision/`)
  - VisionElementDetector: Screenshot → action
  - AccessibilityTreeParser: CDP-based selectors
  - ActionCache: Replay without LLM calls
  - VisionBrowserAgent: Full automation

#### Voice Pipeline 2.0
- **Service** (`services/voiced/`) on port 7079
  - VADProcessor: WebRTC Voice Activity Detection
  - WakeWordDetector: "Hey JARVIS" detection
  - StreamingTTS: Piper-based streaming synthesis
  - STTProcessor: Whisper transcription
  - Real-time interruption handling

#### Desktop Automation
- **Service** (`services/desktopd/`) on port 7080
  - Cross-platform screenshot capture
  - PyAutoGUI/pynput input control
  - Mouse, keyboard, clipboard control
  - Safety policies with restricted zones
  - Vision-based UI understanding

#### Multi-Agent Framework
- **Service** (`services/agentd/v2/`) on port 7081
  - 8 predefined agent roles with capabilities
  - Crew/team orchestration
  - Sequential, hierarchical, parallel execution
  - Agent delegation and messaging

#### Security & Performance
- **Security Module** (`clawos_core/security.py`)
  - InputValidator: Path sanitization, code injection detection
  - RateLimiter: API rate limiting
  - SecurityContext: Permission management
  - AuditLogger: Security audit logging

- **Performance Module** (`clawos_core/performance.py`)
  - PerformanceMonitor: Singleton metric tracker
  - @timed decorator for function timing
  - MemoryProfiler: Memory usage tracking
  - CachingDecorator: TTL-based memoization

#### CLI Dashboard
- **Dashboard** (`clawctl/commands/dashboard.py`)
  - Real-time service status for 12 services
  - Color-coded status display
  - Watch mode with auto-refresh
  - Service logs viewer
  - Performance metrics display

#### Documentation
- **Research Documents** (`docs/research/`)
  - CRITICAL_GAPS_RESEARCH.md - 14 gaps identified
  - STRATEGIC_MASTERPLAN.md - Implementation roadmap
  - 15 additional research documents

- **API Reference** (`docs/API_REFERENCE.md`)
  - Complete API documentation for all services
  - Request/response examples
  - Authentication and rate limiting

- **Testing Guide** (`docs/TESTING_GUIDE.md`)
  - Comprehensive testing procedures
  - Static analysis, unit, integration tests
  - Performance and security tests

- **Bug Bounty Report** (`docs/BUG_BOUNTY_REPORT.md`)
  - Full testing results
  - Bugs found and fixed
  - Security posture assessment

- **Test Report** (`docs/END_TO_END_TEST_REPORT.md`)
  - End-to-end testing results
  - Service status matrix
  - Production readiness assessment

### Fixed
- Syntax error in mcpd (missing parenthesis)
- Code Companion hard ChromaDB dependency (made optional)
- Script permissions (install.sh, dev_boot.sh)

### Changed
- Port allocation extended (7077-7081 for new services)
- Added health checks to dev_boot.sh
- Added new services to dashboard API

### Security
- Added input validation module
- Added rate limiting
- Added audit logging framework
- Added security headers

## Stats
- **Total Commits:** 17
- **Files Changed:** 45+
- **Lines Added:** ~20,000
- **New Services:** 6
- **New CLI Commands:** 15+
- **Documentation:** 8 new docs

## Migration Guide

### From 0.0.x to 0.1.0

1. Update configuration:
```bash
# Add new service ports to config
clawctl config set ports.mcpd 7077
clawctl config set ports.observd 7078
clawctl config set ports.voiced 7079
clawctl config set ports.desktopd 7080
clawctl config set ports.agentd_v2 7081
```

2. Install new dependencies:
```bash
pip install -e ".[dev]"
```

3. Start new services:
```bash
./scripts/dev_boot.sh
```

4. Test new features:
```bash
clawctl mcp init
clawctl observ status
clawctl dashboard
```

---

**Full Changelog:** https://github.com/clawos/clawos/commits/main
