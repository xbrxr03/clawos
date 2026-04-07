# SPDX-License-Identifier: AGPL-3.0-or-later
"""
tests/unit/test_skilld.py — Skill loader unit tests
Run: python -m pytest tests/unit/test_skilld.py -v
"""
import sys
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.skilld.service import (
    _tokenise,
    _bm25,
    _parse_frontmatter,
    _load_skill,
    SkillLoader,
    format_skills_block,
    Skill,
    SCORE_THRESHOLD,
)


# ── Frontmatter ────────────────────────────────────────────────────────────────

def test_frontmatter_basic():
    raw = """---
description: Summarizes documents
triggers: [summarize, recap, tldr]
pinned: false
---
## Skill body
Does something useful.
"""
    meta, body = _parse_frontmatter(raw)
    assert meta["description"] == "Summarizes documents"
    assert meta["triggers"] == ["summarize", "recap", "tldr"]
    assert meta["pinned"] == False
    assert "Does something useful" in body


def test_frontmatter_pinned_true():
    raw = "---\ndescription: Always here\npinned: true\n---\nBody."
    meta, _ = _parse_frontmatter(raw)
    assert meta["pinned"] == True


def test_frontmatter_none():
    raw = "## Just a skill\nNo frontmatter here."
    meta, body = _parse_frontmatter(raw)
    assert meta == {}
    assert "No frontmatter" in body


def test_frontmatter_empty_val():
    raw = "---\ndescription: Something\ntools:\npinned: false\n---\nBody."
    meta, body = _parse_frontmatter(raw)
    assert meta["description"] == "Something"
    assert "Body" in body


# ── Tokeniser ──────────────────────────────────────────────────────────────────

def test_tokenise_basic():
    tokens = _tokenise("Summarize this document for me")
    assert "summarize" in tokens
    assert "document" in tokens
    assert "for" not in tokens   # 3 chars — filtered (>3 required)
    assert "this" in tokens


def test_tokenise_lowercase():
    tokens = _tokenise("GitHub SKILL Ollama")
    assert "github" in tokens
    assert "skill" in tokens
    assert "ollama" in tokens


def test_tokenise_strips_punctuation():
    tokens = _tokenise("hello, world! fuzzy-wuzzy")
    assert "hello" in tokens
    assert "world" in tokens
    assert "fuzzy" in tokens
    assert "wuzzy" in tokens


# ── BM25 ───────────────────────────────────────────────────────────────────────

def test_bm25_relevant_higher():
    corpus = [
        ["summarize", "document", "text", "content"],
        ["github", "pull", "request", "merge"],
        ["recipe", "cook", "food", "ingredient"],
    ]
    q  = ["summarize", "text"]
    s0 = _bm25(q, corpus[0], corpus)
    s1 = _bm25(q, corpus[1], corpus)
    assert s0 > s1


def test_bm25_empty_query():
    corpus = [["summarize", "document"]]
    assert _bm25([], corpus[0], corpus) == 0.0


def test_bm25_no_match():
    corpus = [["github", "pull", "request"]]
    assert _bm25(["summarize", "document"], corpus[0], corpus) == 0.0


# ── Single skill load ──────────────────────────────────────────────────────────

@pytest.fixture
def skill_dir(tmp_path):
    d = tmp_path / "my-skill"
    d.mkdir()
    (d / "SKILL.md").write_text("""---
description: Summarizes documents and text
triggers: [summarize, recap, tldr]
pinned: false
---
## My Skill
Use when summarizing.
""")
    return d


def test_load_skill_basic(skill_dir):
    s = _load_skill("my-skill", skill_dir / "SKILL.md", "claw")
    assert s is not None
    assert s.name == "my-skill"
    assert s.description == "Summarizes documents and text"
    assert "summarize" in s.triggers
    assert s.pinned == False
    assert s.source == "claw"


def test_load_skill_no_frontmatter(tmp_path):
    d = tmp_path / "bare"
    d.mkdir()
    (d / "SKILL.md").write_text("## Bare Skill\nDoes something useful.")
    s = _load_skill("bare", d / "SKILL.md", "openclaw")
    assert s is not None
    assert s.source == "openclaw"
    assert s.description  # falls back to first body line


def test_load_skill_pinned(tmp_path):
    d = tmp_path / "pinned"
    d.mkdir()
    (d / "SKILL.md").write_text("---\ndescription: Always\npinned: true\n---\nAlways on.")
    s = _load_skill("pinned", d / "SKILL.md", "claw")
    assert s.pinned == True


