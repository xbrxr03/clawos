# SPDX-License-Identifier: AGPL-3.0-or-later
"""setupd health check."""
from services.setupd.service import get_service


def health() -> dict:
    return get_service().health()
