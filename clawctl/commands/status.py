"""clawctl status — show all service health, nicely."""
import subprocess
import urllib.request
from clawos_core.constants import SERVICES, OLLAMA_HOST

PURPLE = "\033[38;5;141m"
GREEN  = "\033[38;5;84m"
RED    = "\033[38;5;203m"
AMBER  = "\033[38;5;220m"
BLUE   = "\033[38;5;75m"
DIM    = "\033[2m"
GREY   = "\033[38;5;245m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def _ok(s):   return f"{GREEN}✓{RESET}  {s}"
def _fail(s): return f"{RED}✗{RESET}  {s}"
def _warn(s): return f"{AMBER}⚠{RESET}  {s}"
def _dim(s):  return f"{DIM}{GREY}{s}{RESET}"

def _http_ok(url):
    try:
        urllib.request.urlopen(url, timeout=2)
        return True
    except Exception:
        return False

def _systemd(svc):
    try:
        r = subprocess.run(
            ["systemctl","--user","is-active",f"clawos-{svc}.service"],
            capture_output=True, text=True, timeout=3
        )
        return r.stdout.strip()
    except Exception:
        return "unknown"

def run():
    import shutil
    print()
    print(f"  {PURPLE}{BOLD}CLAWOS{RESET}  {_dim('service status')}")
    print(f"  {_dim('─' * 46)}")
    print()

    # Ollama
    ollama_ok = _http_ok(f"{OLLAMA_HOST}/api/tags")
    print("  " + (_ok(f"{BLUE}ollama{RESET}       running  {_dim(OLLAMA_HOST)}")
                  if ollama_ok else _fail(f"{BLUE}ollama{RESET}       not running  {_dim('start: ollama serve')}")))

    if ollama_ok:
        try:
            r = subprocess.run(["ollama","list"],capture_output=True,text=True,timeout=5)
            models = [l.split()[0] for l in r.stdout.strip().splitlines()[1:] if l.strip()]
            if models:
                print(f"     {_dim('models:')} {AMBER}{', '.join(models[:3])}{RESET}")
        except Exception:
            pass

    print()

    # ClawOS daemon — all core services run in-process inside clawos.service
    daemon_active = False
    try:
        r = subprocess.run(
            ["systemctl", "--user", "is-active", "clawos.service"],
            capture_output=True, text=True, timeout=3
        )
        daemon_active = r.stdout.strip() == "active"
    except Exception:
        pass

    dash_ok = _http_ok("http://localhost:7070/health") or _http_ok("http://localhost:7070/api/health")

    if daemon_active:
        print("  " + _ok(f"{PURPLE}clawos.service{RESET}  active"))
    else:
        print("  " + _warn(f"{PURPLE}clawos.service{RESET}  inactive  {_dim('clawctl start')}"))

    # Individual in-process services — show running if daemon is up
    in_process = ["policyd", "memd", "modeld", "agentd", "toolbridge", "voiced", "clawd"]
    for svc in in_process:
        if daemon_active:
            print("  " + _ok(f"{PURPLE}{svc:<12}{RESET} running {_dim('(in-process)')}"))
        else:
            print("  " + _warn(f"{PURPLE}{svc:<12}{RESET} inactive"))

    print()

    # Dashboard
    print("  " + (_ok(f"dashboard    {_dim('http://localhost:7070')}")
                  if dash_ok else _dim("·  dashboard    not running")))

    # WhatsApp
    from clawos_core.constants import CONFIG_DIR
    wa_linked = (CONFIG_DIR / "whatsapp" / ".wa_linked").exists()
    oc_ok     = shutil.which("openclaw") is not None
    print("  " + (_ok(f"openclaw     installed")
                  if oc_ok else _dim("·  openclaw     not installed  (clawctl openclaw install)")))
    print("  " + (_ok(f"whatsapp     linked")
                  if wa_linked else _dim("·  whatsapp     not linked  (clawctl openclaw whatsapp)")))

    # Token compression (show only if openclaw is installed)
    if oc_ok:
        print()
        try:
            from openclaw_integration.compression import (
                headroom_installed, headroom_running,
                rtk_installed, HEADROOM_PORT, headroom_stats, rtk_stats
            )
            h_run = headroom_running()
            h_ins = headroom_installed()
            r_ins = rtk_installed()

            print(f"  {_dim('Token compression')} {_dim('─' * 24)}")

            # Headroom
            if h_run:
                s = headroom_stats()
                saved = s.get("tokens", {}).get("saved", 0)
                pct   = s.get("tokens", {}).get("savings_percent", 0)
                detail = (f"{_dim(str(saved) + ' tokens saved (' + str(round(pct)) + '%)')}")
                print("  " + _ok(f"headroom     proxy :{HEADROOM_PORT}  {detail}"))
            elif h_ins:
                print("  " + _warn(f"headroom     installed, not running  {_dim('clawctl openclaw start')}"))
            else:
                print("  " + _dim(f"·  headroom     not installed  (clawctl openclaw install)"))

            # RTK
            if r_ins:
                s = rtk_stats()
                raw = s.get("raw", "")
                # Try to extract a number from gain output
                import re as _re
                m = _re.search(r'([\d,]+)\s*tokens', raw)
                detail = _dim(m.group(0)) if m else _dim("active")
                print("  " + _ok(f"rtk          CLI compression  {detail}"))
            else:
                print("  " + _dim(f"·  rtk          not installed  (clawctl openclaw install)"))
        except Exception:
            pass

    print()
    print(f"  {_dim('─' * 46)}")
    print(f"  {_dim('clawctl start   — start all services')}")
    print(f"  {_dim('clawctl chat    — start chatting')}")
    print()
