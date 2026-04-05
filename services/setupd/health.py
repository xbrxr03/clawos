"""setupd health check."""
from services.setupd.service import get_service


def health() -> dict:
    return get_service().health()
