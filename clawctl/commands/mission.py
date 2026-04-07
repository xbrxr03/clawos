# SPDX-License-Identifier: AGPL-3.0-or-later
"""clawctl mission - inspect or start Nexus missions."""
from __future__ import annotations

from clawos_core.catalog import make_trace, record_trace
from clawos_core.presence import list_missions, start_mission

from clawctl.ui.banner import error, success, table


def run_list():
    missions = list_missions()
    print()
    rows = [
        (
            item.get("id", ""),
            item.get("status", ""),
            "blocked" if item.get("blocked") else item.get("trust_lane", ""),
            item.get("title", ""),
        )
        for item in missions
    ]
    table(rows, headers=("id", "status", "lane", "title"))
    print()


def run_start(title: str, summary: str = ""):
    print()
    try:
        mission = start_mission(title, summary=summary)
    except ValueError as exc:
        error(str(exc))
        print()
        return

    record_trace(
        make_trace(
            title=f"Mission started: {mission.get('title', title)}",
            category="missions",
            status="completed",
            tools=["clawctl.mission.start"],
            metadata={"trust_lane": mission.get("trust_lane", "trusted-automatic")},
        )
    )
    success(f"Started mission: {mission.get('title', title)}")
    if mission.get("summary"):
        print(f"      {mission['summary']}")
    print()
