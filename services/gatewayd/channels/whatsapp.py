# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS WhatsApp Channel
========================
Bot account approach — dedicated number saved as "Jarvis" in contacts.
Uses whatsapp-web.js (Node.js) via subprocess bridge — most reliable method.

Setup:
  1. Get a spare number (Google Voice, cheap SIM, virtual number)
  2. Run: clawctl whatsapp link  → scan QR code with that number's WhatsApp
  3. Save it in your contacts as "Jarvis"
  4. Message it — Jarvis replies

The Node.js bridge script is written to ~/.clawos/config/whatsapp/bridge.js
and runs as a subprocess when gatewayd starts.
"""
import asyncio
import json
import logging
import subprocess
import time
from pathlib import Path
from clawos_core.constants import CONFIG_DIR

log = logging.getLogger("gatewayd.whatsapp")

WA_DIR      = CONFIG_DIR / "whatsapp"
SESSION_DIR = WA_DIR / "session"
LINKED_FILE = WA_DIR / ".wa_linked"
QR_FILE     = WA_DIR / "qr_data.txt"
BRIDGE_JS   = WA_DIR / "bridge.js"


class WhatsAppChannel:
    def __init__(self):
        self.phone_number = LINKED_FILE.read_text().strip() if LINKED_FILE.exists() else ""
        self._bridge_proc = None
        self._running     = False
        self._on_message  = None

    def set_message_handler(self, fn):
        self._on_message = fn

    # ── Link (QR scan) ────────────────────────────────────────────────────────

    def link_interactive(self) -> bool:
        """Print QR code, wait for scan. Returns True on success."""
        import shutil
        WA_DIR.mkdir(parents=True, exist_ok=True)
        self._write_bridge_js()

        if not shutil.which("node"):
            print()
            print("  Node.js required for WhatsApp. Install:")
            print("    curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo bash -")
            print("    sudo apt install nodejs")
            return False

        # Install whatsapp-web.js if needed
        node_modules = WA_DIR / "node_modules" / "whatsapp-web.js"
        if not node_modules.exists():
            print("  Installing whatsapp-web.js (~200MB, one time) ...")
            r = subprocess.run(
                ["npm", "install", "whatsapp-web.js", "qrcode-terminal"],
                cwd=str(WA_DIR), capture_output=False
            )
            if r.returncode != 0:
                print("  npm install failed")
                return False

        print()
        print("  Starting WhatsApp QR session ...")
        print("  Scan the QR code with your Jarvis number's WhatsApp:")
        print("  Phone → WhatsApp → ⋮ → Linked Devices → Link a Device")
        print()

        proc = subprocess.Popen(
            ["node", str(BRIDGE_JS)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True, bufsize=1,
            cwd=str(WA_DIR)
        )

        linked   = False
        deadline = time.time() + 180

        for raw in proc.stdout:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("LINKED:"):
                phone = line.split("LINKED:", 1)[1].strip()
                self.phone_number = phone
                WA_DIR.mkdir(parents=True, exist_ok=True)
                LINKED_FILE.write_text(phone)
                linked = True
                proc.terminate()
                print(f"\n  ✓ Linked: {phone}")
                break
            elif line.startswith("QR_TEXT:"):
                self._print_qr(line.split("QR_TEXT:", 1)[1].strip())
            elif not line.startswith("["):
                print(f"  {line}")
            if time.time() > deadline:
                print("\n  Timed out (3 min). Run: clawctl whatsapp link")
                proc.terminate()
                break

        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

        return linked

    def _print_qr(self, data: str):
        QR_FILE.write_text(data)
        try:
            import qrcode
            qr = qrcode.QRCode(border=2)
            qr.add_data(data)
            qr.make(fit=True)
            qr.print_ascii(invert=True)
        except ImportError:
            print(f"  (QR data saved to {QR_FILE})")
            print("  To display: pip install qrcode && python3 -c \"")
            print(f"  import qrcode; q=qrcode.QRCode(); q.add_data(open('{QR_FILE}').read()); q.make(); q.print_ascii(invert=True)\"")

    # ── Send ─────────────────────────────────────────────────────────────────

    def send(self, jid: str, message: str):
        if self._bridge_proc and self._bridge_proc.poll() is None:
            try:
                cmd = json.dumps({"action": "send", "jid": jid, "message": message})
                self._bridge_proc.stdin.write(cmd + "\n")
                self._bridge_proc.stdin.flush()
            except Exception as e:
                log.error(f"Send failed: {e}")
        else:
            log.warning("Bridge not running — cannot send message")

    def send_self(self, message: str):
        """Send alert/notification to the bot's own number (appears as self-message)."""
        if not self.phone_number:
            log.warning("No phone linked")
            return
        self.send(f"{self.phone_number}@s.whatsapp.net", message)

    def send_to(self, phone: str, message: str):
        """Send to any phone number (without @)."""
        jid = phone if "@" in phone else f"{phone}@s.whatsapp.net"
        self.send(jid, message)

    # ── Start / stop daemon ───────────────────────────────────────────────────

    async def start(self, on_message=None) -> bool:
        if on_message:
            self._on_message = on_message
        if not LINKED_FILE.exists():
            log.info("WhatsApp not linked — skipping")
            return False

        import shutil
        if not shutil.which("node"):
            log.warning("node not found — WhatsApp unavailable")
            return False

        self._write_bridge_js()
        log.info("Starting WhatsApp bridge daemon ...")

        self._bridge_proc = subprocess.Popen(
            ["node", str(BRIDGE_JS), "--daemon"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True, bufsize=1,
            cwd=str(WA_DIR)
        )
        self._running = True
        asyncio.create_task(self._read_loop())
        return True

    async def stop(self):
        self._running = False
        if self._bridge_proc:
            try:
                self._bridge_proc.terminate()
                self._bridge_proc.wait(timeout=5)
            except Exception:
                self._bridge_proc.kill()

    async def _read_loop(self):
        loop = asyncio.get_event_loop()
        while self._running and self._bridge_proc and self._bridge_proc.poll() is None:
            try:
                line = await loop.run_in_executor(None, self._bridge_proc.stdout.readline)
                if not line:
                    break
                line = line.strip()
                if not line or not line.startswith("{"):
                    continue
                event = json.loads(line)
                await self._dispatch(event)
            except Exception as e:
                if self._running:
                    log.error(f"Bridge read: {e}")
                break
        if self._running:
            log.warning("Bridge exited — will restart in 10s")
            await asyncio.sleep(10)
            await self.start()

    async def _dispatch(self, event: dict):
        t = event.get("type")
        if t == "ready":
            log.info(f"WhatsApp ready — {event.get('phone','')}")
        elif t == "disconnected":
            log.warning(f"WhatsApp disconnected: {event.get('reason','')}")
        elif t == "message" and self._on_message:
            jid        = event.get("from", "")
            body       = event.get("body", "")
            media_path = event.get("media_path")
            try:
                await self._on_message(jid, body, media_path)
            except Exception as e:
                log.error(f"Message handler: {e}")

    # ── Bridge JS ─────────────────────────────────────────────────────────────

    def _write_bridge_js(self):
        WA_DIR.mkdir(parents=True, exist_ok=True)
        BRIDGE_JS.write_text(_NODE_BRIDGE)


# ── Node.js bridge script ─────────────────────────────────────────────────────
_NODE_BRIDGE = r"""
// ClawOS WhatsApp Bridge — whatsapp-web.js
'use strict';
const path      = require('path');
const fs        = require('fs');
const readline  = require('readline');
const isDaemon  = process.argv.includes('--daemon');
const SESS_DIR  = path.join(__dirname, 'session');

let Client, LocalAuth;
try {
  ({ Client, LocalAuth } = require('whatsapp-web.js'));
} catch(e) {
  process.stderr.write('whatsapp-web.js not found. Run: npm install whatsapp-web.js qrcode-terminal\n');
  process.exit(1);
}

let QRTerm;
try { QRTerm = require('qrcode-terminal'); } catch(e) {}

const client = new Client({
  authStrategy: new LocalAuth({ dataPath: SESS_DIR }),
  puppeteer: {
    headless: true,
    args: [
      '--no-sandbox','--disable-setuid-sandbox',
      '--disable-dev-shm-usage','--disable-gpu',
      '--no-first-run','--no-zygote',
    ],
  },
  webVersionCache: { type: 'remote', remotePath: 'https://raw.githubusercontent.com/wppconnect-team/wa-version/main/html/2.2412.54.html' },
});

client.on('qr', qr => {
  if (QRTerm) {
    QRTerm.generate(qr, { small: true });
  }
  process.stdout.write('QR_TEXT:' + qr + '\n');
});

client.on('authenticated', () => {
  process.stdout.write('AUTH_OK\n');
});

client.on('ready', () => {
  const phone = (client.info && client.info.wid && client.info.wid.user) || '';
  process.stdout.write('LINKED:' + phone + '\n');
  if (isDaemon) {
    emit({ type: 'ready', phone });
  } else {
    setTimeout(() => process.exit(0), 500);
  }
});

client.on('message', async msg => {
  if (!isDaemon) return;
  let media_path = null;
  if (msg.hasMedia) {
    try {
      const media = await msg.downloadMedia();
      if (media) {
        media_path = path.join(__dirname, 'media_' + Date.now() + '.' + (media.mimetype.split('/')[1] || 'bin'));
        fs.writeFileSync(media_path, Buffer.from(media.data, 'base64'));
      }
    } catch(e) {}
  }
  emit({ type: 'message', from: msg.from, body: msg.body || '', media_path, ts: msg.timestamp });
});

client.on('disconnected', reason => {
  emit({ type: 'disconnected', reason });
});

client.on('auth_failure', msg => {
  emit({ type: 'auth_failure', message: msg });
  process.exit(1);
});

// stdin command reader (daemon mode)
if (isDaemon) {
  const rl = readline.createInterface({ input: process.stdin, terminal: false });
  rl.on('line', async line => {
    line = line.trim();
    if (!line) return;
    try {
      const cmd = JSON.parse(line);
      if (cmd.action === 'send') {
        await client.sendMessage(cmd.jid, cmd.message);
      }
    } catch(e) {
      process.stderr.write('CMD error: ' + e.message + '\n');
    }
  });
}

function emit(obj) {
  process.stdout.write(JSON.stringify(obj) + '\n');
}

client.initialize().catch(e => {
  process.stderr.write('Init error: ' + e.message + '\n');
  process.exit(1);
});
"""
