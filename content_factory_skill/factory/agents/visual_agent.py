"""
visual_agent.py — image and thumbnail generation.

Uses ComfyUI via its REST API (default: http://localhost:8188).
Reads shots.json written by the writer agent.
Produces: image_01.png … image_N.png, thumbnail.png

Resume logic: each image file is checked individually — only missing ones
are generated.  thumbnail is only generated if all shot images exist.
"""

import json
import os
import subprocess
import time
import requests
from pathlib import Path

from core.agent_base import AgentBase


COMFYUI_BASE    = os.environ.get("COMFYUI_BASE",        "http://localhost:8188")
COMFYUI_DIR     = os.environ.get("COMFYUI_DIR",         str(Path.home() / "ComfyUI"))
DEFAULT_WIDTH   = int(os.environ.get("VISUAL_IMAGE_WIDTH",  "512"))
DEFAULT_HEIGHT  = int(os.environ.get("VISUAL_IMAGE_HEIGHT", "512"))
DEFAULT_STEPS   = int(os.environ.get("VISUAL_STEPS",        "15"))
DEFAULT_CFG     = 7.0
DEFAULT_SAMPLER = "euler"
CHECKPOINT      = os.environ.get("COMFYUI_CHECKPOINT", "dreamshaper.safetensors")
COMFYUI_STARTUP_TIMEOUT = 120   # seconds to wait for ComfyUI to be ready


