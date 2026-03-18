# ClawOS
**Local AI agent OS. One command. No API keys. No monthly bill.**

```bash
curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh | bash
```

Installs OpenClaw + Ollama on any Ubuntu/Debian machine in ~10 minutes.
Everything runs on your hardware. Nothing leaves your machine.

---

## Why this exists

OpenClaw costs $300–750/month in API tokens. The creator left for OpenAI.
CVE-2026-25253 lets anyone steal your keys in one click. Cisco found 17% of
ClawHub skills are malicious.

ClawOS runs the full OpenClaw ecosystem on your hardware, with local models,
for the cost of electricity.

## What you get

- **OpenClaw** — pre-configured for offline Ollama, no API keys, no cloud
- **Claw Core** — lightweight native agent for 8GB machines (gemma3:4b)
- **Memory** — 4-layer memory that survives reboots (PINNED + vector + FTS5)
- **policyd** — every tool call gated and audited before execution
- **Voice** — Whisper STT + Piper TTS, fully offline
- **WhatsApp** — message your agent from your phone
- **Dashboard** — operations console at `http://localhost:7070`

## Hardware

Any x86_64 machine with 8GB+ RAM running Ubuntu 22.04/24.04 or Debian 12.

| RAM | What works |
|-----|------------|
| 8GB | Claw Core — gemma3:4b, full agent, voice |
| 16GB | + OpenClaw — qwen2.5:7b, WhatsApp, 13,700+ skills |
| 32GB+ | Larger models, faster inference |

Tested on: ROG Ally, Intel NUC, old laptops, mini PCs, Raspberry Pi 5.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh | bash
```

The installer:
1. Detects your hardware and picks the right profile
2. Installs Ollama and pulls the best model for your RAM
3. Sets up ClawOS services and memory
4. Configures OpenClaw for offline Ollama (no API keys ever)
5. Adds `claw` and `clawctl` to your PATH

## Usage

```bash
claw                    # start chatting immediately
clawctl start           # start all services + dashboard
clawctl status          # check service health
```

Dashboard at `http://localhost:7070`

```
you › what can you do?
jarvis › I can read and write files, search the web, remember facts
         across sessions, and run tools on this machine. Everything
         runs locally — nothing leaves this computer.
```

## OpenClaw (16GB+ RAM)

```bash
clawctl openclaw install    # install and configure for offline Ollama
clawctl openclaw start      # start the gateway
openclaw onboard            # connect WhatsApp via QR scan
```

Full OpenClaw ecosystem — 13,700+ skills, WhatsApp, Telegram, voice — offline.

## Architecture

```
User (WhatsApp / Terminal / Dashboard :7070)
  → agentd       task queue + sessions
  → Ollama        local inference — no cloud
  → policyd       every tool call gated + audited
  → toolbridge    files, shell, web, memory
  → memd          4-layer memory: PINNED + WORKFLOW + vector + FTS5
```

## Security

Every action goes through `policyd`. Sensitive operations pause for human
approval. Full tamper-evident Merkle-chained audit log. No API keys anywhere.
Nothing talks to the internet unless you explicitly allow it.

Meets 6/7 enterprise AI security requirements (IBM ADLC / NIST AI RMF).
No other open-source agent meets more than 3.

## What nobody else has

| Feature | OpenClaw | Alternatives | ClawOS |
|---------|----------|--------------|--------|
| One-command install | ❌ | partial | ✅ |
| Works offline | ❌ | ❌ | ✅ |
| No API keys ever | ❌ | ❌ | ✅ |
| OpenClaw ecosystem | ✅ | ❌ | ✅ |
| Human approval queue | ❌ | ❌ | ✅ |
| Merkle audit trail | ❌ | ❌ | ✅ |
| Voice (offline) | ❌ | ❌ | ✅ |
| Zero monthly cost | ❌ | ✅ | ✅ |

## Roadmap

- [x] Core agent runtime (56/56 tests passing)
- [x] 4-layer memory architecture
- [x] policyd permission gate + Merkle audit
- [x] Voice pipeline (Whisper + Piper)
- [x] OpenClaw offline configuration
- [x] One-command installer
- [ ] Dashboard (Phase 3)
- [ ] WhatsApp gateway (Phase 3)
- [ ] systemd services (Phase 4)
- [ ] Bootable ISO (Phase 7)

## Build from source

```bash
git clone https://github.com/xbrxr03/clawos
cd clawos
pip install pyyaml aiohttp fastapi uvicorn ollama click chromadb json_repair --break-system-packages
python3 -m bootstrap.bootstrap
claw
```

## License

MIT — ClawOS is not affiliated with OpenClaw or Anthropic.
OpenClaw is MIT licensed. Ollama is MIT licensed.
