# ClawOS CLI Reference

> Complete reference for all `clawctl` commands. For setup help, see the [Installation Guide](INSTALL_URL_SETUP.md).

---

## Global Usage

```bash
clawctl <command> [subcommand] [options] [arguments]
```

---

## Service Management

### `clawctl status`

Show health status of all services.

```bash
clawctl status
```

### `clawctl health`

Alias for `status` — show the service health dashboard.

### `clawctl start [SERVICE]`

Start all services, or one named service.

| Flag | Description |
|:-----|:------------|
| `--dev` | Dev mode (no systemd/launchd) |

```bash
clawctl start            # start all services
clawctl start dashd      # start just the dashboard
clawctl start --dev      # dev mode
```

### `clawctl stop [SERVICE]`

Stop all services, or one named service.

```bash
clawctl stop
clawctl stop agentd
```

### `clawctl restart [SERVICE]`

Restart all services, or one named service.

```bash
clawctl restart
clawctl restart memd
```

### `clawctl logs [SERVICE]`

Tail service logs.

| Flag | Description |
|:-----|:------------|
| `-f`, `--follow` | Follow log output (tail) |
| `-n`, `--lines` | Number of lines to show (default: 40) |

```bash
clawctl logs                  # all services
clawctl logs agentd -f        # follow agentd logs
clawctl logs dashd -n 100     # last 100 lines
```

### `clawctl doctor`

Diagnose ClawOS issues.

| Flag | Description |
|:-----|:------------|
| `--fix` | Auto-fix safe issues |

```bash
clawctl doctor
clawctl doctor --fix
```

### `clawctl verify`

Post-install smoke test — verify ClawOS is ready to use.

```bash
clawctl verify
```

---

## Model Management

### `clawctl model list`

List installed Ollama models.

### `clawctl model pull <NAME>`

Pull a model from Ollama registry.

```bash
clawctl model pull qwen2.5:7b
```

### `clawctl model remove <NAME>`

Remove an installed model.

```bash
clawctl model remove qwen2.5:3b
```

### `clawctl model default <NAME>`

Set the default model.

```bash
clawctl model default qwen2.5:7b
```

---

## Workspace Management

### `clawctl workspace list`

List all workspaces.

### `clawctl workspace create <NAME>`

Create a new workspace.

```bash
clawctl workspace create project-alpha
```

### `clawctl workspace delete <NAME>`

Delete a workspace.

```bash
clawctl workspace delete old-project
```

---

## Voice Pipeline

### `clawctl voice status`

Check voice dependencies and status.

### `clawctl voice enable`

Enable voice input (push-to-talk mode).

### `clawctl voice disable`

Disable voice input.

### `clawctl voice test`

Test TTS output.

### `clawctl voice mode [MODE]`

Set or show voice mode.

---

## Workflows

### `clawctl wf list`

List all built-in workflows.

| Flag | Description |
|:-----|:------------|
| `-c`, `--category` | Filter by category |
| `-s`, `--search` | Search workflow names |

```bash
clawctl wf list
clawctl wf list --category productivity
clawctl wf list --search pdf
```

### `clawctl wf info <ID>`

Show details for a single workflow.

```bash
clawctl wf info summarize_pdf
```

### `clawctl wf run <ID> [KEY=VALUE...]`

Run a workflow with arguments.

| Flag | Description |
|:-----|:------------|
| `-w`, `--workspace` | Target workspace |
| `--dry-run` | Preview without executing |

```bash
clawctl wf run summarize_pdf input=/path/to/file.pdf
clawctl wf run batch_summarize dir=/docs --dry-run
```

---

## Durable Workflows

### `clawctl durable runs`

List workflow runs with checkpoint/resume support.

| Flag | Description |
|:-----|:------------|
| `-w`, `--workflow` | Filter by workflow |
| `-s`, `--status` | Filter by status |
| `-l`, `--limit` | Max results |
| `--json` | JSON output |

### `clawctl durable show <RUN_ID>`

Show run details.

| Flag | Description |
|:-----|:------------|
| `--json` | JSON output |

### `clawctl durable resume <RUN_ID>`

Resume a failed/paused workflow run.

### `clawctl durable cancel <RUN_ID>`

Cancel a running workflow.

### `clawctl durable stats`

Show workflow statistics.

| Flag | Description |
|:-----|:------------|
| `--json` | JSON output |

### `clawctl durable cleanup`

Clean up old workflow runs.

