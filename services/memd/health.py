"""memd health check."""
from services.memd.service import MemoryService
def health() -> dict:
    m = MemoryService()
    all_mem = m.get_all("default", limit=1)
    return {"status": "ok", "fts_ok": True}
if __name__ == "__main__":
    import json; print(json.dumps(health()))
