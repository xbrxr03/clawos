# ClawOS

> ClawOS is what you get when Apple builds JARVIS for everyone: a local-first AI operating environment that runs on your hardware, works offline, and costs nothing.
>
> [![License: AGPL v3+](https://img.shields.io/badge/License-AGPL%20v3%2B-1f6feb.svg)](LICENSE)

```bash
curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh -o /tmp/clawos.sh && bash /tmp/clawos.sh
```

In ~4 minutes you have the ClawOS command center and the OpenClaw ecosystem running locally - offline, private, and free.

Current release status:

- `0.1.0` is the active release target.
- Linux host installs are the most battle-tested path today.
- macOS 14+ on Apple Silicon is supported through the Homebrew + `launchd` path.
- `.deb` packaging exists in-repo.
- The ISO path exists in-repo but still needs final Linux-host and real-hardware validation before it is treated as release-ready.

For the product north star and quality bar, see [docs/PRODUCT_VISION.md](docs/PRODUCT_VISION.md). For the release plan, see [docs/ROADMAP.md](docs/ROADMAP.md).

---

## What ClawOS is (and isn't)

ClawOS is a **local-first AI command center and install surface** for Ubuntu/Debian and macOS 14+ machines. OpenClaw remains the primary migration wedge, but ClawOS now also includes pack-first setup, provider profiles, trusted extensions, local traces, and guided setup. Linux is still the most battle-tested path; macOS support now uses Homebrew plus `launchd` and is documented in [docs/MACOS.md](docs/MACOS.md). Production deployment notes live in [docs/PRODUCTION.md](docs/PRODUCTION.md), the repo verification path lives in [docs/VERIFICATION.md](docs/VERIFICATION.md), and the competitive-platform roadmap now lives in [docs/COMPETITIVE_PLATFORM.md](docs/COMPETITIVE_PLATFORM.md).

A dedicated security-audit path now lives in [docs/SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md).

The end goal is a **bootable ISO** - flash a USB, boot, your AI is ready. That's the last stage on the roadmap. We're building in public and shipping working software at each stage instead of waiting until it's perfect.

If you want to follow along or contribute: [github.com/xbrxr03/clawos](https://github.com/xbrxr03/clawos)

---

## Why this exists

OpenClaw hit 280,000 GitHub stars in six weeks. Most people who tried it gave up.

The setup takes hours. It requires API keys. It costs $300-750/month in tokens. The creator left for OpenAI in February. CVE-2026-25253 lets anyone steal your keys in one click. Cisco found that 17% of ClawHub skills are malicious.

ClawOS fixes all of that. It runs OpenClaw on your hardware, with your models, for the cost of electricity. No monthly bill. No API keys. No cloud dependency.

---

## What you get

After one command:

- **OpenClaw** — pre-configured for offline Ollama, no API keys required
- **Ollama** — local model runtime, right model for your hardware auto-selected
- **Nexus** — native Python agent with memory, voice, browser control, and 29 workflows
- **Pack-first setup** — Daily Briefing OS, Sales Operator, Chat-App Command Center, or Coding Autopilot
- **MCP Manager** — visual UI to connect any Model Context Protocol server (local or remote)
- **A2A Federation** — Agent-to-Agent protocol to link multiple ClawOS instances on your network
- **Nexus Brain** — 3D knowledge graph: drop a ZIP of notes, watch your personal knowledge base build itself
- **Proactive ambient intelligence** — ClawOS notices things and tells you ("82% disk full", "brain found new connection")
- **Skill Marketplace** — Ed25519-signed skills; unsigned packages cannot install
- **Provider control plane** — switch between Ollama, OpenRouter, Anthropic API, Azure/OpenAI
- **WhatsApp bridge** — text your AI from your phone, approve sensitive actions by reply
- **policyd** — every tool call gated, audited, and logged before it runs; human approval queue for sensitive ops
- **Dashboard** — 17-page React UI: tasks, approvals, models, memory, audit log, workflows, brain graph, MCP
- **29 one-command workflows** — organize downloads, summarize PDFs, review PRs, disk reports, daily digest, and more

```
$ clawos

you > what can you do?
nexus > I can read and write files, search the web, remember things
         across sessions, and run tools on this machine. Everything
         runs locally - nothing leaves this computer.

you > create a file called notes.txt with my meeting agenda
nexus > Created notes.txt in your workspace.
```

Or run any of the 29 built-in workflows from the terminal:

```bash
nexus workflow list                        # browse all 29 workflows
nexus workflow run organize-downloads      # sort your Downloads folder
nexus workflow run summarize-pdf           # summarize a PDF
nexus workflow run disk-report             # see what's eating your disk
nexus workflow suggest developer           # get suggestions based on your setup
```

Or use the dashboard - navigate to the Workflows tab, pick one, click Run.

You can also inspect the new competitive-platform surfaces directly:

```bash
clawctl packs list
clawctl providers list
clawctl extensions list
clawctl rescue openclaw
clawctl benchmark
```

And in the Command Center:

- **Packs** - install first-party outcome bundles and set your primary pack
- **Providers** - test and switch model/runtime profiles
- **Registry** - review trusted extensions and their permission posture
- **Traces** - inspect local run timelines, outcomes, and pack activity

---

## Requirements

- Ubuntu 24.04, Debian 12, Raspberry Pi OS, or macOS 14+ (Apple Silicon first, Intel best-effort)
- 8GB RAM minimum
- 10GB free disk space
- Internet on first run only (pulls models, then fully offline)

The installer automatically detects your hardware and picks the right model:

| Hardware | RAM | Tier | Model | Speed |
|----------|-----|------|-------|-------|
| Raspberry Pi 5 / ARM | 8GB | A | `gemma3:4b` | ~3-5 tok/s CPU |
| x86 laptop / mini PC | 8-16GB | B | `gemma3:4b` | ~8-20 tok/s CPU |
| x86 workstation with GPU | 16-32GB | C | `qwen2.5:7b` | ~40-80 tok/s GPU |
| Gaming rig / workstation | 32GB+ + GPU | D | `qwen2.5:7b` | ~80+ tok/s GPU |

`gemma3:4b` is the best CPU-only model at 3.3GB — runs comfortably on 8GB RAM with no GPU required. GPU optional (NVIDIA CUDA and AMD ROCm both supported via Ollama).

---

## Raspberry Pi 5 / ARM

ClawOS works on RPi 5 8GB. The installer detects ARM and pulls `gemma3:4b` automatically - no configuration needed.

```bash
curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh -o /tmp/clawos.sh && bash /tmp/clawos.sh
```

Expected response time: 2-4 seconds for short answers on RPi 5.

---

## Using a Remote Ollama Server

If you have a more powerful machine running Ollama on your local network, you can point ClawOS at it instead of running inference locally. Useful for low-power devices like the RPi 5.

**On the powerful machine** - make Ollama listen on the network:
```bash
OLLAMA_HOST=0.0.0.0 ollama serve
# Pull the models ClawOS needs:
ollama pull gemma3:4b          # for CPU-only / 8-16GB RAM machines
ollama pull qwen2.5:7b         # for GPU-equipped machines (16GB+)
ollama pull nomic-embed-text
```

**On the ClawOS machine** - set the host before installing or running:
```bash
export OLLAMA_HOST=http://192.168.1.50:11434   # replace with your server IP
curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh -o /tmp/clawos.sh && bash /tmp/clawos.sh
```

To make it permanent:
```bash
echo 'export OLLAMA_HOST=http://192.168.1.50:11434' >> ~/.bashrc
source ~/.bashrc
```

ClawOS will use the remote server for all inference - the local machine only runs the agent runtime, dashboard, and memory services.

---

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh -o /tmp/clawos.sh && bash /tmp/clawos.sh
```

Handles everything: Ollama, Node.js, Python dependencies, model download, OpenClaw configuration, and the `clawos` command. No prompts. No choices. Just works.

> **Why not `curl | bash`?** Piping directly kills the TTY so interactive steps (Ollama login, first-run wizard, OpenClaw TUI launch) are silently skipped. The two-step command above keeps stdin attached.

On macOS, the installer uses Homebrew for core dependencies and installs per-user `launchd` agents for ClawOS and Ollama. The target path is macOS 14+ on Apple Silicon; see [docs/MACOS.md](docs/MACOS.md) for current scope and verification steps.

**After install:**

```bash
# Start Nexus (native agent)
clawos

# Start OpenClaw gateway (for WhatsApp + full skill ecosystem)
openclaw gateway --allow-unconfigured
```

---

## Connect WhatsApp

```bash
openclaw gateway --allow-unconfigured
```

Scan the QR code with WhatsApp on your phone. Text your AI from anywhere.

---

## Why Ollama

We use Ollama because it has the best out-of-the-box experience for consumer hardware - one command to pull and run any model, automatic GPU detection, and a clean API. For single-user local inference on 8-32GB machines it's the right tool.

If you're running a multi-user server deployment, `vllm` or `llama.cpp` with a custom server are valid alternatives. Ollama support in ClawOS doesn't prevent you from pointing the model endpoint elsewhere - it's just the default that works for most people on first install.

---

## How it works

```
You (Terminal / WhatsApp / Voice)
         |
      agentd   <-- task queue + session manager
         |
      Ollama   <-- local inference, no cloud, no API keys
         |
     policyd   <-- every tool call checked before it runs
         |
   toolbridge  <-- files, web, shell, memory
         |
       memd    <-- 4-layer memory: PINNED + WORKFLOW + ChromaDB + FTS5
```

Every action goes through `policyd`. Sensitive operations pause for your approval. Nothing talks to the internet unless you explicitly allow it. A tamper-evident Merkle-chained audit log records every action taken on your machine.

---

## Security

ClawOS meets 6 of 7 enterprise security requirements. No other open-source agent project meets more than 3.

| Requirement | Status |
|-------------|--------|
| Agent-level RBAC with scoped permissions | Yes |
| Runtime permission check before every tool call | Yes |
| Immutable Merkle-chained audit trail | Yes |
| Human-in-loop approval for sensitive actions | Yes |
| Kill switch - terminate agent actions in real time | Yes |
| Credential isolation - no API keys in agent context | Yes |

---

## Build from source

```bash
git clone https://github.com/xbrxr03/clawos
cd clawos
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[full]"
python3 -m bootstrap.bootstrap
clawos
```

Or use the pre-flight check to see what the installer will do on your machine before committing:

```bash
bash install.sh --check
```

---

## Roadmap

Linux remains the most battle-tested install path. macOS now uses Homebrew + `launchd`; the primary target is macOS 14+ on Apple Silicon, with Intel as best-effort.

- [x] Core runtime — policyd, memd, toolbridge, agentd, modeld, voiced, metricd
- [x] Voice pipeline — Whisper STT + Piper TTS + wake word detection
- [x] One-command installer — Ubuntu, Debian, macOS, `--check` pre-flight mode
- [x] OpenClaw offline + WhatsApp bridge with approval-by-reply
- [x] Dashboard — 17-page React UI, WebSocket real-time updates, dark mode
- [x] systemd / launchd service management
- [x] First-run setup wizard — hardware profiling, model selection, API key vault
- [x] nexus CLI — 12 commands, RAG pipeline, project upload/query
- [x] Key vault — secretd, per-service credential isolation
- [x] OpenRouter support — cloud models as fallback
- [x] 29 offline workflows — files, documents, developer, content, system, data categories
- [x] Capability discovery — auto-suggests workflows based on your setup
- [x] MCP Manager — connect any Model Context Protocol server, visual UI
- [x] A2A Federation — Agent-to-Agent protocol, multi-instance networking
- [x] Nexus Brain — 3D knowledge graph, ZIP ingestion, GraphRAG retrieval
- [x] Proactive ambient intelligence — suggestions feed, morning briefing push
- [x] Skill Marketplace — Ed25519 signing, sandbox, trust tiers
- [x] Browser control — Playwright-backed headless browser tools for the agent
- [x] PWA — installable as app on desktop and mobile
- [ ] **Bootable ISO** — flash and boot, no install needed (v0.1.1)

---

## vs. everything else

macOS support in ClawOS now means the Homebrew + `launchd` path described in [docs/MACOS.md](docs/MACOS.md). Apple Silicon is the primary target today.

| | OpenClaw | Leon | khoj | Open WebUI | ClawOS |
|---|---|---|---|---|---|
| One-command install | No | No | No | Partial | **Yes** |
| Fully offline, no API keys | No | No | No | Yes | **Yes** |
| Dashboard UI (17 pages) | No | No | No | Yes | **Yes** |
| 29 built-in workflows | No | Partial | No | No | **Yes** |
| MCP Manager (visual UI) | No | No | No | Partial | **Yes** |
| Agent-to-Agent federation | No | No | No | No | **Yes** |
| 3D knowledge brain | No | No | No | No | **Yes** |
| Proactive ambient alerts | No | No | No | No | **Yes** |
| Signed skill marketplace | Unsafe | No | No | No | **Yes** |
| Human approval queue | No | No | No | No | **Yes** |
| WhatsApp bridge | Yes | No | No | No | **Yes** |
| Voice pipeline (offline) | No | Partial | No | No | **Yes** |
| Zero monthly cost | No | Yes | Partial | Yes | **Yes** |

---

## License

ClawOS is licensed under the GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later). See [LICENSE](LICENSE) for the full text.

ClawOS is not affiliated with OpenClaw or Anthropic. OpenClaw and Ollama remain MIT-licensed upstream projects.

---

*Built for people who wanted OpenClaw to work. [github.com/xbrxr03/clawos](https://github.com/xbrxr03/clawos)*

