# SPDX-License-Identifier: AGPL-3.0-or-later
"""metricd entrypoint (if run as standalone)."""
import logging
logging.basicConfig(level=logging.INFO)

from services.metricd.service import get_metrics

if __name__ == "__main__":
    m = get_metrics()
    print(f"metricd ready. Budget: {m._budget_on}")
