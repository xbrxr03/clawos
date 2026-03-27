"""clawctl whatsapp — manage WhatsApp gateway."""
from pathlib import Path
from clawos_core.constants import CONFIG_DIR
from clawctl.ui.banner import success, error, info

WA_DIR    = CONFIG_DIR / "whatsapp"
WA_LINKED = WA_DIR / ".wa_linked"


def run_status():
    print()
    linked = WA_LINKED.exists()
    info(f"WhatsApp: {'linked ✓' if linked else 'not linked'}")
    if linked:
        number = WA_LINKED.read_text().strip()
        info(f"Number:   {number or 'personal'}")
        info("Restart gateway to reconnect: clawctl restart gatewayd")
    else:
        info("Link your phone: clawctl whatsapp link")
    print()


def run_link():
    print()
    info("Starting WhatsApp link process ...")
    info("Phone → WhatsApp → ⋮ → Linked Devices → Link a Device")
    print()
    try:
        from services.gatewayd.channels.whatsapp import WhatsAppChannel
        channel = WhatsAppChannel()
        linked  = channel.link_interactive()
        if linked:
            WA_DIR.mkdir(parents=True, exist_ok=True)
            WA_LINKED.write_text(getattr(channel, "phone_number", "personal"))
            success("WhatsApp linked")
            info("Send yourself 'hello' to test")
        else:
            error("Link failed or timed out")
            info("Try again: clawctl whatsapp link")
    except ImportError:
        error("WhatsApp bridge not installed")
        info("Install: pip install whatsapp-web.py --break-system-packages")
    except Exception as e:
        error(f"Link error: {e}")
    print()


def run_unlink():
    print()
    if WA_LINKED.exists():
        WA_LINKED.unlink()
        import shutil
        session = WA_DIR / "session"
        if session.exists():
            shutil.rmtree(session)
        success("WhatsApp unlinked")
    else:
        info("Not currently linked")
    print()


def run_test():
    print()
    if not WA_LINKED.exists():
        error("Not linked. Run: clawctl whatsapp link")
        return
    info("Sending test message to yourself ...")
    try:
        from services.gatewayd.channels.whatsapp import WhatsAppChannel
        channel = WhatsAppChannel()
        channel.send_self("ClawOS WhatsApp test — Nexus is connected.")
        success("Test message sent")
    except Exception as e:
        error(f"Test failed: {e}")
    print()
