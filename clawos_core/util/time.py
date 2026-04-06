# SPDX-License-Identifier: AGPL-3.0-or-later
"""Time utilities."""
from datetime import datetime, timezone
import time

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

def elapsed(start: float) -> float:
    return round(time.time() - start, 2)
