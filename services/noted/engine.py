# SPDX-License-Identifier: AGPL-3.0-or-later
"""
noted — Notes Service
======================
Local-first note-taking with markdown support.
Notes are stored as flat markdown files in ~/.clawos/notes/.
"""
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

log = logging.getLogger("noted")

try:
    from clawos_core.constants import CONFIG_DIR
    NOTES_DIR = CONFIG_DIR / "notes"
except (ImportError, ModuleNotFoundError):
    NOTES_DIR = Path.home() / ".clawos" / "notes"


@dataclass
class Note:
    id: str
    title: str
    content: str
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    updated_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self) -> None:
        NOTES_DIR.mkdir(parents=True, exist_ok=True)
        path = NOTES_DIR / f"{self.id}.md"
        # Store metadata as YAML front matter
        front = [
            "---",
            f"id: {self.id}",
            f"title: {self.title}",
            f"tags: {', '.join(self.tags)}",
            f"created: {self.created_at}",
            f"updated: {self.updated_at}",
            "---",
            "",
            self.content,
        ]
        path.write_text("\n".join(front), encoding="utf-8")

    @classmethod
    def load(cls, note_id: str) -> Optional["Note"]:
        path = NOTES_DIR / f"{note_id}.md"
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8")
        # Parse front matter
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                meta = parts[1].strip()
                content = parts[2].strip()
                note_data = {"id": note_id, "content": content}
                for line in meta.split("\n"):
                    if line.startswith("title:"):
                        note_data["title"] = line.split(":", 1)[1].strip()
                    elif line.startswith("tags:"):
                        tags_str = line.split(":", 1)[1].strip()
                        note_data["tags"] = [t.strip() for t in tags_str.split(",") if t.strip()]
                    elif line.startswith("created:"):
                        note_data["created_at"] = line.split(":", 1)[1].strip()
                    elif line.startswith("updated:"):
                        note_data["updated_at"] = line.split(":", 1)[1].strip()
                return cls(**note_data)
        # Fallback: treat entire file as content
        return cls(id=note_id, title=note_id, content=text)


def create_note(title: str, content: str = "", tags: list[str] | None = None) -> Note:
    """Create a new note."""
    import secrets
    note_id = secrets.token_hex(6)
    note = Note(id=note_id, title=title, content=content, tags=tags or [])
    note.save()
    return note


def list_notes(tag: str | None = None, search: str | None = None) -> list[dict]:
    """List all notes with optional tag filter and text search."""
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    notes = []
    for path in sorted(NOTES_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        note = Note.load(path.stem)
        if not note:
            continue
        if tag and tag not in note.tags:
            continue
        if search and search.lower() not in note.title.lower() and search.lower() not in note.content.lower():
            continue
        notes.append({
            "id": note.id,
            "title": note.title,
            "tags": note.tags,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
            "preview": note.content[:120],
        })
    return notes


def delete_note(note_id: str) -> bool:
    path = NOTES_DIR / f"{note_id}.md"
    if path.exists():
        path.unlink()
        return True
    return False