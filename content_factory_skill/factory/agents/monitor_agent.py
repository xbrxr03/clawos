"""
monitor_agent.py — system telemetry collection + HTTP health endpoint.

Responsibilities:
  - Every MONITOR_TICK seconds: collect CPU, RAM, disk, queue depth,
    agent heartbeats, and job runtimes → write state/metrics/system.json
  - Serves HTTP API + dashboard on port 7000 (stdlib only):
      GET  /                    → inspector.html dashboard
      GET  /health              → full system snapshot
      GET  /agents              → agent health dict
      GET  /jobs                → all jobs (all queues)
      GET  /jobs/<id>           → single job detail + artifacts
      GET  /jobs/<id>/artifact/<name> → raw artifact file
      GET  /jobs/<id>/logs      → agent log tail for job
      GET  /events?tail=N       → last N events
      GET  /metrics             → system resource metrics
      POST /api/jobs            → create job  {topic, priority}
      POST /api/jobs/<id>/retry  → retry job
      POST /api/jobs/<id>/cancel → cancel job
      POST /api/jobs/<id>/pause  → pause job
      POST /api/jobs/<id>/resume → resume job
      POST /api/agents/<id>/pause   → write pause signal
      POST /api/agents/<id>/resume  → clear pause signal

This agent never requests a lease — it runs its own loop independently.
"""

import json
import logging
import time
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import psutil

from core.config import (
    AGENTS_STATE, METRICS_FILE, LOGS_DIR,
    MONITOR_TICK, HEARTBEAT_INTERVAL,
    COMPLETED_DIR, FAILED_DIR, DASHBOARD_DIR,
    ARTIFACTS_DIR, INBOX_DIR, ACTIVE_DIR,
)
from core.job_store import JobStore as _JobStore
from core.lease_manager import LeaseManager as _LeaseManager
from core.event_logger import EventLogger


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


STALE_THRESHOLD = 30    # seconds — agent considered dead if heartbeat older
HEALTH_PORT     = 7000


# ── HTTP handler ──────────────────────────────────────────────────────────────

