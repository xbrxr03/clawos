# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Unit tests for all tools/filesystem/ modules:
  - read_file.py   (fs.read)
  - write_file.py  (fs.write)
  - list_dir.py    (fs.list)
  - delete.py      (fs.delete)
  - search.py      (fs.search)

All tests use pytest's tmp_path fixture. No real files are touched.
"""
import json
from pathlib import Path

import pytest

from tools.filesystem.read_file import run as read_run, _resolve as read_resolve, MAX_BYTES as READ_MAX
from tools.filesystem.write_file import run as write_run, _resolve as write_resolve
from tools.filesystem.list_dir import run as list_run, _resolve as list_resolve
from tools.filesystem.delete import run as delete_run, _resolve as delete_resolve
from tools.filesystem.search import run as search_run


# ── fs.read ───────────────────────────────────────────────────────────────────

class TestFsRead:
    def test_read_existing_file(self, tmp_path):
        (tmp_path / "hello.txt").write_text("Hello World")
        assert read_run("hello.txt", tmp_path) == "Hello World"

    def test_read_missing_file(self, tmp_path):
        assert "[NOT FOUND]" in read_run("missing.txt", tmp_path)

    def test_read_directory_returns_error(self, tmp_path):
        (tmp_path / "subdir").mkdir()
        assert "[ERROR]" in read_run("subdir", tmp_path)

    def test_read_absolute_path(self, tmp_path):
        target = tmp_path / "abs.txt"
        target.write_text("absolute content")
        assert "absolute content" in read_run(str(target), tmp_path)

    def test_read_large_file_returns_error(self, tmp_path):
        big = tmp_path / "big.txt"
        big.write_text("x" * (READ_MAX + 1))
        result = read_run("big.txt", tmp_path)
        assert "[ERROR]" in result or "too large" in result.lower()

    def test_read_empty_file(self, tmp_path):
        (tmp_path / "empty.txt").write_text("")
        assert read_run("empty.txt", tmp_path) == ""

    def test_read_nested_path(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c.txt"
        nested.parent.mkdir(parents=True)
        nested.write_text("deep content")
        assert read_run("a/b/c.txt", tmp_path) == "deep content"

    def test_read_unicode_content(self, tmp_path):
        (tmp_path / "unicode.txt").write_text("日本語テスト 🎉", encoding="utf-8")
        assert "日本語" in read_run("unicode.txt", tmp_path)


# ── fs.write ──────────────────────────────────────────────────────────────────

class TestFsWrite:
    def test_write_creates_file(self, tmp_path):
        result = write_run("test.txt", "Hello ClawOS", tmp_path)
        assert "[OK]" in result
        assert "Written" in result
        assert (tmp_path / "test.txt").read_text() == "Hello ClawOS"

    def test_write_overwrites_existing(self, tmp_path):
        (tmp_path / "note.md").write_text("old content")
        write_run("note.md", "new content", tmp_path)
        assert (tmp_path / "note.md").read_text() == "new content"

    def test_write_append_mode(self, tmp_path):
        (tmp_path / "log.txt").write_text("line1\n")
        result = write_run("log.txt", "line2\n", tmp_path, append=True)
        assert "Appended" in result
        content = (tmp_path / "log.txt").read_text()
        assert "line1" in content
        assert "line2" in content

    def test_write_creates_parent_dirs(self, tmp_path):
        result = write_run("sub/dir/file.txt", "nested", tmp_path)
        assert "[OK]" in result
        assert (tmp_path / "sub" / "dir" / "file.txt").exists()

    def test_write_absolute_path(self, tmp_path):
        target = tmp_path / "abs.txt"
        result = write_run(str(target), "absolute", tmp_path)
        assert "[OK]" in result
        assert target.read_text() == "absolute"

    def test_write_returns_char_count(self, tmp_path):
        result = write_run("sized.txt", "x" * 42, tmp_path)
        assert "42 chars" in result

    def test_write_bad_path_returns_error(self, tmp_path):
        result = write_run("/nonexistent/readonly/path/file.txt", "nope", tmp_path)
        assert "[ERROR]" in result

    def test_write_empty_content(self, tmp_path):
        result = write_run("empty.txt", "", tmp_path)
        assert "[OK]" in result
        assert (tmp_path / "empty.txt").read_text() == ""

    def test_write_append_to_nonexistent_file(self, tmp_path):
        result = write_run("new.txt", "fresh", tmp_path, append=True)
        assert "Appended" in result or "[OK]" in result


# ── fs.list ───────────────────────────────────────────────────────────────────

class TestFsList:
    def test_list_empty_directory(self, tmp_path):
        (tmp_path / "emptydir").mkdir()
        result = list_run("emptydir", tmp_path)
        entries = json.loads(result)
        assert entries == []

    def test_list_directory_with_files(self, tmp_path):
        (tmp_path / "dir").mkdir()
        (tmp_path / "dir" / "a.txt").write_text("aaa")
        (tmp_path / "dir" / "b.txt").write_text("bbb")
        result = list_run("dir", tmp_path)
        entries = json.loads(result)
        names = [e["name"] for e in entries]
        assert "a.txt" in names
        assert "b.txt" in names

    def test_list_shows_dirs(self, tmp_path):
        (tmp_path / "dir").mkdir()
        (tmp_path / "dir" / "subdir").mkdir()
        (tmp_path / "dir" / "file.txt").write_text("x")
        result = list_run("dir", tmp_path)
        entries = json.loads(result)
        types = {e["name"]: e["type"] for e in entries}
        assert types["subdir"] == "dir"
        assert types["file.txt"] == "file"

    def test_list_shows_file_sizes(self, tmp_path):
        (tmp_path / "dir").mkdir()
        (tmp_path / "dir" / "sized.txt").write_text("hello world")
        result = list_run("dir", tmp_path)
        entries = json.loads(result)
        sized = [e for e in entries if e["name"] == "sized.txt"][0]
        assert sized["size_bytes"] == 11

    def test_list_missing_directory(self, tmp_path):
        result = list_run("nonexistent", tmp_path)
        assert "[NOT FOUND]" in result

    def test_list_file_instead_of_dir(self, tmp_path):
        (tmp_path / "file.txt").write_text("x")
        result = list_run("file.txt", tmp_path)
        assert "[ERROR]" in result

    def test_list_absolute_path(self, tmp_path):
        (tmp_path / "dir").mkdir()
        (tmp_path / "dir" / "x.txt").write_text("x")
        result = list_run(str(tmp_path / "dir"), tmp_path)
        entries = json.loads(result)
        assert any(e["name"] == "x.txt" for e in entries)

    def test_list_entries_have_required_fields(self, tmp_path):
        (tmp_path / "dir").mkdir()
        (tmp_path / "dir" / "f.txt").write_text("x")
        result = list_run("dir", tmp_path)
        entries = json.loads(result)
        for entry in entries:
            assert "name" in entry
            assert "type" in entry
            assert "size_bytes" in entry


# ── fs.delete ─────────────────────────────────────────────────────────────────

class TestFsDelete:
    def test_delete_file(self, tmp_path):
        (tmp_path / "todelete.txt").write_text("bye")
        result = delete_run("todelete.txt", tmp_path)
        assert "[OK]" in result
        assert not (tmp_path / "todelete.txt").exists()

    def test_delete_empty_directory(self, tmp_path):
        (tmp_path / "emptydir").mkdir()
        result = delete_run("emptydir", tmp_path)
        assert "[OK]" in result
        assert not (tmp_path / "emptydir").exists()

    def test_delete_nonempty_directory_fails(self, tmp_path):
        (tmp_path / "fulldir").mkdir()
        (tmp_path / "fulldir" / "file.txt").write_text("x")
        result = delete_run("fulldir", tmp_path)
        assert "[ERROR]" in result

    def test_delete_missing_file(self, tmp_path):
        result = delete_run("ghost.txt", tmp_path)
        assert "[NOT FOUND]" in result

    def test_delete_absolute_path(self, tmp_path):
        target = tmp_path / "abs_del.txt"
        target.write_text("bye")
        result = delete_run(str(target), tmp_path)
        assert "[OK]" in result
        assert not target.exists()


# ── fs.search ─────────────────────────────────────────────────────────────────

class TestFsSearch:
    def test_search_finds_match(self, tmp_path):
        (tmp_path / "notes.txt").write_text("ClawOS is awesome\nNo match here\nClawOS rules")
        result = search_run("ClawOS", tmp_path)
        assert "ClawOS" in result
        assert "notes.txt" in result

    def test_search_no_results(self, tmp_path):
        (tmp_path / "empty.txt").write_text("nothing relevant")
        result = search_run("missing_query", tmp_path)
        assert "[NO RESULTS]" in result

    def test_search_empty_query(self, tmp_path):
        result = search_run("", tmp_path)
        assert "[ERROR]" in result

    def test_search_case_insensitive(self, tmp_path):
        (tmp_path / "mixed.txt").write_text("Hello World")
        result = search_run("hello", tmp_path)
        assert "Hello" in result

    def test_search_shows_line_numbers(self, tmp_path):
        (tmp_path / "doc.txt").write_text("line1\nline2 match\nline3")
        result = search_run("match", tmp_path)
        assert ":2:" in result

    def test_search_multiple_files(self, tmp_path):
        (tmp_path / "a.txt").write_text("findme in a")
        (tmp_path / "b.txt").write_text("findme in b")
        result = search_run("findme", tmp_path)
        assert "a.txt" in result
        assert "b.txt" in result

    def test_search_skips_large_files(self, tmp_path):
        big = tmp_path / "big.txt"
        # Write a file larger than MAX_FILE_KB with the needle buried inside
        big.write_text("x" * (500 * 1024) + "needle here")
        # Also write a small file with the needle so we can verify
        # the big one was skipped but search itself still works
        (tmp_path / "small.txt").write_text("needle in small")
        result = search_run("needle", tmp_path)
        # The small file should be found, the big one should be skipped
        assert "small.txt" in result
        assert "big.txt" not in result


# ── _resolve helpers (all modules) ────────────────────────────────────────────

class TestResolveHelpers:
    def test_all_resolve_relative_identically(self, tmp_path):
        """All _resolve functions handle relative paths the same way."""
        rel = "docs/readme.md"
        expected = (tmp_path / rel).resolve()
        assert read_resolve(rel, tmp_path) == expected
        assert write_resolve(rel, tmp_path) == expected
        assert list_resolve(rel, tmp_path) == expected
        assert delete_resolve(rel, tmp_path) == expected

    def test_all_resolve_absolute_identically(self, tmp_path):
        abs_path = Path("/tmp/some/file.txt")
        for resolve_fn in [read_resolve, write_resolve, list_resolve, delete_resolve]:
            assert resolve_fn(str(abs_path), tmp_path) == abs_path