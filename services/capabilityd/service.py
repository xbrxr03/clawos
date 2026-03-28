"""
capabilityd — Capability Graph Engine

Indexes skill capabilities (inputs/outputs/permissions) and solves execution
pipelines using BFS on a directed acyclic graph.

A node = a data state (e.g. "text", "audio_file", "video_file", "url")
An edge = a skill/tool that transforms one state to another

Given:
  goal_state = "youtube_url"
  current_state = "text"

Finds:
  text → [script_generator] → script
       → [piper_tts]        → audio_file
       → [comfyui]          → images
       → [ffmpeg_render]    → video_file
       → [youtube_upload]   → youtube_url
"""
import logging
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger("capabilityd")

CAPABILITY_DIRS = [
    Path(__file__).parent.parent,           # services/ — built-in capabilities
    Path.home() / ".claw" / "skills",       # user skills
    Path.home() / ".openclaw" / "skills",   # OpenClaw skills
]


@dataclass
class Capability:
    name:        str
    inputs:      list
    outputs:     list
    permissions: list = field(default_factory=list)
    cost:        str  = "medium"   # low / medium / high
    latency:     str  = "medium"   # fast / medium / slow
    tags:        list = field(default_factory=list)
    entry:       Optional[str] = None  # python entry point or shell command


class CapabilityGraph:
    def __init__(self):
        self._caps:  list[Capability]           = []
        self._index: dict[str, list[Capability]] = {}  # input_state → [capabilities]

    def load_all(self):
        """Scan capability dirs for *.capability.yaml files."""
        self._caps.clear()
        self._index.clear()
        loaded = 0
        for cap_dir in CAPABILITY_DIRS:
            if not cap_dir.exists():
                continue
            for fpath in cap_dir.rglob("*.capability.yaml"):
                try:
                    import yaml
                    data = yaml.safe_load(fpath.read_text())
                    if not data or not isinstance(data, dict):
                        continue
                    cap = Capability(
                        name=data.get("name", fpath.stem),
                        inputs=data.get("inputs", []),
                        outputs=data.get("outputs", []),
                        permissions=data.get("permissions", []),
                        cost=data.get("cost", "medium"),
                        latency=data.get("latency", "medium"),
                        tags=data.get("tags", []),
                        entry=data.get("entry"),
                    )
                    self._caps.append(cap)
                    for inp in cap.inputs:
                        self._index.setdefault(inp, []).append(cap)
                    loaded += 1
                except Exception as e:
                    log.warning(f"Failed to load capability {fpath}: {e}")
        log.info(f"Loaded {loaded} capabilities from {len(CAPABILITY_DIRS)} dirs")

    def solve(self, from_state: str, to_state: str) -> Optional[list[Capability]]:
        """BFS from from_state to to_state. Returns capability chain or None."""
        if from_state == to_state:
            return []
        queue   = deque([(from_state, [])])
        visited = {from_state}
        while queue:
            current, path = queue.popleft()
            for cap in self._index.get(current, []):
                new_path = path + [cap]
                for output in cap.outputs:
                    if output == to_state:
                        return new_path
                    if output not in visited:
                        visited.add(output)
                        queue.append((output, new_path))
        return None

    def describe_pipeline(self, pipeline: list[Capability]) -> str:
        if not pipeline:
            return "No steps needed"
        return " → ".join(
            f"{c.name}({', '.join(c.outputs)})" for c in pipeline
        )

    def list_capabilities(self) -> list[dict]:
        return [
            {
                "name":    c.name,
                "inputs":  c.inputs,
                "outputs": c.outputs,
                "cost":    c.cost,
                "latency": c.latency,
                "tags":    c.tags,
            }
            for c in self._caps
        ]


_graph: Optional[CapabilityGraph] = None


def get_graph() -> CapabilityGraph:
    global _graph
    if _graph is None:
        _graph = CapabilityGraph()
        _graph.load_all()
    return _graph
