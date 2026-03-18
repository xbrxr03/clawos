"""
Screen 7 — WhatsApp setup.
Personal number — Jarvis lives in your main WhatsApp.
QR scan links the session once. After that it auto-reconnects.
"""


def run(state) -> bool:
    print("\n  ── WhatsApp Setup ──────────────────────────────")
    print()
    print("  Connect your personal WhatsApp number to Jarvis.")
    print("  Jarvis will receive messages YOU send to yourself,")
    print("  or from contacts you whitelist.")
    print()
    print("  How it works:")
    print("    1. Scan a QR code once (like WhatsApp Web)")
    print("    2. Message yourself or say 'Hey Jarvis, ...'")
    print("    3. Approve tool calls by replying 'approve' or 'deny'")
    print("    4. Session persists — no re-scan after reboot")
    print()

    ans = input("  Set up WhatsApp now? [y/N]: ").strip().lower()
    if ans != "y":
        print("  Skipped — set up later: clawctl whatsapp link")
        state.whatsapp_enabled = False
        state.mark_done("whatsapp_setup")
        return True

    # Check dependency
    try:
        import importlib
        importlib.import_module("whatsapp")
        wa_ok = True
    except ImportError:
        wa_ok = False

    if not wa_ok:
        print()
        print("  Installing WhatsApp bridge ...")
        import subprocess
        r = subprocess.run(
            ["pip", "install", "whatsapp-web.py", "--break-system-packages", "-q"],
            capture_output=True
        )
        if r.returncode != 0:
            print("  [ERROR] Install failed. Try manually:")
            print("    pip install whatsapp-web.py --break-system-packages")
            print("  Then: clawctl whatsapp link")
            state.whatsapp_enabled = False
            state.mark_done("whatsapp_setup")
            return True

    print()
    print("  Launching QR code ... (scan with WhatsApp on your phone)")
    print("  Phone → WhatsApp → ⋮ → Linked Devices → Link a Device")
    print()

    try:
        from services.gatewayd.channels.whatsapp import WhatsAppChannel
        channel = WhatsAppChannel()
        linked  = channel.link_interactive()   # prints QR, waits for scan
        if linked:
            state.whatsapp_enabled = True
            state.whatsapp_number  = channel.phone_number or "personal"
            print(f"\n  ✓ WhatsApp linked: {state.whatsapp_number}")
            print("  Send yourself a message to test Jarvis.")
        else:
            print("  QR scan failed or timed out.")
            print("  Try again later: clawctl whatsapp link")
            state.whatsapp_enabled = False
    except Exception as e:
        print(f"  WhatsApp setup error: {e}")
        print("  Try later: clawctl whatsapp link")
        state.whatsapp_enabled = False

    state.mark_done("whatsapp_setup")
    return True
