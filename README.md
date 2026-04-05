# ClawOS

> OpenClaw on your own hardware. One command. No API keys. No monthly bill.

```bash
curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh -o /tmp/clawos.sh && bash /tmp/clawos.sh
```

In ~4 minutes you have the full OpenClaw ecosystem running locally — offline, private, and free.

---

## What ClawOS is (and isn't)

ClawOS is currently a **one-command installer** that turns Ubuntu/Debian and macOS 14+ machines into a working OpenClaw environment. Linux is still the most battle-tested path; macOS support now uses Homebrew plus `launchd` and is documented in [docs/MACOS.md](docs/MACOS.md).

The end goal is a **bootable ISO** — flash a USB, boot, your AI is ready. That's the last stage on the roadmap. We're building in public and shipping working software at each stage instead of waiting until it's perfect.

If you want to follow along or contribute: [github.com/xbrxr03/clawos](https://github.com/xbrxr03/clawos)

---

## Why this exists

OpenClaw hit 280,000 GitHub stars in six weeks. Most people who tried it gave up.

The setup takes hours. It requires API keys. It costs $300–750/month in tokens. The creator left for OpenAI in February. CVE-2026-25253 lets anyone steal your keys in one click. Cisco found that 17% of ClawHub skills are malicious.

ClawOS fixes all of that. It runs OpenClaw on your hardware, with your models, for the cost of electricity.

---

## What you get

After one command:

- **OpenClaw** — pre-configured for offline Ollama, no API keys required
- **Ollama** — local model runtime, right model for your hardware pulled automatically
- **Nexus** — native Python agent with memory, tools, and voice
- **29 one-command workflows** — organize downloads, summarize PDFs, review PRs, disk reports, daily digest, and more — all offline
- **WhatsApp bridge** — text your AI from your phone
- **policyd** — every tool call gated and audited before it runs
- **Dashboard** — web UI showing tasks, approvals, models, memory, audit log, and workflows
- **Full OpenClaw ecosystem** — 13,700+ skills and more to come

```
$ clawos

you › what can you do?
nexus › I can read and write files, search the web, remember things
         across sessions, and run tools on this machine. Everything
         runs locally — nothing leaves this computer.

you › create a file called notes.txt with my meeting agenda
nexus › Created notes.txt in your workspace.
```

Or run any of the 29 built-in workflows from the terminal:

```bash
nexus workflow list                        # browse all 29 workflows
nexus workflow run organize-downloads      # sort your Downloads folder
nexus workflow run summarize-pdf           # summarize a PDF
nexus workflow run disk-report             # see what's eating your disk
nexus workflow suggest developer           # get suggestions based on your setup
```

Or use the dashboard — navigate to the Workflows tab, pick one, click Run.

---

## Requirements

- Ubuntu 24.04, Debian 12, Raspberry Pi OS, or macOS 14+ (Apple Silicon first, Intel best-effort)
- 8GB RAM minimum
- 10GB free disk space
- Internet on first run only (pulls models, then fully offline)

The installer automatically detects your hardware and picks the right model:

| Hardware | RAM | Model | Speed |
|----------|-----|-------|-------|
| Raspberry Pi 5, ARM devices | 8GB | `qwen2.5:1.5b` | ~3–5 tok/s on CPU |
| x86 laptop / mini PC | 8–16GB | `qwen2.5:3b` | ~8–15 tok/s |
| x86 workstation with GPU | 16GB+ | `qwen2.5:7b` | ~40–80 tok/s GPU |

GPU optional. NVIDIA (CUDA) and AMD (ROCm) both supported via Ollama.

---

## Raspberry Pi 5 / ARM

ClawOS works on RPi 5 8GB. The installer detects ARM and pulls `qwen2.5:1.5b` automatically — no configuration needed.

```bash
curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh -o /tmp/clawos.sh && bash /tmp/clawos.sh
```

Expected response time: 2–4 seconds for short answers on RPi 5.

---

## Using a Remote Ollama Server

If you have a more powerful machine running Ollama on your local network, you can point ClawOS at it instead of running inference locally. Useful for low-power devices like the RPi 5.

**On the powerful machine** — make Ollama listen on the network:
```bash
OLLAMA_HOST=0.0.0.0 ollama serve
# Pull the models ClawOS needs:
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

**On the ClawOS machine** — set the host before installing or running:
```bash
export OLLAMA_HOST=http://192.168.1.50:11434   # replace with your server IP
curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh -o /tmp/clawos.sh && bash /tmp/clawos.sh
```

To make it permanent:
```bash
echo 'export OLLAMA_HOST=http://192.168.1.50:11434' >> ~/.bashrc
source ~/.bashrc
```

ClawOS will use the remote server for all inference — the local machine only runs the agent runtime, dashboard, and memory services.

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

We use Ollama because it has the best out-of-the-box experience for consumer hardware — one command to pull and run any model, automatic GPU detection, and a clean API. For single-user local inference on 8–32GB machines it's the right tool.

If you're running a multi-user server deployment, `vllm` or `llama.cpp` with a custom server are valid alternatives. Ollama support in ClawOS doesn't prevent you from pointing the model endpoint elsewhere — it's just the default that works for most people on first install.

---

## How it works

```
You (Terminal / WhatsApp / Voice)
         │
      agentd   ←── task queue + session manager
         │
      Ollama   ←── local inference, no cloud, no API keys
         │
     policyd   ←── every tool call checked before it runs
         │
   toolbridge  ←── files, web, shell, memory
         │
       memd    ←── 4-layer memory: PINNED + WORKFLOW + ChromaDB + FTS5
```

Every action goes through `policyd`. Sensitive operations pause for your approval. Nothing talks to the internet unless you explicitly allow it. A tamper-evident Merkle-chained audit log records every action taken on your machine.

---

## Security

ClawOS meets 6 of 7 enterprise security requirements. No other open-source agent project meets more than 3.

| Requirement | Status |
|-------------|--------|
| Agent-level RBAC with scoped permissions | ✅ |
| Runtime permission check before every tool call | ✅ |
| Immutable Merkle-chained audit trail | ✅ |
| Human-in-loop approval for sensitive actions | ✅ |
| Kill switch — terminate agent actions in real time | ✅ |
| Credential isolation — no API keys in agent context | ✅ |

---

## Build from source

```bash
git clone https://github.com/xbrxr03/clawos
cd clawos
pip install pyyaml aiohttp fastapi uvicorn ollama click json-repair chromadb --break-system-packages
python3 -m bootstrap.bootstrap
clawos
```

---

## Roadmap

Linux remains the most battle-tested install path. macOS now uses Homebrew + `launchd`; the primary target is macOS 14+ on Apple Silicon, with Intel as best-effort.

- [x] Core runtime — policyd, memd, toolbridge, agentd, modeld, voiced
- [x] Voice pipeline — Whisper STT + Piper TTS
- [x] One-command installer — Ubuntu, Debian, macOS
- [x] OpenClaw offline + WhatsApp
- [x] Dashboard — FastAPI + WebSocket + React
- [x] systemd service units
- [x] First-run wizard — hardware profiling, model selection, API key vault
- [x] nexus CLI — 12 commands, RAG pipeline, project upload/query
- [x] Key vault — secretd, per-service credential isolation
- [x] OpenRouter support — use cloud models as fallback
- [x] 29 offline workflows — files, documents, developer, content, system, data categories
- [x] Capability discovery — auto-suggests workflows based on your hardware and profile
- [ ] **Bootable ISO** — flash and boot, no install needed (final stage)

---

## vs. everything else

macOS support in ClawOS now means the Homebrew + `launchd` path described in [docs/MACOS.md](docs/MACOS.md). Apple Silicon is the primary target today.

| | OpenClaw | Nanobot | NanoClaw | ZeroClaw | ClawOS |
|---|---|---|---|---|---|
| One-command install | ❌ | ❌ | ❌ | ❌ | ✅ |
| Offline — no API keys | ❌ | ❌ | ❌ | ❌ | ✅ |
| OpenClaw ecosystem | ✅ | ❌ | ❌ | ❌ | ✅ |
| Human approval queue | ❌ | ❌ | ❌ | ❌ | ✅ |
| Tamper-evident audit | ❌ | ❌ | ❌ | ❌ | ✅ |
| WhatsApp bridge | ✅ | ❌ | ❌ | ❌ | ✅ |
| macOS support | ❌ | ✅ | ❌ | ✅ | ✅ |
| Zero monthly cost | ❌ | ✅ | ✅ | ✅ | ✅ |

---

## License

MIT. ClawOS is not affiliated with OpenClaw or Anthropic.
OpenClaw is MIT licensed. Ollama is MIT licensed.

---

*Built for people who wanted OpenClaw to work. [github.com/xbrxr03/clawos](https://github.com/xbrxr03/clawos)*
