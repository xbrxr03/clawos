# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Productivity tools — reminders, time, weather, calendar, news.

Reminders: SQLite-backed, lives at ~/.clawos/reminders.db. Self-contained,
no daemon required (the agent reads/writes directly).
Calendar: reads local ICS files from ~/.clawos/calendars/*.ics.
Weather: wttr.in (text API, no key). Cached for 5 minutes.
News: configured RSS feeds at ~/.clawos/news_feeds.txt, cached 15 min.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from clawos_core.constants import CLAWOS_DIR

log = logging.getLogger("agent.tools.productivity")

REMINDER_DB = CLAWOS_DIR / "reminders.db"
CALENDAR_DIR = CLAWOS_DIR / "calendars"
NEWS_FEEDS_FILE = CLAWOS_DIR / "news_feeds.txt"


# ── reminder DB ──────────────────────────────────────────────────────────────

def _open_reminders() -> sqlite3.Connection:
    REMINDER_DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(REMINDER_DB), check_same_thread=False)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id          TEXT PRIMARY KEY,
            task        TEXT NOT NULL,
            due_at      TEXT NOT NULL,
            repeat      TEXT DEFAULT 'none',
            created_at  TEXT NOT NULL,
            done        INTEGER DEFAULT 0
        )
    """)
    db.commit()
    return db


# ── time parsing ─────────────────────────────────────────────────────────────

_REL_PATTERNS = [
    (re.compile(r"^in\s+(\d+)\s*(min(ute)?s?|hours?|hrs?|days?)$", re.I), True),
    (re.compile(r"^(today)\b", re.I), False),
    (re.compile(r"^(tonight)\b", re.I), False),
    (re.compile(r"^(tomorrow)\b", re.I), False),
]

_TIME_PATTERN = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm|AM|PM)?\b"
)


def _parse_when(text: str) -> datetime:
    """Best-effort natural-language → datetime. Defaults to +1 hour."""
    now = datetime.now()
    s = (text or "").strip().lower()
    if not s:
        return now + timedelta(hours=1)

    # "in N min/hour/day"
    m = re.match(r"^in\s+(\d+)\s*(min(?:ute)?s?|hours?|hrs?|days?)$", s)
    if m:
        n = int(m.group(1)); unit = m.group(2)
        if unit.startswith("min"): return now + timedelta(minutes=n)
        if unit.startswith("h"):   return now + timedelta(hours=n)
        if unit.startswith("d"):   return now + timedelta(days=n)

    base = now
    if "tomorrow" in s: base = now + timedelta(days=1)
    elif "tonight" in s:
        base = now.replace(hour=20, minute=0, second=0, microsecond=0)

    # Look for an explicit time
    m = _TIME_PATTERN.search(s)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        ampm = (m.group(3) or "").lower()
        if ampm == "pm" and hour < 12: hour += 12
        if ampm == "am" and hour == 12: hour = 0
        try:
            base = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if base < now: base += timedelta(days=1)
        except ValueError:
            pass

    if base <= now:
        base = now + timedelta(hours=1)
    return base


# ── reminders ────────────────────────────────────────────────────────────────

async def add_reminder(args: dict, ctx: dict) -> str:
    task = (args.get("task") or "").strip()
    when = (args.get("when") or "in 1 hour").strip()
    repeat = (args.get("repeat") or "none").lower()
    if not task:
        return "[ERROR] task required"
    due = _parse_when(when)
    rid = uuid.uuid4().hex[:8]

    loop = asyncio.get_running_loop()
    def _save():
        db = _open_reminders()
        db.execute(
            "INSERT INTO reminders (id, task, due_at, repeat, created_at) VALUES (?,?,?,?,?)",
            (rid, task, due.isoformat(), repeat, datetime.now().isoformat()),
        )
        db.commit()
        db.close()
    try:
        await loop.run_in_executor(None, _save)
    except Exception as e:
        return f"[ERROR] {e}"
    return f"[OK] reminder set: \"{task}\" at {due.strftime('%a %b %d, %I:%M %p')} (id {rid})"


async def list_reminders(args: dict, ctx: dict) -> str:
    days = int(args.get("days_ahead", 7))
    cutoff = (datetime.now() + timedelta(days=days)).isoformat()

    loop = asyncio.get_running_loop()
    def _read():
        db = _open_reminders()
        rows = db.execute(
            "SELECT id, task, due_at, repeat FROM reminders "
            "WHERE done = 0 AND due_at <= ? ORDER BY due_at LIMIT 20",
            (cutoff,),
        ).fetchall()
        db.close()
        return rows
    try:
        rows = await loop.run_in_executor(None, _read)
    except Exception as e:
        return f"[ERROR] {e}"

    if not rows:
        return "No upcoming reminders."
    lines = []
    for rid, task, due_at, repeat in rows:
        try:
            dt = datetime.fromisoformat(due_at)
            when_str = dt.strftime("%a %b %d, %I:%M %p")
        except Exception:
            when_str = due_at
        suffix = f" (repeats {repeat})" if repeat and repeat != "none" else ""
        lines.append(f"- [{rid}] {when_str} — {task}{suffix}")
    return "\n".join(lines)


async def remove_reminder(args: dict, ctx: dict) -> str:
    rid = (args.get("reminder_id") or "").strip()
    if not rid:
        return "[ERROR] reminder_id required"
    loop = asyncio.get_running_loop()
    def _del():
        db = _open_reminders()
        cur = db.execute("DELETE FROM reminders WHERE id = ?", (rid,))
        db.commit()
        deleted = cur.rowcount
        db.close()
        return deleted
    try:
        n = await loop.run_in_executor(None, _del)
    except Exception as e:
        return f"[ERROR] {e}"
    return f"[OK] removed reminder {rid}" if n else f"[ERROR] no reminder with id {rid}"


# ── time ─────────────────────────────────────────────────────────────────────

async def get_time(args: dict, ctx: dict) -> str:
    now = datetime.now()
    tz = datetime.now(timezone.utc).astimezone().tzinfo
    return now.strftime("%A, %B %d, %Y · %I:%M %p ") + str(tz)


# ── weather (cached) ─────────────────────────────────────────────────────────

_WEATHER_CACHE: dict[str, tuple[float, str]] = {}
_WEATHER_TTL = 300  # 5 min


async def get_weather(args: dict, ctx: dict) -> str:
    location = (args.get("location") or "").strip()
    key = location or "_default"
    now = time.time()
    cached = _WEATHER_CACHE.get(key)
    if cached and (now - cached[0]) < _WEATHER_TTL:
        return cached[1]

    # wttr.in returns plain text for any location; empty location = IP geolocation
    url = f"https://wttr.in/{location}?format=3" if location else "https://wttr.in/?format=3"
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(url, headers={"User-Agent": "curl/8.0"})
            r.raise_for_status()
            text = r.text.strip()
    except Exception as e:
        log.debug(f"weather fetch failed: {e}")
        return "[OFFLINE] weather unavailable (no internet)"
    _WEATHER_CACHE[key] = (now, text)
    return text


# ── calendar (local ICS) ─────────────────────────────────────────────────────

def _parse_ics_dt(s: str) -> datetime | None:
    s = s.strip().rstrip("Z")
    for fmt in ("%Y%m%dT%H%M%S", "%Y%m%d", "%Y-%m-%dT%H:%M:%S"):
        try: return datetime.strptime(s, fmt)
        except ValueError: continue
    return None


def _parse_ics(path: Path) -> list[dict]:
    """Minimal ICS parser — enough for VEVENT summaries + start times."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    events: list[dict] = []
    cur: dict | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT":
            if cur and "summary" in cur and "start" in cur:
                events.append(cur)
            cur = None
        elif cur is not None:
            if line.startswith("SUMMARY:"):
                cur["summary"] = line[len("SUMMARY:"):]
            elif line.startswith("DTSTART"):
                _, _, val = line.partition(":")
                dt = _parse_ics_dt(val)
                if dt: cur["start"] = dt
            elif line.startswith("DTEND"):
                _, _, val = line.partition(":")
                dt = _parse_ics_dt(val)
                if dt: cur["end"] = dt
    return events


def _resolve_date_arg(s: str, today: datetime) -> datetime:
    s = (s or "today").lower().strip()
    if s == "today":     return today
    if s == "tomorrow":  return today + timedelta(days=1)
    try:    return datetime.strptime(s, "%Y-%m-%d")
    except ValueError: return today


async def get_calendar_events(args: dict, ctx: dict) -> str:
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start = _resolve_date_arg(args.get("start", "today"), today)
    end   = _resolve_date_arg(args.get("end",   "today"), today)
    end   = end.replace(hour=23, minute=59, second=59)

    if not CALENDAR_DIR.exists():
        return "No calendars configured. Drop .ics files in ~/.clawos/calendars/."

    loop = asyncio.get_running_loop()
    def _scan():
        all_events: list[dict] = []
        for ics in CALENDAR_DIR.glob("*.ics"):
            for ev in _parse_ics(ics):
                if start <= ev["start"] <= end:
                    all_events.append(ev)
        return sorted(all_events, key=lambda e: e["start"])
    events = await loop.run_in_executor(None, _scan)

    if not events:
        if start.date() == end.date():
            return f"No events for {start.strftime('%a %b %d')}."
        return f"No events between {start.strftime('%b %d')} and {end.strftime('%b %d')}."
    lines = []
    for ev in events[:10]:
        lines.append(f"- {ev['start'].strftime('%a %b %d, %I:%M %p')} — {ev['summary']}")
    return "\n".join(lines)


# ── news (cached RSS) ────────────────────────────────────────────────────────

_NEWS_CACHE: tuple[float, str] | None = None
_NEWS_TTL = 900  # 15 min


def _default_feeds() -> list[str]:
    return [
        "https://feeds.bbci.co.uk/news/rss.xml",
        "https://news.ycombinator.com/rss",
    ]


def _read_feed_list() -> list[str]:
    if NEWS_FEEDS_FILE.exists():
        feeds = [l.strip() for l in NEWS_FEEDS_FILE.read_text().splitlines()
                 if l.strip() and not l.strip().startswith("#")]
        return feeds or _default_feeds()
    return _default_feeds()


async def _fetch_one_feed(client: httpx.AsyncClient, url: str, limit: int) -> list[str]:
    try:
        r = await client.get(url, timeout=4.0)
        r.raise_for_status()
        text = r.text
    except Exception:
        return []
    # Extremely lightweight title extraction — works for RSS 2.0 + Atom
    titles = re.findall(r"<title[^>]*>(.*?)</title>", text, re.S | re.I)
    # Strip CDATA wrappers
    cleaned = []
    for t in titles[1:]:  # skip the channel title
        t = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", t, flags=re.S)
        t = re.sub(r"<.*?>", "", t).strip()
        if t: cleaned.append(t)
        if len(cleaned) >= limit: break
    return cleaned


async def get_news(args: dict, ctx: dict) -> str:
    global _NEWS_CACHE
    limit = int(args.get("limit", 5))
    now = time.time()
    if _NEWS_CACHE and (now - _NEWS_CACHE[0]) < _NEWS_TTL:
        return _NEWS_CACHE[1]

    feeds = _read_feed_list()
    try:
        async with httpx.AsyncClient() as client:
            results = await asyncio.gather(*[_fetch_one_feed(client, u, limit) for u in feeds])
    except Exception as e:
        return f"[OFFLINE] news unavailable: {e}"
    headlines: list[str] = []
    for h in results:
        for title in h:
            if title not in headlines:
                headlines.append(title)
            if len(headlines) >= limit: break
        if len(headlines) >= limit: break
    if not headlines:
        return "[OFFLINE] no headlines fetched"
    text = "\n".join(f"- {h}" for h in headlines[:limit])
    _NEWS_CACHE = (now, text)
    return text
