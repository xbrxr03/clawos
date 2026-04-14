# SPDX-License-Identifier: AGPL-3.0-or-later
import asyncio
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


def _run(args, cwd: Path) -> None:
    subprocess.run(args, cwd=str(cwd), check=True, capture_output=True, text=True)

def _commit(repo: Path, message: str) -> None:
    _run(["git", "add", "."], repo)
    _run(
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


def test_priority_workflows_are_direct_and_cross_platform():
    from workflows.engine import WorkflowEngine

    expected = {
        "organize-downloads",
        "summarize-pdf",
        "repo-summary",
        "pr-review",
        "write-readme",
        "disk-report",
        "log-summarize",
        "changelog",
        "find-duplicates",
        "clean-empty-dirs",
    }

    engine = WorkflowEngine()
    engine.load_registry()
    metas = {meta.id: meta for meta in engine.list_workflows()}

    assert expected.issubset(metas)
    for workflow_id in expected:
        meta = metas[workflow_id]
        assert meta.needs_agent is False
        assert meta.platforms == ["linux", "macos", "windows"]


def test_organize_downloads_dry_run_and_apply(workspace_tmp_dir):
    from workflows.organize_downloads.workflow import run

    (workspace_tmp_dir / "photo.jpg").write_bytes(b"image-bytes")
    (workspace_tmp_dir / "notes.md").write_text("docs", encoding="utf-8")

    dry_result = asyncio.run(run({"target_dir": str(workspace_tmp_dir), "dry_run": True}, None))
    assert dry_result.status.value == "ok"
    assert (workspace_tmp_dir / "photo.jpg").exists()
    assert "**Category breakdown:**" in dry_result.output
    assert dry_result.metadata["files_moved"] == 2
    assert dry_result.metadata["total_bytes"] >= 10
    assert dry_result.metadata["category_counts"]["Images"] == 1

    apply_result = asyncio.run(run({"target_dir": str(workspace_tmp_dir), "dry_run": False}, None))
    assert apply_result.status.value == "ok"
    assert (workspace_tmp_dir / "Images" / "photo.jpg").exists()
    assert (workspace_tmp_dir / "Documents" / "notes.md").exists()


def test_organize_downloads_ignores_hidden_and_system_files(workspace_tmp_dir):
    from workflows.organize_downloads.workflow import run

    (workspace_tmp_dir / ".DS_Store").write_text("cache", encoding="utf-8")
    (workspace_tmp_dir / ".env").write_text("SECRET=1\n", encoding="utf-8")
    (workspace_tmp_dir / "desktop.ini").write_text("[.ShellClassInfo]\n", encoding="utf-8")
    (workspace_tmp_dir / "report.pdf").write_text("quarterly report", encoding="utf-8")

    result = asyncio.run(run({"target_dir": str(workspace_tmp_dir), "dry_run": True}, None))

    assert result.status.value == "ok"
    assert result.metadata["files_planned"] == 1
    assert result.metadata["files_skipped"] == 3
    assert "**Ignored files:**" in result.output
    skipped = {item["name"]: item["reason"] for item in result.metadata["skipped_files"]}
    assert skipped[".DS_Store"] == "system"
    assert skipped[".env"] == "hidden"
    assert skipped["desktop.ini"] == "system"


def test_organize_downloads_reports_failed_moves(monkeypatch, workspace_tmp_dir):
    from workflows.organize_downloads.workflow import run

    (workspace_tmp_dir / "photo.jpg").write_bytes(b"image-bytes")
    (workspace_tmp_dir / "locked.txt").write_text("locked", encoding="utf-8")

    def _failing_move(source: Path, destination: Path) -> None:
        if source.name == "locked.txt":
            raise PermissionError("file is in use")
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.rename(destination)

    monkeypatch.setattr("workflows.organize_downloads.workflow._move_file", _failing_move)

    result = asyncio.run(run({"target_dir": str(workspace_tmp_dir), "dry_run": False}, None))

    assert result.status.value == "failed"
    assert result.metadata["files_planned"] == 2
    assert result.metadata["files_moved"] == 1
    assert result.metadata["files_failed"] == 1
    assert "Failed moves" in result.output
    assert result.error == "1 file move failed during organization."
    assert (workspace_tmp_dir / "Images" / "photo.jpg").exists()
    assert (workspace_tmp_dir / "locked.txt").exists()


def test_summarize_pdf_uses_extractable_text(monkeypatch, workspace_tmp_dir):
    from workflows.summarize_pdf.workflow import run

    pdf_path = workspace_tmp_dir / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 test")
    monkeypatch.setattr(
        "workflows.summarize_pdf.workflow.extract_pdf_text",
        lambda path: (
            "ClawOS provides a local-first assistant environment. "
            "It bundles setup, dashboard, and workflow tools. "
            "Users can automate tasks offline with predictable flows. "
            "Security and setup posture matter for deployment decisions.",
            2,
        ),
    )

    result = asyncio.run(run({"file": str(pdf_path)}, None))
    assert result.status.value == "ok"
    assert "**Document:** sample" in result.output
    assert "**Coverage:**" in result.output
    assert "**Key terms:**" in result.output
    assert result.metadata["pages_used"] == 2
    assert result.metadata["read_minutes"] >= 1
    assert result.metadata["keywords"]


def test_summarize_pdf_reports_image_only_or_encrypted_failure(monkeypatch, workspace_tmp_dir):
    from workflows.summarize_pdf.workflow import run

    pdf_path = workspace_tmp_dir / "scan.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 image-only")
    monkeypatch.setattr(
        "workflows.summarize_pdf.workflow.extract_pdf_text",
        lambda path: ("", 0),
    )

    result = asyncio.run(run({"file": str(pdf_path)}, None))

    assert result.status.value == "failed"
    assert result.metadata["failure_reason"] == "no_extractable_text"
    assert result.metadata["pages_used"] == 0
    assert "image-only" in result.error


