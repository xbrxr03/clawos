# SPDX-License-Identifier: AGPL-3.0-or-later
"""Path helpers — always use these, never construct paths manually.
All functions import from constants at call time so tests can patch CLAWOS_DIR.
"""
from pathlib import Path


def _root() -> Path:
    from clawos_core import constants
    return constants.CLAWOS_DIR

def workspace_path(workspace_id: str) -> Path:
    p = _root() / "workspace" / workspace_id
    p.mkdir(parents=True, exist_ok=True)
    return p

def memory_path(workspace_id: str) -> Path:
    p = _root() / "memory" / workspace_id
    p.mkdir(parents=True, exist_ok=True)
    for sub in ("preferences", "knowledge", "context"):
        (p / sub).mkdir(exist_ok=True)
    return p

def pinned_path(workspace_id: str)    -> Path: return memory_path(workspace_id) / "PINNED.md"
def workflow_path(workspace_id: str)  -> Path: return memory_path(workspace_id) / "WORKFLOW.md"
def history_path(workspace_id: str)   -> Path: return memory_path(workspace_id) / "HISTORY.md"
def soul_path(workspace_id: str)      -> Path: return memory_path(workspace_id) / "SOUL.md"
def agents_path(workspace_id: str)    -> Path: return memory_path(workspace_id) / "AGENTS.md"
def heartbeat_path(workspace_id: str) -> Path: return memory_path(workspace_id) / "HEARTBEAT.md"
def identity_path(workspace_id: str)  -> Path: return memory_path(workspace_id) / "IDENTITY.md"

def log_path(name: str) -> Path:
    p = _root() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{name}.log"
