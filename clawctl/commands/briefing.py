# SPDX-License-Identifier: AGPL-3.0-or-later
"""clawctl briefing - generate and display the current Nexus briefing."""
from __future__ import annotations

from clawos_core.presence import build_today_briefing, list_missions
from services.setupd.state import SetupState

from clawctl.ui.banner import info


def run_now():
    state = SetupState.load()
    briefing = build_today_briefing(setup_state=state, missions=list_missions())

    print()
    print(f"  {briefing.get('title', 'Today')}")
    print(f"  {'=' * max(8, len(briefing.get('title', 'Today')))}")
    print()
    print(f"  {briefing.get('headline', 'Nexus is on watch.')}")
    print(f"  {briefing.get('summary', '')}")
    print()

    for item in briefing.get("items", []):
        label = item.get("title", "Item")
        body = item.get("body", "")
        priority = item.get("priority", "low")
        info(f"{label} [{priority}]")
        print(f"      {body}")
    print()
