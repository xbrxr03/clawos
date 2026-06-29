# SPDX-License-Identifier: AGPL-3.0-or-later
"""clawctl status - show all service health, nicely."""

import os
import json
import subprocess
import urllib.request
from pathlib import Path

from clawos_core.constants import OLLAMA_HOST

PURPLE = "\033[38;5;141m"
GREEN = "\033[38;5;84m"
RED = "\033[38;5;203m"
AMBER = "\033[38;5;220m"
BLUE = "\033[38;5;75m"
DIM = "\033[2m"
GREY = "\033[38;5;245m"
BOLD = "\033[1m"
RESET = "\033[0m"

# All ClawOS services: (name, port, description, type)
# type: "http" = serves HTTP health, "daemon" = async daemon (no HTTP)
SERVICES = [
    ("dashd", 7070, "Dashboard", "http"),
    ("clawd", 7071, "Core Engine", "daemon"),
    ("agentd", 7072, "Agent Service", "daemon"),
    ("memd", 7073, "Memory Service", "daemon"),
    ("policyd", 7074, "Policy Engine", "daemon"),
    ("modeld", 7075, "Model Manager", "daemon"),
    ("metricd", 7076, "Metrics", "daemon"),
    ("mcpd", 7077, "MCP Server", "http"),
    ("observd", 7078, "Observability", "http"),
    ("voiced", 7079, "Voice Pipeline", "http"),
    ("desktopd", 7080, "Desktop Automation", "http"),
    ("agentd_v2", 7081, "Multi-Agent", "http"),
    ("braind", 7082, "Second Brain", "http"),
    ("a2ad", 7083, "A2A Protocol", "http"),
    ("sandboxd", 7085, "Secure Sandbox", "http"),
    ("visuald", 7086, "Visual Workflows", "http"),
    ("reminderd", 7087, "Reminders", "http"),
    ("waketrd", 7088, "Wake Word", "http"),
    ("researchd", 7089, "Deep Research", "http"),
    ("noted", 7091, "Notes", "http"),
    ("calendard", 7092, "Calendar", "http"),
    ("maild", 7093, "Email", "http"),
]


def _ok(text):
    return f"{GREEN}[OK]{RESET} {text}"


def _fail(text):
    return f"{RED}[X]{RESET} {text}"


def _warn(text):
    return f"{AMBER}[?]{RESET} {text}"


def _dim(text):
    return f"{DIM}{GREY}{text}{RESET}"


def _http_get(url, timeout=2):
    """Try HTTP GET, return (status_code, body) or None."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ClawOS-Status/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode()[:200]
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return None, None


def _check_service(name, port, svc_type):
    """Check a single service. Returns (status, detail_str)."""
    if svc_type == "http":
        # Try /api/health first, then /health
        for path in ["/api/health", "/health"]:
            code, body = _http_get(f"http://127.0.0.1:{port}{path}")
            if code == 200 and body:
                try:
                    data = json.loads(body)
                    # Extract useful detail
                    detail = data.get("service", "")
                    features = data.get("features", {})
                    if features:
                        feat_str = ", ".join(k for k, v in features.items() if v)
                        if feat_str:
                            detail = f"{detail} ({feat_str})"
                    return "up", detail or "running"
                except (json.JSONDecodeError, ValueError):
                    return "up", "running"
        # No HTTP response - check PID file
        return _check_pid(name), ""
    else:
        # Daemon service - check PID file first, then process list
        status, detail = _check_pid(name)
        if status == "up":
            return status, "daemon (no HTTP)"
        # Fallback: check if any process is listening on this port
        try:
            result = subprocess.run(
                ["lsof", "-i", f":{port}", "-t"],
                capture_output=True, text=True, timeout=2,
            )
            if result.stdout.strip():
                return "up", "daemon (no HTTP)"
        except Exception:
            pass
        return "down", ""


def _check_pid(name):
    """Check PID file for a service. Returns (status, detail)."""
    pid_file = Path.home() / ".clawos" / "run" / "dev_boot.pid"
    if pid_file.exists():
        for line in pid_file.read_text().strip().splitlines():
            parts = line.split(":")
            if len(parts) >= 2 and parts[0] == name:
                try:
                    pid = int(parts[1])
                    os.kill(pid, 0)
                    return "up", f"PID {pid}"
                except (ProcessLookupError, PermissionError, ValueError):
                    return "down", "process dead"
    return "unknown", ""


def run():
    print()
    print(f"  {PURPLE}{BOLD}CLAWOS{RESET}  {_dim('service status')}")
    print(f"  {_dim('-' * 52)}")
    print()

    # Check Ollama
    ollama_code, _ = _http_get(f"{OLLAMA_HOST}/api/tags")
    if ollama_code:
        print("  " + _ok(f"{BLUE}ollama{RESET}       running  {_dim(OLLAMA_HOST)}"))
        try:
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
            models = [line.split()[0] for line in result.stdout.strip().splitlines()[1:] if line.strip()]
            if models:
                print(f"     {_dim('models:')} {AMBER}{', '.join(models[:4])}{RESET}")
        except (subprocess.SubprocessError, OSError):
            pass
    else:
        print("  " + _fail(f"{BLUE}ollama{RESET}       not running"))

    # Check dashboard
    dash_code, _ = _http_get("http://127.0.0.1:7070/api/health")
    if dash_code == 200:
        print("  " + _ok(f"{PURPLE}dashboard{RESET}    {_dim('http://localhost:7070')}"))
    else:
        print("  " + _fail(f"{PURPLE}dashboard{RESET}    not running"))

    print()
    print(f"  {BOLD}Services:{RESET}")
    print(f"  {_dim('-' * 52)}")

    up_count = 0
    down_count = 0
    for name, port, desc, svc_type in SERVICES:
        status, detail = _check_service(name, port, svc_type)
        if status == "up":
            up_count += 1
            detail_str = f"  {_dim(detail)}" if detail else ""
            print(f"  {GREEN}*{RESET} {name:<13} :{port}  {desc}{detail_str}")
        elif status == "unknown":
            print(f"  {AMBER}?{RESET} {name:<13} :{port}  {desc}  {_dim('unknown')}")
        else:
            down_count += 1
            print(f"  {RED}x{RESET} {name:<13} :{port}  {desc}  {_dim('down')}")

    print(f"  {_dim('-' * 52)}")
    total = len(SERVICES)
    print(f"  {BOLD}{up_count}{RESET}/{total} services up" + (f"  {RED}{down_count} down{RESET}" if down_count else ""))
    print()
    print(f"  {_dim('clawctl start    - start all services')}")
    print(f"  {_dim('clawctl dashboard - live dashboard')}")
    print()