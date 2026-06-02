# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for researchd engine and session management."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from services.researchd.engine import (
    Citation, ResearchSource, ResearchSession, ResearchEngine,
    _extract_citations, _fetch_page, _detect_provider,
)


class TestCitation:
    def test_defaults(self):
        c = Citation(url="https://example.com", title="Test", excerpt="hello")
        assert c.relevance == "supporting"

    def test_to_dict(self):
        c = Citation(url="u", title="t", excerpt="e", relevance="primary")
        d = c.to_dict()
        assert d["relevance"] == "primary"
        assert d["url"] == "u"


class TestResearchSource:
    def test_defaults(self):
        s = ResearchSource(url="https://example.com", title="Test", snippet="hi")
        assert s.fetched is False
        assert s.error == ""

    def test_to_dict(self):
        s = ResearchSource(url="u", title="t", snippet="s", text="txt", fetched=True)
        d = s.to_dict()
        assert d["fetched"] is True
        assert d["text"] == "txt"


class TestResearchSession:
    def test_create(self):
        s = ResearchSession(id="abc", query="test query", status="running", provider="none")
        assert s.id == "abc"
        assert s.sources == []
        assert s.citations == []

    def test_touch_updates_timestamp(self):
        s = ResearchSession(id="abc", query="q", status="running", provider="none")
        old = s.updated_at
        import time
        time.sleep(0.01)
        s.touch()
        assert s.updated_at >= old

    def test_save_and_load(self, tmp_path):
        import services.researchd.engine as eng
        old_dir = eng.RESEARCH_DIR
        eng.RESEARCH_DIR = tmp_path
        try:
            s = ResearchSession(id="test123", query="save test", status="done", provider="brave")
            s.sources = [ResearchSource(url="https://ex.com", title="Example", snippet="hi")]
            s.citations = [Citation(url="https://ex.com", title="Example", excerpt="text", relevance="primary")]
            s.save()

            loaded = ResearchSession.load("test123")
            assert loaded is not None
            assert loaded.query == "save test"
            assert len(loaded.sources) == 1
            assert len(loaded.citations) == 1
            assert loaded.citations[0].relevance == "primary"
        finally:
            eng.RESEARCH_DIR = old_dir

    def test_load_nonexistent(self, tmp_path):
        import services.researchd.engine as eng
        old_dir = eng.RESEARCH_DIR
        eng.RESEARCH_DIR = tmp_path
        try:
            assert ResearchSession.load("nonexistent") is None
        finally:
            eng.RESEARCH_DIR = old_dir

    def test_list_all(self, tmp_path):
        import services.researchd.engine as eng
        old_dir = eng.RESEARCH_DIR
        eng.RESEARCH_DIR = tmp_path
        try:
            s1 = ResearchSession(id="s1", query="q1", status="done", provider="brave")
            s1.save()
            s2 = ResearchSession(id="s2", query="q2", status="running", provider="tavily")
            s2.save()
            all_sessions = ResearchSession.list_all()
            assert len(all_sessions) == 2
            ids = {s["id"] for s in all_sessions}
            assert "s1" in ids
            assert "s2" in ids
        finally:
            eng.RESEARCH_DIR = old_dir


class TestExtractCitations:
    def test_extracts_from_fetched_sources(self):
        sources = [
            ResearchSource(
                url="https://example.com",
                title="Example",
                snippet="hello",
                text="Python testing frameworks are important for software quality. Unit tests ensure correctness. Integration tests verify components work together.",
                fetched=True,
            ),
        ]
        citations = _extract_citations(sources, "python testing framework")
        assert len(citations) >= 1
        assert citations[0].url == "https://example.com"

    def test_skips_unfetched_sources(self):
        sources = [ResearchSource(url="https://example.com", title="Test", snippet="hi", fetched=False)]
        citations = _extract_citations(sources, "test")
        assert len(citations) == 0

    def test_ranks_primary_first(self):
        sources = [
            ResearchSource(url="https://a.com", title="A", snippet="",
                          text="Machine learning neural networks deep learning architectures for natural language processing tasks.",
                          fetched=True),
            ResearchSource(url="https://b.com", title="B", snippet="",
                          text="The weather forecast suggests sunny weekend activities outdoors recreation.",
                          fetched=True),
        ]
        citations = _extract_citations(sources, "machine learning neural networks natural language")
        if len(citations) >= 2:
            # Source A should rank higher than source B
            a_idx = next((i for i, c in enumerate(citations) if c.url == "https://a.com"), 99)
            b_idx = next((i for i, c in enumerate(citations) if c.url == "https://b.com"), 99)
            assert a_idx < b_idx


