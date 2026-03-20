#!/usr/bin/env python3
"""
factoryctl — command-line control tool for the AI Automated Content Factory.

Usage:
  factoryctl new-job "Your topic here"
  factoryctl new-job "Your topic here" --priority 8
  factoryctl status
  factoryctl status <job_id>
  factoryctl agents
  factoryctl logs [agent_id] [--tail 50]
  factoryctl events [--tail 30]
  factoryctl metrics
  factoryctl inspect <job_id>
  factoryctl retry <job_id>
  factoryctl queue
  factoryctl version
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running from any working directory
sys.path.insert(0, str(Path(__file__).parent))

from core.config import ensure_dirs, LOGS_DIR, AGENTS_STATE, METRICS_FILE
from core.job_store import JobStore
from core.event_logger import EventLogger
from core.lease_manager import LeaseManager

VERSION = "1.0.0"

# ── colour helpers (no deps) ─────────────────────────────────────────────────
_USE_COLOR = sys.stdout.isatty()

def _c(text, code):  return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text
def green(t):        return _c(t, "32")
def amber(t):        return _c(t, "33")
def red(t):          return _c(t, "31")
def blue(t):         return _c(t, "34")
def cyan(t):         return _c(t, "36")
def bold(t):         return _c(t, "1")
def muted(t):        return _c(t, "2")

PHASE_COLOR = {
    "created":     muted,
    "writing":     blue,
    "visualizing": cyan,
    "voice":       cyan,
    "assembling":  amber,
    "complete":    green,
    "failed":      red,
}

def phase_str(p):
    fn = PHASE_COLOR.get(p, lambda x: x)
    return fn(p)

# ── commands ─────────────────────────────────────────────────────────────────

def cmd_new_job(args):
    ensure_dirs()
    store = JobStore()
    template = getattr(args, "template", None) or ""
    try:
        job = store.create(topic=args.topic, priority=args.priority, template=template)
    except RuntimeError as e:
        print(red(f"✗ {e}"))
        print()
        print(f"  {muted('Tip:')} run {bold('factoryctl status')} to see current queue depth.")
        sys.exit(1)
    print(f"{green('✓')} Job created")
    print(f"  {muted('job_id')}   {job['job_id']}")
    print(f"  {muted('topic')}    {job['topic']}")
    print(f"  {muted('priority')} {job['priority']}")
    print(f"  {muted('status')}   {job['status']}")
    print()
    print(f"  {muted('Next:')} start the foreman service to begin processing.")


def cmd_status(args):
    store = JobStore()
    if args.job_id:
        job = store.load(args.job_id)
        if not job:
            print(red(f"✗ Job '{args.job_id}' not found"))
            sys.exit(1)
        _print_job_detail(job)
    else:
        _print_queue_overview(store)


def _print_queue_overview(store: JobStore):
    depths = store.queue_depth()
    print()
    print(bold("  Queue"))
    print(f"  {'inbox':<12} {blue(str(depths.get('inbox',0)))}")
    print(f"  {'active':<12} {green(str(depths.get('active',0)))}")
    print(f"  {'completed':<12} {cyan(str(depths.get('completed',0)))}")
    print(f"  {'failed':<12} {red(str(depths.get('failed',0)))}")

    active = store.load_all_active()
    if active:
        print()
        print(bold("  Active jobs"))
        for j in active:
            _print_job_row(j)

    inbox = store.load_all_inbox()
    if inbox:
        print()
        print(bold("  Inbox"))
        for j in inbox[:10]:
            _print_job_row(j)
        if len(inbox) > 10:
            print(f"  {muted(f'… {len(inbox)-10} more')}")
    print()


def _print_job_row(job: dict):
    jid    = muted(job['job_id'][-14:])
    topic  = job.get('topic','')[:48]
    phase  = phase_str(job.get('phase','?'))
    agent  = muted(job.get('assigned_agent') or '—')
    retries = job.get('retry_count', 0)
    retry_str = f" {amber(f'↻{retries}')}" if retries else ''
    print(f"  {jid}  {phase:<18}  {agent:<20}  {topic}{retry_str}")


def _print_job_detail(job: dict):
    print()
    print(bold(f"  {job['job_id']}"))
    print(f"  {muted('topic')}      {job.get('topic','')}")
    print(f"  {muted('status')}     {job.get('status','')}")
    print(f"  {muted('phase')}      {phase_str(job.get('phase','?'))}")
    print(f"  {muted('priority')}   {job.get('priority',5)}")
    print(f"  {muted('retries')}    {job.get('retry_count',0)} / {job.get('max_retries',3)}")
    print(f"  {muted('agent')}      {job.get('assigned_agent') or '—'}")
    print(f"  {muted('created')}    {job.get('created_at','')[:19]}")
    print(f"  {muted('updated')}    {job.get('updated_at','')[:19]}")

    arts = job.get('artifacts', {})
    print()
    print(bold("  Artifacts"))
    for k, v in arts.items():
        if k == 'images':
            val = f"{len(v)} image(s)" if v else muted('—')
        else:
            val = green('✓ ' + Path(v).name) if v else muted('—')
        print(f"  {k:<14} {val}")

    metrics = job.get('metrics', {})
    non_null = {k: v for k, v in metrics.items() if v is not None}
    if non_null:
        print()
        print(bold("  Metrics"))
        for k, v in non_null.items():
            print(f"  {k:<32} {v}s")

    errors = job.get('errors', [])
    if errors:
        print()
        print(bold(red(f"  Errors ({len(errors)})")))
        for e in errors[-5:]:
            print(f"  {muted(e.get('timestamp','')[:19])}  {red(e.get('error',''))}")
    print()


def cmd_queue(args):
    store = JobStore()
    _print_queue_overview(store)


def cmd_agents(args):
    if not AGENTS_STATE.exists():
        print(amber("  No agent state files found. Are agents running?"))
        return
    now = datetime.now(timezone.utc)
    print()
    print(bold("  Agents"))
    print(f"  {'name':<20} {'status':<14} {'job':<26} {'cpu':>6} {'mem':>8} {'hb':>8}")
    print(f"  {muted('─'*20)} {muted('─'*14)} {muted('─'*26)} {muted('─'*6)} {muted('─'*8)} {muted('─'*8)}")
    for p in sorted(AGENTS_STATE.glob("*.json")):
        try:
            rec     = json.loads(p.read_text())
            aid     = rec.get('agent_id', p.stem)
            status  = rec.get('status', '?')
            job     = (rec.get('current_job') or '—')[-22:]
            cpu     = f"{rec.get('cpu_percent',0):.1f}%"
            mem     = f"{rec.get('memory_mb',0)}MB"
            ts      = rec.get('timestamp','')
            age_s   = 0
            if ts:
                age_s = (now - datetime.fromisoformat(ts)).total_seconds()
            hb      = f"{age_s:.0f}s"
            stale   = age_s > 30

            dot = green('●') if status == 'processing' else \
                  blue('●')  if status == 'running'    else \
                  red('●')   if stale                  else \
                  muted('○')
            status_str = red(status) if stale else \
                         green(status) if status in ('processing','running') else \
                         muted(status)
            hb_str = red(hb) if stale else muted(hb)
            print(f"  {dot} {aid:<18} {status_str:<22} {muted(job):<34} {muted(cpu):>14} {muted(mem):>16} {hb_str:>16}")
        except Exception:
            pass
    print()


def cmd_logs(args):
    agent_id = args.agent_id
    tail_n   = args.tail

    if agent_id:
        log_path = LOGS_DIR / f"{agent_id}.log"
        if not log_path.exists():
            print(red(f"  Log not found: {log_path}"))
            sys.exit(1)
        _tail_file(log_path, tail_n)
    else:
        # List available logs
        logs = sorted(LOGS_DIR.glob("*.log"))
        if not logs:
            print(amber("  No log files found yet."))
            return
        print()
        print(bold("  Available logs"))
        for p in logs:
            size = p.stat().st_size
            lines = sum(1 for _ in p.open())
            print(f"  {p.name:<30} {muted(f'{lines} lines, {size//1024}KB')}")
        print()
        print(f"  {muted('Run:')} factoryctl logs <agent_id> [--tail N]")
        print()


def _tail_file(path: Path, n: int):
    lines = path.read_text().splitlines()
    print()
    for line in lines[-n:]:
        # Colour-code log levels
        if ' ERROR ' in line:    print(red(line))
        elif ' WARNING ' in line: print(amber(line))
        elif ' DEBUG ' in line:   print(muted(line))
        else:                     print(line)
    print()


def cmd_events(args):
    log   = EventLogger()
    evts  = log.tail(args.tail)
    if not evts:
        print(amber("  No events recorded yet."))
        return
    print()
    print(bold(f"  Last {len(evts)} events"))
    print(f"  {muted('timestamp'[:19]):<20} {muted('agent'):<20} {muted('type'):<16} {muted('phase'):<14} {muted('message')}")
    print(f"  {muted('─'*19)} {muted('─'*20)} {muted('─'*16)} {muted('─'*14)} {muted('─'*30)}")
    for e in evts:
        ts    = e.get('timestamp','')[:19].replace('T',' ')
        agent = e.get('agent_id','')[:18]
        etype = e.get('event_type','')
        phase = e.get('phase','')[:12]
        msg   = e.get('message','')[:60]
        etype_str = green(etype)   if etype == 'complete'  else \
                    blue(etype)    if etype == 'start'      else \
                    red(etype)     if 'error' in etype or 'fail' in etype else \
                    amber(etype)   if 'expire' in etype or 'retry' in etype else \
                    cyan(etype)    if 'lease' in etype      else \
                    muted(etype)
        print(f"  {muted(ts):<28} {blue(agent):<28} {etype_str:<24} {muted(phase):<22} {msg}")
    print()


def cmd_metrics(args):
    if not METRICS_FILE.exists():
        print(amber("  No metrics file found. Is monitor_agent running?"))
        sys.exit(1)
    data = json.loads(METRICS_FILE.read_text())
    sys  = data.get('system', {})
    q    = data.get('queue_depth', {})
    t    = data.get('throughput', {})
    ts   = data.get('timestamp','')[:19].replace('T',' ')

    print()
    print(bold(f"  System  {muted(ts)}"))
    _bar("CPU",    sys.get('cpu_percent', 0),     100, "%",
         f"{sys.get('cpu_percent',0):.1f}% of {sys.get('cpu_count',1)} cores")
    _bar("Memory", sys.get('memory_used_mb', 0),  sys.get('memory_total_mb', 1), "MB",
         f"{sys.get('memory_used_mb',0)} / {sys.get('memory_total_mb',0)} MB  ({sys.get('memory_percent',0):.0f}%)")
    _bar("Disk",   sys.get('disk_used_gb', 0),    sys.get('disk_total_gb', 1), "GB",
         f"{sys.get('disk_used_gb',0)} / {sys.get('disk_total_gb',0)} GB  ({sys.get('disk_percent',0):.0f}%)")

    print()
    print(bold("  Queue"))
    print(f"  inbox={blue(str(q.get('inbox',0)))}  "
          f"active={green(str(q.get('active',0)))}  "
          f"completed={cyan(str(q.get('completed',0)))}  "
          f"failed={red(str(q.get('failed',0)))}")

    print()
    print(bold("  Throughput"))
    print(f"  Completed:    {cyan(str(t.get('total_completed',0)))} jobs")
    print(f"  Failed:       {red(str(t.get('total_failed',0)))} jobs")
    print(f"  Avg duration: {t.get('avg_job_duration_s',0)}s/job")
    pp = t.get('avg_per_phase_s', {})
    if pp:
        for k, v in pp.items():
            short = k.replace('_duration_s','').replace('_',' ')
            print(f"    {short:<20} {muted(str(v)+'s')}")
    print()


def _bar(label: str, value: float, total: float, unit: str, detail: str = ""):
    pct  = min(value / total, 1.0) if total else 0
    fill = int(pct * 20)
    bar  = green('█' * fill) + muted('░' * (20 - fill))
    print(f"  {label:<8} [{bar}]  {detail}")


def cmd_inspect(args):
    # Alias for status <job_id>
    store = JobStore()
    job   = store.load(args.job_id)
    if not job:
        print(red(f"✗ Job '{args.job_id}' not found"))
        sys.exit(1)
    _print_job_detail(job)

    # Also show events for this job
    evts = EventLogger().events_for_job(args.job_id)
    if evts:
        print(bold(f"  Events ({len(evts)})"))
        for e in evts:
            ts    = e.get('timestamp','')[:19].replace('T',' ')
            etype = e.get('event_type','')
            phase = e.get('phase','')
            msg   = e.get('message','')
            print(f"  {muted(ts)}  {muted(etype):<16}  {muted(phase):<14}  {msg}")
        print()


def cmd_retry(args):
    store = JobStore()
    job   = store.load(args.job_id)
    if not job:
        print(red(f"✗ Job '{args.job_id}' not found"))
        sys.exit(1)
    if job.get('status') not in ('failed', 'pending'):
        print(amber(f"  Job is in status='{job['status']}' — only failed or pending jobs can be retried"))
        sys.exit(1)
    # Reset to beginning of pipeline
    job['retry_count'] = 0
    job['phase']       = 'created'
    job['status']      = 'pending'
    job['lease']       = None
    job['assigned_agent'] = None
    job['errors']      = []

    # Move to inbox if not already there
    from core.config import FAILED_DIR, INBOX_DIR, ACTIVE_DIR
    import shutil
    for base in [FAILED_DIR, ACTIVE_DIR]:
        src = base / args.job_id
        if src.exists():
            dst = INBOX_DIR / args.job_id
            shutil.move(str(src), str(dst))
            (dst / "job.json").write_text(json.dumps(job, indent=2))
            break
    else:
        store.save(job)

    print(green(f"✓ Job {args.job_id} re-queued"))
    print(f"  {muted('phase')}  created → writing")
    print(f"  {muted('The foreman will pick it up on the next tick.')}")



def cmd_list_jobs(args):
    """List jobs across all queues with filtering."""
    store   = JobStore()
    status  = args.status  # None = all

    all_jobs = store.load_all()
    if status:
        all_jobs = [j for j in all_jobs if j.get("status") == status]

    if not all_jobs:
        print(amber(f"  No jobs found" + (f" with status={status}" if status else "")))
        return

    print()
    print(bold(f"  {'job_id':<26} {'phase':<16} {'status':<12} {'priority':>8}  topic"))
    print(f"  {muted('─'*26)} {muted('─'*16)} {muted('─'*12)} {muted('─'*8)}  {muted('─'*40)}")
    for j in all_jobs[:args.limit]:
        jid     = muted(j["job_id"][-22:])
        phase   = phase_str(j.get("phase","?"))
        status_ = j.get("status","?")
        status_str = green(status_) if status_ == "complete" else                      red(status_)   if status_ in ("failed","cancelled") else                      amber(status_) if status_ == "paused" else                      blue(status_)  if status_ == "active" else                      muted(status_)
        pri    = str(j.get("priority", 5))
        topic  = j.get("topic","")[:50]
        print(f"  {jid}  {phase:<18}  {status_str:<20}  {pri:>8}  {topic}")
    if len(all_jobs) > args.limit:
        print(f"  {muted(f'… {len(all_jobs)-args.limit} more (use --limit to show more)')}")
    print()


def cmd_cancel_job(args):
    store = JobStore()
    try:
        job = store.cancel_job(args.job_id, reason=f"cancelled via factoryctl by operator")
    except (FileNotFoundError, ValueError) as e:
        print(red(f"✗ {e}"))
        sys.exit(1)
    print(green(f"✓ Job {args.job_id[-14:]} cancelled"))
    print(f"  {muted('status')} → {red('cancelled')}")
    print(f"  {muted('Job moved to failed/ queue.')}")


def cmd_pause_job(args):
    store = JobStore()
    try:
        job = store.pause_job(args.job_id)
    except (FileNotFoundError, ValueError) as e:
        print(red(f"✗ {e}"))
        sys.exit(1)
    print(amber(f"⏸  Job {args.job_id[-14:]} paused"))
    print(f"  {muted('Foreman will skip this job until resumed.')}")


def cmd_resume_job(args):
    store = JobStore()
    try:
        job = store.resume_job(args.job_id)
    except (FileNotFoundError, ValueError) as e:
        print(red(f"✗ {e}"))
        sys.exit(1)
    print(green(f"▶  Job {args.job_id[-14:]} resumed"))
    print(f"  {muted('Foreman will schedule it on the next tick.')}")


def cmd_pause_agent(args):
    from core.config import AGENTS_STATE
    sig = AGENTS_STATE / f"{args.agent_id}.signal"
    sig.parent.mkdir(parents=True, exist_ok=True)
    sig.write_text("pause")
    print(amber(f"⏸  Pause signal sent to {args.agent_id}"))
    print(f"  {muted('Agent will stop accepting new leases after current job.')}")
    print(f"  {muted('Run')} factoryctl resume-agent {args.agent_id} {muted('to unpause.')}")


def cmd_resume_agent(args):
    from core.config import AGENTS_STATE
    sig = AGENTS_STATE / f"{args.agent_id}.signal"
    sig.unlink(missing_ok=True)
    print(green(f"▶  Resume signal sent to {args.agent_id}"))
    print(f"  {muted('Agent will resume accepting leases on next poll.')}")


def cmd_retry_job(args):
    """Alias for cmd_retry — matches spec command name."""
    cmd_retry(args)

def cmd_version(args):
    print(f"  factoryctl {bold(VERSION)}")
    print(f"  {muted('AI Automated Content Factory')}")


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        prog="factoryctl",
        description="AI Automated Content Factory — control tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
job commands:
  new-job       Submit a new job (--template, --priority)
  list-jobs     List all jobs (--status filter, --limit)
  inspect       Deep-inspect a job (artifacts + events)
  retry-job     Re-queue a failed job from the beginning
  cancel-job    Cancel a pending or active job
  pause-job     Pause a pending job (foreman will skip it)
  resume-job    Resume a paused job

agent commands:
  agents        Show agent health and heartbeat state
  pause-agent   Send pause signal to an agent
  resume-agent  Clear pause signal from an agent

system commands:
  events        Tail the structured event log (--tail N)
  logs          Tail an agent log file (--tail N)
  metrics       System resource snapshot
  status        Queue overview or specific job detail
        """,
    )
    sub = p.add_subparsers(dest="command", required=True)

    # new-job
    s = sub.add_parser("new-job", help="Submit a new job")
    s.add_argument("topic", help="Topic or idea")
    s.add_argument("--priority", type=int, default=5, metavar="1-10",
                   help="Scheduling priority 1-10 (default 5)")
    s.add_argument("--template", default="",
                   choices=["", "educational_video", "short_form_video", "tutorial_video"],
                   metavar="TEMPLATE",
                   help="Pipeline template: educational_video, short_form_video, tutorial_video")

    # status
    s = sub.add_parser("status", help="Queue overview or specific job")
    s.add_argument("job_id", nargs="?", help="Specific job ID (optional)")

    # queue
    sub.add_parser("queue", help="Show queue depth")

    # agents
    sub.add_parser("agents", help="Show agent health")

    # logs
    s = sub.add_parser("logs", help="Tail agent logs")
    s.add_argument("agent_id", nargs="?",
                   help="Agent ID (e.g. writer_agent). Omit to list all logs.")
    s.add_argument("--tail", type=int, default=50, help="Lines to show (default 50)")

    # events
    s = sub.add_parser("events", help="Tail the event log")
    s.add_argument("--tail", type=int, default=30, help="Events to show (default 30)")

    # metrics
    sub.add_parser("metrics", help="System metrics snapshot")

    # inspect
    s = sub.add_parser("inspect", help="Deep-inspect a job")
    s.add_argument("job_id", help="Job ID to inspect")

    # retry (original name)
    s = sub.add_parser("retry", help="Re-queue a failed job from the beginning")
    s.add_argument("job_id", help="Job ID to retry")

    # retry-job (spec alias)
    s = sub.add_parser("retry-job", help="Re-queue a failed job (alias for retry)")
    s.add_argument("job_id", help="Job ID to retry")

    # list-jobs
    s = sub.add_parser("list-jobs", help="List all jobs across all queues")
    s.add_argument("--status", choices=["pending","active","complete","failed","cancelled","paused"],
                   help="Filter by status")
    s.add_argument("--limit", type=int, default=50, help="Max rows to show (default 50)")

    # cancel-job
    s = sub.add_parser("cancel-job", help="Cancel a pending or active job")
    s.add_argument("job_id", help="Job ID to cancel")

    # pause-job
    s = sub.add_parser("pause-job", help="Pause a pending inbox job")
    s.add_argument("job_id", help="Job ID to pause")

    # resume-job
    s = sub.add_parser("resume-job", help="Resume a paused job")
    s.add_argument("job_id", help="Job ID to resume")

    # pause-agent
    s = sub.add_parser("pause-agent", help="Send pause signal to an agent")
    s.add_argument("agent_id", help="Agent ID (e.g. writer_agent)")

    # resume-agent
    s = sub.add_parser("resume-agent", help="Clear pause signal from an agent")
    s.add_argument("agent_id", help="Agent ID (e.g. writer_agent)")

    # version
    sub.add_parser("version", help="Show version")

    args = p.parse_args()
    dispatch = {
        "new-job":      cmd_new_job,
        "list-jobs":    cmd_list_jobs,
        "cancel-job":   cmd_cancel_job,
        "pause-job":    cmd_pause_job,
        "resume-job":   cmd_resume_job,
        "retry-job":    cmd_retry_job,
        "pause-agent":  cmd_pause_agent,
        "resume-agent": cmd_resume_agent,
        "status":       cmd_status,
        "queue":        cmd_queue,
        "agents":       cmd_agents,
        "logs":         cmd_logs,
        "events":       cmd_events,
        "metrics":      cmd_metrics,
        "inspect":      cmd_inspect,
        "retry":        cmd_retry,
        "version":      cmd_version,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
