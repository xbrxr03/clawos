# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Unit tests for ClawOS tools — filesystem (read/write), tool registry,
and dispatch. All tests use temporary workspaces. No real files touched.
"""
from pathlib import Path


from tools.filesystem.write_file import run as write_run, _resolve as write_resolve
from tools.filesystem.read_file import run as read_run, _resolve as read_resolve, MAX_BYTES


# ── fs.write ──────────────────────────────────────────────────────────────────

class TestFsWrite:
    def test_write_creates_file(self, tmp_path):
        """Writing a new file creates it and returns success."""
        result = write_run("test.txt", "Hello ClawOS", tmp_path)
        assert "[OK]" in result
        assert "Written" in result
        assert (tmp_path / "test.txt").exists()
        assert (tmp_path / "test.txt").read_text() == "Hello ClawOS"

    def test_write_overwrites_existing(self, tmp_path):
        """Writing to existing file overwrites content."""
        (tmp_path / "note.md").write_text("old content")
        result = write_run("note.md", "new content", tmp_path)
        assert "[OK]" in result
        assert (tmp_path / "note.md").read_text() == "new content"

    def test_write_append_mode(self, tmp_path):
        """Append mode adds content to existing file."""
        (tmp_path / "log.txt").write_text("line1\n")
        result = write_run("log.txt", "line2\n", tmp_path, append=True)
        assert "Appended" in result
        content = (tmp_path / "log.txt").read_text()
        assert "line1" in content
        assert "line2" in content

    def test_write_creates_parent_dirs(self, tmp_path):
        """Writing creates intermediate directories."""
        result = write_run("sub/dir/file.txt", "nested", tmp_path)
        assert "[OK]" in result
        assert (tmp_path / "sub" / "dir" / "file.txt").exists()

    def test_write_absolute_path(self, tmp_path):
        """Absolute paths are used as-is."""
        target = tmp_path / "abs.txt"
        result = write_run(str(target), "absolute", tmp_path)
        assert "[OK]" in result
        assert target.read_text() == "absolute"

    def test_write_returns_char_count(self, tmp_path):
        """Result message includes character count."""
        content = "x" * 42
        result = write_run("sized.txt", content, tmp_path)
        assert "42 chars" in result

    def test_write_bad_path_returns_error(self, tmp_path):
        """Writing to an invalid path returns error message."""
        result = write_run("/nonexistent/readonly/path/file.txt", "nope", tmp_path)
        assert "[ERROR]" in result


# ── fs.read ───────────────────────────────────────────────────────────────────

class TestFsRead:
    def test_read_existing_file(self, tmp_path):
        """Reading an existing file returns its content."""
        (tmp_path / "hello.txt").write_text("Hello World")
        result = read_run("hello.txt", tmp_path)
        assert result == "Hello World"

    def test_read_missing_file(self, tmp_path):
        """Reading a missing file returns NOT FOUND."""
        result = read_run("missing.txt", tmp_path)
        assert "[NOT FOUND]" in result

    def test_read_directory_returns_error(self, tmp_path):
        """Reading a directory returns error."""
        (tmp_path / "subdir").mkdir()
        result = read_run("subdir", tmp_path)
        assert "[ERROR]" in result

    def test_read_absolute_path(self, tmp_path):
        """Absolute paths are used as-is."""
        target = tmp_path / "abs_read.txt"
        target.write_text("absolute content")
        result = read_run(str(target), tmp_path)
        assert "absolute content" in result

    def test_read_large_file_returns_error(self, tmp_path):
        """Files over 50KB return an error message."""
        big = tmp_path / "big.txt"
        big.write_text("x" * (MAX_BYTES + 1))
        result = read_run("big.txt", tmp_path)
        assert "[ERROR]" in result or "too large" in result.lower()

    def test_read_empty_file(self, tmp_path):
        """Reading an empty file returns empty string."""
        (tmp_path / "empty.txt").write_text("")
        result = read_run("empty.txt", tmp_path)
        assert result == ""


# ── _resolve helpers ──────────────────────────────────────────────────────────

class TestResolve:
    def test_resolve_relative(self, tmp_path):
        """Relative paths resolve under workspace_root."""
        p = write_resolve("foo/bar.txt", tmp_path)
        assert p == (tmp_path / "foo" / "bar.txt").resolve()

    def test_resolve_absolute(self, tmp_path):
        """Absolute paths are returned as-is."""
        abs_path = Path("/tmp/some/file.txt")
        p = write_resolve(str(abs_path), tmp_path)
        assert p == abs_path

    def test_read_resolve_matches_write(self, tmp_path):
        """read and write resolve functions behave identically."""
        rel = "docs/readme.md"
        assert write_resolve(rel, tmp_path) == read_resolve(rel, tmp_path)


# ── Tool dispatch ─────────────────────────────────────────────────────────────

class TestToolDispatch:
    def test_dispatch_unknown_tool(self):
        """Dispatching unknown tool returns error message."""
        from runtimes.agent.tools import dispatch_tool
        import asyncio
        result = asyncio.run(dispatch_tool("nope", {}, {}))
        assert "Unknown tool" in result

    def test_dispatch_get_time(self):
        """get_time tool returns a string with a year."""
        from runtimes.agent.tools import dispatch_tool
        import asyncio
        r = asyncio.run(dispatch_tool("get_time", {}, {}))
        assert isinstance(r, str)
        assert any(d in r for d in ["2025", "2026", "2027", "2028"])

    def test_schema_registry_consistency(self):
        """Every schema has an implementation and vice versa."""
        from runtimes.agent.tools import NATIVE_TOOLS
        from runtimes.agent.tool_schemas import ALL_TOOLS
        for name in ALL_TOOLS:
            assert name in NATIVE_TOOLS, f"schema {name!r} has no implementation"
        for name in NATIVE_TOOLS:
            assert name in ALL_TOOLS, f"impl {name!r} has no JSON schema"