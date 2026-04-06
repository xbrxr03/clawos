# SPDX-License-Identifier: AGPL-3.0-or-later
"""json_repair wrapper + safe parse used everywhere."""
import json
import re
from typing import Any

try:
    from json_repair import repair_json
    _REPAIR = True
except ImportError:
    _REPAIR = False

def safe_parse(raw: str) -> dict | None:
    """Parse JSON from LLM output. Uses json_repair if available."""
    if not raw:
        return None
    raw = raw.strip()
    if _REPAIR:
        try:
            repaired = repair_json(raw)
            if repaired:
                data = json.loads(repaired)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    # Stdlib fallback
    candidates = [raw]
    m = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
    if m:
        candidates.append(m.group(0))
    for c in candidates:
        try:
            data = json.loads(c)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    # Plain text → final_answer
    if len(raw) < 500 and not raw.startswith("{"):
        return {"final_answer": raw}
    return None

def to_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)
