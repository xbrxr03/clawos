"""
writer_agent.py — script and visual prompt generation via local LLM.

Uses Ollama (default model: llama3).
Reads template config from job["pipeline_config"] if present.
Produces:  script.txt, metadata.json, shots.json

Resume logic: each artifact is checked before generation — safe to restart.
"""

import json
import os
import subprocess
from pathlib import Path

from core.agent_base import AgentBase


# ── Runtime config (overridable via env vars) ─────────────────────────────────
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")
OLLAMA_BIN   = "ollama"


def _call_ollama(prompt: str, model: str = OLLAMA_MODEL) -> str:
    """Call ollama run <model> with a prompt, return stdout."""
    result = subprocess.run(
        [OLLAMA_BIN, "run", model, prompt],
        capture_output=True, text=True, timeout=900,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Ollama error: {result.stderr.strip()}")
    return result.stdout.strip()


def _strip_json_fences(raw: str) -> str:
    """Remove markdown code fences from LLM output before JSON parsing."""
    s = raw.strip()
    for prefix in ("```json", "```"):
        if s.startswith(prefix):
            s = s[len(prefix):]
    if s.endswith("```"):
        s = s[:-3]
    return s.strip()


# ── Template loader ───────────────────────────────────────────────────────────

def _load_template(name: str) -> dict:
    """Return the pipeline_config block from job_templates.json for a given template name."""
    schema_path = Path(__file__).parent.parent / "schemas" / "job_templates.json"
    if not schema_path.exists():
        return {}
    try:
        data = json.loads(schema_path.read_text())
        tmpl = data.get("templates", {}).get(name, {})
        return tmpl.get("pipeline_config", {})
    except Exception:
        return {}


class WriterAgent(AgentBase):

    @property
    def phase_name(self) -> str:
        return "writing"

    @property
    def resource_class(self) -> str:
        return "medium"

    def process_job(self, job: dict):
        job_id = job["job_id"]
        topic  = job["topic"]

        # Resolve template config: job-level override > named template > defaults
        pipeline_cfg = job.get("pipeline_config") or {}
        template_name = job.get("template", "")
        if template_name and not pipeline_cfg:
            pipeline_cfg = _load_template(template_name)
        script_cfg  = pipeline_cfg.get("script",  {})
        visuals_cfg = pipeline_cfg.get("visuals", {})

        # ── step 1: generate script ───────────────────────────────────────────
        if not self.artifact_exists(job_id, "script.txt"):
            self.logger.info(f"[writer] generating script for '{topic}'"
                             + (f" (template={template_name})" if template_name else ""))
            script = self._generate_script(topic, script_cfg)
            self.write_artifact(job_id, "script.txt", script)
        else:
            self.logger.info("[writer] script.txt exists — skipping")
            script = self.read_artifact(job_id, "script.txt")

        # ── step 2: generate metadata ─────────────────────────────────────────
        if not self.artifact_exists(job_id, "metadata.json"):
            self.logger.info("[writer] generating metadata")
            metadata = self._generate_metadata(topic, script, script_cfg)
            self.write_artifact(job_id, "metadata.json", metadata)

        # ── step 3: generate visual shot prompts ──────────────────────────────
        if not self.artifact_exists(job_id, "shots.json"):
            shot_count = visuals_cfg.get("shot_count", 6)
            self.logger.info(f"[writer] generating {shot_count} shot prompts")
            shots = self._generate_shots(topic, script, shot_count, visuals_cfg)
            self.write_artifact(job_id, "shots.json", shots)
        else:
            self.logger.info("[writer] shots.json exists — skipping")

    # ── LLM helpers ───────────────────────────────────────────────────────────

    def _generate_script(self, topic: str, cfg: dict) -> str:
        style      = cfg.get("style", "educational")
        max_words  = cfg.get("target_length_words", 400)
        tone       = cfg.get("tone", "clear and engaging")
        structure  = cfg.get("structure", [])
        sys_prompt = cfg.get("ollama_system_prompt", "")

        structure_hint = ""
        if structure:
            structure_hint = f"Structure the script with these sections: {', '.join(structure)}.\n"

        system = sys_prompt or "You are a professional video scriptwriter."
        prompt = (
            f"{system}\n\n"
            f"Write a video script ({max_words} words, {tone} tone) about:\n{topic}\n\n"
            f"{structure_hint}"
            f"Style: {style}. Write only the script text, no headings or stage directions."
        )
        return _call_ollama(prompt)

    def _generate_metadata(self, topic: str, script: str, cfg: dict) -> dict:
        audience = cfg.get("target_audience", "general audience")
        prompt = (
            f"Given this video script about '{topic}':\n\n{script[:1000]}\n\n"
            f"Target audience: {audience}\n\n"
            f"Return a JSON object with exactly these keys:\n"
            f"  title (string)\n"
            f"  description (1-2 sentence string)\n"
            f"  tags (array of 5 strings)\n"
            f"  target_audience (string)\n"
            f"  duration_estimate_seconds (integer)\n\n"
            f"Respond with only valid JSON. No markdown fences, no extra text."
        )
        raw = _call_ollama(prompt)
        try:
            return json.loads(_strip_json_fences(raw))
        except (json.JSONDecodeError, ValueError):
            return {
                "title":                     topic,
                "description":               f"A video about {topic}.",
                "tags":                      [topic],
                "target_audience":           audience,
                "duration_estimate_seconds": 120,
            }

    def _generate_shots(
        self,
        topic: str,
        script: str,
        shot_count: int,
        visuals_cfg: dict,
    ) -> list[dict]:
        style        = visuals_cfg.get("style", "high quality illustration")
        neg_prompt   = visuals_cfg.get("negative_prompt", "blurry, low quality, watermark")
        width        = visuals_cfg.get("image_width", 768)
        height       = visuals_cfg.get("image_height", 512)

        prompt = (
            f"Given this video script about '{topic}':\n\n{script[:1500]}\n\n"
            f"Generate {shot_count} image generation prompts for key visual moments.\n"
            f"Visual style: {style}\n"
            f"Image dimensions: {width}x{height}\n\n"
            f"Respond ONLY with a JSON array of {shot_count} objects, each with:\n"
            f"  shot_number (1-{shot_count})\n"
            f"  description (1 sentence)\n"
            f"  image_prompt (detailed Stable Diffusion prompt, style: {style})\n"
            f"  mood (one word)\n\n"
            f"No markdown fences, no extra text — just the JSON array."
        )
        raw = _call_ollama(prompt)
        try:
            shots = json.loads(_strip_json_fences(raw))
            if not isinstance(shots, list):
                raise ValueError("Not a list")
            # Attach negative prompt to each shot for the visual agent to use
            for shot in shots:
                shot.setdefault("negative_prompt", neg_prompt)
                shot.setdefault("width",  width)
                shot.setdefault("height", height)
            return shots
        except (json.JSONDecodeError, ValueError):
            return [
                {
                    "shot_number":    i,
                    "description":    f"Shot {i} for {topic}",
                    "image_prompt":   f"{style} of {topic}, professional, cinematic",
                    "negative_prompt": neg_prompt,
                    "mood":           "neutral",
                    "width":          width,
                    "height":         height,
                }
                for i in range(1, shot_count + 1)
            ]


if __name__ == "__main__":
    WriterAgent("writer_agent").run()
