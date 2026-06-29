# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for noted — Notes service."""
from services.noted.engine import Note, create_note, list_notes, delete_note


class TestNote:
    def test_create(self):
        note = Note(id="abc", title="Test Note", content="Hello world", tags=["test"])
        assert note.id == "abc"
        assert note.tags == ["test"]

    def test_to_dict(self):
        note = Note(id="abc", title="Test", content="hi")
        d = note.to_dict()
        assert d["title"] == "Test"
        assert d["content"] == "hi"

    def test_save_and_load(self, tmp_path):
        import services.noted.engine as eng
        old_dir = eng.NOTES_DIR
        eng.NOTES_DIR = tmp_path
        try:
            note = Note(id="test1", title="My Note", content="Note body here", tags=["a", "b"])
            note.save()
            loaded = Note.load("test1")
            assert loaded is not None
            assert loaded.title == "My Note"
            assert loaded.content == "Note body here"
            assert sorted(loaded.tags) == ["a", "b"]
        finally:
            eng.NOTES_DIR = old_dir

    def test_load_nonexistent(self):
        assert Note.load("nonexistent_note_xyz") is None


class TestCreateNote:
    def test_create(self, tmp_path):
        import services.noted.engine as eng
        old_dir = eng.NOTES_DIR
        eng.NOTES_DIR = tmp_path
        try:
            note = create_note(title="New Note", content="Body", tags=["tag1"])
            assert note.title == "New Note"
            assert note.id != ""
            loaded = Note.load(note.id)
            assert loaded is not None
        finally:
            eng.NOTES_DIR = old_dir


class TestListNotes:
    def test_list(self, tmp_path):
        import services.noted.engine as eng
        old_dir = eng.NOTES_DIR
        eng.NOTES_DIR = tmp_path
        try:
            create_note(title="Note A", content="Alpha", tags=["work"])
            create_note(title="Note B", content="Beta", tags=["personal"])
            all_notes = list_notes()
            assert len(all_notes) == 2
            work_notes = list_notes(tag="work")
            assert len(work_notes) == 1
            assert work_notes[0]["title"] == "Note A"
        finally:
            eng.NOTES_DIR = old_dir

    def test_search(self, tmp_path):
        import services.noted.engine as eng
        old_dir = eng.NOTES_DIR
        eng.NOTES_DIR = tmp_path
        try:
            create_note(title="Python Tips", content="Use pytest")
            create_note(title="Rust Guide", content="Use cargo test")
            results = list_notes(search="python")
            assert len(results) == 1
            assert results[0]["title"] == "Python Tips"
        finally:
            eng.NOTES_DIR = old_dir


class TestDeleteNote:
    def test_delete(self, tmp_path):
        import services.noted.engine as eng
        old_dir = eng.NOTES_DIR
        eng.NOTES_DIR = tmp_path
        try:
            note = create_note(title="Delete Me", content="bye")
            assert delete_note(note.id) is True
            assert Note.load(note.id) is None
            assert delete_note("nonexistent") is False
        finally:
            eng.NOTES_DIR = old_dir