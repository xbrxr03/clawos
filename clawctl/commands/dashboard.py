# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS CLI Dashboard
====================
Terminal-based dashboard for monitoring all ClawOS services.

Usage:
    clawctl dashboard
    clawctl dashboard --watch
"""
import sys
import os
import time
import json
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

# Colors for terminal
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# Service definitions
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


def clear_screen():
    """Clear terminal screen."""
    print('\033[2J\033[H', end='')


def get_health(name: str, port: int) -> Tuple[str, Optional[Dict]]:
    """Get health status for a service.
    
    Tries HTTP health endpoints first, then falls back to PID check
    for daemon services that don't serve HTTP.
    """
    # Try /api/health first (most services), then /health fallback
    for path in ["/api/health", "/health"]:
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}{path}",
                method="GET",
                headers={"User-Agent": "ClawOS-Dashboard/1.0"}
            )
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    try:
                        data = json.loads(resp.read().decode())
                        return "up", data
                    except (json.JSONDecodeError, ValueError):
                        # Got a response but not JSON — service is up
                        return "up", {"status": "up"}
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue  # Try next path
            return f"http_{e.code}", None
        except urllib.error.URLError:
            pass  # Fall through to PID check
        except Exception:
            pass  # Fall through to PID check
    
    # No HTTP response — check if process is alive via PID file
    pid_file = Path.home() / ".clawos" / "run" / "dev_boot.pid"
    if pid_file.exists():
        for line in pid_file.read_text().strip().splitlines():
            parts = line.split(":")
            if len(parts) >= 2 and parts[0] == name:
                try:
                    pid = int(parts[1])
                    os.kill(pid, 0)  # Check if process exists (raises if dead)
                    return "up", {"status": "up", "type": "daemon", "pid": pid}
                except (ProcessLookupError, PermissionError, ValueError):
                    return "down", None
    
    # Check if port is in use by any process
    try:
        import subprocess
        result = subprocess.run(
            ["lsof", "-i", f":{port}", "-t"],
            capture_output=True, text=True, timeout=2
        )
        if result.stdout.strip():
            return "up", {"status": "up", "type": "daemon"}
    except Exception:
        pass
    
    return "down", None


def format_status(status: str) -> str:
    """Format status with colors."""
    if status == "up":
        return f"{Colors.OKGREEN}● UP{Colors.ENDC}"
    elif status == "degraded":
        return f"{Colors.WARNING}● DEGRADED{Colors.ENDC}"
    elif status == "down":
        return f"{Colors.FAIL}● DOWN{Colors.ENDC}"
    else:
        return f"{Colors.FAIL}● {status.upper()}{Colors.ENDC}"


def format_uptime(seconds: float) -> str:
    """Format uptime nicely."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds/60)}m"
    elif seconds < 86400:
        return f"{int(seconds/3600)}h"
    else:
        return f"{int(seconds/86400)}d"


def draw_box(content: List[str], title: str = "", width: int = 40) -> str:
    """Draw ASCII box."""
    lines = []
    
    # Top border
    if title:
        lines.append(f"┌─ {Colors.BOLD}{title}{Colors.ENDC} {'─' * (width - len(title) - 5)}┐")
    else:
        lines.append(f"┌{'─' * width}┐")
    
    # Content
    for line in content:
        padding = width - len(line) - 2
        lines.append(f"│ {line}{' ' * padding}│")
    
    # Bottom border
    lines.append(f"└{'─' * width}┘")
    
    return '\n'.join(lines)


