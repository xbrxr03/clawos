# SPDX-License-Identifier: AGPL-3.0-or-later
"""clawctl status - show all service health, nicely."""

import shutil
import subprocess
import urllib.request

from clawos_core.constants import OLLAMA_HOST
from clawos_core.service_manager import is_active as is_service_active, service_hint, service_manager_name

PURPLE = "\033[38;5;141m"
GREEN = "\033[38;5;84m"
RED = "\033[38;5;203m"
AMBER = "\033[38;5;220m"
BLUE = "\033[38;5;75m"
DIM = "\033[2m"
GREY = "\033[38;5;245m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _ok(text):
    return f"{GREEN}[ok]{RESET}  {text}"


def _fail(text):
    return f"{RED}[x]{RESET}  {text}"


def _warn(text):
    return f"{AMBER}[!]{RESET}  {text}"


def _dim(text):
    return f"{DIM}{GREY}{text}{RESET}"


def _http_ok(url):
    try:
        urllib.request.urlopen(url, timeout=2)
        return True
    except Exception:
        return False


def run():
    manager = service_manager_name()
    print()
    print(f"  {PURPLE}{BOLD}CLAWOS{RESET}  {_dim('service status - ' + manager)}")
    print(f"  {_dim('-' * 46)}")
    print()

    ollama_ok = _http_ok(f"{OLLAMA_HOST}/api/tags")
    start_hint = service_hint("start", "ollama.service")
    print(
        "  "
        + (
            _ok(f"{BLUE}ollama{RESET}       running  {_dim(OLLAMA_HOST)}")
            if ollama_ok
            else _fail(f"{BLUE}ollama{RESET}       not running  {_dim('start: ' + start_hint)}")
        )
    )

    if ollama_ok:
        try:
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
            models = [line.split()[0] for line in result.stdout.strip().splitlines()[1:] if line.strip()]
            if models:
                print(f"     {_dim('models:')} {AMBER}{', '.join(models[:3])}{RESET}")
        except Exception:
            pass

    print()

    daemon_active = is_service_active("clawos.service")
    dash_ok = _http_ok("http://localhost:7070/health") or _http_ok("http://localhost:7070/api/health")

    if daemon_active:
        print("  " + _ok(f"{PURPLE}clawos.service{RESET}  active"))
    else:
        print("  " + _warn(f"{PURPLE}clawos.service{RESET}  inactive  {_dim(service_hint('start', 'clawos.service'))}"))

    in_process = ["policyd", "memd", "modeld", "agentd", "toolbridge", "voiced", "clawd"]
    for svc in in_process:
        if daemon_active:
            print("  " + _ok(f"{PURPLE}{svc:<12}{RESET} running {_dim('(in-process)')}"))
        else:
            print("  " + _warn(f"{PURPLE}{svc:<12}{RESET} inactive"))

    print()
    print("  " + (_ok(f"dashboard    {_dim('http://localhost:7070')}") if dash_ok else _dim("-  dashboard    not running")))

    from clawos_core.constants import CONFIG_DIR

    wa_linked = (CONFIG_DIR / "whatsapp" / ".wa_linked").exists()
    oc_ok = shutil.which("openclaw") is not None
    print("  " + (_ok("openclaw     installed") if oc_ok else _dim("-  openclaw     not installed  (clawctl openclaw install)")))
    print("  " + (_ok("whatsapp     linked") if wa_linked else _dim("-  whatsapp     not linked  (clawctl openclaw whatsapp)")))

    if oc_ok:
        print()
        try:
            from openclaw_integration.compression import (
                HEADROOM_PORT,
                headroom_installed,
                headroom_running,
                headroom_stats,
                rtk_installed,
                rtk_stats,
            )

            h_run = headroom_running()
            h_ins = headroom_installed()
            r_ins = rtk_installed()

            print(f"  {_dim('Token compression')} {_dim('-' * 24)}")

            if h_run:
                stats = headroom_stats()
                saved = stats.get("tokens", {}).get("saved", 0)
                pct = stats.get("tokens", {}).get("savings_percent", 0)
                detail = _dim(f"{saved} tokens saved ({round(pct)}%)")
                print("  " + _ok(f"headroom     proxy :{HEADROOM_PORT}  {detail}"))
            elif h_ins:
                print("  " + _warn(f"headroom     installed, not running  {_dim('clawctl openclaw start')}"))
            else:
                print("  " + _dim("-  headroom     not installed  (clawctl openclaw install)"))

            if r_ins:
                stats = rtk_stats()
                raw = stats.get("raw", "")
                import re as _re

                match = _re.search(r"([\d,]+)\s*tokens", raw)
                detail = _dim(match.group(0)) if match else _dim("active")
                print("  " + _ok(f"rtk          CLI compression  {detail}"))
            else:
                print("  " + _dim("-  rtk          not installed  (clawctl openclaw install)"))
        except Exception:
            pass

    print()
    print(f"  {_dim('-' * 46)}")
    print(f"  {_dim('clawctl start   - start all services')}")
    print(f"  {_dim('clawctl chat    - start chatting')}")
    print()