| Flag | Description |
|:-----|:------------|
| `-d`, `--days` | Remove runs older than N days |
| `--yes` | Skip confirmation |

---

## Project & RAG

### `clawctl project upload <FILEPATH>`

Ingest a document into RAG (pdf, txt, md, docx).

| Flag | Description |
|:-----|:------------|
| `--workspace` | Target workspace (default: nexus_default) |

```bash
clawctl project upload report.pdf
clawctl project upload data.docx --workspace project-alpha
```

### `clawctl project list`

List indexed documents.

| Flag | Description |
|:-----|:------------|
| `--workspace` | Target workspace |

### `clawctl project query <QUESTION>`

Query indexed documents with citations.

| Flag | Description |
|:-----|:------------|
| `--workspace` | Target workspace |

```bash
clawctl project query "What are the key findings?"
```

### `clawctl project stats`

Show RAG index stats.

| Flag | Description |
|:-----|:------------|
| `--workspace` | Target workspace |

---

## Skills

### `clawctl skill search [QUERY]`

Search ClawHub for skills.

| Flag | Description |
|:-----|:------------|
| `--page` | Page number |

```bash
clawctl skill search
clawctl skill search "web scraper"
```

### `clawctl skill install <SKILL_ID>`

Install a skill from ClawHub.

| Flag | Description |
|:-----|:------------|
| `--force` | Reinstall if already installed |
| `--no-community` | Reject community (unverified) skills |

### `clawctl skill remove <SKILL_ID>`

Remove an installed skill.

### `clawctl skill list`

List installed skills.

### `clawctl skill verify <SKILL_PATH>`

Verify Ed25519 signature of a local skill directory.

### `clawctl skill local <SKILL_PATH>`

Install skill from local path (dev mode).

| Flag | Description |
|:-----|:------------|
| `--id` | Override skill ID |

### `clawctl skill sign <SKILL_PATH>`

Sign a skill with Ed25519 (requires `CLAWOS_SIGN_KEY` env var).

---

## Packs

### `clawctl packs list`

List first-party ClawOS packs.

### `clawctl packs install <PACK_ID>`

Install a pack.

| Flag | Description |
|:-----|:------------|
| `--primary` | Set as primary pack |
| `--provider` | Bind to a provider profile |

```bash
clawctl packs install default --primary
```

---

## Providers

### `clawctl providers list`

List provider profiles.

### `clawctl providers test <PROFILE_ID>`

Test a provider profile.

### `clawctl providers switch <PROFILE_ID>`

Switch active provider profile.

---

## Frameworks

### `clawctl framework list`

List all available frameworks with install status.

### `clawctl framework install <NAME>`

Install a framework from the Framework Store.

```bash
clawctl framework install openclaw
```

### `clawctl framework remove <NAME>`

Remove an installed framework.

### `clawctl framework start <NAME>`

Start an installed framework's service.

### `clawctl framework stop <NAME>`

Stop a running framework.

### `clawctl framework use <NAME>`

Set the active framework for agent routing.

### `clawctl framework status`

Show status of all installed frameworks.

---

## Extensions

### `clawctl extensions list`

List trusted ClawOS extensions.

### `clawctl extensions install <EXTENSION_ID>`

Install a trusted extension.

---

## A2A (Agent-to-Agent)

### `clawctl a2a peers`

List discovered ClawOS nodes on LAN.

### `clawctl a2a card`

Print this node's Agent Card JSON.

### `clawctl a2a delegate <TASK>`

Delegate a task to a remote ClawOS node.

| Flag | Description |
|:-----|:------------|
| `--peer` | Peer IP address (required) |
| `--workspace` | Target workspace |

```bash
clawctl a2a delegate "Summarize these logs" --peer 192.168.1.42
```

### `clawctl a2a status`

Check a2ad service status.

---

## MCP (Model Context Protocol)

### `clawctl mcp init`

Create default MCP configuration.

### `clawctl mcp list`

List configured MCP servers.

### `clawctl mcp add <NAME>`

Add an MCP server.

| Flag | Description |
|:-----|:------------|
| `--stdio` | Use stdio transport |
| `--http` | Use HTTP transport |
| `--env` | Environment variables |

### `clawctl mcp remove <NAME>`

Remove an MCP server.

### `clawctl mcp test <NAME>`

Test connection to an MCP server.

### `clawctl mcp discover`

Discover available MCP servers.