class HealthHandler(BaseHTTPRequestHandler):
    """Minimal read-only HTTP API backed by the state JSON files."""

    monitor: "MonitorAgent" = None   # injected before server starts

    def do_GET(self):
        parsed  = urlparse(self.path)
        path    = parsed.path.rstrip("/")
        params  = parse_qs(parsed.query)
        parts   = [p for p in path.split("/") if p]   # e.g. ["jobs","job_123","artifact","script.txt"]

        try:
            # ── Dashboard UI ──────────────────────────────────────────────────
            if path in ("", "/dashboard", "/inspector"):
                self._static(DASHBOARD_DIR / "inspector.html", "text/html")

            # ── Single job detail  GET /jobs/<id> ─────────────────────────────
            elif len(parts) == 2 and parts[0] == "jobs":
                store = _JobStore()
                job   = store.load(parts[1])
                if not job:
                    self._error(404, f"Job {parts[1]} not found")
                    return
                # Attach artifact file list
                art_dir = ARTIFACTS_DIR / parts[1]
                files   = sorted(str(p.name) for p in art_dir.glob("*")) if art_dir.exists() else []
                job["_artifact_files"] = files
                self._json(job)

            # ── Serve raw artifact  GET /jobs/<id>/artifact/<name> ────────────
            elif len(parts) == 4 and parts[0] == "jobs" and parts[2] == "artifact":
                art_path = ARTIFACTS_DIR / parts[1] / parts[3]
                if not art_path.exists():
                    self._error(404, f"Artifact {parts[3]} not found")
                    return
                suffix = art_path.suffix.lower()
                ctype  = {
                    ".txt":  "text/plain",
                    ".json": "application/json",
                    ".png":  "image/png",
                    ".jpg":  "image/jpeg",
                    ".wav":  "audio/wav",
                    ".mp3":  "audio/mpeg",
                }.get(suffix, "application/octet-stream")
                body = art_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)

            # ── Agent log for a job  GET /jobs/<id>/logs ──────────────────────
            elif len(parts) == 3 and parts[0] == "jobs" and parts[2] == "logs":
                store = _JobStore()
                job   = store.load(parts[1])
                agent = (job or {}).get("assigned_agent") if job else None
                logs  = []
                for log_file in LOGS_DIR.glob("*.log"):
                    try:
                        lines = log_file.read_text().splitlines()
                        job_lines = [l for l in lines if parts[1] in l]
                        logs.extend(job_lines[-50:])
                    except Exception:
                        pass
                self._json({"job_id": parts[1], "lines": logs[-100:]})

            # ── All jobs  GET /jobs ───────────────────────────────────────────
            elif path == "/jobs":
                store = _JobStore()
                self._json({
                    "active":    store.load_all_active(),
                    "inbox":     store.load_all_inbox(),
                    "completed": self._load_recent(COMPLETED_DIR, 20),
                    "failed":    self._load_recent(FAILED_DIR, 20),
                    "depth":     store.queue_depth(),
                })

            # ── API endpoints ─────────────────────────────────────────────────
            elif path == "/health":
                self._json(self.monitor.last_snapshot or {"status": "starting"})
            elif path == "/agents":
                snap = self.monitor.last_snapshot or {}
                self._json(snap.get("agent_health", {}))
            elif path == "/events":
                tail_n = int(params.get("tail", ["50"])[0])
                self._json(EventLogger().tail(tail_n))
            elif path == "/metrics":
                snap = self.monitor.last_snapshot or {}
                self._json(snap.get("system", {}))
            elif path == "/favicon.ico":
                # Return a minimal inline SVG favicon
                svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#2dd4bf" stroke-width="2"><path d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18"/></svg>'
                self.send_response(200)
                self.send_header("Content-Type", "image/svg+xml")
                self.send_header("Content-Length", str(len(svg)))
                self.end_headers()
                self.wfile.write(svg)
            else:
                self._error(404, f"Unknown endpoint: {path}")
        except Exception as exc:
            import traceback
            self._error(500, str(exc) + "\n" + traceback.format_exc())

    def _load_recent(self, directory: Path, n: int) -> list[dict]:
        jobs = []
        for p in sorted(directory.glob("*/job.json"),
                        key=lambda x: x.stat().st_mtime, reverse=True)[:n]:
            try:
                jobs.append(json.loads(p.read_text()))
            except Exception:
                pass
        return jobs

    def _static(self, file_path: Path, content_type: str):
        if not file_path.exists():
            self._error(404, f"File not found: {file_path.name}")
            return
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data):
        body = json.dumps(data, indent=2).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, code: int, msg: str):
        body = json.dumps({"error": msg}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        """CORS preflight — allow browser fetch from any origin."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        parsed  = urlparse(self.path)
        path    = parsed.path.rstrip("/")
        parts   = [p for p in path.split("/") if p]
        length  = int(self.headers.get("Content-Length", 0))
        body    = json.loads(self.rfile.read(length)) if length else {}

        try:
            # ── Create job  POST /api/jobs ────────────────────────────────────
            if path == "/api/jobs":
                topic = (body.get("topic") or "").strip()
                if not topic:
                    self._error(400, "topic is required")
                    return
                priority = int(body.get("priority", 5))
                template = (body.get("template") or "").strip()
                store    = _JobStore()
                job      = store.create(topic=topic, priority=priority, template=template)
                EventLogger().emit(job["job_id"], "api", "start", "created",
                                   f"Job created via API: {topic[:60]}")
                self._json({"ok": True, "job": job})

            # ── Job actions  POST /api/jobs/<id>/<action> ─────────────────────
            elif len(parts) == 4 and parts[0] == "api" and parts[1] == "jobs":
                job_id = parts[2]
                action = parts[3]
                store  = _JobStore()
                lm     = _LeaseManager()

                if action == "retry":
                    lm.release_lease(job_id, "")   # clean any stale lease
                    job = store.mark_retry(job_id)
                    EventLogger().emit(job_id, "api", "retry", job["phase"], "Retried via API")
                    self._json({"ok": True, "job": job})

                elif action == "cancel":
                    lm.release_lease(job_id, "")
                    job = store.cancel_job(job_id, "cancelled via dashboard")
                    EventLogger().emit(job_id, "api", "failed", job["phase"], "Cancelled via API")
                    self._json({"ok": True, "job": job})

                elif action == "pause":
                    job = store.pause_job(job_id)
                    EventLogger().emit(job_id, "api", "start", job["phase"], "Paused via API")
                    self._json({"ok": True, "job": job})

                elif action == "resume":
                    job = store.resume_job(job_id)
                    EventLogger().emit(job_id, "api", "start", job["phase"], "Resumed via API")
                    self._json({"ok": True, "job": job})

                else:
                    self._error(404, f"Unknown job action: {action}")

            # ── Agent control  POST /api/agents/<id>/<action> ────────────────
            elif len(parts) == 4 and parts[0] == "api" and parts[1] == "agents":
                agent_id = parts[2]
                action   = parts[3]
                sig_path = AGENTS_STATE / f"{agent_id}.signal"

                if action == "pause":
                    sig_path.write_text("pause")
                    self._json({"ok": True, "agent": agent_id, "signal": "pause"})
                elif action == "resume":
                    sig_path.unlink(missing_ok=True)
                    self._json({"ok": True, "agent": agent_id, "signal": "resumed"})
                else:
                    self._error(404, f"Unknown agent action: {action}")

            else:
                self._error(404, f"Unknown POST endpoint: {path}")

        except (ValueError, FileNotFoundError) as exc:
            self._error(400, str(exc))
        except Exception as exc:
            self._error(500, str(exc))

    def log_message(self, fmt, *args):
        pass  # silence default access log


# ── MonitorAgent ──────────────────────────────────────────────────────────────

class MonitorAgent:
    AGENT_ID = "monitor_agent"

    def __init__(self):
        self.job_store     = _JobStore()
        self.event_logger  = EventLogger()
        self._proc         = psutil.Process()
        self.logger        = self._build_logger()
        self._last_hb      = 0.0
        self.last_snapshot: dict | None = None

    def run(self):
        self._register()
        self.logger.info(f"[monitor] started — health endpoint http://localhost:{HEALTH_PORT}")
        self._start_http_server()

        while True:
            now = time.monotonic()
            if now - self._last_hb >= HEARTBEAT_INTERVAL:
                self._publish_heartbeat()
                self._last_hb = now
            self._collect_and_write()
            time.sleep(MONITOR_TICK)

    def _start_http_server(self):
        HealthHandler.monitor = self
        server = HTTPServer(("0.0.0.0", HEALTH_PORT), HealthHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        self.logger.info(f"[monitor] HTTP server on :{HEALTH_PORT}")

    # ── collection ────────────────────────────────────────────────────────────

    def _collect_and_write(self):
        snapshot = {
            "timestamp":    _now(),
            "system":       self._system_metrics(),
            "queue_depth":  self.job_store.queue_depth(),
            "active_jobs":  self._active_jobs(),
            "agent_health": self._agent_health(),
            "throughput":   self._throughput(),
        }
        self.last_snapshot = snapshot
        METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = METRICS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(snapshot, indent=2))
        tmp.replace(METRICS_FILE)

    def _system_metrics(self) -> dict:
        vm   = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        cpu  = psutil.cpu_percent(interval=1)
        return {
            "cpu_percent":         cpu,
            "cpu_count":           psutil.cpu_count(),
            "memory_used_mb":      vm.used      // (1024 * 1024),
            "memory_total_mb":     vm.total     // (1024 * 1024),
            "memory_available_mb": vm.available // (1024 * 1024),
            "memory_percent":      vm.percent,
            "disk_used_gb":        round(disk.used  / (1024 ** 3), 2),
            "disk_total_gb":       round(disk.total / (1024 ** 3), 2),
            "disk_free_gb":        round(disk.free  / (1024 ** 3), 2),
            "disk_percent":        disk.percent,
        }

    def _active_jobs(self) -> list[dict]:
        return [
            {
                "job_id":  j["job_id"],
                "topic":   j.get("topic", ""),
                "phase":   j.get("phase", ""),
                "agent":   j.get("assigned_agent", ""),
                "retries": j.get("retry_count", 0),
            }
            for j in self.job_store.load_all_active()
        ]

    def _agent_health(self) -> dict:
        health = {}
        ts_now = datetime.now(timezone.utc)
        for p in AGENTS_STATE.glob("*.json"):
            try:
                rec      = json.loads(p.read_text())
                agent_id = rec.get("agent_id", p.stem)
                last_hb  = rec.get("timestamp", "")
                age_s    = 0.0
                if last_hb:
                    age_s = (ts_now - datetime.fromisoformat(last_hb)).total_seconds()
                health[agent_id] = {
                    "status":          rec.get("status", "unknown"),
                    "current_job":     rec.get("current_job"),
                    "cpu_percent":     rec.get("cpu_percent", 0),
                    "memory_mb":       rec.get("memory_mb", 0),
                    "last_heartbeat":  last_hb,
                    "heartbeat_age_s": round(age_s, 1),
                    "stale":           age_s > STALE_THRESHOLD,
                }
            except Exception:
                pass
        return health

    def _throughput(self) -> dict:
        completed_count = sum(1 for _ in COMPLETED_DIR.glob("*/job.json"))
        failed_count    = sum(1 for _ in FAILED_DIR.glob("*/job.json"))

        total_dur   = 0.0
        count       = 0
        phase_totals: dict[str, float] = {}
        phase_keys  = [
            "writing_duration_s", "visualizing_duration_s",
            "voice_duration_s",   "assembling_duration_s",
        ]

        for p in COMPLETED_DIR.glob("*/job.json"):
            try:
                metrics   = json.loads(p.read_text()).get("metrics", {})
                job_total = sum(metrics.get(k) or 0 for k in phase_keys)
                if job_total > 0:
                    total_dur += job_total
                    count     += 1
                for k in phase_keys:
                    v = metrics.get(k) or 0
                    if v:
                        phase_totals[k] = phase_totals.get(k, 0.0) + v
            except Exception:
                pass

        return {
            "total_completed":    completed_count,
            "total_failed":       failed_count,
            "avg_job_duration_s": round(total_dur / count, 1) if count else 0,
            "avg_per_phase_s":    {k: round(v / count, 1) for k, v in phase_totals.items()} if count else {},
        }

    # ── registration / heartbeat ──────────────────────────────────────────────

    def _register(self):
        self._write_state("idle")
        self.event_logger.emit("system", self.AGENT_ID, "registered", "boot",
                               f"Monitor started (health :{HEALTH_PORT})")

    def _publish_heartbeat(self):
        self._write_state("running")

    def _write_state(self, status: str):
        try:
            mem_mb = self._proc.memory_info().rss // (1024 * 1024)
            cpu    = self._proc.cpu_percent(interval=None)
        except psutil.NoSuchProcess:
            mem_mb, cpu = 0, 0.0
        record = {
            "agent_id":    self.AGENT_ID,
            "status":      status,
            "cpu_percent": cpu,
            "memory_mb":   mem_mb,
            "timestamp":   _now(),
        }
        path = AGENTS_STATE / f"{self.AGENT_ID}.json"
        tmp  = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(record, indent=2))
        tmp.replace(path)

    def _build_logger(self) -> logging.Logger:
        log = logging.getLogger(self.AGENT_ID)
        log.setLevel(logging.DEBUG)
        if not log.handlers:
            fh = logging.FileHandler(LOGS_DIR / f"{self.AGENT_ID}.log")
            fh.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s"))
            log.addHandler(fh)
            sh = logging.StreamHandler()
            sh.setFormatter(logging.Formatter(
                "%(asctime)s  [monitor]  %(levelname)s  %(message)s",
                datefmt="%H:%M:%S",
            ))
            log.addHandler(sh)
        return log


if __name__ == "__main__":
    MonitorAgent().run()
