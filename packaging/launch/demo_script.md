# ClawOS Demo Script
## 60-second video for GitHub README and social

---

## What to record

### Shot 1 — The install (10 seconds)
Show terminal:
```
curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh | bash
```
Let the progress scroll for a few seconds. Cut.

### Shot 2 — The boot (15 seconds)
Show dashboard opening at http://localhost:7070 — dark theme, Overview page.
The command center appearing is the visual hook.
Let it sit for 2 seconds.

### Shot 3 — Morning briefing (20 seconds)
```
clawctl demos morning-briefing
```
Show the spoken briefing playing through Piper TTS.
Show the five parallel tool calls in the terminal output.

### Shot 4 — Approval popup (15 seconds)
```
clawctl demos approval-test
```
Show the floating borderless Tauri window appearing over the desktop.
Click Approve. Show confirmation.

---

## Recording tips

- Terminal font size: 20px minimum (readable on mobile)
- Dark theme terminal (matches the dashboard)
- Trim all waiting/loading time
- Total video: 60-90 seconds max

## Tools
- OBS or SimpleScreenRecorder for terminal recording
- Keep it raw — no music, no voiceover needed
- Upload to GitHub as a GIF (use ffmpeg to convert) or as a YouTube link

## ffmpeg GIF conversion
```bash
ffmpeg -i demo.mp4 -vf "fps=12,scale=800:-1:flags=lanczos" \
  -c:v gif demo.gif
```

---

## Caption for social

> One command. No cloud. Your AI is ready.
>
> ClawOS — local AI agent on your Linux machine.
> No API keys. No setup complexity. No monthly bill.
>
> github.com/xbrxr03/clawos
> #ai #selfhosted #homelab #ollama #localai
