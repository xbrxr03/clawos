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

    # ClawOS services
    use_systemd = shutil.which("systemctl") is not None
    for svc in ["policyd","memd","modeld","agentd","toolbridge","voiced","clawd","dashd","gatewayd"]:
        if use_systemd:
            st = _systemd(svc)
            icon = _ok if st == "active" else (_warn if st == "inactive" else _fail)
            print("  " + icon(f"{PURPLE}{svc:<12}{RESET} {st}"))
        else:
            # Dev mode — check by port
            port_map = {"dashd": 7070, "agentd": 7072, "clawd": 7071}
            p = port_map.get(svc)
            if p:
                up = _http_ok(f"http://localhost:{p}/api/health")
                icon = _ok if up else _fail
                print("  " + icon(f"{PURPLE}{svc:<12}{RESET} {'running' if up else 'not running'}"))
            else:
                print(f"  {_dim('·')}  {PURPLE}{svc:<12}{RESET} {_dim('(systemd not available)')}")

    print()

    # Dashboard
    dash_ok = _http_ok("http://localhost:7070/api/health")
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

    print()
    print(f"  {_dim('─' * 46)}")
    print(f"  {_dim('clawctl start   — start all services')}")
    print(f"  {_dim('clawctl chat    — start chatting')}")
    print()
