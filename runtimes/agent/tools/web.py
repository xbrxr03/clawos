# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Web tools — DuckDuckGo search with graceful offline fallback.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import quote_plus

import httpx

log = logging.getLogger("agent.tools.web")


async def web_search(args: dict, ctx: dict) -> str:
    query = (args.get("query") or "").strip()
    if not query:
        return "[ERROR] query required"

    # DuckDuckGo HTML endpoint — no API key, returns extractable results
    url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
    try:
        async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as c:
            r = await c.get(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; ClawOS/1.0)",
            })
            r.raise_for_status()
            html = r.text
    except (httpx.HTTPError, OSError, ConnectionError) as e:
        log.debug(f"ddg search failed: {e}")
        return "[OFFLINE] web search unavailable"

    # Extract result titles + snippets. DuckDuckGo HTML structure:
    #   <a class="result__a" href="...">TITLE</a>
    #   <a class="result__snippet">SNIPPET</a>
    titles  = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html, re.S)
    snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.S)

    def _clean(t: str) -> str:
        t = re.sub(r"<.*?>", "", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    out = []
    for i, (t, s) in enumerate(zip(titles, snippets)):
        if i >= 5: break
        out.append(f"{i+1}. {_clean(t)}\n   {_clean(s)[:200]}")
    return "\n\n".join(out) if out else "No results."
