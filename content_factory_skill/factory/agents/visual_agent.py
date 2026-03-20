"""
visual_agent.py — image and thumbnail generation.

Primary:  Pollinations.ai (free, no API key, no setup required)
Optional: ComfyUI via REST API (http://localhost:8188) — used if running

Reads shots.json produced by writer_agent.
Produces: image_01.png … image_N.png, thumbnail.png

Resume logic: each image file is checked individually — only missing ones
are generated. thumbnail is only generated after all shot images exist.
"""

import json
import os
import time
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

from core.agent_base import AgentBase

# ── config ─────────────────────────────────────────────────────────────────────
COMFYUI_BASE    = os.environ.get("COMFYUI_BASE",         "http://localhost:8188")
COMFYUI_DIR     = os.environ.get("COMFYUI_DIR",          "")   # empty = don't try
DEFAULT_WIDTH   = int(os.environ.get("VISUAL_IMAGE_WIDTH",  "512"))
DEFAULT_HEIGHT  = int(os.environ.get("VISUAL_IMAGE_HEIGHT", "512"))
DEFAULT_STEPS   = int(os.environ.get("VISUAL_STEPS",        "15"))
CHECKPOINT      = os.environ.get("COMFYUI_CHECKPOINT",   "dreamshaper.safetensors")

# Pollinations.ai — free, no API key
POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}?width={w}&height={h}&nologo=true"
POLLINATIONS_TIMEOUT = 60   # seconds per image


class VisualAgent(AgentBase):

    @property
    def phase_name(self) -> str:
        return "visualizing"

    @property
    def resource_class(self) -> str:
        return "heavy"

    def process_job(self, job: dict):
        job_id = job["job_id"]

        shots_raw = self.read_artifact(job_id, "shots.json")
        if not shots_raw:
            raise RuntimeError("shots.json not found — writer must run first")
        shots = json.loads(shots_raw)

        # Decide which backend to use
        use_comfyui = self._comfyui_ready()
        backend = "ComfyUI" if use_comfyui else "Pollinations.ai"
        self.logger.info(f"[visual] using backend: {backend}")

        generated_images = []

        for shot in shots:
            num      = shot.get("shot_number", 1)
            filename = f"image_{num:02d}.png"

            if self.artifact_exists(job_id, filename):
                self.logger.info(f"[visual] {filename} exists, skipping")
                generated_images.append(str(self.artifact_path(job_id, filename)))
                continue

            prompt = shot.get("image_prompt", f"image for shot {num}")
            width  = shot.get("width",  DEFAULT_WIDTH)
            height = shot.get("height", DEFAULT_HEIGHT)
            neg    = shot.get("negative_prompt", "blurry, low quality, watermark")

            self.logger.info(f"[visual] generating {filename} via {backend}: {prompt[:60]}…")

            if use_comfyui:
                image_bytes = self._generate_comfyui(prompt, width, height, neg)
            else:
                image_bytes = self._generate_pollinations(prompt, width, height)

            dest = self.write_artifact(job_id, filename, image_bytes)
            generated_images.append(str(dest))
            self.logger.info(f"[visual] saved {filename} ({len(image_bytes):,} bytes)")
            time.sleep(1)

        # Generate thumbnail
        if not self.artifact_exists(job_id, "thumbnail.png") and generated_images:
            thumb_prompt = (
                shots[0].get("image_prompt", "thumbnail") +
                ", centered composition, vibrant colours, thumbnail style"
            )
            self.logger.info("[visual] generating thumbnail")
            if use_comfyui:
                thumb_bytes = self._generate_comfyui(thumb_prompt, 512, 512)
            else:
                thumb_bytes = self._generate_pollinations(thumb_prompt, 512, 512)
            self.write_artifact(job_id, "thumbnail.png", thumb_bytes)
            self.logger.info("[visual] thumbnail saved")
        else:
            self.logger.info("[visual] thumbnail.png exists, skipping")

    # ── Pollinations.ai (free fallback, no deps) ────────────────────────────────

    def _generate_pollinations(self, prompt: str, width: int, height: int) -> bytes:
        """Generate image via Pollinations.ai — free, no API key required."""
        encoded = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&nologo=true"

        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "ClawOS-Factory/1.0"})
                with urllib.request.urlopen(req, timeout=POLLINATIONS_TIMEOUT) as resp:
                    data = resp.read()
                    if len(data) > 1000:   # valid image is at least ~1KB
                        return data
                    raise ValueError(f"Response too small ({len(data)} bytes)")
            except Exception as e:
                self.logger.warning(f"[visual] Pollinations attempt {attempt+1}/3 failed: {e}")
                if attempt < 2:
                    time.sleep(5)

        raise RuntimeError(f"Pollinations.ai failed after 3 attempts for prompt: {prompt[:60]}")

    # ── ComfyUI (optional, used when running) ──────────────────────────────────

    def _comfyui_ready(self) -> bool:
        """Return True if ComfyUI API is responding."""
        try:
            import urllib.request as r
            with r.urlopen(f"{COMFYUI_BASE}/system_stats", timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

    def _generate_comfyui(self, prompt: str, width: int, height: int,
                           negative_prompt: str = "blurry, low quality") -> bytes:
        """Generate image via ComfyUI REST API."""
        import urllib.request as r
        import json as _json

        workflow = self._build_workflow(prompt, width, height, negative_prompt)
        data = _json.dumps({"prompt": workflow}).encode()
        req  = r.Request(f"{COMFYUI_BASE}/prompt", data=data,
                         headers={"Content-Type": "application/json"})
        with r.urlopen(req, timeout=30) as resp:
            prompt_id = _json.loads(resp.read())["prompt_id"]

        deadline = time.time() + 2700
        while time.time() < deadline:
            with r.urlopen(f"{COMFYUI_BASE}/history/{prompt_id}", timeout=10) as resp:
                history = _json.loads(resp.read())
            if prompt_id in history:
                for node_output in history[prompt_id].get("outputs", {}).values():
                    for img_info in node_output.get("images", []):
                        params = urllib.parse.urlencode({
                            "filename":  img_info["filename"],
                            "subfolder": img_info.get("subfolder", ""),
                            "type":      img_info.get("type", "output"),
                        })
                        with r.urlopen(f"{COMFYUI_BASE}/view?{params}", timeout=30) as img:
                            return img.read()
            time.sleep(2)

        raise TimeoutError(f"ComfyUI timed out for prompt_id={prompt_id}")

    def _build_workflow(self, prompt: str, width: int, height: int,
                        negative_prompt: str = "blurry, low quality") -> dict:
        return {
            "3": {"class_type": "KSampler", "inputs": {
                "seed": 42, "steps": DEFAULT_STEPS, "cfg": 7.0,
                "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0,
                "model": ["4", 0], "positive": ["6", 0],
                "negative": ["7", 0], "latent_image": ["5", 0],
            }},
            "4": {"class_type": "CheckpointLoaderSimple",
                  "inputs": {"ckpt_name": CHECKPOINT}},
            "5": {"class_type": "EmptyLatentImage",
                  "inputs": {"width": width, "height": height, "batch_size": 1}},
            "6": {"class_type": "CLIPTextEncode",
                  "inputs": {"text": prompt, "clip": ["4", 1]}},
            "7": {"class_type": "CLIPTextEncode",
                  "inputs": {"text": negative_prompt, "clip": ["4", 1]}},
            "8": {"class_type": "VAEDecode",
                  "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
            "9": {"class_type": "SaveImage",
                  "inputs": {"filename_prefix": "factory_output", "images": ["8", 0]}},
        }


if __name__ == "__main__":
    VisualAgent("visual_agent").run()
