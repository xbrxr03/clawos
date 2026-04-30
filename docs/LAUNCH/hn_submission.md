# Hacker News Launch Submission

**Title:** Show HN: ClawOS – local-first AI agent that runs on your laptop

**URL:** https://github.com/xbrxr03/clawos

**Body:**

ClawOS is a local AI agent for your existing Linux machine. One curl command, no cloud, no API keys, no telemetry.

```bash
curl -fsSL https://install.clawos.io | bash
```

**What it does:**
- Say "Hey Claw" → get morning briefing (time, weather, calendar, tasks)
- "Write essay and paste to editor" → 4 tools, one sentence, essay appears in gedit
- Sensitive operations show floating approval popup (not browser tab)
- Everything runs local via Ollama — works offline

**Hardware:** 8GB RAM minimum, 16GB recommended. Tier A/B/C model selection in first-run wizard.

**Architecture:** 10 microservices, FastAPI, SQLite, Tauri overlay, systemd user units. AGPL-3.0.

**Demo GIFs:**
- Morning briefing: [link]
- Essay-to-editor: [link]  
- Approval popup: [link]

Built over 3 months. Would love feedback from anyone running local LLMs.
