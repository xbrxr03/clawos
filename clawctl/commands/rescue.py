# SPDX-License-Identifier: AGPL-3.0-or-later
"""clawctl rescue - migration helpers for existing OpenClaw users."""
from __future__ import annotations

import json

from clawos_core.catalog import detect_openclaw_install, make_trace, record_trace
from services.setupd.state import SetupState

from clawctl.ui.banner import error, info, success


def run_openclaw(path_hint: str = ""):
    print()
    manifest = detect_openclaw_install(path_hint)
    state = SetupState.load()
    state.imported_openclaw = manifest.to_dict()
    if manifest.suggested_primary_pack:
        state.primary_pack = manifest.suggested_primary_pack
    state.enable_openclaw = bool(manifest.config_path or manifest.detected_version)
    state.save()

    if state.enable_openclaw:
        success("OpenClaw rescue data detected")
        info(f"Suggested pack: {manifest.suggested_primary_pack or state.primary_pack}")
    else:
        error("No complete OpenClaw install was detected")

    print(json.dumps(manifest.to_dict(), indent=2))
    record_trace(
        make_trace(
            title="OpenClaw rescue inspection",
            category="migration",
            status="completed" if state.enable_openclaw else "warning",
            provider=state.selected_provider_profile,
            pack_id=state.primary_pack,
            tools=["clawctl.rescue.openclaw"],
            metadata={"source_path": manifest.source_path},
        )
    )
    print()
