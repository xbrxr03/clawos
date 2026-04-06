# SPDX-License-Identifier: AGPL-3.0-or-later
"""web.search — DuckDuckGo search. No API key. Returns top 5 results as JSON."""
import json
import urllib.request
import urllib.parse


MAX_RESULTS = 5
TIMEOUT     = 10


def run(target: str) -> str:
    """target is the search query string."""
    query = target.strip()
    if not query:
        return "[ERROR] Empty search query"
    try:
        # DuckDuckGo Instant Answer API — no key required
        params = urllib.parse.urlencode({"q": query, "format": "json", "no_html": "1"})
        url    = f"https://api.duckduckgo.com/?{params}"
        req    = urllib.request.Request(url, headers={"User-Agent": "ClawOS/0.1"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read())

        results = []
        # AbstractText — instant answer
        if data.get("AbstractText"):
            results.append({"title": data.get("Heading", "Answer"),
                            "url": data.get("AbstractURL", ""),
                            "snippet": data["AbstractText"][:300]})

        # RelatedTopics
        for topic in data.get("RelatedTopics", [])[:MAX_RESULTS]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({"title": topic.get("Text", "")[:80],
                                "url": topic.get("FirstURL", ""),
                                "snippet": topic.get("Text", "")[:300]})
            if len(results) >= MAX_RESULTS:
                break

        if not results:
            return f"[NO RESULTS] No results found for: {query}"
        return json.dumps(results, indent=2)
    except Exception as e:
        return f"[OFFLINE] Web search unavailable: {e}"
