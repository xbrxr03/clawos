"""dashd health check."""
import urllib.request
def health() -> dict:
    try:
        urllib.request.urlopen("http://localhost:7070/api/health", timeout=2)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "down", "error": str(e)}
if __name__ == "__main__":
    import json; print(json.dumps(health()))
