"""fs.search — grep-style search across workspace files."""
import re
from pathlib import Path

MAX_RESULTS = 20
MAX_FILE_KB = 500


def run(target: str, workspace_root: Path) -> str:
    """target is the search query string."""
    query = target.strip()
    if not query:
        return "[ERROR] Empty search query"

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
            except Exception:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    rel = str(path.relative_to(workspace_root))
                    results.append(f"{rel}:{i}: {line.strip()}")
                    if len(results) >= MAX_RESULTS:
                        results.append(f"... (truncated at {MAX_RESULTS} results)")
                        return "\n".join(results)
    except Exception as e:
        return f"[ERROR] Search failed: {e}"

    if not results:
        return f"[NO RESULTS] No matches for: {query}"
    return "\n".join(results)
