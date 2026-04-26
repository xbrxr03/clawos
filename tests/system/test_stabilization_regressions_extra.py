# SPDX-License-Identifier: AGPL-3.0-or-later
import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient


def _git(args, cwd: Path) -> None:
    subprocess.run(args, cwd=str(cwd), check=True, capture_output=True, text=True)


def _commit(repo: Path, message: str) -> None:
    _git(["git", "add", "."], repo)
    _git(
        [
            "git",
            "-c",
            "user.name=Test User",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-m",
            message,
        ],
        repo,
    )


def test_dashboard_bearer_token_grants_access(monkeypatch):
    from services.dashd.api import create_app

    class IncompleteSetupState:
        completion_marker = False

    monkeypatch.setattr("services.dashd.api._setup_state", lambda: IncompleteSetupState())

    app = create_app({
        "host": "127.0.0.1",
        "auth_required": True,
        "token": "dash-token",
        "cookie_name": "dash_session",
    })

    with TestClient(app) as client:
        response = client.get("/api/tasks", headers={"Authorization": "Bearer dash-token"})
        assert response.status_code == 200


def test_dashboard_cookie_session_grants_access_after_login(monkeypatch):
    from services.dashd.api import create_app

    class IncompleteSetupState:
        completion_marker = False

    monkeypatch.setattr("services.dashd.api._setup_state", lambda: IncompleteSetupState())

    app = create_app({
        "host": "127.0.0.1",
        "auth_required": True,
        "token": "dash-token",
        "cookie_name": "dash_session",
    })

    with TestClient(app) as client:
        assert client.post("/api/login", json={"token": "dash-token"}).status_code == 200
        assert client.get("/api/tasks").status_code == 200


def test_a2a_peer_listing_rejects_untrusted_header(monkeypatch):
    monkeypatch.setattr(
        "services.a2ad.peer_registry.get_registry",
        lambda: type(
            "Registry",
            (),
            {
                "is_blocked": staticmethod(lambda url: False),
                "is_trusted_url": staticmethod(lambda url: False),
            },
        )(),
    )

    from services.a2ad.service import create_app

    app = create_app({
        "host": "127.0.0.1",
        "auth_token": "secret-token",
        "mdns_enabled": False,
    })

    with TestClient(app) as client:
        response = client.get(
            "/a2a/peers",
            headers={
                "Authorization": "Bearer secret-token",
                "X-ClawOS-Peer-URL": "http://unknown-peer.test/a2a",
            },
        )
        assert response.status_code == 403




def test_toolbridge_prompt_only_lists_granted_tools():
    from services.toolbridge.service import ToolBridge

    policy = type("Policy", (), {"granted_tools": ["fs.read", "shell.restricted"]})()
    bridge = ToolBridge(policy, None, "nexus_default")

    prompt = bridge.get_tool_list_for_prompt()
    assert "fs.read" in prompt
    assert "shell.restricted" in prompt
    assert "fs.write" not in prompt


def test_keyword_terms_filters_common_words():
    from workflows.helpers import keyword_terms

    terms = keyword_terms("the system keeps the logs and the system summarizes logs for operators", limit=3)
    assert "system" in terms
    assert "logs" in terms
    assert "the" not in terms


def test_summarize_sentences_returns_key_sentences():
    from workflows.helpers import summarize_sentences

    summary = summarize_sentences(
        "ClawOS manages workflows for local automation. "
        "Workflows improve reliability for local automation. "
        "Automation benefits from deterministic execution on every run.",
        limit=2,
    )
    assert len(summary) == 2
    assert any("local automation" in sentence for sentence in summary)


def test_repo_summary_works_from_nested_git_directory(workspace_tmp_dir):
    from workflows.repo_summary.workflow import run

    repo = workspace_tmp_dir / "repo"
    repo.mkdir()
    _git(["git", "init"], repo)
    (repo / "README.md").write_text("demo\n", encoding="utf-8")
    _commit(repo, "feat: initial import")
    nested = repo / "docs"
    nested.mkdir()

    result = asyncio.run(run({"dir": str(nested)}, None))
    assert result.status.value == "ok"
    assert "**Repository:** docs" in result.output


def test_write_readme_uses_package_json_description(workspace_tmp_dir):
    from workflows.write_readme.workflow import run

    package_json = workspace_tmp_dir / "package.json"
    package_json.write_text(
        json.dumps({"name": "frontend-app", "description": "Browser dashboard", "scripts": {"dev": "vite"}}),
        encoding="utf-8",
    )

    result = asyncio.run(run({"dir": str(workspace_tmp_dir)}, None))
    assert result.status.value == "ok"
    assert "# frontend-app" in result.output
    assert "Browser dashboard" in result.output


def test_pr_review_fails_on_empty_diff_file(workspace_tmp_dir):
    from workflows.pr_review.workflow import run

    diff = workspace_tmp_dir / "empty.diff"
    diff.write_text("", encoding="utf-8")

    result = asyncio.run(run({"file": str(diff)}, None))
    assert result.status.value == "failed"
    assert "No diff content was found" in (result.error or "")


def test_changelog_fails_on_invalid_git_range(workspace_tmp_dir):
    from workflows.changelog.workflow import run

    repo = workspace_tmp_dir / "repo"
    repo.mkdir()
    _git(["git", "init"], repo)
    (repo / "README.md").write_text("demo\n", encoding="utf-8")
    _commit(repo, "feat: initial import")

    result = asyncio.run(run({"dir": str(repo), "from": "does-not-exist", "to": "HEAD"}, None))
    assert result.status.value == "failed"
