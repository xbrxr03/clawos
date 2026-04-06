# SPDX-License-Identifier: AGPL-3.0-or-later
"""
HTTP proxy: gatewayd → PicoClaw API on :18800.
Routes inbound messages from any channel to PicoClaw's HTTP API.
"""
import json
import logging
import urllib.request
from clawos_core.constants import PORT_PICOCLAWD

log = logging.getLogger("picoclawd.bridge")

PICOCLAW_API = f"http://localhost:18800/chat"


def send(message: str, sender: str = "") -> str:
    """Send message to PicoClaw and return response text."""
    payload = json.dumps({"message": message, "sender": sender}).encode()
    try:
        req = urllib.request.Request(
            PICOCLAW_API,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        return data.get("response", data.get("text", "[no response]"))
    except Exception as e:
        log.warning(f"PicoClaw bridge error: {e}")
        return f"[PICOCLAW OFFLINE] {e}"
