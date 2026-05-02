# ClawOS API Reference

Complete API documentation for all ClawOS services.

---

## Service Ports

| Service | Port | Purpose |
|---------|------|---------|
| dashd | 7070 | Dashboard & health |
| clawd | 7071 | Main orchestrator |
| agentd | 7072 | Agent management |
| memd | 7073 | Memory service |
| policyd | 7074 | Policy engine |
| modeld | 7075 | Model management |
| metricd | 7076 | Metrics collection |
| **mcpd** | **7077** | **MCP Server** |
| **observd** | **7078** | **Observability** |
| **voiced** | **7079** | **Voice Pipeline** |
| **desktopd** | **7080** | **Desktop Automation** |
| **agentd_v2** | **7081** | **Multi-Agent Framework** |

---

## MCP Server (mcpd) API

### Health Check
```http
GET http://localhost:7077/health
```

**Response:**
```json
{
  "status": "up",
  "service": "mcpd",
  "tools": 7,
  "resources": 4,
  "prompts": 2
}
```

### List Tools
```http
GET http://localhost:7077/api/v1/tools
```

**Response:**
```json
{
  "tools": [
    {
      "name": "clawos_skill_execute",
      "description": "Execute a ClawOS skill"
    },
    {
      "name": "clawos_memory_search", 
      "description": "Search memory"
    }
  ]
}
```

### Execute Tool
```http
POST http://localhost:7077/api/v1/tools/execute
Content-Type: application/json

{
  "name": "clawos_skill_execute",
  "arguments": {
    "skill": "git",
    "target": "status"
  }
}
```

---

## Observability (observd) API

### Health Check
```http
GET http://localhost:7078/health
```

### Record LLM Call
```http
POST http://localhost:7078/api/v1/llm_calls
Content-Type: application/json

{
  "workspace": "default",
  "model": "llama3.2",
  "provider": "ollama",
  "prompt_tokens": 100,
  "completion_tokens": 50,
  "total_tokens": 150,
  "cost_usd": 0.0,
  "duration_ms": 500
}
```

### Get Recent Calls
```http
GET http://localhost:7078/api/v1/calls?hours=24&workspace=default
```

### Get Statistics
```http
GET http://localhost:7078/api/v1/stats?workspace=default&days=7
```

### Cost Analysis
```http
GET http://localhost:7078/api/v1/cost?days=7
```

### Latency Analysis
```http
GET http://localhost:7078/api/v1/latency?days=7
```

---

## Voice Pipeline (voiced) API

### Health Check
```http
GET http://localhost:7079/health
```

### Text-to-Speech
```http
POST http://localhost:7079/api/v1/speak
Content-Type: application/json

{
  "text": "Hello, this is a test",
  "voice": "en_US-lessac-medium"
}
```

**Response:**
```json
{
  "audio": "base64encoded...",
  "format": "wav",
  "duration_ms": 2000
}
```

### Speech-to-Text
```http
POST http://localhost:7079/api/v1/transcribe
Content-Type: application/json

{
  "audio": "base64encoded...",
  "language": "en"
}
```

**Response:**
```json
{
  "text": "Hello world",
  "language": "en"
}
```

### WebSocket Streaming
```
ws://localhost:7079/ws/voice
```

Send binary audio chunks, receive binary TTS audio.

---

## Desktop Automation (desktopd) API

### Health Check
```http
GET http://localhost:7080/health
```

### Take Screenshot
```http
POST http://localhost:7080/api/v1/screenshot
Content-Type: application/json

{
  "region": [100, 100, 800, 600]  // Optional: x, y, w, h
}
```

**Response:** PNG image data

### Execute Action
```http
POST http://localhost:7080/api/v1/action
Content-Type: application/json

{
  "type": "click",
  "x": 500,
  "y": 300,
  "button": "left"
}
```

**Action Types:**
- `click` - Mouse click
- `double_click` - Double click
- `right_click` - Right click
- `drag` - Drag to position
- `scroll` - Scroll wheel
- `type` - Type text
- `hotkey` - Press key combination
- `screenshot` - Take screenshot
- `clipboard_get` - Get clipboard
- `clipboard_set` - Set clipboard
- `get_cursor_pos` - Get mouse position
- `move_to` - Move mouse