def show_dashboard(watch: bool = False, interval: float = 2.0):
    """Show dashboard."""
    try:
        while True:
            if watch:
                clear_screen()
            
            # Header
            print(f"{Colors.HEADER}{'='*70}{Colors.ENDC}")
            print(f"{Colors.BOLD}{Colors.OKCYAN}  ClawOS Service Dashboard{Colors.ENDC}")
            print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{Colors.HEADER}{'='*70}{Colors.ENDC}")
            print()
            
            # Get all service statuses
            statuses = []
            up_count = 0
            down_count = 0
            
            for name, port, description, svc_type in SERVICES:
                status, data = get_health(name, port)
                # Daemon services are "up" if process is alive, even without HTTP
                if status == "down" and svc_type == "daemon":
                    # get_health already checks PID file and lsof
                    pass  # keep the result from get_health which handles daemon detection
                statuses.append((name, port, description, status, data))
                if status == "up":
                    up_count += 1
                else:
                    down_count += 1
            
            # Summary box
            summary_lines = [
                f"Services: {len(SERVICES)}",
                f"Up: {Colors.OKGREEN}{up_count}{Colors.ENDC}",
                f"Down: {Colors.FAIL}{down_count}{Colors.ENDC}" if down_count > 0 else "Down: 0",
                f"",
                f"Press Ctrl+C to exit" if watch else "",
            ]
            print(draw_box(summary_lines, "Summary", 30))
            print()
            
            # Service table
            print(f"{Colors.BOLD}{'Service':<15} {'Port':<8} {'Status':<15} {'Details'}{Colors.ENDC}")
            print(f"{'-'*15} {'-'*8} {'-'*15} {'-'*30}")
            
            for name, port, description, status, data in statuses:
                status_str = format_status(status)
                
                # Get extra info
                details = ""
                if data:
                    if "tools" in data:
                        details = f"{data['tools']} tools"
                    elif "agents" in data:
                        details = f"{data['agents']} agents"
                    elif "calls" in data:
                        details = f"{data['calls']} calls"
                    elif status == "up":
                        details = "OK"
                else:
                    details = "No response"
                
                print(f"{description:<15} {port:<8} {status_str:<20} {details}")
            
            print()
            
            # Recent activity (from observd)
            try:
                req = urllib.request.Request(
                    "http://127.0.0.1:7078/api/v1/calls?hours=1",
                    method="GET",
                    headers={"User-Agent": "ClawOS-Dashboard/1.0"}
                )
                with urllib.request.urlopen(req, timeout=2) as resp:
                    data = json.loads(resp.read().decode())
                    calls = data.get("calls", [])
                    if calls:
                        print(f"{Colors.BOLD}Recent LLM Calls (last hour):{Colors.ENDC}")
                        for call in calls[:5]:
                            model = call.get("model", "unknown")
                            duration = call.get("duration_ms", 0)
                            print(f"  • {model}: {duration}ms")
                        print()
            except:
                pass
            
            # Performance metrics
            try:
                from clawos_core.performance import monitor
                metrics = monitor.get_all_metrics()
                if metrics:
                    print(f"{Colors.BOLD}Performance Metrics:{Colors.ENDC}")
                    for name, metric in list(metrics.items())[:5]:
                        avg = metric.get("avg_ms", 0)
                        print(f"  • {name}: {avg}ms avg")
                    print()
            except:
                pass
            
            if not watch:
                break
            
            time.sleep(interval)
    
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}Dashboard stopped{Colors.ENDC}")


def show_service_logs(service: str, lines: int = 50):
    """Show logs for a service."""
    import subprocess
    
    # Try journalctl first
    try:
        result = subprocess.run(
            ["journalctl", "-u", f"clawos-{service}", "-n", str(lines)],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(result.stdout)
            return
    except:
        pass
    
    # Fallback to log file
    log_file = f"/var/log/clawos/{service}.log"
    try:
        with open(log_file) as f:
            content = f.readlines()
            print(''.join(content[-lines:]))
    except:
        print(f"No logs found for {service}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="ClawOS Service Dashboard")
    parser.add_argument("--watch", "-w", action="store_true", help="Watch mode")
    parser.add_argument("--interval", "-i", type=float, default=2.0, help="Refresh interval")
    parser.add_argument("--logs", "-l", help="Show logs for service")
    parser.add_argument("--lines", "-n", type=int, default=50, help="Number of log lines")
    
    args = parser.parse_args()
    
    if args.logs:
        show_service_logs(args.logs, args.lines)
    else:
        show_dashboard(args.watch, args.interval)


if __name__ == "__main__":
    main()
