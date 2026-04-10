# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Kizuna (braind) — standalone entrypoint.
Normally loaded inline by daemon.py. Run standalone for testing:
  python3 services/braind/main.py
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [braind] %(levelname)s %(message)s",
)
log = logging.getLogger("braind")


def main():
    from services.braind.service import get_brain
    brain = get_brain()
    stats = brain.stats()
    log.info(f"Kizuna ready: {stats['node_count']} nodes, {stats['edge_count']} edges, {stats['community_count']} communities")

    from services.braind.health import health
    print(health())


if __name__ == "__main__":
    main()