def test_load_skill_truncates(tmp_path):
    d = tmp_path / "big"
    d.mkdir()
    (d / "SKILL.md").write_text("---\ndescription: Big\n---\n" + "x" * 2000)
    s = _load_skill("big", d / "SKILL.md", "claw")
    assert len(s.content) < 1000
    assert "[...truncated]" in s.content


# ── SkillLoader ────────────────────────────────────────────────────────────────

@pytest.fixture
def loader(tmp_path):
    skills = tmp_path / "skills"
    skills.mkdir()

    (skills / "summarize").mkdir()
    (skills / "summarize" / "SKILL.md").write_text("""---
description: Summarizes documents
triggers: [summarize, recap, tldr, condense]
pinned: false
---
Use when the user wants to summarize or condense content.
""")

    (skills / "github").mkdir()
    (skills / "github" / "SKILL.md").write_text("""---
description: GitHub PR and issue management
triggers: [github, pull, request, issue, merge]
pinned: false
---
Use when managing GitHub repos, PRs, or issues.
""")

    (skills / "workspace-context").mkdir()
    (skills / "workspace-context" / "SKILL.md").write_text("""---
description: Always-on workspace context
pinned: true
---
You are in the default workspace. PINNED.md contains user preferences.
""")

    with patch("services.skilld.service.SKILL_PATHS", [skills]):
        return SkillLoader(skill_paths=[skills])


def test_loader_count(loader):
    assert loader.count == 3


def test_loader_pinned(loader):
    p = loader.pinned()
    assert len(p) == 1
    assert p[0].name == "workspace-context"


def test_loader_score_summarize(loader):
    matches = loader.score("please summarize this document for me")
    assert len(matches) > 0
    assert matches[0].skill.name == "summarize"


def test_loader_score_github(loader):
    matches = loader.score("create a pull request for my changes on github")
    names = [m.skill.name for m in matches]
    assert "github" in names


def test_loader_top_includes_pinned(loader):
    top = loader.top("summarize this document")
    names = [s.name for s in top]
    assert "workspace-context" in names
    assert "summarize" in names


def test_loader_trivial_input_low_score(loader):
    matches = loader.score("hi")
    assert all(m.score < SCORE_THRESHOLD for m in matches)


def test_loader_dedup(tmp_path):
    claw_dir     = tmp_path / "claw_skills"
    openclaw_dir = tmp_path / "openclaw_skills"
    claw_dir.mkdir()
    openclaw_dir.mkdir()

    for d in [claw_dir, openclaw_dir]:
        s = d / "summarize"
        s.mkdir()
        (s / "SKILL.md").write_text(f"---\ndescription: From {d.name}\n---\nBody.")

    loader = SkillLoader(skill_paths=[claw_dir, openclaw_dir])
    # Only one skill named "summarize" — first path wins
    assert loader.count == 1
    assert loader.get("summarize") is not None


def test_loader_reload(tmp_path):
    skills = tmp_path / "skills"
    skills.mkdir()
    loader = SkillLoader(skill_paths=[skills])
    assert loader.count == 0

    s = skills / "new-skill"
    s.mkdir()
    (s / "SKILL.md").write_text("---\ndescription: New\n---\nNew skill.")

    n = loader.reload()
    assert n == 1
    assert loader.count == 1


def test_loader_get(loader):
    s = loader.get("summarize")
    assert s is not None
    assert s.name == "summarize"


def test_loader_get_missing(loader):
    assert loader.get("nonexistent") is None


def test_loader_list_all(loader):
    items = loader.list_all()
    assert len(items) == 3
    names = [i["name"] for i in items]
    assert "summarize" in names
    assert "github" in names
    assert "workspace-context" in names


# ── Format block ───────────────────────────────────────────────────────────────

def test_format_empty():
    assert format_skills_block([]) == ""


def test_format_single():
    s = Skill(name="summarize", path=Path("/fake"),
              content="Use when summarizing.", description="Summarizes docs")
    block = format_skills_block([s])
    assert "<available_skills>" in block
    assert "## summarize" in block
    assert "Use when summarizing." in block
    assert "</available_skills>" in block


def test_format_multiple():
    skills = [
        Skill(name="alpha", path=Path("/a"), content="Alpha content.", description="A"),
        Skill(name="beta",  path=Path("/b"), content="Beta content.",  description="B"),
    ]
    block = format_skills_block(skills)
    assert "## alpha" in block
    assert "## beta" in block
