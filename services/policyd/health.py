"""policyd health check."""
from services.policyd.service import get_engine
def health() -> dict:
    e = get_engine()
    return {"status": "ok", "pending_approvals": len(e.get_pending_approvals())}
if __name__ == "__main__":
    import json; print(json.dumps(health()))