### Execute Complex Task
```http
POST http://localhost:7080/api/v1/task
Content-Type: application/json

{
  "instruction": "Open calculator and calculate 2+2",
  "max_steps": 20
}
```

### Get Cursor Position
```http
GET http://localhost:7080/api/v1/cursor
```

### Get Screen Info
```http
GET http://localhost:7080/api/v1/screen
```

---

## Multi-Agent Framework (agentd_v2) API

### Health Check
```http
GET http://localhost:7081/health
```

### Create Agent
```http
POST http://localhost:7081/api/v2/agents
Content-Type: application/json

{
  "name": "Researcher",
  "role": "researcher",
  "goal": "Find accurate information",
  "backstory": "Expert researcher with web access",
  "allow_delegation": true,
  "tools": ["web_search", "browser"]
}
```

### List Agents
```http
GET http://localhost:7081/api/v2/agents
```

### Create Crew
```http
POST http://localhost:7081/api/v2/crews
Content-Type: application/json

{
  "name": "Research Team",
  "description": "Team for research tasks",
  "agent_ids": ["agent-1", "agent-2"],
  "process_type": "sequential"  // or "hierarchical", "parallel"
}
```

### Create Task
```http
POST http://localhost:7081/api/v2/tasks
Content-Type: application/json

{
  "description": "Research ClawOS competitors",
  "expected_output": "List of 10 competitors",
  "agent_id": "agent-1",
  "context": {"topic": "AI operating systems"}
}
```

### Execute Crew
```http
POST http://localhost:7081/api/v2/crews/{crew_id}/execute
```

### List Roles
```http
GET http://localhost:7081/api/v2/roles
```

---

## CLI Commands

### MCP Client
```bash
# Initialize MCP configuration
clawctl mcp init

# List configured servers
clawctl mcp list

# Add new server
clawctl mcp add filesystem --stdio "npx -y @modelcontextprotocol/server-filesystem /home/user"

# Test connection
clawctl mcp test filesystem

# Discover available servers
clawctl mcp discover

# Run MCP demo
clawctl mcp demo
```

### MCP Server
```bash
# Start MCP server
clawctl mcpd start

# Stop MCP server
clawctl mcpd stop

# Get server info
clawctl mcpd info

# Check status
clawctl mcpd status
```

### Observability
```bash
# Check service status
clawctl observ status

# View recent LLM calls
clawctl observ calls --hours 24

# Get aggregate statistics
clawctl observ stats --days 7

# Cost analysis
clawctl observ cost --days 7

# Latency analysis
clawctl observ latency --days 7

# List workspaces
clawctl observ workspaces

# Export data
clawctl observ export --format csv --output usage.csv
```

### Durable Workflows
```bash
# List workflow runs
clawctl durable runs

# Show run details
clawctl durable show <run_id>

# Resume failed workflow
clawctl durable resume <run_id>

# Cancel running workflow
clawctl durable cancel <run_id>

# Get statistics
clawctl durable stats

# Cleanup old runs
clawctl durable cleanup --days 30
```

### Code Companion
```bash
# Index a codebase
clawctl code index ~/my-project --workspace myproject

# Search code
clawctl code search "authentication middleware"

# Review code
clawctl code review src/app.py

# Generate tests
clawctl code test UserService --file src/services.py

# Explain symbol
clawctl code explain UserService --file src/models.py --line 45

# Check index status
clawctl code status
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAWOS_DIR` | `~/.clawos` | Data directory |
| `CLAWOS_CONFIG` | `~/.config/clawos/config.yml` | Config file |
| `CLAWOS_LOG_LEVEL` | `INFO` | Logging level |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama endpoint |

---

## Response Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad Request |
| 403 | Forbidden |
| 404 | Not Found |
| 429 | Rate Limited |
| 500 | Internal Error |
| 503 | Service Unavailable |

---

## Authentication

Currently, ClawOS services run on localhost without authentication.
For production deployment:

1. Enable API keys via `clawctl config set security.api_keys true`
2. Set key via `CLAWOS_API_KEY` environment variable
3. Include key in header: `X-API-Key: your-key-here`

---

## Rate Limiting

Default limits:
- 100 requests per minute per IP
- 1000 requests per hour per IP

Configure via config:
```yaml
security:
  rate_limit:
    requests_per_minute: 100
    requests_per_hour: 1000
```

---

**Version:** ClawOS 0.1.1  
**Last Updated:** April 30, 2026
