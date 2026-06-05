# SPDX-License-Identifier: AGPL-3.0-or-later
"""clawctl search — FTS5 full-text search across past session turns."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.memd.service import MemoryService


def run(query: str, workspace: str = "nexus_default", limit: int = 5):
    """Run a cross-session FTS5 search and print formatted results."""
    memd = MemoryService()
    results = memd.recall_cross_session(query, workspace, n=limit)

    if not results:
        print(f"\n  No results for: {query!r}\n")
        return

    print()
    for i, r in enumerate(results, 1):
        # Truncate long content for display
        content = r["content"][:200] + "…" if len(r["content"]) > 200 else r["content"]
        highlight = r.get("highlight", "")
        ts = r.get("timestamp", "?")
        role = r.get("role", "?")
        rank = r.get("rank", 0)

        print(f"  ┌─ [{i}] session={r['session_id'][:8]}… role={role} rank={rank:.1f}")
        print(f"  │ {ts}")
        if highlight:
            print(f"  │ ⟫ {highlight}")
        else:
            print(f"  │ {content}")
        print(f"  └─")
    print()