### `clawctl mcp template <TEMPLATE_NAME>`

Show MCP server templates.

---

## MCP Server (expose ClawOS to external AI)

### `clawctl mcpd status`

Check MCP server status.

### `clawctl mcpd start`

Start the MCP server.

### `clawctl mcpd stop`

Stop the MCP server.

### `clawctl mcpd info`

Show MCP server capabilities.

### `clawctl mcpd test`

Test MCP server with sample request.

| Flag | Description |
|:-----|:------------|
| `--tool` | Test a specific tool |

### `clawctl mcpd clients`

Show connection instructions for MCP clients.

---

## Observability

### `clawctl observ status`

Check observability service status.

### `clawctl observ calls`

Show recent LLM calls.

| Flag | Description |
|:-----|:------------|
| `-w`, `--workspace` | Filter by workspace |
| `-s`, `--service` | Filter by service |
| `-m`, `--model` | Filter by model |
| `-h`, `--hours` | Look back N hours |
| `-l`, `--limit` | Max results |
| `--json` | JSON output |

### `clawctl observ stats`

Show aggregate statistics.

| Flag | Description |
|:-----|:------------|
| `-w`, `--workspace` | Filter by workspace |
| `-h`, `--hours` | Look back N hours |
| `--json` | JSON output |

### `clawctl observ cost`

Show cost breakdown.

| Flag | Description |
|:-----|:------------|
| `-w`, `--workspace` | Filter by workspace |
| `-d`, `--days` | Look back N days |

### `clawctl observ latency`

Show latency analysis.

| Flag | Description |
|:-----|:------------|
| `-w`, `--workspace` | Filter by workspace |
| `-h`, `--hours` | Look back N hours |

### `clawctl observ workspaces`

List workspaces with activity.

### `clawctl observ export`

Export observability data.

| Flag | Description |
|:-----|:------------|
| `--format` | Output format |
| `-o`, `--output` | Output file |
| `-h`, `--hours` | Look back N hours |
| `-w`, `--workspace` | Filter by workspace |

---

## Code Companion

### `clawctl code index <PATH>`

Index a codebase for semantic search.

| Flag | Description |
|:-----|:------------|
| `-w`, `--workspace` | Target workspace |
| `-v`, `--verbose` | Verbose output |

### `clawctl code search <QUERY>`

Search codebase using semantic search.

| Flag | Description |
|:-----|:------------|
| `-w`, `--workspace` | Target workspace |
| `-l`, `--limit` | Max results |
| `--json` | JSON output |

### `clawctl code explain <LOCATION>`

Explain code at a location (file:line format).

| Flag | Description |
|:-----|:------------|
| `-w`, `--workspace` | Target workspace |

```bash
clawctl code explain services/memd/service.py:42
```

### `clawctl code review <FILE_PATH>`

Review code for issues.

| Flag | Description |
|:-----|:------------|
| `--json` | JSON output |

### `clawctl code test <SYMBOL>`

Generate test cases for a symbol.

| Flag | Description |
|:-----|:------------|
| `-f`, `--file` | Source file |
| `-w`, `--workspace` | Target workspace |

### `clawctl code status`

Show code companion status.

| Flag | Description |
|:-----|:------------|
| `-w`, `--workspace` | Target workspace |

---

## Second Brain

### `clawctl brain entity <NAME>`

Create a knowledge entity.

| Flag | Description |
|:-----|:------------|
| `--type` | Entity type |
| `-d`, `--description` | Description |

### `clawctl brain search <QUERY>`

Search the knowledge base.

| Flag | Description |
|:-----|:------------|
| `-t`, `--tags` | Filter by tags |
| `-l`, `--limit` | Max results |

### `clawctl brain timeline`

View knowledge timeline.

| Flag | Description |
|:-----|:------------|
| `--start` | Start date |
| `--end` | End date |
| `--entity` | Filter by entity |

### `clawctl brain insights`

Show discovered insights.

---

## Sandbox

### `clawctl sandbox create`

Create a new sandbox.

| Flag | Description |
|:-----|:------------|
| `-l`, `--language` | Programming language |
| `-t`, `--timeout` | Timeout in seconds |
| `-m`, `--memory` | Memory limit |
| `--network` / `--no-network` | Network access |

### `clawctl sandbox execute <SANDBOX_ID> <CODE_FILE>`

Execute code in a sandbox.

### `clawctl sandbox list`

List active sandboxes.

