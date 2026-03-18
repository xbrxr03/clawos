# Hacker News Launch Post

## Title (pick one)
- "ClawOS – bootable ISO that runs OpenClaw + Ollama locally, no API keys"
- "Show HN: ClawOS – flash a USB, boot, your AI agent is running offline"
- "ClawOS – the first OS built specifically for local AI agents"

## Best title
**Show HN: ClawOS – bootable ISO that runs OpenClaw + Ollama offline, no API keys**

---

## Body text

Hi HN,

I built ClawOS — a bootable Linux ISO that turns any x86 machine into a local AI agent computer.

Flash the ISO, boot from USB, and you have OpenClaw running offline in about 2 minutes.
No npm. No pip. No config. No API keys. No monthly bill.

```
sudo dd if=clawos-0.1.0-amd64.iso of=/dev/sdX bs=4M status=progress
```

**Why I built it:**

OpenClaw costs $300-750/month in API tokens. There's an active CVE (CVE-2026-25253)
that lets anyone steal your keys in one click. The original creator just left for OpenAI.
Meanwhile the software itself is brilliant — 13,700+ community skills, WhatsApp,
Telegram, voice, agent-to-agent communication.

I wanted all of that but offline, on hardware I own, for free.

**What's different:**

Every other alternative is software you install on top of an existing OS.
ClawOS is the OS. It comes with:
- OpenClaw pre-configured for Ollama (no API keys ever)
- gemma3:4b pulled on first boot
- Pre-applied Linux auth fix (the bug that breaks Ollama+OpenClaw on Linux)
- Claw Core — a lightweight native Python agent for low-RAM machines (8GB)
- Full security layer (policyd, Merkle audit trail, human approval queue)
- Dashboard at :7070

Works on: ROG Ally, Intel NUC, old laptops, mini PCs, anything x86_64 with 8GB+.

**Hardware note:**

8GB = Claw Core only (gemma3:4b)
16GB = + OpenClaw with qwen2.5:7b
32GB+ = larger models, faster inference

**GitHub:** https://github.com/you/clawos

Happy to answer questions about the architecture, the OpenClaw offline setup,
or the ISO build process.

---

## Subreddits to also post in

- r/selfhosted  — this is their exact audience
- r/homelab     — "AI appliance on a mini PC" framing
- r/LocalLLaMA  — technical audience, will care about offline + no API keys
- r/OpenClaw (if exists) — direct audience

## Journalists who covered OpenClaw scandals

Search for recent coverage of:
- CVE-2026-25253
- OpenClaw "lethal trifecta" (Palo Alto Networks)
- Cisco "17% of ClawHub skills malicious"
- OpenClaw creator leaving for OpenAI

Those journalists are primed for "here's the safe local alternative" story.

## Timing

Post on Tuesday or Wednesday morning, 9am ET.
That's peak HN traffic.
Don't post on weekends — dies fast.
