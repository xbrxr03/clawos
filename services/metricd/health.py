# SPDX-License-Identifier: AGPL-3.0-or-later
"""metricd health check."""
from clawos_core.constants import OTEL_JSONL


def check() -> dict:
    return {
        "service": "metricd",
        "status": "ok",
        "otel_log": str(OTEL_JSONL),
        "log_exists": OTEL_JSONL.exists(),
    }
