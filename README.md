# ClawOS

> OpenClaw on your own hardware. One command. No API keys. No monthly bill.

```bash
curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh | bash
```

In 25 seconds you have the full OpenClaw ecosystem running locally — offline, private, and free.

---

## What ClawOS is (and isn't)

ClawOS is currently a **one-command installer** that turns any Ubuntu/Debian/macOS machine into a working OpenClaw environment. No manual config. No API keys. Just works.

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
- **Ollama** — local model runtime, `qwen2.5:7b` pulled and ready
- **Claw Core** — native Python agent with memory, tools, and voice
- **WhatsApp bridge** — text your AI from your phone
- **policyd** — every tool call gated and audited before it runs
- **Dashboard** — web UI showing tasks, approvals, models, memory, audit log
- **Full OpenClaw ecosystem** — 13,700+ skills, all working offline

```
$ clawos

you › what can you do?
jarvis › I can read and write files, search the web, remember things
         across sessions, and run tools on this machine. Everything
         runs locally — nothing leaves this computer.

you › create a file called notes.txt with my meeting agenda
jarvis › Created notes.txt in your workspace.
```

---

## Requirements

- Ubuntu 24.04, Debian 12, or macOS (Apple Silicon + Intel)
- 8GB RAM minimum (16GB recommended)
- 10GB free disk space
- Internet on first run only (pulls models, then fully offline)

| RAM | What runs |
|-----|-----------|
| 8GB | Claw Core — gemma3:4b, full agent, voice |
| 16GB | + OpenClaw — qwen2.5:7b, WhatsApp, 13,700+ skills |
| 32GB+ | Larger models, faster inference |

GPU optional but recommended. NVIDIA (CUDA) and AMD (ROCm) both supported.

---

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh | bash
```

Handles everything: Ollama, Node.js, Python dependencies, model download, OpenClaw configuration, and the `clawos` command. No prompts. No choices. Just works.

**After install:**

```bash
# Start Claw Core (native agent)
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

- [x] Core runtime — policyd, memd, toolbridge, agentd, modeld, voiced
- [x] Voice pipeline — Whisper STT + Piper TTS
- [x] One-command installer — Ubuntu, Debian, macOS
- [x] OpenClaw offline + WhatsApp
- [x] Dashboard — FastAPI + WebSocket + React
- [ ] systemd service units
- [ ] First-run wizard
- [ ] claw CLI — 12 commands, prompt injection scanner
- [ ] **Bootable ISO** — flash and boot, no install needed (final stage)

---

## vs. everything else

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
