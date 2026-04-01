"""picoclawd health check."""
import platform


def check() -> dict:
    from services.picoclawd.installer import is_installed, INSTALL_PATH
    return {
        "service": "picoclawd",
        "status": "ok" if is_installed() else "not_installed",
        "arch": platform.machine(),
        "binary": str(INSTALL_PATH),
    }
