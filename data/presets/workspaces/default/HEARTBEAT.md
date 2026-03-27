# Nexus — Heartbeat Schedule

## What is this?
This file defines what Nexus checks proactively, on a schedule, without being asked.
Results are pushed to WhatsApp (if connected) or logged to HISTORY.md.

## How to use
Add tasks in this format:
  - interval: how often (e.g. daily, hourly, 30min)
  - check: what to check
  - report: how to summarise

## Default checks (edit or remove as needed)

### Daily briefing — 08:00
- Check system health: disk, RAM, service status
- Report: "Good morning. System status: [summary]. Anything urgent: [issues or 'all clear']."

### Hourly — system health
- Check: disk usage, memory pressure
- Report only if: disk > 85% used OR memory > 90% used
- Message: "⚠️ System alert: [issue]"

## Add your own
Examples:
  - "Every Monday 09:00 — summarise files modified this week in ~/Documents"
  - "Every 4 hours — check if Ollama is still running"
  - "Daily 07:30 — read ~/todo.md and remind me of top 3 items"
