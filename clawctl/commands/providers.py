# SPDX-License-Identifier: AGPL-3.0-or-later
"""clawctl providers - inspect, test, and switch provider profiles."""
from __future__ import annotations

from clawos_core.catalog import get_provider_profile, list_provider_profiles, make_trace, record_trace, test_provider_profile
from services.setupd.state import SetupState

from clawctl.ui.banner import error, info, success, table


def run_list():
    print()
    state = SetupState.load()
    rows = []
    for profile in list_provider_profiles():
        result = test_provider_profile(profile.id)
        rows.append(
            (
                profile.id,
                "selected" if profile.id == state.selected_provider_profile else "available",
                result.get("status", "unknown"),
                profile.kind,
                profile.privacy_posture,
            )
        )
    table(rows, headers=("id", "status", "health", "kind", "privacy"))
    print()


def run_test(profile_id: str):
    print()
    profile = get_provider_profile(profile_id)
    if not profile:
        error(f"Unknown provider profile: {profile_id}")
        print()
        return
    result = test_provider_profile(profile.id)
    if result.get("ok"):
        success(result.get("detail", "Provider is ready"))
    else:
        info(result.get("detail", "Provider needs attention"))
    record_trace(
        make_trace(
            title=f"Tested provider {profile.name}",
            category="providers",
            status="completed" if result.get("ok") else "warning",
            provider=profile.id,
            tools=["clawctl.providers.test"],
            metadata={"health": result.get("status", "unknown")},
        )
    )
    print()


def run_switch(profile_id: str):
    print()
    profile = get_provider_profile(profile_id)
    if not profile:
        error(f"Unknown provider profile: {profile_id}")
        print()
        return
    state = SetupState.load()
    state.selected_provider_profile = profile.id
    state.save()
    record_trace(
        make_trace(
            title=f"Switched provider to {profile.name}",
            category="providers",
            status="completed",
            provider=profile.id,
            pack_id=state.primary_pack,
            tools=["clawctl.providers.switch"],
        )
    )
    success(f"Selected provider: {profile.name}")
    info(f"Endpoint: {profile.endpoint}")
    print()
