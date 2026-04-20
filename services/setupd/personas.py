# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Canonical first-run personas for the setup wizard.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SetupPersona:
    id: str
    title: str
    glyph: str
    subtitle: str
    goals: tuple[str, ...]
    suggested_pack: str
    tag: str = ""
    install_openclaude: bool = False
    extra_models: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "glyph": self.glyph,
            "subtitle": self.subtitle,
            "goals": list(self.goals),
            "suggested_pack": self.suggested_pack,
            "tag": self.tag,
            "install_openclaude": self.install_openclaude,
            "extra_models": list(self.extra_models),
        }


PERSONAS: tuple[SetupPersona, ...] = (
    SetupPersona(
        id="developer",
        title="Developer",
        glyph="{ }",
        subtitle="Coding, git, repos, code review. OpenClaw + qwen2.5-coder.",
        goals=("code review", "git workflows", "repo analysis"),
        suggested_pack="coding-autopilot",
        tag="POPULAR",
        install_openclaude=True,
        extra_models=("qwen2.5-coder:7b",),
    ),
    SetupPersona(
        id="creator",
        title="Content Creator",
        glyph="TXT",
        subtitle="Writing, captions, images, daily digest workflows.",
        goals=("daily digest", "captions", "long-form drafts"),
        suggested_pack="daily-briefing-os",
    ),
    SetupPersona(
        id="researcher",
        title="Researcher",
        glyph="R&D",
        subtitle="PDFs, note summarisation, knowledge graph.",
        goals=("paper summarisation", "knowledge graph", "citation search"),
        suggested_pack="daily-briefing-os",
    ),
    SetupPersona(
        id="business",
        title="Business",
        glyph="BIZ",
        subtitle="Reports, spreadsheets, lead research, scheduling.",
        goals=("daily briefing", "meeting prep", "lead research"),
        suggested_pack="daily-briefing-os",
    ),
    SetupPersona(
        id="student",
        title="Student",
        glyph="STU",
        subtitle="Lecture notes, wiki, proofread, study plans.",
        goals=("lecture notes", "proofreading", "study plans"),
        suggested_pack="daily-briefing-os",
    ),
    SetupPersona(
        id="teacher",
        title="Teacher",
        glyph="EDU",
        subtitle="Lesson planning, curriculum, scheduling.",
        goals=("lesson planning", "curriculum", "scheduling"),
        suggested_pack="daily-briefing-os",
    ),
    SetupPersona(
        id="freelancer",
        title="Freelancer",
        glyph="FL",
        subtitle="Proposals, client research, outreach, invoicing.",
        goals=("proposals", "outreach", "invoicing"),
        suggested_pack="chat-app-command-center",
    ),
    SetupPersona(
        id="general",
        title="General",
        glyph="GEN",
        subtitle="Balanced - a bit of everything.",
        goals=("daily briefing", "meeting prep", "inbox triage"),
        suggested_pack="daily-briefing-os",
    ),
)


def list_setup_personas() -> list[dict[str, object]]:
    return [persona.to_dict() for persona in PERSONAS]


def get_setup_persona(persona_id: str) -> SetupPersona | None:
    wanted = (persona_id or "").strip().lower()
    for persona in PERSONAS:
        if persona.id == wanted:
            return persona
    return None