def test_summarize_pdf_reports_extractor_failures_clearly(monkeypatch, workspace_tmp_dir):
    from workflows.summarize_pdf.workflow import run

    pdf_path = workspace_tmp_dir / "broken.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 broken")

    def _raise(path):
        raise RuntimeError("pypdf is required to summarize PDFs")

    monkeypatch.setattr("workflows.summarize_pdf.workflow.extract_pdf_text", _raise)

    result = asyncio.run(run({"file": str(pdf_path)}, None))

    assert result.status.value == "failed"
    assert result.metadata["failure_reason"] == "extract_unavailable"
    assert "PDF text extraction is unavailable" in result.error


def test_workflow_engine_emits_live_progress_events(workspace_tmp_dir):
    from clawos_core.events.bus import get_bus
    from workflows.engine import WorkflowEngine

    (workspace_tmp_dir / "photo.jpg").write_bytes(b"image-bytes")
    (workspace_tmp_dir / "notes.md").write_text("docs", encoding="utf-8")

    events = []
    bus = get_bus()

    def _subscriber(event):
        if event.get("type") == "workflow_progress" and event.get("id") == "organize-downloads":
            events.append(event)

    bus.subscribe(_subscriber)
    try:
        engine = WorkflowEngine()
        engine.load_registry()
        result = asyncio.run(
            engine.run(
                "organize-downloads",
                {"target_dir": str(workspace_tmp_dir), "dry_run": True},
            )
        )
    finally:
        bus.unsubscribe(_subscriber)

    assert result.status.value == "ok"
    assert any(event.get("phase") == "scan" for event in events)
    assert any(event.get("phase") == "summary" for event in events)
    assert any(event.get("status") == "ok" for event in events)


def test_repo_summary_reports_git_activity(workspace_tmp_dir):
    from workflows.repo_summary.workflow import run

    repo = workspace_tmp_dir / "repo"
    repo.mkdir()
    _run(["git", "init"], repo)
    (repo / "README.md").write_text("# Demo Repo\n\nA small repository for testing.", encoding="utf-8")
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "demo-repo"\ndescription = "demo description"\n',
        encoding="utf-8",
    )
    (repo / "src").mkdir()
    (repo / "src" / "main.py").write_text("print('hello')\n", encoding="utf-8")
    _commit(repo, "feat: initial import")
    (repo / "docs").mkdir()
    (repo / "docs" / "guide.md").write_text("guide\n", encoding="utf-8")
    _commit(repo, "docs: add guide")

    result = asyncio.run(run({"dir": str(repo)}, None))
    assert result.status.value == "ok"
    assert "**Repository:** repo" in result.output
    assert "**Recent activity:**" in result.output
    assert "feat: initial import" in result.output