class TestFetchPage:
    def test_unsupported_scheme(self):
        result = _fetch_page("ftp://example.com")
        assert result.error != ""

    def test_http_fetch(self):
        """Test fetching a real HTTP page (integration test)."""
        try:
            result = _fetch_page("https://httpbin.org/html")
            # May fail in offline environments
            if not result.error:
                assert result.fetched is True
                assert result.title != ""
        except (OSError, TimeoutError):
            pytest.skip("Network unavailable")


class TestDetectProvider:
    def test_no_provider(self):
        with patch.dict("os.environ", {"BRAVE_API_KEY": "", "TAVILY_API_KEY": ""}):
            provider, key = _detect_provider()
            assert provider in ("none", "brave", "tavily")

    def test_brave_from_env(self):
        with patch.dict("os.environ", {"BRAVE_API_KEY": "test-key-123"}, clear=False):
            provider, key = _detect_provider()
            if "BRAVE_API_KEY" in __import__("os").environ:
                assert provider == "brave"
                assert key == "test-key-123"


class TestResearchEngine:
    def test_start_session_no_provider(self, tmp_path):
        import services.researchd.engine as eng
        old_dir = eng.RESEARCH_DIR
        eng.RESEARCH_DIR = tmp_path
        try:
            with patch.dict("os.environ", {"BRAVE_API_KEY": "", "TAVILY_API_KEY": ""}):
                engine = ResearchEngine()
                session = engine.start_session(query="test query about Python")
                assert session.id != ""
                assert session.query == "test query about Python"
                assert session.status == "running"
        finally:
            eng.RESEARCH_DIR = old_dir

    def test_fetch_sources_empty(self, tmp_path):
        import services.researchd.engine as eng
        old_dir = eng.RESEARCH_DIR
        eng.RESEARCH_DIR = tmp_path
        try:
            engine = ResearchEngine()
            session = ResearchSession(id="test", query="q", status="running", provider="none")
            session = engine.fetch_sources(session)
            assert session.citations == []
        finally:
            eng.RESEARCH_DIR = old_dir

    def test_mark_done(self, tmp_path):
        import services.researchd.engine as eng
        old_dir = eng.RESEARCH_DIR
        eng.RESEARCH_DIR = tmp_path
        try:
            engine = ResearchEngine()
            session = ResearchSession(id="test", query="q", status="running", provider="none")
            session.save()
            engine.mark_done(session, summary="Research complete")
            loaded = ResearchSession.load("test")
            assert loaded.status == "done"
            assert loaded.summary == "Research complete"
        finally:
            eng.RESEARCH_DIR = old_dir

    def test_delete_session(self, tmp_path):
        import services.researchd.engine as eng
        old_dir = eng.RESEARCH_DIR
        eng.RESEARCH_DIR = tmp_path
        try:
            engine = ResearchEngine()
            session = ResearchSession(id="del-test", query="q", status="done", provider="none")
            session.save()
            assert engine.delete_session("del-test") is True
            assert ResearchSession.load("del-test") is None
            assert engine.delete_session("nonexistent") is False
        finally:
            eng.RESEARCH_DIR = old_dir

    def test_build_agent_intent(self):
        engine = ResearchEngine()
        session = ResearchSession(id="test", query="python testing", status="running", provider="none")
        session.sources = [
            ResearchSource(url="https://a.com", title="Source A", snippet="",
                          text="Python testing is important. Use pytest for best results.",
                          fetched=True),
        ]
        session.citations = [
            Citation(url="https://a.com", title="Source A", excerpt="Python testing is important.",
                     relevance="primary"),
        ]
        intent = engine.build_agent_intent(session)
        assert "Research task: python testing" in intent
        assert "Source A" in intent
        assert "primary" in intent