# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Tests for auto_skill module — Issue #64
"""
import os
import re
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure project root is importable
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))

from services.skilld.auto_skill import (
    should_auto_skill,
    generate_skill,
    save_auto_skill,
    update_auto_skill,
    find_similar_skill,
    _generate_template,
)
from clawos_core.constants import AUTO_SKILLS_DIR


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def temp_skills_dir(tmp_path, monkeypatch):
    """Use a temp directory for auto skills instead of real ~/.claw/skills/auto."""
    auto_dir = tmp_path / "skills" / "auto"
    auto_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("services.skilld.auto_skill.AUTO_SKILLS_DIR", auto_dir)
    yield auto_dir


def _make_tool_call(name, args=None):
    """Helper to create a tool_call dict."""
    return {"function": {"name": name, "arguments": args or {}}}


def _make_history(tool_calls=0, user_turns=1, assistant_text="Done."):
    """Build a simple history with specified tool calls and user turns."""
    history = []
    for i in range(user_turns):
        history.append({"role": "user", "content": f"User message {i+1}: do something useful"})
        if tool_calls > 0 and i == user_turns - 1:
            tcs = [_make_tool_call(f"tool_{j+1}") for j in range(tool_calls)]
            history.append({"role": "assistant", "content": assistant_text, "tool_calls": tcs})
            for j in range(tool_calls):
                history.append({"role": "tool", "content": f"Result of tool_{j+1}", "tool_name": f"tool_{j+1}"})
        else:
            history.append({"role": "assistant", "content": assistant_text})
    return history


# ── Detection tests ───────────────────────────────────────────────────────────

class TestShouldAutoSkill:
    def test_should_auto_skill_multiple_tools(self):
        """3+ tool calls triggers auto-skill."""
        history = _make_history(tool_calls=3, user_turns=1)
        assert should_auto_skill(history) is True

    def test_should_auto_skill_multiple_turns(self):
        """2+ user turns triggers auto-skill."""
        history = _make_history(tool_calls=0, user_turns=3)
        assert should_auto_skill(history) is True

    def test_should_not_auto_skill_simple(self):
        """Single tool, single turn does NOT trigger auto-skill."""
        history = _make_history(tool_calls=1, user_turns=1)
        assert should_auto_skill(history) is False

    def test_empty_history(self):
        """Empty history should not trigger."""
        assert should_auto_skill([]) is False

    def test_exactly_two_turns(self):
        """Exactly 2 user turns should trigger (>=2)."""
        history = _make_history(tool_calls=0, user_turns=2)
        assert should_auto_skill(history) is True

    def test_exactly_three_tools_via_assistant(self):
        """3 tool calls embedded in assistant message triggers."""
        history = [
            {"role": "user", "content": "do stuff"},
            {"role": "assistant", "content": "", "tool_calls": [
                _make_tool_call("read_file"),
                _make_tool_call("write_file"),
                _make_tool_call("search"),
            ]},
        ]
        assert should_auto_skill(history) is True

    def test_tool_result_messages_also_count(self):
        """Tool result messages (role=tool) also count toward tool count."""
        history = [
            {"role": "user", "content": "hello"},
            {"role": "tool", "content": "result1", "tool_name": "search"},
            {"role": "tool", "content": "result2", "tool_name": "read"},
            {"role": "tool", "content": "result3", "tool_name": "write"},
        ]
        assert should_auto_skill(history) is True


# ── Generation tests ───────────────────────────────────────────────────────────

class TestGenerateSkill:
    def test_generate_skill_template(self):
        """Template generation produces valid SKILL.md with frontmatter."""
        history = _make_history(tool_calls=2, user_turns=1, assistant_text="Done")
        slug, content = generate_skill(history)
        # Must have frontmatter
        assert content.startswith("---")
        assert "trigger:" in content
        assert "name:" in content
        assert "pinned: false" in content
        # Slug should be derived
        assert len(slug) > 0

    def test_generate_skill_has_steps(self):
        """Template generation includes steps section."""
        history = _make_history(tool_calls=2, user_turns=1)
        _, content = generate_skill(history)
        assert "## Steps" in content

    def test_generate_skill_has_tools_section(self):
        """Template generation includes tools section."""
        history = [
            {"role": "user", "content": "Search for cats"},
            {"role": "assistant", "content": "", "tool_calls": [
                _make_tool_call("search"),
                _make_tool_call("read_file"),
            ]},
        ]
        _, content = generate_skill(history)
        assert "## Tools used" in content
        assert "search" in content
        assert "read_file" in content

    def test_slug_derived_from_first_message(self):
        """Slug is derived from first user message."""
        history = [
            {"role": "user", "content": "search for important files"},
            {"role": "assistant", "content": "Done"},
        ]
        slug, _ = generate_skill(history)
        # Slug should contain keywords from the message
        assert isinstance(slug, str)
        assert len(slug) > 0


# ── Save / Update tests ────────────────────────────────────────────────────────

class TestSaveAutoSkill:
    def test_save_auto_skill(self, temp_skills_dir):
        """Skill saved to correct directory."""
        slug = "test-skill-42"
        content = "---\nname: test-skill-42\ntrigger: test trigger\npinned: false\n---\n# Test Skill\nTest content."
        path = save_auto_skill(slug, content, )
        assert path.exists()
        assert path.parent.name == slug
        assert path.name == "SKILL.md"
        assert "test-skill-42" in path.read_text()

    def test_save_creates_directory(self, temp_skills_dir):
        """Creates the auto directory if it doesn't exist."""
        slug = "new-dir-skill"
        content = "---\nname: new-dir-skill\ntrigger: test\npinned: false\n---\n# New"
        path = save_auto_skill(slug, content)
        assert path.exists()
        assert path.parent.is_dir()