def test_pr_review_flags_risky_patterns(workspace_tmp_dir):
    from workflows.pr_review.workflow import run

    diff = workspace_tmp_dir / "change.diff"
    diff.write_text(
        "\n".join(
            [
                "diff --git a/app.py b/app.py",
                "index 111..222 100644",
                "--- a/app.py",
                "+++ b/app.py",
                "@@",
                "+print('debugging')",
                "+requests.get(url, verify=False)",
                "+token='secret-value'",
            ]
        ),
        encoding="utf-8",
    )

    result = asyncio.run(run({"file": str(diff)}, None))
    assert result.status.value == "ok"
    assert "**Verdict:** Request Changes" in result.output
    assert "TLS verification is disabled." in result.output


def test_write_readme_generates_core_sections(workspace_tmp_dir):
    from workflows.write_readme.workflow import run

    project = workspace_tmp_dir / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        '[project]\nname = "sample-app"\ndescription = "Sample application"\nrequires-python = ">=3.11"\n',
        encoding="utf-8",
    )
    (project / "clawctl").mkdir()
    (project / "clawctl" / "main.py").write_text("def main():\n    return 0\n", encoding="utf-8")

    result = asyncio.run(run({"dir": str(project)}, None))
    assert result.status.value == "ok"
    assert "# sample-app" in result.output
    assert "## Installation" in result.output
    assert "## Usage" in result.output


def test_changelog_groups_commits(workspace_tmp_dir):
    from workflows.changelog.workflow import run

    repo = workspace_tmp_dir / "repo"
    repo.mkdir()
    _run(["git", "init"], repo)
    (repo / "README.md").write_text("demo\n", encoding="utf-8")
    _commit(repo, "feat: initial import")
    (repo / "feature.txt").write_text("feature\n", encoding="utf-8")
    _commit(repo, "feat: add dashboard")
    (repo / "bugfix.txt").write_text("fix\n", encoding="utf-8")
    _commit(repo, "fix: patch parser")

    result = asyncio.run(run({"dir": str(repo), "from": "HEAD~2", "to": "HEAD"}, None))
    assert result.status.value == "ok"
    assert "### Features" in result.output
    assert "### Bug Fixes" in result.output
    assert "add dashboard" in result.output


def test_disk_report_runs_without_agent(workspace_tmp_dir):
    from workflows.disk_report.workflow import run

    (workspace_tmp_dir / "large.bin").write_bytes(b"x" * 2048)
    result = asyncio.run(run({"dir": str(workspace_tmp_dir), "large_file_mb": 0}, None))
    assert result.status.value == "ok"
    assert "**Disk Usage Report**" in result.output


def test_log_summarize_detects_errors(workspace_tmp_dir):
    from workflows.log_summarize.workflow import run

    log_path = workspace_tmp_dir / "app.log"
    log_path.write_text(
        "INFO started service\nWARNING retrying request\nERROR failed to bind socket\n",
        encoding="utf-8",
    )

    result = asyncio.run(run({"file": str(log_path), "lines": 20}, None))
    assert result.status.value == "ok"
    assert "### Errors Found" in result.output
    assert result.metadata["errors"] >= 1


def test_find_duplicates_reports_reclaimable_space(workspace_tmp_dir):
    from workflows.find_duplicates.workflow import run

    content = b"duplicate payload"
    (workspace_tmp_dir / "a.txt").write_bytes(content)
    (workspace_tmp_dir / "b.txt").write_bytes(content)
    (workspace_tmp_dir / "c.txt").write_text("unique", encoding="utf-8")

    result = asyncio.run(run({"dir": str(workspace_tmp_dir), "delete": False}, None))
    assert result.status.value == "ok"
    assert "Duplicate File Report" in result.output
    assert result.metadata["groups"] == 1


def test_clean_empty_dirs_dry_run_and_apply(workspace_tmp_dir):
    from workflows.clean_empty_dirs.workflow import run

    empty_dir = workspace_tmp_dir / "empty"
    empty_dir.mkdir()
    nested = workspace_tmp_dir / "nested" / "child"
    nested.mkdir(parents=True)

    dry_result = asyncio.run(run({"dir": str(workspace_tmp_dir), "dry_run": True}, None))
    assert dry_result.status.value == "ok"
    assert dry_result.metadata["dry_run"] is True
    assert empty_dir.exists()

    apply_result = asyncio.run(run({"dir": str(workspace_tmp_dir), "dry_run": False}, None))
    assert apply_result.status.value == "ok"
    assert not empty_dir.exists()
