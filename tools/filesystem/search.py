# SPDX-License-Identifier: AGPL-3.0-or-later
"""fs.search — grep-style search across workspace files.
Supports --cross-session flag to search past conversations via memd FTS5.
"""
import re
from pathlib import Path

MAX_RESULTS = 20
MAX_FILE_KB = 500


def run(target: str, workspace_root: Path, cross_session: bool = False,
        workspace_id: str = "nexus_default", limit: int = 5) -> str:
    """target is the search query string.

    If cross_session=True, searches past session turns via memd FTS5 instead
    of grepping files.
    """
    query = target.strip()
    if not query:
        return "[ERROR] Empty search query"

    # ── Cross-session search via memd FTS5 ─────────────────────────────────
    if cross_session:
        try:
            from services.memd.service import MemoryService
            memd = MemoryService()
            results = memd.recall_cross_session(query, workspace_id, n=limit)
        except (ImportError, OSError, RuntimeError) as e:
            return f"[ERROR] Session search failed: {e}"
        if not results:
            return f"[NO RESULTS] No session turns match: {query}"
        lines = []
        for i, r in enumerate(results, 1):
            content = r["content"][:300]
            lines.append(
                f"[{i}] session={r['session_id'][:8]}… role={r['role']} "
                f"rank={r['rank']:.1f}\n"
                f"    {r.get('highlight') or content}"
            )
        return "\n\n".join(lines)

    # ── Standard file grep search ──────────────────────────────────────────
    results = []
    try:
        pattern = re.compile(re.escape(query), re.IGNORECASE)
    except re.error:
        pattern = re.compile(re.escape(query), re.IGNORECASE)

    try:
        for path in workspace_root.rglob("*"):
            if not path.is_file():
                continue
            if path.stat().st_size > MAX_FILE_KB * 1024:
                continue
            try:
                text = path.read_text(errors="replace")
            except (OSError, UnicodeDecodeError):
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    rel = str(path.relative_to(workspace_root))
                    results.append(f"{rel}:{i}: {line.strip()}")
                    if len(results) >= MAX_RESULTS:
                        results.append(f"... (truncated at {MAX_RESULTS} results)")
                        return "\n".join(results)
    except (OSError, UnicodeDecodeError) as e:
        return f"[ERROR] Search failed: {e}"

    if not results:
        return f"[NO RESULTS] No matches for: {query}"
    return "\n".join(results)
