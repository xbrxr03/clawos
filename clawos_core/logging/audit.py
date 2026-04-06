"""
Merkle-chained audit journal.
Every entry hashes the previous — tamper-evident chain.
"""
import json
import logging
import sqlite3
from pathlib import Path
from clawos_core.constants import AUDIT_JSONL, POLICYD_DB
from clawos_core.models import AuditEntry

log = logging.getLogger("audit")
_prev_hash = ""
_db: sqlite3.Connection = None


def _get_db() -> sqlite3.Connection:
    global _db
    if _db is None:
        POLICYD_DB.parent.mkdir(parents=True, exist_ok=True)
        _db = sqlite3.connect(str(POLICYD_DB), check_same_thread=False)
        _db.execute("PRAGMA journal_mode=WAL")
        _db.execute("PRAGMA busy_timeout=5000")
        _db.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                entry_id TEXT PRIMARY KEY, task_id TEXT, workspace TEXT,
                tool TEXT, target TEXT, decision TEXT, reason TEXT,
                timestamp TEXT, prev_hash TEXT, entry_hash TEXT
            )
        """)
        _db.execute("""
            CREATE TABLE IF NOT EXISTS approvals (
                request_id TEXT PRIMARY KEY, task_id TEXT, workspace TEXT,
                tool TEXT, target TEXT, content TEXT,
                decision TEXT, created_at TEXT, decided_at TEXT
            )
        """)
        _db.commit()
    return _db


def close_db():
    """Release the cached SQLite handle so temp workspaces clean up cleanly."""
    global _db
    if _db is not None:
        try:
            _db.close()
        except Exception:
            pass
        _db = None


def _load_last_hash() -> str:
    try:
        db = _get_db()
        row = db.execute(
            "SELECT entry_hash FROM audit_log ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else ""
    except Exception:
        return ""


def write(entry: AuditEntry) -> AuditEntry:
    global _prev_hash
    if not _prev_hash:
        _prev_hash = _load_last_hash()
    entry.prev_hash  = _prev_hash
    entry.entry_hash = entry.compute_hash()
    _prev_hash       = entry.entry_hash

    # JSONL
    AUDIT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_JSONL, "a") as f:
        f.write(json.dumps(entry.to_dict()) + "\n")

    # SQLite
    try:
        db = _get_db()
        db.execute(
            "INSERT OR REPLACE INTO audit_log VALUES (?,?,?,?,?,?,?,?,?,?)",
            (entry.entry_id, entry.task_id, entry.workspace,
             entry.tool, entry.target, entry.decision, entry.reason,
             entry.timestamp, entry.prev_hash, entry.entry_hash)
        )
        db.commit()
    except Exception as e:
        log.warning(f"Audit DB write failed: {e}")

    return entry


def tail(n: int = 50) -> list[dict]:
    """Return n most recent audit entries, newest first."""
    if not AUDIT_JSONL.exists():
        return []
    try:
        lines = AUDIT_JSONL.read_text().strip().split("\n")
        result = []
        for line in lines[-n:]:
            if line.strip():
                try:
                    result.append(json.loads(line))
                except Exception:
                    pass
        return list(reversed(result))
    except Exception:
        return []


def verify_chain(entries: list[dict]) -> bool:
    """Verify Merkle chain integrity. Returns True if chain is intact."""
    import hashlib
    for i in range(1, len(entries)):
        e = entries[i]
        prev = entries[i-1]
        expected = hashlib.sha256(
            f"{e['prev_hash']}{e['entry_id']}{e['tool']}{e['target']}{e['decision']}{e['timestamp']}".encode()
        ).hexdigest()
        if expected != e["entry_hash"]:
            return False
    return True
