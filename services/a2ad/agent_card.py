# SPDX-License-Identifier: AGPL-3.0-or-later
"""Builds the A2A Agent Card JSON from workspace config and SOUL.md."""
from clawos_core.models import AgentCard, AgentSkill
from clawos_core.constants import PORT_A2AD, DEFAULT_WORKSPACE


def build_card(workspace_id: str = DEFAULT_WORKSPACE,
               local_ip: str = "127.0.0.1") -> AgentCard:
    """Build AgentCard for this ClawOS node."""
    from clawos_core.constants import WORKSPACE_DIR, DEFAULT_MODEL
    from clawos_core.config.loader import get

    # Read SOUL.md first line for description
    soul_path = WORKSPACE_DIR / workspace_id / "SOUL.md"
    description = "ClawOS agent node"
    if soul_path.exists():
        first_line = soul_path.read_text().splitlines()[0].strip()
        if first_line:
            description = first_line.lstrip("#").strip()

    # Detect capabilities
    voice = get("voice.enabled", False)
    model = get("model.chat", DEFAULT_MODEL)

    try:
        from bootstrap.hardware_probe import load_saved, get_tier
        tier = get_tier(load_saved())
    except (ImportError, ModuleNotFoundError):
        tier = "C"

    skills = [
        AgentSkill("chat",      "General task execution and Q&A"),
        AgentSkill("rag_search","Search workspace documents"),
    ]

    # Add shell if granted
    try:
        from services.policyd.service import PolicyService
        skills.append(AgentSkill("shell", "Run allowlisted shell commands"))
    except (ImportError, ModuleNotFoundError):
        pass

    return AgentCard(
        name         = f"ClawOS-{workspace_id}",
        description  = description,
        url          = f"http://{local_ip}:{PORT_A2AD}/a2a",
        skills       = skills,
        tier         = tier,
        model        = model,
        voice        = voice,
        offline      = True,
        workspace_id = workspace_id,
    )
