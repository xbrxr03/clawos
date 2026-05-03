# SPDX-License-Identifier: AGPL-3.0-or-later
"""voiced health check."""
import urllib.request


def health() -> dict:
    """Check voice service health."""
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:7079/health",
            method="GET"
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status == 200:
                return {"status": "up"}
            return {"status": "degraded", "http_status": resp.status}
    except (OSError, ConnectionRefusedError, TimeoutError) as e:
        return {"status": "down", "error": str(e)}


if __name__ == "__main__":
    import json
    print(json.dumps(health()))
