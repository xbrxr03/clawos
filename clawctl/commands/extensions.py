"""clawctl extensions - inspect and install trusted ClawOS extensions."""
from __future__ import annotations

from clawos_core.catalog import get_extension, list_extensions, make_trace, record_trace
from services.setupd.state import SetupState

from clawctl.ui.banner import error, info, success, table


def run_list():
    print()
    state = SetupState.load()
    rows = []
    for extension in list_extensions():
        rows.append(
            (
                extension.id,
                "installed" if extension.id in state.installed_extensions else "available",
                extension.trust_tier,
                extension.category,
                extension.network_access,
            )
        )
    table(rows, headers=("id", "status", "trust", "category", "network"))
    print()


def run_install(extension_id: str):
    print()
    extension = get_extension(extension_id)
    if not extension:
        error(f"Unknown extension: {extension_id}")
        print()
        return
    state = SetupState.load()
    if extension.id not in state.installed_extensions:
        state.installed_extensions.append(extension.id)
        state.save()
    record_trace(
        make_trace(
            title=f"Installed extension {extension.name}",
            category="extensions",
            status="completed",
            provider=state.selected_provider_profile,
            pack_id=state.primary_pack,
            tools=["clawctl.extensions.install"],
        )
    )
    success(f"{extension.name} installed")
    info(f"Permissions: {', '.join(extension.permissions)}")
    print()
