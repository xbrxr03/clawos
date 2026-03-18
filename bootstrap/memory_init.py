"""Initialise memory backends — FTS5 + ChromaDB (if available)."""
import sqlite3
from pathlib import Path
from clawos_core.constants import MEMORY_FTS_DB, MEMORY_DIR


def init_fts():
    MEMORY_FTS_DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(MEMORY_FTS_DB))
    db.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS memories USING fts5(
            memory_id, workspace_id, text, source, created_at,
            tokenize='porter ascii'
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS memories_meta (
            memory_id TEXT PRIMARY KEY, workspace_id TEXT,
            text TEXT, source TEXT, created_at TEXT,
            lifecycle TEXT DEFAULT 'ACTIVE'
        )
    """)
    db.commit()
    db.close()
    return True


def init_chroma() -> bool:
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(MEMORY_DIR / "chroma"))
        return True
    except ImportError:
        return False
    except Exception:
        return False


def init_all() -> dict:
    return {
        "fts5":   init_fts(),
        "chroma": init_chroma(),
    }
