# ClawOS — Product Vision

## The One Sentence

ClawOS is what you get when Apple builds Iron Man's JARVIS for everyone — a real AI operating
environment that runs on your hardware, works offline, costs nothing, and feels like it was
made by people who care about every second of the experience.

---

## Why This Exists

Every other local AI tool asks you to be technical.
You configure model files. You edit JSON. You read GitHub issues to understand why it won't start.

ClawOS asks nothing of the kind.

You install it. You go through a setup that feels like Apple's. You talk to it.
It answers. It runs your workflows. It lives in your dashboard. It picks up your voice.

That is the promise: AI that belongs to you, fully, without compromise.

---

## The Product in Plain Language

- **An OS layer** — not a chatbot, not an app. An ambient intelligence layer on Linux or macOS.
- **Bootable or installable** — ships as a clean Ubuntu-based ISO or installs onto an existing machine.
- **Local-first and offline-capable** — Ollama models on your hardware. No cloud required, no API keys.
- **Command Center** — a polished dashboard at :7070. Operations, workflows, traces, approvals, settings.
- **Voice** — Whisper STT + Piper TTS. Wake word ("Hey Claw"). Push-to-talk. Native audio pipeline.
- **Workflows** — 29 prebuilt jobs across files, documents, code, content, system, and data. One click.
- **Packs** — curated use-case configurations. Pick "Coding Autopilot" or "Daily Briefing OS" during setup.
- **Provider-neutral** — local Ollama by default. Plug in Anthropic, OpenAI, or any compatible endpoint.
- **OpenClaw migration path** — detect an existing OpenClaw install, import what's safe, improve the rest.
- **Policy-gated** — every tool call goes through policyd. Destructive actions require explicit approval.
- **Fully open source** — AGPL. No paid tier. No telemetry. No call home.

---

## Premium Quality Bars

These are non-negotiable. Every milestone is measured against them.

| Area | Bar |
|------|-----|
| First run | < 5 minutes from install to first AI response |
| Setup wizard | Guided, beautiful, no terminal required |
| Dashboard | 60fps feel, no spinners on hot paths, design-system consistent |
| Voice | < 500ms word-end to response start on target hardware |
| Top workflows | 100% success rate on supported platforms |
| CLI | Every command has a help string. Every error is actionable. |
| Docs | Every page is accurate and current. |
| Install | Works first try on Ubuntu 22.04/24.04 LTS and macOS 14+. |
| Errors | Helpful, not cryptic. The wizard offers a fix path. |
| Empty states | Beautiful, not blank. Onboarding lives in empty states. |

---

## Hardware Targets

| Tier | Device | RAM | Notes |
|------|--------|-----|-------|
| A | 8GB mini PC / low-spec laptop | 8GB | Claw Core only, qwen2.5:1.5b |
| B | ROG Ally, 16GB laptop | 16GB | Claw Core default, OpenClaw optional, qwen2.5:7b |
| C | 32GB+ workstation | 32GB+ | Full stack, all packs |

Primary dev target: Tier B (ROG Ally RC71L).
ISO validation target: Tier A + B on clean Ubuntu.

---

## Runtime Ecosystem

### Claw Core / Nexus (default)
Native Python agent with native Ollama function calling. Works on 8GB RAM. CPU-only capable.
The reliable foundation every user gets by default.

### PicoClaw (Tier A ARM)
Lightweight agent runtime from Sipeed.
Auto-activated on Raspberry Pi and ARM SBCs at install time.
No configuration required — detected automatically by the installer.

### OpenClaw (all tiers)
Node.js ecosystem with 13,700+ skills.
Pre-configured for Ollama offline.
Installed via: `clawctl openclaw install`
The main agent ecosystem for skills, automations, and community workflows.

### Hermes Agent (planned)
Self-improving agent from Nous Research.
Persistent cross-session memory, MCP integration, autonomous skill loops.
Support planned post-v0.1.

---

## What "Apple Made JARVIS Real" Means in Practice

This is not a metaphor for style. It is a quality filter.

**Apple standard:**
- First-time setup is guided and cannot fail silently.
- Every transition is animated, intentional, and fast.
- You never see a raw stack trace.
- The empty state is designed, not forgotten.
- The CLI is as good as the GUI.
- The docs ship with the product.
- The hardware constraints are known and respected.

**JARVIS standard:**
- It anticipates. Workflows surface when the agent detects relevant context.
- It explains itself. Traces and approvals make the AI's actions transparent.
- It works across surfaces. Voice, dashboard, CLI — same intelligence.
- It never loses context. Memory is durable, layered, and searchable.
- It stays in the background until you need it.

**For everyone standard:**
- Not for developers only. The first-run wizard is the product.
- Not for high-end hardware only. Tier A must be first-class.
- Not behind a paywall. Never.
- Not dependent on someone else's servers. Always.

---

## What ClawOS Is Not (v0.1)

- Not a multi-user enterprise system.
- Not a desktop environment replacement.
- Not a robotics platform.
- Not a cloud SaaS.
- Not a ChatGPT clone with local models bolted on.

---

## Promotion Channels

HN Show HN is not the launch vehicle. Promotion is happening on other platforms directly.

Social assets needed:
- Dashboard screenshot (dark, polished, real data)
- First-run wizard screenshot
- Voice workflow demo GIF (< 15 seconds)
- organize-downloads demo GIF (before/after)
- summarize-pdf demo GIF

Every asset should pass the bar: "would this look at home in an Apple product launch deck?"