### `clawctl sandbox destroy <SANDBOX_ID>`

Destroy a sandbox.

---

## Notebooks

### `clawctl notebook new <NAME>`

Create a new devops notebook.

### `clawctl notebook run <NOTEBOOK_FILE>`

Execute a notebook.

### `clawctl notebook export <NOTEBOOK_FILE>`

Export notebook to a script.

| Flag | Description |
|:-----|:------------|
| `-f`, `--format` | Output format |

---

## ACE (Self-Improving Loop)

### `clawctl ace status`

Show LEARNED.md size, entry count, last write timestamp.

| Flag | Description |
|:-----|:------------|
| `--workspace` | Target workspace |

### `clawctl ace show`

Print current LEARNED.md content.

| Flag | Description |
|:-----|:------------|
| `--workspace` | Target workspace |

### `clawctl ace clear`

Truncate LEARNED.md (irreversible).

| Flag | Description |
|:-----|:------------|
| `--workspace` | Target workspace |
| `--yes` | Skip confirmation |

### `clawctl ace pause`

Stop writing new entries to LEARNED.md.

| Flag | Description |
|:-----|:------------|
| `--workspace` | Target workspace |

### `clawctl ace resume`

Resume writing entries to LEARNED.md.

| Flag | Description |
|:-----|:------------|
| `--workspace` | Target workspace |

---

## OMI Integration (BasedHardware)

### `clawctl omi status`

Show webhook URL, last event, conversation count.

### `clawctl omi history`

List recent OMI conversations.

| Flag | Description |
|:-----|:------------|
| `-n`, `--limit` | Max conversations |

### `clawctl omi show <CONV_ID>`

Show full conversation detail.

### `clawctl omi setup`

Print webhook URLs to paste into OMI app settings.

---

## Visual Workflows

### `clawctl visual create <NAME>`

Create a visual workflow.

### `clawctl visual open`

Open visual workflow editor.

### `clawctl visual run <WORKFLOW_ID>`

Execute a visual workflow.

---

## License

### `clawctl license activate <KEY>`

Activate a license key (format: `CLAW-XXXX-XXXX-XXXX-XXXX`).

### `clawctl license status`

Show current license status.

### `clawctl license deactivate`

Deactivate license on this machine.

---

## Other Commands

### `clawctl benchmark`

Show pack eval readiness and trace availability.

### `clawctl briefing`

Generate the current Nexus briefing.

### `clawctl budget`

Show per-workspace token usage.

### `clawctl dashboard show`

Show service dashboard.

| Flag | Description |
|:-----|:------------|
| `-w`, `--watch` | Auto-refresh |
| `-i`, `--interval` | Refresh interval (seconds) |

### `clawctl dashboard logs <SERVICE>`

Show logs for a service.

| Flag | Description |
|:-----|:------------|
| `-n`, `--lines` | Number of lines |

### `clawctl mission list`

List Nexus missions.

### `clawctl mission start <TITLE>`

Start a new mission.

| Flag | Description |
|:-----|:------------|
| `--summary` | Mission summary |

### `clawctl presence show`

Show Nexus presence and autonomy state.

### `clawctl wizard`

Open the browser-based first-run setup wizard.

| Flag | Description |
|:-----|:------------|
| `--reset` | Clear persisted wizard state |

### `clawctl chat [WORKSPACE]`

Start an interactive Nexus session (default workspace: `nexus_default`).

```bash
clawctl chat
clawctl chat project-alpha
```

### `clawctl rescue openclaw`

Import OpenClaw configuration into ClawOS.

| Flag | Description |
|:-----|:------------|
| `--path` | OpenClaw home directory path |

---

## Demos

### `clawctl demos morning-briefing`

Trigger the morning briefing (Demo 1).

| Flag | Description |
|:-----|:------------|
| `--voice` / `--text` | Output mode (default: voice) |

### `clawctl demos essay-editor`

Grammar check and rewrite text (Demo 2).

| Flag | Description |
|:-----|:------------|
| `--style` | Style: formal, casual, academic, concise, engaging |
| `--text` | Input text (prompts if omitted) |
| `--skip-grammar` | Skip grammar check |

### `clawctl demos approval-test`

Test the approval popup system (Demo 3).

---

## See Also

- [Architecture Diagram](ARCHITECTURE_DIAGRAM.md)
- [Architecture Guide](ARCHITECTURE.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [Testing Guide](TESTING_GUIDE.md)