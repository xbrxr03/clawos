"""
visual_agent.py — image generation via Pollinations.ai.

Free, no API key, no GPU required. Works on any machine with internet.
Reads shots.json. Produces image_01.png ... image_N.png, thumbnail.png.
Resume: each image checked individually, only missing ones generated.
"""
import json
import os
import time
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from core.agent_base import AgentBase

POLLINATIONS_TIMEOUT = int(os.environ.get("POLLINATIONS_TIMEOUT", "90"))
DEFAULT_WIDTH  = int(os.environ.get("VISUAL_IMAGE_WIDTH",  "1280"))
DEFAULT_HEIGHT = int(os.environ.get("VISUAL_IMAGE_HEIGHT", "720"))
POLLINATIONS_MODEL = os.environ.get("POLLINATIONS_MODEL", "flux")


class VisualAgent(AgentBase):
    @property
    def phase_name(self): return "visualizing"
    @property
    def resource_class(self): return "heavy"

    def process_job(self, job: dict):
        job_id = job["job_id"]
        shots_raw = self.read_artifact(job_id, "shots.json")
        if not shots_raw:
            raise RuntimeError("shots.json not found — writer must run first")
        shots = json.loads(shots_raw)

        self.logger.info(f"[visual] generating {len(shots)} images via Pollinations.ai")

        for shot in shots:
            num      = shot.get("shot_number", 1)
            filename = f"image_{num:02d}.png"
            if self.artifact_exists(job_id, filename):
                self.logger.info(f"[visual] {filename} exists — skipping")
                continue
            prompt = shot.get("image_prompt", f"documentary shot {num}")
            width  = shot.get("width",  DEFAULT_WIDTH)
            height = shot.get("height", DEFAULT_HEIGHT)
            self.logger.info(f"[visual] generating {filename}: {prompt[:60]}...")
            image_bytes = self._generate(prompt, width, height)
            self.write_artifact(job_id, filename, image_bytes)
            self.logger.info(f"[visual] saved {filename} ({len(image_bytes)//1024}KB)")
            time.sleep(2)  # be polite to Pollinations

        # Thumbnail
        if not self.artifact_exists(job_id, "thumbnail.png"):
            art_dir = self.artifact_dir(job_id)
            if list(art_dir.glob("image_*.png")) and shots:
                thumb_prompt = (
                    shots[0].get("image_prompt", "documentary thumbnail") +
                    ", bold centered YouTube thumbnail composition, vibrant"
                )
                self.logger.info("[visual] generating thumbnail")
                thumb = self._generate(thumb_prompt, 1280, 720)
                self.write_artifact(job_id, "thumbnail.png", thumb)
                self.logger.info("[visual] thumbnail saved")
        else:
            self.logger.info("[visual] thumbnail.png exists — skipping")

    def _generate(self, prompt: str, width: int, height: int) -> bytes:
        encoded = urllib.parse.quote(prompt)
        url = (f"https://image.pollinations.ai/prompt/{encoded}"
               f"?width={width}&height={height}&model={POLLINATIONS_MODEL}"
               f"&nologo=true&enhance=true")

        for attempt in range(4):
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "ClawOS-Factory/1.0"})
                with urllib.request.urlopen(req, timeout=POLLINATIONS_TIMEOUT) as resp:
                    data = resp.read()
                    if len(data) > 5000:
                        return data
                    raise ValueError(f"Response too small ({len(data)} bytes)")
            except Exception as e:
                self.logger.warning(
                    f"[visual] Pollinations attempt {attempt+1}/4 failed: {e}")
                if attempt < 3:
                    time.sleep(10 * (attempt + 1))

        raise RuntimeError(
            f"Pollinations.ai failed after 4 attempts.\n"
            f"Check internet connection or try again later.")

if __name__ == "__main__":
    VisualAgent("visual_agent").run()
