# SPDX-License-Identifier: AGPL-3.0-or-later
"""
researchd - Research Engine
===========================
Multi-source research with citations, provider-neutral search,
and disk-persisted resumable sessions.

Search providers (all optional, falls back gracefully):
  - Brave Search API  (env: BRAVE_API_KEY  or config: research.brave_api_key)
  - Tavily Search API (env: TAVILY_API_KEY or config: research.tavily_api_key)
  - SearXNG           (self-hosted or public instance, config: research.searxng_url)
  - DuckDuckGo HTML   (no API key needed, always available)
  - Wikipedia         (no API key needed, always available)
  - Fetch-only mode   (user-supplied URLs only)

Provider priority: brave > tavily > searxng > ddg > wikipedia > fetch
No-key mode (default): ddg + wikipedia + searxng — zero API keys required.
"""
from __future__ import annotations

import json
import logging
import os
import re
import secrets
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("researchd")

# ── Paths ─────────────────────────────────────────────────────────────────────
try:
    from clawos_core.constants import CONFIG_DIR
    RESEARCH_DIR = CONFIG_DIR / "research" / "sessions"
except (ImportError, ModuleNotFoundError):
    RESEARCH_DIR = Path.home() / ".clawos" / "research" / "sessions"


# ── Data model ────────────────────────────────────────────────────────────────
@dataclass
class Citation:
    url: str
    title: str
    excerpt: str
    relevance: str = "supporting"   # supporting | primary | tangential

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ResearchSource:
    url: str
    title: str
    snippet: str
    text: str = ""
    fetched: bool = False
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ResearchSession:
    id: str
    query: str
    status: str          # running | paused | done | error
    provider: str        # brave | tavily | searxng | ddg | wikipedia | fetch | none
    sources: List[ResearchSource] = field(default_factory=list)
    citations: List[Citation] = field(default_factory=list)
    summary: str = ""
    task_id: str = ""
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    updated_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def touch(self) -> None:
        self.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    def save(self) -> None:
        RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
        path = RESEARCH_DIR / f"{self.id}.json"
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, session_id: str) -> Optional["ResearchSession"]:
        path = RESEARCH_DIR / f"{session_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            sources = [ResearchSource(**s) for s in data.pop("sources", [])]
            citations = [Citation(**c) for c in data.pop("citations", [])]
            session = cls(**data)
            session.sources = sources
            session.citations = citations
            return session
        except (json.JSONDecodeError, ValueError) as exc:
            log.warning("Failed to load research session %s: %s", session_id, exc)
            return None

    @classmethod
    def list_all(cls) -> List[dict]:
        RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
        sessions = []
        for path in sorted(RESEARCH_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                sessions.append({
                    "id": data.get("id"),
                    "query": data.get("query"),
                    "status": data.get("status"),
                    "provider": data.get("provider"),
                    "source_count": len(data.get("sources", [])),
                    "citation_count": len(data.get("citations", [])),
                    "summary": data.get("summary", "")[:200],
                    "task_id": data.get("task_id", ""),
                    "created_at": data.get("created_at"),
                    "updated_at": data.get("updated_at"),
                })
            except (json.JSONDecodeError, ValueError):
                continue
        return sessions


# ── URL fetching (shared with workbench) ─────────────────────────────────────
def _fetch_page(url: str, timeout: int = 10) -> ResearchSource:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return ResearchSource(url=url, title=url, snippet="", error="Unsupported scheme")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ClawOS-Research/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read(512 * 1024)
        try:
            html = raw.decode("utf-8", errors="replace")
        except (OSError, RuntimeError, AttributeError):
            html = raw.decode("latin-1", errors="replace")

        title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        title = re.sub(r"\s+", " ", title_m.group(1)).strip()[:200] if title_m else parsed.netloc

        clean = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r"<style[^>]*>.*?</style>", " ", clean, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r"<[^>]+>", " ", clean)
        clean = re.sub(r"&[a-z#0-9]+;", " ", clean)
        clean = re.sub(r"[ \t]{2,}", " ", clean)
        clean = re.sub(r"\n{3,}", "\n\n", clean).strip()

        snippet = " ".join(clean.split()[:60])
        return ResearchSource(url=url, title=title, snippet=snippet, text=clean[:8000], fetched=True)
    except (OSError, ConnectionRefusedError, TimeoutError) as exc:
        return ResearchSource(url=url, title=url, snippet="", error=str(exc))


