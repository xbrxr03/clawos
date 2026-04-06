# SPDX-License-Identifier: AGPL-3.0-or-later
"""
researchd - Research Engine
===========================
Multi-source research with citations, provider-neutral search,
and disk-persisted resumable sessions.

Search providers (all optional, falls back gracefully):
  - Brave Search API  (env: BRAVE_API_KEY  or config: research.brave_api_key)
  - Tavily Search API (env: TAVILY_API_KEY or config: research.tavily_api_key)
  - No-key mode: fetches user-supplied URLs directly
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
except Exception:
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
    provider: str        # brave | tavily | fetch | none
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
        except Exception as exc:
            log.warning("Failed to load research session %s: %s", session_id, exc)
            return None

    @classmethod
    def list_all(cls) -> List[dict]:
        RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
        sessions = []
        for path in sorted(RESEARCH_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                # Return lightweight summary (no full source text)
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
            except Exception:
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
        except Exception:
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
    except Exception as exc:
        return ResearchSource(url=url, title=url, snippet="", error=str(exc))


# ── Search providers ──────────────────────────────────────────────────────────
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


def _detect_provider() -> tuple[str, str]:
    """Return (provider_name, api_key) using env/config. Falls back to 'none'."""
    brave_key = os.environ.get("BRAVE_API_KEY", "").strip()
    if brave_key:
        return "brave", brave_key
    tavily_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if tavily_key:
        return "tavily", tavily_key
    try:
        from clawos_core.config.loader import get as get_config
        brave_key = str(get_config("research.brave_api_key", "")).strip()
        if brave_key:
            return "brave", brave_key
        tavily_key = str(get_config("research.tavily_api_key", "")).strip()
        if tavily_key:
            return "tavily", tavily_key
    except Exception:
        pass
    return "none", ""


# ── Citation extraction ───────────────────────────────────────────────────────
def _extract_citations(sources: List[ResearchSource], query: str) -> List[Citation]:
    """Extract citations from fetched sources using keyword matching."""
    query_terms = set(re.findall(r"\b\w{4,}\b", query.lower()))
    citations: List[Citation] = []
    for source in sources:
        if not source.fetched or not source.text:
            continue
        # Score sentences by query term overlap
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

        # Search
        if provider == "brave" and api_key:
            try:
                session.sources = _brave_search(query, api_key)
            except Exception as exc:
                log.warning("Brave search failed: %s", exc)
                session.sources = []
        elif provider == "tavily" and api_key:
            try:
                session.sources = _tavily_search(query, api_key)
            except Exception as exc:
                log.warning("Tavily search failed: %s", exc)
                session.sources = []
        else:
            session.provider = "fetch"

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

    def resume_session(self, session_id: str) -> Optional[ResearchSession]:
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
