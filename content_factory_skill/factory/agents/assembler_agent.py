# SPDX-License-Identifier: AGPL-3.0-or-later
"""
assembler_agent.py — artifact validation and final package assembly.

Reads all artifacts produced by earlier phases.
Validates they exist and are non-empty.
Produces: edit_plan.json  (structured production manifest)
Marks the job complete if all checks pass.

Resume logic: if edit_plan.json exists, validation is skipped.
"""

import json
from pathlib import Path

from core.agent_base import AgentBase


# Artifacts that MUST exist for a job to be considered complete
# Note: images are generated AFTER assembly (visual phase runs last)
# so they are not required here.
REQUIRED_ARTIFACTS = [
    "script.txt",
    "shots.json",
    "voice.wav",
]

# Artifacts that are nice-to-have but not blocking
OPTIONAL_ARTIFACTS = [
    "metadata.json",
    "thumbnail.png",
]


class AssemblerAgent(AgentBase):

    @property
    def phase_name(self) -> str:
        return "assembling"

    @property
    def resource_class(self) -> str:
        return "light"

    def process_job(self, job: dict):
        job_id = job["job_id"]

        if self.artifact_exists(job_id, "edit_plan.json"):
            self.logger.info("[assembler] edit_plan.json exists, skipping")
            return

        # ── validate required artifacts ───────────────────────────────────────
        self.logger.info(f"[assembler] validating artifacts for {job_id}")
        missing = self._validate_required(job_id)
        if missing:
            raise RuntimeError(
                f"Required artifacts missing: {missing}. "
                f"Cannot assemble final package."
            )

        # ── load artifact contents ────────────────────────────────────────────
        script   = self.read_artifact(job_id, "script.txt") or ""
        shots    = self._load_json(job_id, "shots.json") or []
        metadata = self._load_json(job_id, "metadata.json") or {}

        # Inventory all image files
        art_dir = self.artifact_dir(job_id)
        images  = sorted(str(p) for p in art_dir.glob("image_*.png"))
        thumb   = str(art_dir / "thumbnail.png") if self.artifact_exists(job_id, "thumbnail.png") else None
        voice   = str(art_dir / "voice.wav")

        # ── build edit plan ───────────────────────────────────────────────────
        edit_plan = {
            "job_id":    job_id,
            "topic":     job.get("topic", ""),
            "metadata":  metadata,
            "assets": {
                "script":    str(art_dir / "script.txt"),
                "voice":     voice,
                "images":    images,
                "thumbnail": thumb,
                "shots":     shots,
            },
            "timeline": self._build_timeline(shots, images, script),
            "validation": {
                "required_present": True,
                "optional_present": self._check_optional(job_id),
                "image_count":      len(images),
                "script_words":     len(script.split()),
                "voice_size_bytes": (art_dir / "voice.wav").stat().st_size
                                    if (art_dir / "voice.wav").exists() else 0,
            },
        }

        self.write_artifact(job_id, "edit_plan.json", edit_plan)
        self.logger.info(
            f"[assembler] package assembled: {len(images)} images, "
            f"{edit_plan['validation']['script_words']} script words"
        )

    # ── helpers ───────────────────────────────────────────────────────────────

    def _validate_required(self, job_id: str) -> list[str]:
        """Return list of missing required artifact filenames."""
        return [f for f in REQUIRED_ARTIFACTS if not self.artifact_exists(job_id, f)]

    def _check_optional(self, job_id: str) -> dict[str, bool]:
        return {f: self.artifact_exists(job_id, f) for f in OPTIONAL_ARTIFACTS}

    def _load_json(self, job_id: str, filename: str):
        raw = self.read_artifact(job_id, filename)
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return None
        return None

    def _build_timeline(self, shots: list, images: list, script: str) -> list[dict]:
        """
        Build a simple ordered timeline mapping shots to images.
        This is the data a future video editor agent would consume.
        """
        timeline = []
        words        = script.split()
        total_words  = len(words) or 1
        wpm          = 150  # average narration words per minute
        total_secs   = total_words / wpm * 60

        for i, shot in enumerate(shots):
            num   = shot.get("shot_number", i + 1)
            start = round(total_secs * i / max(len(shots), 1), 2)
            end   = round(total_secs * (i + 1) / max(len(shots), 1), 2)

            img = images[i] if i < len(images) else None

            timeline.append({
                "index":      i,
                "shot":       num,
                "image":      img,
                "description":shot.get("description", ""),
                "mood":       shot.get("mood", "neutral"),
                "start_s":    start,
                "end_s":      end,
                "duration_s": round(end - start, 2),
            })
        return timeline


if __name__ == "__main__":
    AssemblerAgent("assembler_agent").run()
