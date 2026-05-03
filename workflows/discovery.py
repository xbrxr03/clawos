# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS Capability Discovery — Phase 11
========================================
Scans the local machine to build a capability profile, then ranks
workflows by relevance for personalized 'Try these first' suggestions.
"""
import os
import shutil
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from clawos_core.platform import platform_key


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class CapabilityProfile:
    # Installed binaries
    has_git:         bool = False
    has_ffmpeg:      bool = False
    has_docker:      bool = False
    has_node:        bool = False
    has_python:      bool = False
    has_ollama:      bool = False
    has_imagemagick: bool = False
    has_pandoc:      bool = False
    has_tesseract:   bool = False
    # File types found in home dir (ext → count)
    file_types:      dict = field(default_factory=dict)
    # Open local ports (as strings)
    running_services: List[str] = field(default_factory=list)
    # Interesting dirs
    has_downloads:   bool = False
    has_repos:       bool = False
    has_pdfs:        bool = False


@dataclass
class WorkflowSuggestion:
    workflow_id: str
    relevance:   float   # 0.0–1.0
    reason:      str


# ── Capability scanner ────────────────────────────────────────────────────────

class CapabilityScanner:
    """Sync, fast (<1 s), never raises."""

    def __init__(self, home_dir: Optional[Path] = None):
        self._home = home_dir or Path.home()

    # ── Public API ────────────────────────────────────────────────────────────

    def scan(self) -> CapabilityProfile:
        p = CapabilityProfile()
        # Binary checks
        p.has_git         = bool(shutil.which("git"))
        p.has_ffmpeg      = bool(shutil.which("ffmpeg"))
        p.has_docker      = bool(shutil.which("docker"))
        p.has_node        = bool(shutil.which("node"))
        p.has_python      = bool(shutil.which("python3") or shutil.which("python"))
        p.has_ollama      = bool(shutil.which("ollama"))
        p.has_imagemagick = bool(shutil.which("convert"))
        p.has_pandoc      = bool(shutil.which("pandoc"))
        p.has_tesseract   = bool(shutil.which("tesseract"))
        # File type scan
        try:
            p.file_types = self._scan_file_types()
        except (OSError, RuntimeError, AttributeError):
            pass
        # Running services
        try:
            p.running_services = self._check_ports()
        except (OSError, RuntimeError, AttributeError):
            pass
        # Interesting dirs
        p.has_downloads = (self._home / "Downloads").is_dir()
        p.has_repos     = any(
            (self._home / d).is_dir() for d in ("repos", "projects", "code", "dev", "src")
        )
        p.has_pdfs = p.file_types.get(".pdf", 0) > 0
        return p

    def suggest(
        self,
        profile:      Optional[CapabilityProfile] = None,
        user_profile: str = "",
    ) -> List[WorkflowSuggestion]:
        """Return workflow suggestions sorted by relevance descending."""
        if profile is None:
            profile = self.scan()

        # Lazy-load registry
        try:
            from workflows.engine import get_engine
            eng = get_engine()
            eng.load_registry()
            workflows = eng.list_workflows()
        except (ImportError, ModuleNotFoundError):
            return []

        suggestions = []
        for meta in workflows:
            score, reason = self._score(meta, profile, user_profile)
            suggestions.append(WorkflowSuggestion(
                workflow_id=meta.id,
                relevance=min(1.0, score),
                reason=reason,
            ))

        suggestions.sort(key=lambda s: s.relevance, reverse=True)
        return suggestions

    # ── Internal ──────────────────────────────────────────────────────────────

    def _scan_file_types(self) -> dict:
        """Walk home dir up to depth 2, count file extensions. Cap at 5000 visits."""
        counts: dict = {}
        visited = 0
        limit   = 5000
        home    = self._home

        def _walk(path: Path, depth: int):
            nonlocal visited
            if depth > 2 or visited >= limit:
                return
            try:
                for entry in os.scandir(path):
                    if visited >= limit:
                        return
                    visited += 1
                    if entry.is_file(follow_symlinks=False):
                        ext = Path(entry.name).suffix.lower()
                        if ext:
                            counts[ext] = counts.get(ext, 0) + 1
                    elif entry.is_dir(follow_symlinks=False):
                        name = entry.name
                        if name.startswith(".") or name in ("node_modules", "__pycache__", ".git"):
                            continue
                        _walk(Path(entry.path), depth + 1)
            except PermissionError:
                pass

        _walk(home, 0)
        return counts

    def _check_ports(self) -> List[str]:
        """Check common ports to infer running services."""
        port_map = {
            11434: "ollama",
            7070:  "clawos-dash",
            8080:  "http-server",
            3000:  "node-server",
            5432:  "postgres",
            3306:  "mysql",
            6379:  "redis",
            27017: "mongodb",
        }
        active = []
        for port, name in port_map.items():
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    active.append(name)
            except (OSError, RuntimeError, AttributeError):
                pass
        return active

    def _score(self, meta, profile: CapabilityProfile, user_profile: str) -> tuple:
        """Return (score, reason) for a workflow."""
        score  = 0.0
        reason = ""

        if meta.platforms:
            current = self._normalize_platform(platform_key())
            supported = {self._normalize_platform(name) for name in meta.platforms}
            if current not in supported:
                return 0.0, f"Supported on: {', '.join(meta.platforms)}"

        # All required binaries present
        if meta.requires:
            present = all(
                bool(shutil.which(req)) for req in meta.requires
            )
            if present:
                score  += 0.3
                reason  = f"You have {', '.join(meta.requires)} installed"
            else:
                missing = [r for r in meta.requires if not shutil.which(r)]
                score  -= 0.2
                reason  = f"Missing: {', '.join(missing)}"

        # File type relevance
        file_bonus = self._file_type_bonus(meta, profile)
        if file_bonus > 0:
            score  += file_bonus
            if not reason:
                reason = self._file_type_reason(meta, profile)

        # User profile match
        profile_bonus = self._profile_bonus(meta, user_profile)
        if profile_bonus > 0:
            score += profile_bonus
            if not reason:
                reason = f"Matches your profile: {user_profile}"

        # Beginner boost — tag present
        if "beginner" in meta.tags:
            score += 0.1

        # Destructive penalty
        if meta.destructive:
            score -= 0.1

        # Default reason
        if not reason:
            reason = meta.description

        return max(0.0, score), reason

    def _normalize_platform(self, name: str) -> str:
        lowered = name.strip().lower()
        return {"macos": "darwin", "osx": "darwin"}.get(lowered, lowered)

    def _file_type_bonus(self, meta, profile: CapabilityProfile) -> float:
        ft = profile.file_types
        bonuses = {
            "files":     (profile.has_downloads or sum(ft.values()) > 50) * 0.2,
            "documents": (ft.get(".pdf", 0) + ft.get(".docx", 0) + ft.get(".txt", 0)) > 5 and 0.2 or 0.0,
            "developer": (ft.get(".py", 0) + ft.get(".js", 0) + ft.get(".ts", 0)) > 10 and 0.2 or 0.0,
            "content":   (ft.get(".jpg", 0) + ft.get(".png", 0) + ft.get(".mp4", 0)) > 5 and 0.2 or 0.0,
            "system":    0.1,  # always somewhat relevant
            "data":      (ft.get(".csv", 0) + ft.get(".json", 0)) > 3 and 0.2 or 0.0,
        }
        return bonuses.get(meta.category, 0.0)

    def _file_type_reason(self, meta, profile: CapabilityProfile) -> str:
        ft = profile.file_types
        reasons = {
            "files":     f"You have {sum(ft.values())} files to organize",
            "documents": f"You have {ft.get('.pdf', 0)} PDFs",
            "developer": f"You have code files ({ft.get('.py', 0)} .py, {ft.get('.js', 0)} .js)",
            "content":   f"You have {ft.get('.jpg', 0) + ft.get('.png', 0)} images",
            "system":    "Useful for system monitoring",
            "data":      f"You have {ft.get('.csv', 0)} CSV files",
        }
        return reasons.get(meta.category, meta.description)

    def _profile_bonus(self, meta, user_profile: str) -> float:
        if not user_profile:
            return 0.0
        mapping = {
            "developer":       {"developer"},
            "content_creator": {"content"},
            "researcher":      {"documents"},
            "business":        {"data", "documents"},
            "general":         set(),
        }
        relevant = mapping.get(user_profile.lower(), set())
        return 0.2 if meta.category in relevant else 0.0
