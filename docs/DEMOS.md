# ClawOS Demos — Phrasing, Expected Output, and Recording Guide

> The four flagship demos that showcase what ClawOS can do offline.
> This is the canonical reference for what each demo should look like.
> Use it as the script when recording videos.

---

## Status

| Demo | Code | Tested live | Video recorded |
|------|------|-------------|----------------|
| 1. Morning briefing | ✅ | ⏳ needs Linux dev box | ❌ placeholder |
| 2. Multi-step composition (essay → editor) | ✅ | ⏳ needs Linux dev box | ❌ placeholder |
| 3. Floating approval popup | ✅ (Tauri rebuilt) | ⏳ needs Linux dev box with desktop env | ❌ placeholder |
| 4. Quirky combo (volume + spotify) | ✅ | ⏳ needs Linux dev box | ❌ placeholder |

**Honest note:** the files at `docs/media/demos/` are placeholders, not
real recordings. Replace them before tagging v0.1.2.

---

## Demo 1 — Morning briefing

**Phrase to say (or type):**
> "Hey Claw, good morning."
> Or any of: *"morning briefing"*, *"what's on today"*, *"brief me"*.

**What should happen:**
1. Wake word fires (or text input bypasses to deterministic intent)
2. Intent classifier matches `MORNING_BRIEFING`
3. `runtimes/agent/briefing.py:morning_briefing()` runs
4. Five tool calls fire in **parallel** via `asyncio.gather`:
   - `get_time`
   - `get_weather` (cached 5 min, falls back to `[OFFLINE]`)
   - `get_calendar_events` (today, from `~/.clawos/calendars/*.ics`)
   - `list_reminders` (today)
   - `recall("yesterday")` (semantic memory search)
5. Results assembled into a context block
6. qwen2.5:7b synthesizes a 4-7 sentence briefing
7. Piper voices it via voiced

**Expected reply (template):**
> *"Good morning, sir. It's 7:31 AM, Tuesday April 30th. Currently 14
> degrees and partly cloudy — rain expected at 3 PM. You have a team
> standup at 10, and a dentist appointment at 2. Reminder: take your
> vitamins. Yesterday you were working on the launch plan. Have a
> productive day."*

**Timing target:** ~4 seconds cold, ~2 seconds warm.

**CLI:**
```bash
clawctl demos morning-briefing
```

**Recording cadence:** 50-60 seconds. Show wifi icon disabled for impact
(prove offline). Wait for the synthesized speech to finish.

---

## Demo 2 — Multi-step composition (essay → editor)

**Phrase to say (or type):**
> "Write me a 1000 word essay about AI ethics and paste it into the text editor."

**What should happen:**
1. Intent classifier returns `LLM_NEEDED`
2. Router picks `qwen2.5:7b` (multi-tool, non-trivial input)
3. LLM returns 4 tool calls in one response:
   - `write_text(topic="AI ethics", length="1000 words")`
   - `set_clipboard(text=<essay>)`
   - `open_app(name="text editor")`
   - `paste_to_app(app="text editor")`
4. Tools execute. `write_text` is itself an LLM call internally.
5. Editor (gedit / kate / mousepad) opens with the essay pasted.
6. Final synthesis: short confirmation.

**Expected reply (template):**
> *"Done. Your essay's in the editor — 1,024 words on AI ethics."*

**Timing target:** 12-15 seconds (LLM generation is the bottleneck).

**CLI:**
```bash
clawctl demos essay-editor
```

> The current `essay-editor` CLI demo wraps the multi-step chain. If
> you want the raw "agent driving" experience, run `clawos` and type
> the phrase verbatim.

**Recording cadence:** 60 seconds. Show the editor opening live and the
text appearing. Don't cut — the latency IS the demo (proves it's local).

---

## Demo 3 — Floating approval popup

**Phrase to say (or type):**
> "Delete config.json"

