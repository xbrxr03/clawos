"""Response parser using json_repair (from Nanobot research)."""
import logging
from clawos_core.util.jsonx import safe_parse

log = logging.getLogger("parser")

def parse_response(raw: str) -> dict:
    """Parse LLM response. Returns dict with final_answer, action, or parse_error."""
    result = safe_parse(raw)
    if result is None:
        log.warning(f"Parse error on: {raw[:80]}")
        return {"parse_error": True, "raw": raw}
    if "final_answer" in result or "action" in result:
        return result
    # If parsed but no recognized key, treat as final_answer
    if isinstance(result, dict) and len(result) == 1:
        return {"final_answer": str(list(result.values())[0])}
    return {"parse_error": True, "raw": raw}