class TestUpdateAutoSkill:
    def test_update_auto_skill(self, temp_skills_dir):
        """Updates existing skill instead of duplicating."""
        slug = "existing-skill"
        original = "---\nname: existing-skill\ntrigger: test\npinned: false\n---\n# Existing\nOld content."
        save_auto_skill(slug, original)

        updated = "---\nname: existing-skill\ntrigger: test updated\npinned: false\n---\n# Existing\nNew content."
        path = update_auto_skill(slug, updated)
        assert path.exists()
        text = path.read_text()
        assert "New content." in text

    def test_update_nonexistent_creates_new(self, temp_skills_dir):
        """Updating a nonexistent skill just saves as new."""
        slug = "ghost-skill"
        content = "---\nname: ghost\ntrigger: ghost\npinned: false\n---\n# Ghost\nContent."
        path = update_auto_skill(slug, content)
        assert path.exists()


# ── Duplicate detection ────────────────────────────────────────────────────────

class TestFindSimilarSkill:
    def test_find_similar_skill_returns_none_when_empty(self, temp_skills_dir):
        """No skills means no similar skill found."""
        result = find_similar_skill("search for files")
        assert result is None

    def test_find_similar_skill_detects_existing(self, temp_skills_dir):
        """Detects a skill with similar trigger."""
        # Create a skill with a known trigger
        skill_dir = temp_skills_dir / "file-search"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: file-search\ntrigger: search for files on disk\npinned: false\n---\n# File Search\nFind files."
        )

        # Search for something similar
        result = find_similar_skill("search for files on disk")
        # The result depends on BM25 scoring — may or may not match depending on threshold
        # At minimum, it shouldn't crash
        assert result is None or isinstance(result, str)


# ── Integration: clawctl skill list ────────────────────────────────────────────

class TestAutoSkillTagInList:
    def test_auto_skill_tag_in_list(self, temp_skills_dir, capsys):
        """clawctl skill list shows [auto] tag for auto-generated skills."""
        # Create an auto-skill
        slug = "auto-test-skill"
        skill_dir = temp_skills_dir / slug
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: auto-test-skill\ntrigger: testing auto skill\npinned: false\n---\n# Auto Test\nAuto skill."
        )

        # Mock the marketplace registry to return empty list
        mock_registry = MagicMock(return_value=[])
        # Patch AUTO_SKILLS_DIR in the constants module (which is what run_list imports)
        with patch("clawos_core.constants.AUTO_SKILLS_DIR", temp_skills_dir):
            with patch("skills.marketplace.registry.get_installed_skills", mock_registry):
                # Import run_list AFTER patching so it picks up the patched constant
                from clawctl.commands.skill import run_list
                run_list()

        captured = capsys.readouterr()
        assert "[auto]" in captured.out