# Hacker News Launch Post

## Title (pick one)
- "Show HN: ClawOS – local-first AI agent that runs on your existing Linux laptop"
- "Show HN: ClawOS – flash a USB, boot, your AI agent is running offline"
- "ClawOS – the first OS built specifically for local AI agents"

## Best title
**Show HN: ClawOS – local-first AI agent for your laptop, no cloud, no API keys**

---

## Body text

Hi HN,

I built ClawOS — a local AI agent that installs on your existing Linux machine (or boots from ISO) and runs entirely offline.

One command to install:

```bash
curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh | bash
```

Or flash the ISO and boot from USB:

```
sudo dd if=clawos-0.1.1-amd64.iso of=/dev/sdX bs=4M status=progress
```

**What it does:**

- Say "Hey Claw" → get a spoken morning briefing (time, weather, calendar, tasks). Five tool calls, parallel, Piper TTS.
- "Write 1000 words on AI ethics and paste it into the text editor" → 4 tool chain, essay lands in gedit.
- Sensitive operations (file delete, shell commands) show a floating native approval popup — not a browser tab.
- Everything runs via Ollama. Works offline.

**Hardware:**

8GB = Claw Core only (qwen2.5:3b, fast CPU inference)
16GB = full stack + OpenClaw optional (qwen2.5:7b)
32GB+ = larger models, faster inference

**Architecture:** 10 microservices, FastAPI, SQLite, Tauri overlay, systemd user units. AGPL-3.0.

**GitHub:** https://github.com/xbrxr03/clawos

Happy to answer questions about the architecture, the offline Ollama setup, or the Tauri approval overlay.

---

## Subreddits to also post in

- r/selfhosted  — this is their exact audience
- r/homelab     — "AI appliance on a mini PC" framing
- r/LocalLLaMA  — technical audience, will care about offline + no API keys

## Timing

Post on Tuesday or Wednesday morning, 9am ET.
That's peak HN traffic.
Don't post on weekends — dies fast.
