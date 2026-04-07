# SPDX-License-Identifier: AGPL-3.0-or-later
"""clawctl presence - inspect Nexus presence and autonomy."""
from __future__ import annotations

from clawos_core.presence import get_presence_payload

from clawctl.ui.banner import info


def run_show():
    payload = get_presence_payload()
    profile = payload.get("profile") or {}
    autonomy = payload.get("autonomy_policy") or {}
    voice_session = payload.get("voice_session") or {}

    print()
    info(f"Assistant:     {profile.get('assistant_identity', 'Nexus')}")
    info(f"Tone:          {profile.get('tone', 'crisp-executive')}")
    info(f"Presence:      {profile.get('presence_level', 'conversational')}")
    info(f"Interruptions: {profile.get('interruption_threshold', 'meaningful')}")
    info(f"Voice mode:    {voice_session.get('mode', profile.get('preferred_voice_mode', 'push_to_talk'))}")
    info(f"Autonomy:      {autonomy.get('mode', 'mostly-autonomous')}")
    quiet_hours = autonomy.get("quiet_hours") or {}
    info(f"Quiet hours:   {quiet_hours.get('start', '22:00')} -> {quiet_hours.get('end', '07:00')}")
    print()
