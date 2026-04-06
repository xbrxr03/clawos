# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS skilld — Skill Loader Service
=====================================
Loads SKILL.md packages from ~/.claw/skills/ and ~/.openclaw/skills/.
Compatible with OpenClaw/ClawHub skill format — any skill that works
with OpenClaw also works with Claw Core.

Features:
  - BM25 relevance scoring — injects only skills relevant to the current turn
  - Pinned skills — always injected (pinned: true in frontmatter)
  - Lazy loading — dynamic info goes in user message, not system prompt
    (Nanobot PR #1704 pattern — keeps system prompt static for cache hits)
  - Deduplication — ~/.claw/skills/ takes priority over ~/.openclaw/skills/
  - Zero external dependencies — pure stdlib

Skill package format (OpenClaw-compatible):
  ~/.claw/skills/<skill-name>/SKILL.md        ← required
  ~/.claw/skills/<skill-name>/install.sh      ← optional
  ~/.claw/skills/<skill-name>/*.py            ← optional entry points

Minimal SKILL.md with Claw Core frontmatter:
  ---
  description: Summarizes documents and text
  triggers: [summarize, recap, tldr, condense]
  pinned: false
  ---
  ## Summarize
  Use this skill when the user wants to summarize or condense content.
  Call it when you see: summarize, recap, condense, brief, tldr.
"""

import re
import math
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from collections import defaultdict

log = logging.getLogger("skilld")

# ── Configuration ──────────────────────────────────────────────────────────────

MAX_SKILLS_PER_TURN    = 3      # max non-pinned skills injected per turn
MAX_SKILL_CHARS        = 800    # truncate large SKILL.md bodies
SCORE_THRESHOLD        = 0.15   # minimum BM25 score to inject a skill
PINNED_MAX             = 3      # cap on pinned skills (always injected)

# Search order matters — ~/.claw/ wins over ~/.openclaw/ for dedup
SKILL_PATHS = [
    Path.home() / ".claw"     / "skills",
    Path.home() / ".openclaw" / "skills",
]


# ── Data types ─────────────────────────────────────────────────────────────────

@dataclass
class Skill:
    name:        str
    path:        Path
    content:     str
    description: str              = ""
    triggers:    list[str]        = field(default_factory=list)
    tools:       list[str]        = field(default_factory=list)
    pinned:      bool             = False
    source:      str              = "claw"    # "claw" | "openclaw"
    _tokens:     list[str]        = field(default_factory=list)

    def __post_init__(self):
        text = f"{self.name} {self.description} {' '.join(self.triggers)} {self.content}"
        self._tokens = _tokenise(text)


@dataclass
class SkillMatch:
    skill: Skill
    score: float


# ── Tokeniser ──────────────────────────────────────────────────────────────────

def _tokenise(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return [t for t in text.split() if len(t) > 3]


# ── BM25 scoring ───────────────────────────────────────────────────────────────

def _bm25(query: list[str], doc: list[str], corpus: list[list[str]],
          k1: float = 1.5, b: float = 0.75) -> float:
    if not query or not doc:
        return 0.0
    avg_dl = sum(len(d) for d in corpus) / max(len(corpus), 1)
    tf: dict[str, int] = defaultdict(int)
    for t in doc:
        tf[t] += 1
    score = 0.0
    for term in set(query):
        if term not in tf:
            continue
        df  = sum(1 for d in corpus if term in d)
        idf = math.log((len(corpus) - df + 0.5) / (df + 0.5) + 1)
        num = tf[term] * (k1 + 1)
        den = tf[term] + k1 * (1 - b + b * len(doc) / max(avg_dl, 1))
        score += idf * (num / den)
    return score


# ── Frontmatter parser ─────────────────────────────────────────────────────────

def _parse_frontmatter(raw: str) -> tuple[dict, str]:
    """
    Parse YAML-lite frontmatter between --- delimiters.
    Handles both OpenClaw and Claw Core SKILL.md formats.
    Returns (meta dict, body string).
    """
    meta: dict = {}
    if not raw.startswith("---"):
        return meta, raw

    end = raw.find("\n---", 3)
    if end == -1:
        return meta, raw

    fm    = raw[3:end].strip()
    body  = raw[end + 4:].strip()

    for line in fm.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip()
        if not key or not val:
            continue
        if val.startswith("[") and val.endswith("]"):
            items = [x.strip().strip("\"'") for x in val[1:-1].split(",")]
            meta[key] = [i for i in items if i]
        elif val.lower() in ("true", "yes"):
            meta[key] = True
        elif val.lower() in ("false", "no"):
            meta[key] = False
        else:
            meta[key] = val

    return meta, body


# ── Single skill loader ────────────────────────────────────────────────────────

def _load_skill(name: str, skill_md: Path, source: str) -> Optional[Skill]:
    try:
        raw = skill_md.read_text(encoding="utf-8", errors="ignore")
    except OSError as e:
        log.warning(f"skilld: cannot read {skill_md}: {e}")
        return None

    meta, body = _parse_frontmatter(raw)

    if len(body) > MAX_SKILL_CHARS:
        body = body[:MAX_SKILL_CHARS] + "\n[...truncated]"

    # Description: frontmatter first, fall back to first non-empty body line
    description = str(meta.get("description", ""))
    if not description:
        for line in body.splitlines():
            line = line.strip().lstrip("#").strip()
            if line:
                description = line[:120]
                break

    triggers = meta.get("triggers", [])
    if isinstance(triggers, str):
        triggers = [t.strip() for t in triggers.split(",")]

    tools = meta.get("tools", meta.get("requires_tools", []))
    if isinstance(tools, str):
        tools = [t.strip() for t in tools.split(",")]

    skill = Skill(
        name        = name,
        path        = skill_md.parent,
        content     = body,
        description = description,
        triggers    = [t for t in triggers if t],
        tools       = [t for t in tools if t],
        pinned      = bool(meta.get("pinned", False)),
        source      = source,
    )
    log.debug(f"skilld: loaded '{name}' [{source}] pinned={skill.pinned}")
    return skill


# ── Skill loader ───────────────────────────────────────────────────────────────

class SkillLoader:
    """
    Scans all skill paths, loads SKILL.md packages, scores per turn.
    Instantiate once at startup. Call reload() after install/remove.
    """

    def __init__(self, skill_paths: list[Path] | None = None):
        self._paths:   list[Path]       = skill_paths or SKILL_PATHS
        self._skills:  list[Skill]      = []
        self._corpus:  list[list[str]]  = []
        self.reload()

    def reload(self) -> int:
        found: list[Skill] = []
        seen:  set[str]    = set()

        for search_path in self._paths:
            source = "claw" if ".claw" in str(search_path) and ".openclaw" not in str(search_path) else "openclaw"
            if not search_path.exists():
                continue
            for skill_dir in sorted(search_path.iterdir()):
                if not skill_dir.is_dir():
                    continue
                skill_md = skill_dir / "SKILL.md"
                if not skill_md.exists():
                    continue
                name = skill_dir.name
                if name in seen:
                    continue   # first path wins (claw > openclaw)
                skill = _load_skill(name, skill_md, source)
                if skill:
                    found.append(skill)
                    seen.add(name)

        self._skills  = found
        self._corpus  = [s._tokens for s in self._skills]
        log.info(f"skilld: {len(self._skills)} skills loaded "
                 f"({sum(1 for s in self._skills if s.pinned)} pinned)")
        return len(self._skills)

    # ── Queries ────────────────────────────────────────────────────────────────

    def pinned(self) -> list[Skill]:
        return [s for s in self._skills if s.pinned][:PINNED_MAX]

    def score(self, user_input: str) -> list[SkillMatch]:
        if not self._skills:
            return []
        qtoks = _tokenise(user_input)
        out: list[SkillMatch] = []
        for i, skill in enumerate(self._skills):
            if skill.pinned:
                continue
            s = _bm25(qtoks, self._corpus[i], self._corpus)
            if s >= SCORE_THRESHOLD:
                out.append(SkillMatch(skill=skill, score=s))
        out.sort(key=lambda m: m.score, reverse=True)
        return out

    def top(self, user_input: str) -> list[Skill]:
        """
        Skills to inject this turn:
          pinned (always) + top-scored relevant skills up to MAX_SKILLS_PER_TURN
        """
        p     = self.pinned()
        slots = MAX_SKILLS_PER_TURN - len(p)
        hits  = self.score(user_input)[:max(slots, 0)]
        return p + [m.skill for m in hits]

    def get(self, name: str) -> Optional[Skill]:
        for s in self._skills:
            if s.name == name:
                return s
        return None

    def list_all(self) -> list[dict]:
        return [
            {
                "name":        s.name,
                "description": s.description,
                "pinned":      s.pinned,
                "source":      s.source,
                "triggers":    s.triggers,
            }
            for s in self._skills
        ]

    @property
    def count(self) -> int:
        return len(self._skills)


# ── Injection formatter ────────────────────────────────────────────────────────

def format_skills_block(skills: list[Skill]) -> str:
    """
    Render skills into the block injected into the user message.
    Follows Nanobot PR #1704: dynamic context in user msg, not system prompt.
    Empty string if no skills to inject.
    """
    if not skills:
        return ""
    lines = ["<available_skills>"]
    for skill in skills:
        lines.append(f"\n## {skill.name}")
        if skill.description:
            lines.append(skill.description)
        if skill.content:
            lines.append(skill.content)
    lines.append("\n</available_skills>")
    return "\n".join(lines)


# ── Singleton ──────────────────────────────────────────────────────────────────

_loader: Optional[SkillLoader] = None

def get_loader() -> SkillLoader:
    global _loader
    if _loader is None:
        _loader = SkillLoader()
    return _loader

def reload_skills() -> int:
    return get_loader().reload()
