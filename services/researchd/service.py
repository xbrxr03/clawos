# SPDX-License-Identifier: AGPL-3.0-or-later
"""
researchd — Deep Research Service
==================================
FastAPI service for multi-source research with citation tracking.
Searches via Brave/Tavily API or direct URL fetch, extracts content,
builds citations, and provides structured session management.

Endpoints:
  POST /api/research/start   — start a research session
  GET  /api/research/list    — list all sessions
  GET  /api/research/{id}    — get session details
  POST /api/research/{id}/fetch  — fetch source content
  POST /api/research/{id}/pause  — pause session
  POST /api/research/{id}/delete — delete session
  GET  /api/research/health   — service health
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.researchd.engine import (
    ResearchSession,
    get_engine,
)

log = logging.getLogger("researchd")
router = APIRouter(prefix="/api/research", tags=["research"])


# ── Health check (defined first to avoid /{session_id} matching "health") ───────

@router.get("/health")
async def health():
    """Service health check."""
    from services.researchd.engine import _detect_provider
    provider, key = _detect_provider()
    providers = {
        "active": provider,
        "available": ["ddg", "wikipedia"],  # always free
        "configured": [],
    }
    # Check paid providers
    import os
    if os.environ.get("BRAVE_API_KEY", "").strip():
        providers["available"].append("brave")
        providers["configured"].append("brave")
    if os.environ.get("TAVILY_API_KEY", "").strip():
        providers["available"].append("tavily")
        providers["configured"].append("tavily")
    searxng_url = os.environ.get("SEARXNG_URL", "").strip()
    if searxng_url:
        providers["available"].append("searxng")
        providers["configured"].append({"searxng": searxng_url})
    return {"status": "ok", "engine": "ready", "providers": providers}


# ── Request models ────────────────────────────────────────────────────────────

class StartRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)
    seed_urls: Optional[list[str]] = Field(default=None, max_length=10)
    provider: Optional[str] = Field(default=None, pattern="^(brave|tavily|searxng|ddg|wikipedia|fetch|none)$")
    api_key: Optional[str] = None  # API key for brave/tavily, or SearXNG URL for searxng


class FetchRequest(BaseModel):
    pass  # No params needed, fetches all unfetched sources


class MarkDoneRequest(BaseModel):
    task_id: Optional[str] = None
    summary: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/start")
async def start_research(req: StartRequest):
    """Start a new research session."""
    engine = get_engine()
    try:
        session = engine.start_session(
            query=req.query,
            seed_urls=req.seed_urls,
            provider_override=req.provider,
            api_key_override=req.api_key,
        )
        # Auto-fetch sources
        session = engine.fetch_sources(session)
        return session.to_dict()
    except Exception as exc:
        log.error("Research start failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/list")
async def list_sessions():
    """List all research sessions."""
    return ResearchSession.list_all()


@router.get("/{session_id}")
async def get_session(session_id: str):
    """Get a research session by ID."""
    session = ResearchSession.load(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.to_dict()


@router.post("/{session_id}/fetch")
async def fetch_sources(session_id: str):
    """Fetch content for all unfetched sources in a session."""
    session = ResearchSession.load(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    engine = get_engine()
    try:
        session = engine.fetch_sources(session)
        return session.to_dict()
    except Exception as exc:
        log.error("Fetch failed for %s: %s", session_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{session_id}/pause")
async def pause_session(session_id: str):
    """Pause a running research session."""
    engine = get_engine()
    ok = engine.pause_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "paused"}


@router.post("/{session_id}/resume")
async def resume_session(session_id: str):
    """Resume a paused research session."""
    engine = get_engine()
    session = engine.resume_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.to_dict()


@router.post("/{session_id}/done")
async def mark_done(session_id: str, req: MarkDoneRequest):
    """Mark a session as done with optional summary."""
    session = ResearchSession.load(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    engine = get_engine()
    engine.mark_done(session, task_id=req.task_id or "", summary=req.summary or "")
    return {"status": "done"}


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """Delete a research session."""
    engine = get_engine()
    ok = engine.delete_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True}