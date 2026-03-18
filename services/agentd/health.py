"""agentd health check."""
from services.agentd.service import get_manager
def health() -> dict:
    mgr = get_manager()
    tasks = mgr.list_tasks(5)
    return {"status": "ok", "recent_tasks": len(tasks)}
if __name__ == "__main__":
    import json; print(json.dumps(health()))
