"""clawctl openclaw — manage the optional OpenClaw runtime."""
import shutil
import subprocess
from clawctl.ui.banner import success, error, info, warn


def run_status():
    print()
    from openclaw_integration.installer import system_check, gateway_status
    c = system_check()
    info(f"node:       {'✓ v' + str(c['node_version']) if c['node'] else '✗ missing'}")
    info(f"openclaw:   {'✓ installed' if c['openclaw'] else '✗ not installed'}")
    info(f"ollama:     {'✓ running' if c['ollama'] else '✗ not running'}")
    info(f"ram:        {c['ram_gb']}GB {'✓' if c['ram_ok'] else '⚠ low'}")
    if c['openclaw']:
        info(f"gateway:    {gateway_status()}")
    else:
        info("Install:    clawctl openclaw install")
    print()


def run_install(model: str = None, force: bool = False):
    from openclaw_integration.installer import install
    install(model=model, force=force, skip_whatsapp=True)


def run_start():
    print()
    if not shutil.which("openclaw"):
        error("OpenClaw not installed — run: clawctl openclaw install")
        return
    from openclaw_integration.installer import start_gateway
    proc = start_gateway()
    import time; time.sleep(2)
    if proc.poll() is None:
        success("OpenClaw gateway started")
        info("WhatsApp: openclaw channels login whatsapp")
        info("TUI:      openclaw tui")
        info("Status:   openclaw status")
    else:
        error("Gateway failed — check: openclaw logs")
    print()


def run_stop():
    print()
    from openclaw_integration.installer import stop_gateway
    stop_gateway()
    success("OpenClaw gateway stopped")
    print()


def run_restart():
    print()
    from openclaw_integration.installer import restart_gateway
    restart_gateway()
    success("OpenClaw gateway restarted")
    print()


def run_whatsapp():
    """Wire WhatsApp using openclaw's own onboarding — no reinventing the wheel."""
    print()
    if not shutil.which("openclaw"):
        error("OpenClaw not installed — run: clawctl openclaw install")
        return
    info("Launching OpenClaw WhatsApp login ...")
    info("Phone → WhatsApp → ⋮ → Linked Devices → Link a Device")
    print()
    try:
        subprocess.run(["openclaw", "channels", "login", "whatsapp"])
        print()
        phone = input("  Your phone number for allowlist (e.g. +15551234567): ").strip()
        if phone:
            from openclaw_integration.installer import add_whatsapp_allowlist
            add_whatsapp_allowlist(phone)
        from openclaw_integration.installer import restart_gateway
        restart_gateway()
        success("WhatsApp linked and gateway restarted")
    except FileNotFoundError:
        error("openclaw not found in PATH")
    except KeyboardInterrupt:
        print("\n  Cancelled")
    print()


def run_config(model: str = None):
    print()
    from openclaw_integration.config_gen import write_config, detect_best_model, apply_auth_fix
    if model is None:
        model = detect_best_model()
    write_config(model)
    apply_auth_fix()
    success(f"Config regenerated — model: {model}")
    info("Restart: clawctl openclaw restart")
    print()


def run_onboard():
    """Full OpenClaw onboard wizard — their official flow."""
    print()
    if not shutil.which("openclaw"):
        error("OpenClaw not installed — run: clawctl openclaw install")
        return
    info("Launching OpenClaw onboard wizard ...")
    info("Choose: Ollama as provider, your model, WhatsApp as channel")
    print()
    try:
        subprocess.run(["openclaw", "onboard"])
    except FileNotFoundError:
        error("openclaw not found in PATH")
    except KeyboardInterrupt:
        print("\n  Cancelled")
    print()
