"""voiced health check."""
from services.voiced.service import get_service
def health() -> dict:
    return get_service().health()
if __name__ == "__main__":
    import json; print(json.dumps(health()))