**What should happen:**
1. Intent classifier returns `LLM_NEEDED`
2. LLM emits `write_file` or `run_command "rm config.json"` tool call
3. Tool is in `SENSITIVE_TOOLS` set → policyd evaluates → returns `QUEUE`
4. policyd inserts row in `~/.clawos/policy.db` `approvals` table and
   emits `approval_pending` event on event bus
5. Tauri command-center listens, calls `show_approval_overlay`
6. **Borderless always-on-top window** appears over the user's desktop:
   - Tool name + arguments
   - "Approve" / "Deny" buttons
   - Y / N keyboard shortcuts
7. User clicks Approve → POST `/api/approve/{request_id}` to dashd
8. policyd resolves the queued request → original tool call returns ALLOW
9. Tool executes, agent confirms

**Expected reply path:**
> Visible: floating popup mid-screen
> Spoken: *"I need your approval to delete config.json. Reply yes or no."*
> After approve: *"Deleted."*

**Timing target:** popup appears in <1 second after tool call.

**CLI:**
```bash
clawctl demos approval-test
```

**Recording cadence:** 30 seconds. Show the floating popup over a
realistic desktop (not just terminal). Prove it's a native window by
moving another window beneath it without losing focus.

**Pre-flight check:** Tauri binary must be rebuilt for the
`show_approval_overlay` command to be exposed:
```bash
cd desktop/command-center
npm install && npm run tauri build
```

---

## Demo 4 — Quirky combo

**Phrase to say (or type):**
> "Set volume to 30 and play Spotify."

**What should happen:**
1. Intent classifier matches **partial** (`VOLUME_SET` for the first half)
   — but the `and play X` makes it ambiguous, so it falls through to LLM
2. Router picks `qwen2.5:3b` (short input, single-tool-tier feel) or
   `qwen2.5:7b` (multi-tool) depending on heuristics
3. LLM emits 2 tool calls:
   - `set_volume(level=30)`
   - `open_app(name="spotify")`
4. Both execute (parallel where safe).
5. Spotify launches; volume is at 30%.

**Expected reply:**
> *"Volume's at 30%. Spotify's coming up."*

**Timing target:** 2-3 seconds.

**CLI:**
```bash
clawctl demos quirky-combo
```

**Variations worth recording (pick one for the launch video):**
- "What's eating my CPU?" → `system_stats` + brief synthesis
- "Screenshot my screen" → `screenshot` + path return
- "What's on the news?" → `get_news`
- "Remember I'm interested in AI safety" → `pin_fact` and recall in next briefing

---

## Recording the launch videos

For each of the four demos:

1. **Set up a clean Ubuntu 24.04 desktop**, GNOME or KDE, dark theme.
2. **Run** `peek --record-area screen` (Linux GIF recorder), or `obs-studio`
   for higher quality + audio.
3. **Disable wifi** for demos 1 and 2 to prove offline (visible in the
   top bar / system tray for credibility).
4. **Speak naturally** — don't perform. The demos are about how unhyped
   the experience feels.
5. **Don't cut latency.** A real-feel demo where you wait 12 seconds for
   the essay generation tells viewers "this is genuinely running on this
   laptop, not a fake mockup."
6. **Encode each to two formats:**
   - GIF, ≤8 MB, 800px wide (for README + GitHub)
   - MP4, H.264, 1080p (for landing page + Twitter)
7. **Save originals** at `docs/media/demos/demo{N}_{name}.mp4` and
   `.gif` (overwrite the placeholder duplicates currently committed).
8. **Update README** to embed the GIFs in the Demos section.

Total recording time: ~3 hours including retakes.

---

## Why these four demos

The product story is *"local AI agent that does real things on your
machine, fully offline."* Each demo proves one piece of that:

| Demo | Proves |
|------|--------|
| Morning briefing | Memory + parallel tool gather + voice |
| Essay → editor | Multi-step chain + native function calling on 7B |
| Approval popup | Trust / safety story (humans control sensitive ops) |
| Quirky combo | Speed + system control + intent classifier |

Together they show ClawOS is **a real OS-level agent**, not a chatbot
wrapped in `subprocess.run`.
