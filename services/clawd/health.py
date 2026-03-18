"""clawd health check."""
from services.clawd.service import get_daemon
def health() -> dict:
    return get_daemon().health()
if __name__ == "__main__":
    import json; print(json.dumps(health()))
