# ClawOS

**Flash it. Boot it. Your AI is ready.**

```
sudo dd if=clawos.iso of=/dev/sdX bs=4M status=progress
```

OpenClaw + Ollama on any machine. No API keys. No monthly bill. No setup.

---

## What it is

ClawOS is a bootable Linux ISO that turns any machine into a local AI agent computer.

Boot from USB and you have OpenClaw running offline — with memory, tools, WhatsApp,
and a dashboard — before you've opened a terminal.

## Why this exists

OpenClaw costs $300–750/month in API tokens. The creator left for OpenAI.
CVE-2026-25253 lets anyone steal your keys in one click.

ClawOS runs OpenClaw on your hardware, with your models, for the cost of electricity.

## What nobody else has

| Feature | OpenClaw | Everything else | ClawOS |
|---------|----------|-----------------|--------|
| Bootable ISO | ❌ | ❌ | ✅ |
| Works offline | ❌ | ❌ | ✅ |
| No API keys ever | ❌ | ❌ | ✅ |
| OpenClaw ecosystem | ✅ | ❌ | ✅ |
| Zero monthly cost | ❌ | ✅ | ✅ |

## Hardware

Any x86_64 machine with 8GB+ RAM. Tested on: ROG Ally, Intel NUC, old laptops, mini PCs.

| RAM | What works |
|-----|-----------|
| 8GB | Claw Core — gemma3:4b, full agent, voice |
| 16GB | + OpenClaw — qwen2.5:7b, WhatsApp, skills |
| 32GB+ | Larger models, faster inference |

## Get it

Download the ISO from the [releases page](../../releases), then:

```bash
# Flash to USB (Linux/Mac)
sudo dd if=clawos-0.1.0-amd64.iso of=/dev/sdX bs=4M status=progress oflag=sync

# Windows — use Balena Etcher
```

## First boot

Boot from USB. Wait 2 minutes (pulls model on first run). Then:

```bash
clawctl chat
```

```
you › what can you do?
jarvis › I can read and write files, search the web, remember facts
         across sessions, and run tools on this machine. Everything
         runs locally — nothing leaves this computer.
```

## OpenClaw

Pre-configured for offline Ollama. No config editing required.

```bash
clawctl openclaw install    # install and configure
clawctl openclaw start      # start the gateway
openclaw onboard            # connect WhatsApp via QR scan
```

Full OpenClaw ecosystem — 13,700+ skills, WhatsApp, Telegram, voice — works offline.

## Build from source

```bash
git clone https://github.com/you/clawos
cd clawos
pip install pyyaml aiohttp fastapi uvicorn ollama click --break-system-packages
python3 -m bootstrap.bootstrap
clawctl chat
```

## Architecture

```
User (WhatsApp / Terminal / Dashboard :7070)
  → agentd (task queue + sessions)
  → Ollama (local inference — no cloud)
  → policyd (every tool call gated + audited)
  → toolbridge (files, shell, web, memory)
```

## Security

Every action goes through `policyd`. Sensitive operations pause for approval.
Full tamper-evident Merkle-chained audit log. Nothing talks to the internet
unless you allow it.

## License

MIT — ClawOS is not affiliated with OpenClaw or Anthropic.
OpenClaw is MIT licensed. Ollama is MIT licensed.
