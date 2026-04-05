"""
Phase 11 tests — Beginner Workflows & Capability Discovery.
All tests run without a live LLM or Ollama instance.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))


# ─────────────────────────────────────────────────────────────────────────────
# 1. WorkflowMeta dataclass — required fields present and typed correctly
# ─────────────────────────────────────────────────────────────────────────────

def test_workflow_meta_fields():
    from workflows.engine import WorkflowMeta
    m = WorkflowMeta(
        id="test-wf",
        name="Test Workflow",
        category="files",
        description="A test workflow",
    )
    assert m.id == "test-wf"
    assert m.category == "files"
    assert isinstance(m.tags, list)
    assert isinstance(m.requires, list)
    assert isinstance(m.platforms, list)
    assert m.destructive is False
    assert m.needs_agent is True
    assert m.timeout_s == 120


# ─────────────────────────────────────────────────────────────────────────────
# 2. WorkflowEngine.load_registry() — loads all 27 workflows
# ─────────────────────────────────────────────────────────────────────────────

def test_load_registry_count():
    from workflows.engine import WorkflowEngine
    eng = WorkflowEngine()
    eng.load_registry()
    wfs = eng.list_workflows()
    assert len(wfs) >= 27, f"Expected >=27 workflows, got {len(wfs)}"


# ─────────────────────────────────────────────────────────────────────────────
# 3. WorkflowEngine.load_registry() — idempotent (double-call doesn't duplicate)
# ─────────────────────────────────────────────────────────────────────────────

def test_load_registry_idempotent():
    from workflows.engine import WorkflowEngine
    eng = WorkflowEngine()
    eng.load_registry()
    count_first = len(eng.list_workflows())
    eng.load_registry()
    count_second = len(eng.list_workflows())
    assert count_first == count_second, "load_registry() is not idempotent"


# ─────────────────────────────────────────────────────────────────────────────
# 4. WorkflowEngine.list_workflows() — category filter works
# ─────────────────────────────────────────────────────────────────────────────

def test_list_workflows_category_filter():
    from workflows.engine import WorkflowEngine
    eng = WorkflowEngine()
    eng.load_registry()
    files_wfs = eng.list_workflows(category="files")
    assert len(files_wfs) > 0
    assert all(w.category == "files" for w in files_wfs)


# ─────────────────────────────────────────────────────────────────────────────
# 5. WorkflowEngine.list_workflows() — search filter works
# ─────────────────────────────────────────────────────────────────────────────

def test_list_workflows_search_filter():
    from workflows.engine import WorkflowEngine
    eng = WorkflowEngine()
    eng.load_registry()
    results = eng.list_workflows(search="organize")
    assert len(results) >= 1
    assert any("organize" in w.id.lower() or "organize" in w.name.lower() for w in results)


# ─────────────────────────────────────────────────────────────────────────────
# 6. WorkflowResult — status enum values are strings (for JSON serialization)
# ─────────────────────────────────────────────────────────────────────────────

def test_workflow_status_is_string():
    from workflows.engine import WorkflowStatus, WorkflowResult
    r = WorkflowResult(status=WorkflowStatus.OK, output="hello")
    assert r.status.value == "ok"
    assert r.status == "ok"   # str subclass check


# ─────────────────────────────────────────────────────────────────────────────
# 7. CapabilityScanner.scan() — never raises, returns CapabilityProfile
# ─────────────────────────────────────────────────────────────────────────────

def test_capability_scanner_never_raises():
    from workflows.discovery import CapabilityScanner, CapabilityProfile
    scanner = CapabilityScanner()
    profile = scanner.scan()
    assert isinstance(profile, CapabilityProfile)
    assert isinstance(profile.file_types, dict)
    assert isinstance(profile.running_services, list)
    assert isinstance(profile.has_git, bool)


# ─────────────────────────────────────────────────────────────────────────────
# 8. CapabilityScanner.suggest() — returns sorted WorkflowSuggestion list
# ─────────────────────────────────────────────────────────────────────────────

def test_capability_scanner_suggest():
    from workflows.engine import WorkflowEngine
    from workflows.discovery import CapabilityScanner, WorkflowSuggestion

    eng = WorkflowEngine()
    eng.load_registry()
    scanner = CapabilityScanner()
    profile = scanner.scan()
    suggestions = scanner.suggest(profile, user_profile="developer")

    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert all(isinstance(s, WorkflowSuggestion) for s in suggestions)
    # sorted descending by relevance
    scores = [s.relevance for s in suggestions]
    assert scores == sorted(scores, reverse=True), "Suggestions not sorted by relevance"


# ─────────────────────────────────────────────────────────────────────────────
# 9. WizardState — has user_profile field with correct default
# ─────────────────────────────────────────────────────────────────────────────

def test_wizard_state_user_profile_field():
    from setup.first_run.state import WizardState
    state = WizardState()
    assert hasattr(state, "user_profile"), "WizardState missing user_profile field"
    assert state.user_profile == "", f"Default user_profile should be '' got {state.user_profile!r}"
    state.user_profile = "developer"
    assert state.user_profile == "developer"
