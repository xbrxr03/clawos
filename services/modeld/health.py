# SPDX-License-Identifier: AGPL-3.0-or-later
"""modeld health check."""
from services.modeld.service import get_service
def health() -> dict:
    return get_service().health()
if __name__ == "__main__":
    import json; print(json.dumps(health()))
