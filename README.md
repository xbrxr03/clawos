# ClawOS

> OpenClaw on your own hardware. One command. No API keys. No monthly bill.

```bash
curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh | bash
```

That's it. In 25 seconds you have the full OpenClaw ecosystem running locally — offline, private, and free.

---

## Why this exists

OpenClaw hit 280,000 GitHub stars in six weeks. Most people who tried it gave up.

The setup takes hours. It requires API keys. It costs $300–750/month in tokens. The creator left for OpenAI in February. CVE-2026-25253 lets anyone steal your keys in one click. Cisco found that 17% of ClawHub skills are malicious.

ClawOS is the answer to all of that. It runs OpenClaw on your hardware, with your models, for the cost of electricity.

---

## What you get

After one command on any Ubuntu 24.04 machine:

- **OpenClaw** — pre-configured for offline Ollama, no API keys required
- **Ollama** — local model runtime, `qwen2.5:7b` pulled and ready
- **Claw Core** — native Python agent with memory, tools, and voice
- **WhatsApp bridge** — text your AI from your phone
- **policyd** — every tool call gated and audited before it runs
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

- Ubuntu 24.04 (or Debian 12)
- 16GB RAM recommended (8GB works for Claw Core only)
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

The script handles everything: Ollama, Node.js, Python dependencies, model download, OpenClaw configuration, and the `clawos` command. No prompts. No choices. Just works.

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

Scan the QR code with WhatsApp on your phone. That's it — you can now text your AI from anywhere.

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
- [x] One-command installer
- [x] OpenClaw offline + WhatsApp
- [ ] Dashboard — FastAPI + WebSocket + React
- [ ] systemd service units
- [ ] First-run wizard
- [ ] Bootable ISO — flash and boot, no install needed

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
| Zero monthly cost | ❌ | ✅ | ✅ | ✅ | ✅ |

---

## License

MIT. ClawOS is not affiliated with OpenClaw or Anthropic.
OpenClaw is MIT licensed. Ollama is MIT licensed.

---

*Built for people who wanted OpenClaw to work. [github.com/xbrxr03/clawos](https://github.com/xbrxr03/clawos)*
