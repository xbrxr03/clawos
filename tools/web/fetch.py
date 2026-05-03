# SPDX-License-Identifier: AGPL-3.0-or-later
"""web.fetch — fetch URL content. Returns text, strips HTML. Max 100KB."""
import re
import urllib.request

MAX_BYTES = 100 * 1024
TIMEOUT   = 15


def run(target: str) -> str:
    url = target.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ClawOS/0.1"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read(MAX_BYTES)

        text = raw.decode("utf-8", errors="replace")

        # Strip HTML tags if content is HTML
        if "html" in content_type.lower() or text.strip().startswith("<"):
            text = _strip_html(text)

        # Trim
        if len(text) > MAX_BYTES:
            text = text[:MAX_BYTES] + "\n... [truncated]"

        return text.strip() or "[EMPTY] No text content"
    except (OSError, ConnectionRefusedError, TimeoutError) as e:
        return f"[OFFLINE] Could not fetch {url}: {e}"


def _strip_html(html: str) -> str:
    # Remove scripts/styles
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.S | re.I)
    # Remove tags
    html = re.sub(r"<[^>]+>", " ", html)
    # Collapse whitespace
    html = re.sub(r"\s{2,}", "\n", html)
    return html.strip()