# ── Paid search providers ─────────────────────────────────────────────────────
def _brave_search(query: str, api_key: str, count: int = 6) -> List[ResearchSource]:
    encoded = urllib.parse.quote(query)
    req = urllib.request.Request(
        f"https://api.search.brave.com/res/v1/web/search?q={encoded}&count={count}",
        headers={"Accept": "application/json", "X-Subscription-Token": api_key},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
        data = json.loads(resp.read())
    results = data.get("web", {}).get("results", [])
    return [
        ResearchSource(url=r.get("url", ""), title=r.get("title", ""), snippet=r.get("description", ""))
        for r in results if r.get("url")
    ]


def _tavily_search(query: str, api_key: str, max_results: int = 6) -> List[ResearchSource]:
    payload = json.dumps({"api_key": api_key, "query": query, "max_results": max_results}).encode()
    req = urllib.request.Request(
        "https://api.tavily.com/search",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
        data = json.loads(resp.read())
    results = data.get("results", [])
    return [
        ResearchSource(url=r.get("url", ""), title=r.get("title", ""), snippet=r.get("content", "")[:300])
        for r in results if r.get("url")
    ]


# ── Free search providers (no API keys) ───────────────────────────────────────
def _ddg_search(query: str, max_results: int = 8) -> List[ResearchSource]:
    """Search DuckDuckGo. No API key required.

    Uses the ddgs library (pip install ddgs) which handles DDG's
    anti-bot measures. Falls back to raw HTML scraping if unavailable.
    This is the default free search provider for ClawOS.
    """
    sources: List[ResearchSource] = []

    # Primary: use ddgs library (handles cookies, CAPTCHA bypass)
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        for r in results:
            url = r.get("href", "") or r.get("link", "")
            title = r.get("title", "")
            snippet = r.get("body", "") or r.get("snippet", "")
            if url:
                sources.append(ResearchSource(
                    url=url,
                    title=title[:300],
                    snippet=snippet[:500],
                ))
        if sources:
            return sources
    except ImportError:
        log.debug("ddgs library not installed, falling back to HTML scraping")
    except Exception as exc:
        log.warning("DDG library search failed: %s", exc)

    # Fallback: raw HTML scraping (less reliable due to DDG bot detection)
    encoded = urllib.parse.quote(query)
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    try:
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:  # noqa: S310
            html = resp.read(256 * 1024).decode("utf-8", errors="replace")

        result_pattern = re.compile(
            r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>'
            r'.*?'
            r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )
        for match in result_pattern.finditer(html):
            result_url = match.group(1)
            title = re.sub(r"<[^>]+>", "", match.group(2)).strip()
            snippet = re.sub(r"<[^>]+>", "", match.group(3)).strip()
            if "//duckduckgo.com/l/" in result_url:
                parsed = urllib.parse.urlparse(result_url)
                params = urllib.parse.parse_qs(parsed.query)
                real_url = params.get("uddg", [result_url])[0]
            else:
                real_url = result_url
            if "duckduckgo.com" in real_url and "uddg" not in real_url:
                continue
            if real_url and title:
                sources.append(ResearchSource(
                    url=urllib.parse.unquote(real_url),
                    title=title[:300],
                    snippet=snippet[:500],
                ))
            if len(sources) >= max_results:
                break
    except (OSError, ConnectionRefusedError, TimeoutError) as exc:
        log.warning("DDG HTML search failed: %s", exc)

    return sources


def _searxng_search(query: str, base_url: str, max_results: int = 8) -> List[ResearchSource]:
    """Search via SearXNG instance. No API key needed, but requires a running instance.

    Args:
        query: Search query string
        base_url: SearXNG instance URL (e.g. "http://localhost:8080" or "https://searx.be")
        max_results: Maximum number of results to return

    SearXNG returns JSON via /search?q=...&format=json.
    Self-hosted instances work best — public instances often disable JSON API.
    To set up: docker run -d -p 8080:8080 searxng/searxng
    """
    sources: List[ResearchSource] = []
    base = base_url.rstrip("/")
    encoded = urllib.parse.quote(query)

    # Try JSON API first (works on self-hosted instances)
    try:
        url = f"{base}/search?q={encoded}&format=json&categories=general"
        req = urllib.request.Request(url, headers={
            "User-Agent": "ClawOS-Research/1.0",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=12) as resp:  # noqa: S310
            data = json.loads(resp.read(256 * 1024))

        for result in data.get("results", [])[:max_results]:
            url_r = result.get("url", "")
            title = result.get("title", "")
            snippet = result.get("content", "")
            if url_r:
                sources.append(ResearchSource(
                    url=url_r,
                    title=title[:300],
                    snippet=snippet[:500],
                ))

        if sources:
            return sources
    except (OSError, json.JSONDecodeError, TimeoutError) as exc:
        log.debug("SearXNG JSON API failed (%s): %s", base_url, exc)

    # Fallback: scrape HTML output
    try:
        url = f"{base}/search?q={encoded}&categories=general"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html",
        })
        with urllib.request.urlopen(req, timeout=12) as resp:  # noqa: S310
            html = resp.read(256 * 1024).decode("utf-8", errors="replace")

        # SearXNG HTML uses <article class="result"> blocks
        article_pattern = re.compile(
            r'<article[^>]*class="result[^"]*"[^>]*>'
            r'(.*?)'
            r'</article>',
            re.DOTALL | re.IGNORECASE,
        )
        link_pattern = re.compile(
            r'<a[^>]*href="([^"]+)"[^>]*class="[^"]*url[^"]*"[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )
        snippet_pattern = re.compile(
            r'<p[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</p>',
            re.DOTALL | re.IGNORECASE,
        )

        for article in article_pattern.finditer(html):
            block = article.group(1)
            link_match = link_pattern.search(block)
            snippet_match = snippet_pattern.search(block)

            if link_match:
                result_url = link_match.group(1)
                title = re.sub(r"<[^>]+>", "", link_match.group(2)).strip()
                snippet = ""
                if snippet_match:
                    snippet = re.sub(r"<[^>]+>", "", snippet_match.group(1)).strip()

                if result_url and not result_url.startswith("/"):
                    sources.append(ResearchSource(
                        url=result_url,
                        title=title[:300],
                        snippet=snippet[:500],
                    ))
            if len(sources) >= max_results:
                break
    except (OSError, TimeoutError) as exc:
        log.debug("SearXNG HTML scrape failed (%s): %s", base_url, exc)

    return sources


def _wikipedia_search(query: str, max_results: int = 4) -> List[ResearchSource]:
    """Search Wikipedia. No API key needed — uses the free MediaWiki API.

    Returns high-quality encyclopedic sources. Best for factual queries.
    """
    sources: List[ResearchSource] = []
    encoded = urllib.parse.quote(query)

    # Step 1: Search for page titles
    try:
        url = (
            f"https://en.wikipedia.org/w/api.php?"
            f"action=query&list=search&srsearch={encoded}&srlimit={max_results}&format=json"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "ClawOS-Research/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            data = json.loads(resp.read())

        search_results = data.get("query", {}).get("search", [])
        page_titles = []

        for result in search_results:
            title = result.get("title", "")
            snippet = re.sub(r"<[^>]+>", "", result.get("snippet", "")).strip()
            page_url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
            page_titles.append(title)
            sources.append(ResearchSource(
                url=page_url,
                title=f"{title} — Wikipedia",
                snippet=snippet[:500],
            ))

    except (OSError, json.JSONDecodeError, TimeoutError) as exc:
        log.warning("Wikipedia search failed: %s", exc)

    return sources


# ── Provider detection ────────────────────────────────────────────────────────
def _detect_provider() -> tuple[str, str]:
    """Return (provider_name, api_key_or_url) using env/config.

    Priority: brave > tavily > searxng > ddg
    Free providers (ddg, wikipedia) are always available as fallback.
    """
    # Paid providers first (if keys are configured)
    brave_key = os.environ.get("BRAVE_API_KEY", "").strip()
    if brave_key:
        return "brave", brave_key
    tavily_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if tavily_key:
        return "tavily", tavily_key

    # Check config for API keys or SearXNG URL
    try:
        from clawos_core.config.loader import get as get_config
        brave_key = str(get_config("research.brave_api_key", "")).strip()
        if brave_key:
            return "brave", brave_key
        tavily_key = str(get_config("research.tavily_api_key", "")).strip()
        if tavily_key:
            return "tavily", tavily_key
        searxng_url = str(get_config("research.searxng_url", "")).strip()
        if searxng_url:
            return "searxng", searxng_url
    except (ImportError, ModuleNotFoundError) as e:
        log.debug(f"suppressed: {e}")

    # Check env for SearXNG URL
    searxng_url = os.environ.get("SEARXNG_URL", "").strip()
    if searxng_url:
        return "searxng", searxng_url

    # Default: free search via DuckDuckGo (always works, no keys)
    return "ddg", ""


def _multi_search(query: str, provider: str, api_key: str, max_results: int = 8) -> List[ResearchSource]:
    """Run a primary search provider, then augment with free providers.

    For paid providers (brave, tavily): use them as primary, add DDG + Wikipedia.
    For free providers (ddg, searxng): use them as primary, add Wikipedia.
    For fetch mode: no search, just seed URLs.
    """
    sources: List[ResearchSource] = []
    seen_urls: set[str] = set()

    def _add_unique(new_sources: List[ResearchSource]) -> None:
        for s in new_sources:
            if s.url not in seen_urls:
                seen_urls.add(s.url)
                sources.append(s)

    # Primary search
    if provider == "brave" and api_key:
        try:
            _add_unique(_brave_search(query, api_key, max_results))
        except Exception as exc:
            log.warning("Brave search failed: %s", exc)

    elif provider == "tavily" and api_key:
        try:
            _add_unique(_tavily_search(query, api_key, max_results))
        except Exception as exc:
            log.warning("Tavily search failed: %s", exc)

    elif provider == "searxng" and api_key:
        try:
            _add_unique(_searxng_search(query, api_key, max_results))
        except Exception as exc:
            log.warning("SearXNG search failed: %s", exc)

    elif provider == "ddg":
        try:
            _add_unique(_ddg_search(query, max_results))
        except Exception as exc:
            log.warning("DDG search failed: %s", exc)

    # Always add Wikipedia results for factual context (if not fetch-only)
    if provider != "fetch":
        try:
            _add_unique(_wikipedia_search(query, max_results=3))
        except Exception as exc:
            log.warning("Wikipedia search failed: %s", exc)

    # If primary search returned nothing, try DDG as fallback (unless DDG was primary)
    if not sources and provider not in ("ddg", "fetch"):
        try:
            _add_unique(_ddg_search(query, max_results))
        except Exception as exc:
            log.warning("DDG fallback search failed: %s", exc)

    return sources


# ── Citation extraction ───────────────────────────────────────────────────────
def _extract_citations(sources: List[ResearchSource], query: str) -> List[Citation]:
    """Extract citations from fetched sources using keyword matching."""
    query_terms = set(re.findall(r"\b\w{4,}\b", query.lower()))
    citations: List[Citation] = []
    for source in sources:
        if not source.fetched or not source.text:
            continue
        sentences = re.split(r"(?<=[.!?])\s+", source.text)
        best_score = 0
        best_excerpt = source.snippet
        for sentence in sentences:
            terms_in = set(re.findall(r"\b\w{4,}\b", sentence.lower()))
            score = len(terms_in & query_terms)
            if score > best_score and len(sentence) > 40:
                best_score = score
                best_excerpt = sentence.strip()[:400]
        relevance = "primary" if best_score >= 3 else "supporting" if best_score >= 1 else "tangential"
        citations.append(Citation(
            url=source.url,
            title=source.title,
            excerpt=best_excerpt,
            relevance=relevance,
        ))
    citations.sort(key=lambda c: {"primary": 0, "supporting": 1, "tangential": 2}[c.relevance])
    return citations[:12]


# ── Engine ────────────────────────────────────────────────────────────────────
class ResearchEngine:
    def start_session(
        self,
        query: str,
        seed_urls: Optional[List[str]] = None,
        provider_override: Optional[str] = None,
        api_key_override: Optional[str] = None,
    ) -> ResearchSession:
        session = ResearchSession(
            id=secrets.token_urlsafe(10),
            query=query,
            status="running",
            provider="none",
        )
        session.save()

        # Determine provider
        if provider_override and api_key_override:
            provider, api_key = provider_override, api_key_override
        else:
            provider, api_key = _detect_provider()
        session.provider = provider

        # Search using multi-provider strategy
        session.sources = _multi_search(query, provider, api_key)

        # Add seed URLs as sources
        for url in (seed_urls or []):
            url = url.strip()
            if url and not any(s.url == url for s in session.sources):
                session.sources.append(ResearchSource(url=url, title=url, snippet=""))

        session.touch()
        session.save()
        return session

    def fetch_sources(self, session: ResearchSession) -> ResearchSession:
        """Fetch page content for all sources in the session."""
        for i, source in enumerate(session.sources):
            if not source.fetched and not source.error:
                session.sources[i] = _fetch_page(source.url)
        session.citations = _extract_citations(session.sources, session.query)
        session.touch()
        session.save()
        return session

    def build_agent_intent(self, session: ResearchSession) -> str:
        """Build a rich intent string for agentd from the session."""
        parts = [f"Research task: {session.query}", ""]
        fetched = [s for s in session.sources if s.fetched and s.text]
        for i, source in enumerate(fetched[:5], 1):
            parts.append(f"Source {i}: {source.title}")
            parts.append(f"URL: {source.url}")
            parts.append(source.text[:2000])
            parts.append("")
        if session.citations:
            parts.append("Citations found:")
            for c in session.citations[:6]:
                parts.append(f"  [{c.relevance}] {c.title} — {c.url}")
                parts.append(f"  \"{c.excerpt}\"")
        parts.append("")
        parts.append(
            "Please synthesize the above sources into a concise research summary "
            "with key findings, and list which sources you consider most relevant."
        )
        return "\n".join(parts)

    def resume_session(self, session_id: str) -> Optional["ResearchSession"]:
        session = ResearchSession.load(session_id)
        if not session:
            return None
        if session.status == "paused":
            session.status = "running"
            session.touch()
            session.save()
        return session

    def mark_done(self, session: ResearchSession, task_id: str = "", summary: str = "") -> None:
        session.status = "done"
        if task_id:
            session.task_id = task_id
        if summary:
            session.summary = summary
        session.touch()
        session.save()

    def mark_error(self, session: ResearchSession, error: str) -> None:
        session.status = "error"
        session.summary = error
        session.touch()
        session.save()

    def pause_session(self, session_id: str) -> bool:
        session = ResearchSession.load(session_id)
        if not session:
            return False
        session.status = "paused"
        session.touch()
        session.save()
        return True

    def delete_session(self, session_id: str) -> bool:
        path = RESEARCH_DIR / f"{session_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False


_engine: Optional[ResearchEngine] = None


def get_engine() -> ResearchEngine:
    global _engine
    if _engine is None:
        _engine = ResearchEngine()
    return _engine