class VisualAgent(AgentBase):

    @property
    def phase_name(self) -> str:
        return "visualizing"

    @property
    def resource_class(self) -> str:
        return "heavy"

    def process_job(self, job: dict):
        job_id = job["job_id"]

        # Load the shot prompts produced by the writer
        shots_raw = self.read_artifact(job_id, "shots.json")
        if not shots_raw:
            raise RuntimeError("shots.json not found — writer must run first")
        shots = json.loads(shots_raw)

        generated_images = []

        # ── start ComfyUI if not already running ─────────────────────────────
        comfyui_proc = self._ensure_comfyui_running()

        try:
            # ── generate each shot image ──────────────────────────────────────────
            for shot in shots:
                num      = shot.get("shot_number", 1)
                filename = f"image_{num:02d}.png"

                if self.artifact_exists(job_id, filename):
                    self.logger.info(f"[visual] {filename} exists, skipping")
                    generated_images.append(str(self.artifact_path(job_id, filename)))
                    continue

                prompt = shot.get("image_prompt", f"image for shot {num}")
                self.logger.info(f"[visual] generating {filename}: {prompt[:60]}…")

                width  = shot.get("width",  DEFAULT_WIDTH)
                height = shot.get("height", DEFAULT_HEIGHT)
                neg    = shot.get("negative_prompt", "blurry, low quality, watermark")
                image_bytes = self._generate_image(prompt, width=width, height=height, negative_prompt=neg)
                dest = self.write_artifact(job_id, filename, image_bytes)
                generated_images.append(str(dest))
                self.logger.info(f"[visual] saved {filename}")

                # Small pause between heavy generations — keeps RAM pressure down
                time.sleep(1)

            # ── generate thumbnail ────────────────────────────────────────────────
            if not self.artifact_exists(job_id, "thumbnail.png"):
                if generated_images:
                    thumb_prompt = (
                        shots[0].get("image_prompt", "thumbnail") +
                        ", centered composition, vibrant colours, thumbnail style"
                    )
                    self.logger.info("[visual] generating thumbnail")
                    thumb_bytes = self._generate_image(
                        thumb_prompt, width=512, height=512
                    )
                    self.write_artifact(job_id, "thumbnail.png", thumb_bytes)
            else:
                self.logger.info("[visual] thumbnail.png exists, skipping")

        finally:
            # ── shut down ComfyUI after all images are generated ──────────────────
            if comfyui_proc is not None:
                self.logger.info("[visual] shutting down ComfyUI to free RAM")
                comfyui_proc.terminate()
                try:
                    comfyui_proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    comfyui_proc.kill()
                self.logger.info("[visual] ComfyUI stopped")
                # Restart agents we killed before image generation
                self._restart_agents()

    def _restart_agents(self):
        """Restart factory agents that were stopped to free RAM for ComfyUI."""
        import os
        from pathlib import Path as _P

        factory_dir = _P(os.environ.get("FACTORY_ROOT", str(_P(__file__).parent.parent)))
        for agent in ["foreman_agent", "monitor_agent", "writer_agent",
                      "voice_agent", "assembler_agent"]:
            script   = factory_dir / "agents" / f"{agent}.py"
            log_file = factory_dir / "logs"   / f"{agent}.log"
            if not script.exists():
                continue
            proc = subprocess.Popen(
                ["python", str(script)],
                stdout=open(log_file, "a"),
                stderr=subprocess.STDOUT,
                env=os.environ.copy(),
            )
            self.logger.info(f"[visual] restarted {agent} (pid={proc.pid})")
        self.logger.info("[visual] all agents restarted")

    # ── ComfyUI lifecycle ─────────────────────────────────────────────────────

    def _ensure_comfyui_running(self) -> "subprocess.Popen | None":
        """
        Check if ComfyUI is already responding. If not, start it as a
        subprocess and wait for it to be ready. Returns the Popen object
        so the caller can shut it down when done, or None if it was
        already running externally.
        """
        # Check if already up
        if self._comfyui_ready():
            self.logger.info("[visual] ComfyUI already running — using existing instance")
            return None  # don't manage it — caller started it manually

        # Stop other agents to free RAM before loading the SD model.
        # They will be restarted automatically after image generation completes.
        self.logger.info("[visual] stopping other agents to free RAM...")
        for agent in ["foreman_agent", "monitor_agent", "writer_agent",
                      "voice_agent", "assembler_agent"]:
            subprocess.run(["pkill", "-f", f"{agent}.py"], capture_output=True)
        time.sleep(3)   # give processes time to exit cleanly

        # Start ComfyUI as a subprocess
        self.logger.info(f"[visual] Starting ComfyUI from {COMFYUI_DIR}...")
        proc = subprocess.Popen(
            ["python", "main.py", "--listen", "0.0.0.0", "--cpu"],
            cwd=COMFYUI_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait for it to be ready
        deadline = time.time() + COMFYUI_STARTUP_TIMEOUT
        while time.time() < deadline:
            if self._comfyui_ready():
                self.logger.info("[visual] ComfyUI is ready")
                return proc
            if proc.poll() is not None:
                raise RuntimeError("ComfyUI process exited unexpectedly during startup")
            time.sleep(3)

        proc.terminate()
        raise RuntimeError(
            f"ComfyUI did not start within {COMFYUI_STARTUP_TIMEOUT}s. "
            f"Check that {COMFYUI_DIR}/main.py exists and dependencies are installed."
        )

    def _comfyui_ready(self) -> bool:
        """Return True if ComfyUI API is responding."""
        try:
            r = requests.get(f"{COMFYUI_BASE}/system_stats", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    # ── ComfyUI image helpers ─────────────────────────────────────────────────

    def _generate_image(
        self,
        prompt: str,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        negative_prompt: str = "blurry, low quality, watermark, text, ugly",
    ) -> bytes:
        """
        Submit a prompt to ComfyUI and poll until the image is ready.
        Returns raw PNG bytes.
        """
        workflow = self._build_workflow(prompt, width, height, negative_prompt)
        # Queue the prompt
        resp = requests.post(
            f"{COMFYUI_BASE}/prompt",
            json={"prompt": workflow},
            timeout=30,
        )
        resp.raise_for_status()
        prompt_id = resp.json()["prompt_id"]

        # Poll for completion
        image_bytes = self._poll_for_output(prompt_id, timeout=2700)  # 45 min — 4.5 min/image × 8 + buffer
        return image_bytes

    def _poll_for_output(self, prompt_id: str, timeout: int = 2700) -> bytes:
        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = requests.get(f"{COMFYUI_BASE}/history/{prompt_id}", timeout=10)
            resp.raise_for_status()
            history = resp.json()
            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                for node_output in outputs.values():
                    images = node_output.get("images", [])
                    if images:
                        img_info = images[0]
                        img_resp = requests.get(
                            f"{COMFYUI_BASE}/view",
                            params={
                                "filename": img_info["filename"],
                                "subfolder": img_info.get("subfolder", ""),
                                "type": img_info.get("type", "output"),
                            },
                            timeout=30,
                        )
                        img_resp.raise_for_status()
                        return img_resp.content
            time.sleep(2)
        raise TimeoutError(f"ComfyUI did not return image for prompt_id={prompt_id} within {timeout}s")

    def _build_workflow(self, prompt: str, width: int, height: int, negative_prompt: str = "blurry, low quality") -> dict:
        """Minimal ComfyUI API workflow for text-to-image."""
        return {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed":         42,
                    "steps":        DEFAULT_STEPS,
                    "cfg":          DEFAULT_CFG,
                    "sampler_name": DEFAULT_SAMPLER,
                    "scheduler":    "normal",
                    "denoise":      1.0,
                    "model":        ["4", 0],
                    "positive":     ["6", 0],
                    "negative":     ["7", 0],
                    "latent_image": ["5", 0],
                },
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": CHECKPOINT},
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": width, "height": height, "batch_size": 1},
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": prompt,
                    "clip": ["4", 1],
                },
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": negative_prompt,
                    "clip": ["4", 1],
                },
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["3", 0],
                    "vae":     ["4", 2],
                },
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": "factory_output",
                    "images":          ["8", 0],
                },
            },
        }


if __name__ == "__main__":
    VisualAgent("visual_agent").run()
