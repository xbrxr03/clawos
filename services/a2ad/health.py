"""a2ad health check."""
from clawos_core.constants import PORT_A2AD


def check() -> dict:
    try:
        import urllib.request
        urllib.request.urlopen(f"http://localhost:{PORT_A2AD}/health", timeout=2)
        return {"service": "a2ad", "status": "ok"}
    except Exception:
        return {"service": "a2ad", "status": "down"}
