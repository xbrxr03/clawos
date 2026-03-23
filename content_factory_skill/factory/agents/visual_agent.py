"""
visual_agent.py — image generation via ComfyUI + DreamShaper 8.

Starts ComfyUI automatically if not already running.
Reads shots.json produced by writer_agent.
Produces: image_01.png ... image_N.png, thumbnail.png

Resume logic: each image checked individually — only missing ones generated.
"""

import json
import os
import subprocess
import time
import requests
from pathlib import Path

from core.agent_base import AgentBase

COMFYUI_BASE     = os.environ.get("COMFYUI_BASE",         "http://localhost:8188")
COMFYUI_DIR      = os.environ.get("COMFYUI_DIR",          str(Path.home() / "ComfyUI"))
CHECKPOINT       = os.environ.get("COMFYUI_CHECKPOINT",   "dreamshaper_8.safetensors")
DEFAULT_WIDTH    = int(os.environ.get("VISUAL_IMAGE_WIDTH",   "512"))
DEFAULT_HEIGHT   = int(os.environ.get("VISUAL_IMAGE_HEIGHT",  "512"))
DEFAULT_STEPS    = int(os.environ.get("VISUAL_STEPS",         "20"))
DEFAULT_CFG      = float(os.environ.get("VISUAL_CFG",         "7.0"))
STARTUP_TIMEOUT  = int(os.environ.get("COMFYUI_STARTUP_TIMEOUT", "180"))


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

        comfyui_proc = self._ensure_comfyui_running()

        try:
            for shot in shots:
                num      = shot.get("shot_number", 1)
                filename = f"image_{num:02d}.png"

                if self.artifact_exists(job_id, filename):
                    self.logger.info(f"[visual] {filename} exists — skipping")
                    continue

                prompt = shot.get("image_prompt", f"shot {num}")
                width  = shot.get("width",  DEFAULT_WIDTH)
                height = shot.get("height", DEFAULT_HEIGHT)
                neg    = shot.get("negative_prompt",
                                  "blurry, low quality, watermark, text, ugly")

                self.logger.info(f"[visual] generating {filename}: {prompt[:60]}...")
                image_bytes = self._generate_image(prompt, width=width,
                                                   height=height, negative_prompt=neg)
                self.write_artifact(job_id, filename, image_bytes)
                size_kb = len(image_bytes) // 1024
                self.logger.info(f"[visual] saved {filename} ({size_kb}KB)")
                time.sleep(1)

            # Thumbnail
            if not self.artifact_exists(job_id, "thumbnail.png"):
                art_dir = self.artifact_dir(job_id)
                if list(art_dir.glob("image_*.png")) and shots:
                    thumb_prompt = (
                        shots[0].get("image_prompt", "documentary thumbnail") +
                        ", bold centered composition, vibrant colours, YouTube thumbnail"
                    )
                    self.logger.info("[visual] generating thumbnail")
                    thumb = self._generate_image(thumb_prompt, width=512, height=512)
                    self.write_artifact(job_id, "thumbnail.png", thumb)
                    self.logger.info("[visual] thumbnail saved")
            else:
                self.logger.info("[visual] thumbnail.png exists — skipping")

        finally:
            if comfyui_proc is not None:
                self.logger.info("[visual] shutting down ComfyUI to free RAM")
                comfyui_proc.terminate()
                try:
                    comfyui_proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    comfyui_proc.kill()
                self.logger.info("[visual] ComfyUI stopped")
                self._restart_agents()

    def _restart_agents(self):
        factory_dir = Path(os.environ.get("FACTORY_ROOT",
                                           str(Path(__file__).parent.parent)))
        for agent in ["foreman_agent", "monitor_agent", "writer_agent",
                      "voice_agent", "assembler_agent"]:
            script   = factory_dir / "agents" / f"{agent}.py"
            log_file = factory_dir / "logs"   / f"{agent}.log"
            if not script.exists():
                continue
            subprocess.Popen(
                ["python3", str(script)],
                stdout=open(log_file, "a"),
                stderr=subprocess.STDOUT,
                env=os.environ.copy(),
            )
            self.logger.info(f"[visual] restarted {agent}")

    def _ensure_comfyui_running(self):
        if self._comfyui_ready():
            self.logger.info("[visual] ComfyUI already running")
            return None

        comfyui_path = Path(COMFYUI_DIR)
        if not comfyui_path.exists() or not (comfyui_path / "main.py").exists():
            raise RuntimeError(
                f"ComfyUI not found at {COMFYUI_DIR}\n"
                f"Run: cd ~/clawos/content_factory_skill && bash install.sh"
            )

        ckpt = comfyui_path / "models" / "checkpoints" / CHECKPOINT
        if not ckpt.exists():
            raise RuntimeError(
                f"Checkpoint not found: {ckpt}\n"
                f"Run: cd ~/clawos/content_factory_skill && bash install.sh"
            )

        self.logger.info("[visual] stopping other agents to free RAM for ComfyUI...")
        for agent in ["foreman_agent", "monitor_agent", "writer_agent",
                      "voice_agent", "assembler_agent"]:
            subprocess.run(["pkill", "-f", f"{agent}.py"], capture_output=True)
        time.sleep(3)

        self.logger.info(f"[visual] starting ComfyUI from {COMFYUI_DIR}...")
        proc = subprocess.Popen(
            ["python3", "main.py", "--listen", "0.0.0.0"],
            cwd=COMFYUI_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        deadline = time.time() + STARTUP_TIMEOUT
        while time.time() < deadline:
            if self._comfyui_ready():
                self.logger.info("[visual] ComfyUI ready")
                return proc
            if proc.poll() is not None:
                raise RuntimeError(
                    "ComfyUI exited during startup. "
                    f"Check logs: journalctl or {COMFYUI_DIR}"
                )
            time.sleep(3)

        proc.terminate()
        raise RuntimeError(
            f"ComfyUI did not start within {STARTUP_TIMEOUT}s. "
            f"Try starting it manually: cd {COMFYUI_DIR} && python3 main.py --listen 0.0.0.0"
        )

    def _comfyui_ready(self) -> bool:
        try:
            r = requests.get(f"{COMFYUI_BASE}/system_stats", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def _generate_image(self, prompt: str, width: int = DEFAULT_WIDTH,
                        height: int = DEFAULT_HEIGHT,
                        negative_prompt: str = "blurry, low quality") -> bytes:
        workflow = self._build_workflow(prompt, width, height, negative_prompt)
        resp = requests.post(f"{COMFYUI_BASE}/prompt",
                             json={"prompt": workflow}, timeout=30)
        resp.raise_for_status()
        prompt_id = resp.json()["prompt_id"]

        deadline = time.time() + 2700
        while time.time() < deadline:
            resp = requests.get(f"{COMFYUI_BASE}/history/{prompt_id}", timeout=10)
            resp.raise_for_status()
            history = resp.json()
            if prompt_id in history:
                for node_out in history[prompt_id].get("outputs", {}).values():
                    for img in node_out.get("images", []):
                        r = requests.get(
                            f"{COMFYUI_BASE}/view",
                            params={"filename": img["filename"],
                                    "subfolder": img.get("subfolder", ""),
                                    "type": img.get("type", "output")},
                            timeout=60,
                        )
                        r.raise_for_status()
                        return r.content
            time.sleep(2)

        raise TimeoutError(f"ComfyUI timed out for prompt_id={prompt_id}")

    def _build_workflow(self, prompt: str, width: int, height: int,
                        negative_prompt: str = "blurry, low quality") -> dict:
        import random
        return {
            "3": {"class_type": "KSampler", "inputs": {
                "seed": random.randint(0, 2**32),
                "steps": DEFAULT_STEPS, "cfg": DEFAULT_CFG,
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
                  "inputs": {"filename_prefix": "cf_output", "images": ["8", 0]}},
        }


if __name__ == "__main__":
    VisualAgent("visual_agent").run()
