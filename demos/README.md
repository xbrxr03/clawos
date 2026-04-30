# ClawOS v1.0 Demos

Three flagship demos that prove offline AI can be magical on your own laptop.

---

## Demo 1: Morning Briefing (Voice-First)

**What it does:** Say "Hey JARVIS" → Get a spoken morning briefing with weather, calendar, and tasks.

**How to try it:**
```bash
# Start all services
bash scripts/dev_boot.sh --full

# Trigger via API (simulates wake word)
curl -X POST http://localhost:7088/trigger
```

**Components:**
- `services/voiced/` - Wake word detection
- `services/waketrd/` - Bridge to briefing (port 7088)
- `runtimes/agent/voice_entry.py` - speak_morning_briefing()
- `tools/calendar/import_ics.py` - Calendar import

**Add your calendar:**
```bash
# Drop .ics files into ~/.clawos/calendars/
python3 -m tools.calendar.import_ics ~/.clawos/calendars/*.ics
```

---

## Demo 2: Essay to Editor (Clipboard Magic)

**What it does:** Copy text from any editor → AI fixes grammar → Rewrites with style → Pastes back.

**How to try it:**
```bash
# Copy text from any editor (Ctrl+C), then:
python3 demos/essay_to_editor.py --style engaging

# Or with explicit text:
python3 demos/essay_to_editor.py --text "Your text here" --style formal
```

**Styles available:**
- `formal` - Professional business tone
- `casual` - Conversational friend tone  
- `academic` - Research paper style
- `concise` - Direct and brief
- `engaging` - Blog post style (default)

**Components:**
- `demos/essay_to_editor.py` - Main workflow
- `runtimes/agent/tools/desktop.py` - Clipboard operations
- `runtimes/agent/runtime.py` - Agent runtime

---

## Demo 3: Approval Popup (Human-in-Loop)

**What it does:** Sensitive operations (file delete, shell commands) show floating approval window.

**How to try it:**
```bash
# The overlay auto-triggers when sensitive tools are called
# Test with a sensitive command:
clawctl chat "delete all files in ~/Downloads"

# Or trigger directly via API:
curl http://localhost:7070/api/approvals
```

**Components:**
- `dashboard/frontend/src/overlays/ApprovalOverlay.tsx` - UI component
- `services/dashd/api.py` - /api/approvals endpoint
- `services/policyd/` - Policy enforcement
- `adapters/policy/local_policy_adapter.py` - Approval integration

---

## Quick Start

```bash
# 1. Install ClawOS
bash install.sh

# 2. Start services
bash scripts/dev_boot.sh --full

# 3. Try the demos

# Morning briefing (voice)
curl -X POST http://localhost:7088/trigger

# Essay editor (clipboard)
echo "test text" | python3 demos/essay_to_editor.py

# Approval popup
curl http://localhost:7070/api/approvals
```

---

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│   voiced    │────>│   waketrd   │────>│ morning_briefing│
│  (port 7079)│     │  (port 7088)│     │   (voice_entry) │
└─────────────┘     └─────────────┘     └─────────────────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │  calendar   │
                                        │  reminders  │
                                        │   weather   │
                                        └─────────────┘

┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│  clipboard  │────>│essay_editor │────>│   set_clipboard │
│   (text)    │     │   (demo)    │     │    (paste)      │
└─────────────┘     └─────────────┘     └─────────────────┘

┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│    user     │────>│   policyd   │────>│ApprovalOverlay  │
│   action    │     │  (gatekeeper)│    │   (Tauri UI)    │
└─────────────┘     └─────────────┘     └─────────────────┘
```

---

## Troubleshooting

**Wake word not working?**
- Check voiced is running: `curl http://localhost:7079/health`
- Check waketrd is running: `curl http://localhost:7088/health`

**Clipboard not working?**
- Install clipboard tools: `sudo apt install xclip wl-clipboard`
- macOS: built-in `pbcopy`/`pbpaste`

**Calendar not showing?**
- Import .ics files: `python3 -m tools.calendar.import_ics ~/Downloads/*.ics`
- Check upcoming: `python3 -m tools.calendar.import_ics --upcoming`

**Approval popup not showing?**
- Check dashd: `curl http://localhost:7070/api/approvals`
- Rebuild Tauri: `cd dashboard/frontend && npm run tauri build`

---

## Files Created for v1.0

| File | Purpose |
|------|---------|
| `services/reminderd/` | Reminder daemon with notifications |
| `services/waketrd/` | Wake word → briefing bridge |
| `tools/calendar/import_ics.py` | Calendar ICS importer |
| `demos/essay_to_editor.py` | Essay editor workflow |
| `LAUNCH_BLOCKERS.md` | Launch tracking document |
