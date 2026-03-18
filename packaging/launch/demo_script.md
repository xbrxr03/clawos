# ClawOS Demo Script
## 60-second video for GitHub README and social

---

## What to record

### Shot 1 — The flash (10 seconds)
Show terminal:
```
sudo dd if=clawos-0.1.0-amd64.iso of=/dev/sdb bs=4M status=progress oflag=sync
```
Let the progress bar run for a few seconds. Cut.

### Shot 2 — The boot (15 seconds)
Show BIOS boot screen → ClawOS MOTD appearing in terminal.
The MOTD with the ASCII art logo is the visual hook.
Let it sit for 2 seconds.

### Shot 3 — First chat (20 seconds)
```
clawctl chat
```
Type: `summarise the files in my workspace`
Show Jarvis responding.
Type: `remember that i prefer dark mode`
Show: `[MEMORY] Saved`

### Shot 4 — WhatsApp (15 seconds)
Show phone — message sent to Jarvis number.
Cut to terminal showing incoming message.
Cut back to phone — Jarvis reply appearing.

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

> Flash a USB. Boot. Your AI is ready.
>
> ClawOS — OpenClaw + Ollama on any machine.
> No API keys. No setup. No monthly bill.
>
> github.com/you/clawos
> #ai #selfhosted #homelab #openclaw #ollama
