# SPDX-License-Identifier: AGPL-3.0-or-later
"""clawctl packs - inspect and install first-party ClawOS packs."""
from __future__ import annotations

from clawos_core.catalog import get_pack, list_packs, make_trace, record_trace
from services.setupd.state import SetupState

from clawctl.ui.banner import error, info, success, table


def run_list():
    print()
    state = SetupState.load()
    rows = []
    for pack in list_packs():
        status = "primary" if pack.id == state.primary_pack else "installed" if pack.id in state.secondary_packs else "available"
        rows.append((pack.id, pack.wave, status, pack.category, pack.name))
    table(rows, headers=("id", "wave", "status", "category", "name"))
    print()


def run_install(pack_id: str, primary: bool = False, provider_profile: str = ""):
    print()
    pack = get_pack(pack_id)
    if not pack:
        error(f"Unknown pack: {pack_id}")
        print()
        return

    state = SetupState.load()
    if primary or not state.primary_pack:
        state.primary_pack = pack.id
        state.secondary_packs = [item for item in state.secondary_packs if item != pack.id]
        info(f"Set primary pack: {pack.name}")
    elif pack.id != state.primary_pack and pack.id not in state.secondary_packs:
        state.secondary_packs.append(pack.id)
        info(f"Added secondary pack: {pack.name}")
    if provider_profile:
        state.selected_provider_profile = provider_profile
        info(f"Selected provider profile: {provider_profile}")
    for extension_id in pack.extension_recommendations[:2]:
        if extension_id not in state.installed_extensions:
            state.installed_extensions.append(extension_id)
    state.save()

    record_trace(
        make_trace(
            title=f"Installed pack {pack.name}",
            category="packs",
            status="completed",
            provider=state.selected_provider_profile,
            pack_id=pack.id,
            tools=["clawctl.packs.install"],
        )
    )
    success(f"{pack.name} is ready")
    info(f"Dashboards: {', '.join(pack.dashboards)}")
    info(f"Workflows: {', '.join(pack.default_workflows)}")
    print()
