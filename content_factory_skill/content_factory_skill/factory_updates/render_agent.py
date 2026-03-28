"""
render_agent.py — video rendering phase.

Reads edit_plan.json produced by assembler_agent.
Produces: final_video.mp4

Pipeline:
  1. Apply Ken Burns zoom effect to each image (ffmpeg zoompan)
  2. Burn in captions from shots.json
  3. Mix voiceover audio
  4. Add background music (optional, fades in/out)
  5. Output final_video.mp4 at 1920x1080 30fps

Resume logic: if final_video.mp4 exists, skip entirely.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from core.agent_base import AgentBase

FFMPEG_BIN    = os.environ.get("FFMPEG_BIN", "ffmpeg")
VIDEO_WIDTH   = 1920
VIDEO_HEIGHT  = 1080
FPS           = 30
FONT_PATH     = os.environ.get("CAPTION_FONT", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
MUSIC_DIR     = Path(os.environ.get("MUSIC_DIR", Path.home() / "factory/assets/music"))


def _ffprobe_duration(path: str) -> float:
    """Get audio duration in seconds using ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


class RenderAgent(AgentBase):

    @property
    def phase_name(self) -> str:
        return "rendering"

    @property
    def resource_class(self) -> str:
        return "medium"

    def process_job(self, job: dict):
        job_id = job["job_id"]

        if self.artifact_exists(job_id, "final_video.mp4"):
            self.logger.info("[render] final_video.mp4 exists — skipping")
            return

        # Load edit plan
        edit_plan_raw = self.read_artifact(job_id, "edit_plan.json")
        if not edit_plan_raw:
            raise RuntimeError("edit_plan.json not found — assembler must run first")
        edit_plan = json.loads(edit_plan_raw)

        timeline  = edit_plan["timeline"]
        voice_path = edit_plan["assets"]["voice"]
        images     = edit_plan["assets"]["images"]
        shots_raw  = self.read_artifact(job_id, "shots.json")
        shots      = json.loads(shots_raw) if shots_raw else []

        if not images:
            raise RuntimeError("No images found in edit_plan — visual phase must run first")

        self.logger.info(f"[render] rendering {len(timeline)} scenes → final_video.mp4")

        # Get actual voice duration to compute accurate scene timings
        voice_duration = _ffprobe_duration(voice_path)
        if voice_duration > 0:
            # Recalculate scene durations based on actual audio length
            n = len(timeline)
            for i, scene in enumerate(timeline):
                scene["start_s"] = round(voice_duration * i / n, 2)
                scene["end_s"]   = round(voice_duration * (i + 1) / n, 2)
                scene["duration_s"] = round(scene["end_s"] - scene["start_s"], 2)

        # Build per-scene clips then concatenate
        with tempfile.TemporaryDirectory() as tmpdir:
            clip_paths = self._render_clips(timeline, shots, tmpdir)
            concat_file = Path(tmpdir) / "concat.txt"
            concat_file.write_text(
                "\n".join(f"file '{p}'" for p in clip_paths)
            )

            # Concatenate clips
            concat_video = Path(tmpdir) / "concat.mp4"
            self._run_ffmpeg([
                "-f", "concat", "-safe", "0", "-i", str(concat_file),
                "-c", "copy",
                str(concat_video)
            ], "concat clips")

            # Mix with voice audio
            mixed_video = Path(tmpdir) / "mixed.mp4"
            self._mix_audio(str(concat_video), voice_path, str(mixed_video))

            # Add background music if available
            final_path = Path(tmpdir) / "final.mp4"
            music_file = self._find_music()
            if music_file:
                self._add_music(str(mixed_video), str(music_file), str(final_path))
            else:
                final_path = mixed_video

            # Write to artifacts
            artifact_dest = self.artifact_dir(job_id) / "final_video.mp4"
            import shutil
            shutil.copy2(str(final_path), str(artifact_dest))
            self.job_store.register_artifact(job_id, "final_video", str(artifact_dest))

        size_mb = round(artifact_dest.stat().st_size / (1024 * 1024), 1)
        self.logger.info(f"[render] ✅ final_video.mp4 written ({size_mb}MB)")

    def _render_clips(self, timeline: list, shots: list, tmpdir: str) -> list:
        """Render each scene as a short MP4 clip with Ken Burns effect and captions."""
        clips = []

        # Build shot descriptions for captions
        shot_map = {}
        for shot in shots:
            num = shot.get("shot_number", 0)
            shot_map[num] = shot.get("description", "")

        for i, scene in enumerate(timeline):
            image_path = scene.get("image")
            duration   = max(scene.get("duration_s", 5.0), 2.0)
            shot_num   = scene.get("shot", i + 1)
            caption    = shot_map.get(shot_num, scene.get("description", ""))

            if not image_path or not Path(image_path).exists():
                self.logger.warning(f"[render] missing image for scene {i} — skipping")
                continue

            clip_path = Path(tmpdir) / f"clip_{i:03d}.mp4"
            self._render_single_clip(
                image_path=image_path,
                output_path=str(clip_path),
                duration=duration,
                caption=caption,
                zoom_direction="in" if i % 2 == 0 else "out"
            )
            clips.append(str(clip_path))
            self.logger.info(f"[render] clip {i+1}/{len(timeline)} done")

        return clips

    def _render_single_clip(self, image_path: str, output_path: str,
                             duration: float, caption: str, zoom_direction: str = "in"):
        """Render one scene clip with Ken Burns zoom and caption overlay."""
        frames = int(duration * FPS)

        # Ken Burns zoom filter
        # zoom_in: slowly zoom from 1.0 to 1.05
        # zoom_out: slowly zoom from 1.05 to 1.0
        if zoom_direction == "in":
            zoom_expr = f"zoom='min(zoom+0.0002,1.05)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        else:
            zoom_expr = f"zoom='if(lte(zoom,1.0),1.05,max(1.0,zoom-0.0002))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"

        # Caption filter — white text, black outline, bottom center
        caption_safe = caption.replace("'", "").replace(":", "")[:80]
        caption_filter = ""
        if caption_safe and Path(FONT_PATH).exists():
            caption_filter = (
                f",drawtext=fontfile='{FONT_PATH}'"
                f":text='{caption_safe}'"
                f":fontcolor=white:fontsize=36:borderw=2:bordercolor=black"
                f":x=(w-text_w)/2:y=h-80"
            )

        vf = (
            f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
            f"zoompan={zoom_expr}:d={frames}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={FPS}"
            f"{caption_filter}"
        )

        self._run_ffmpeg([
            "-loop", "1", "-i", image_path,
            "-vf", vf,
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-an",
            output_path
        ], f"render clip")

    def _mix_audio(self, video_path: str, audio_path: str, output_path: str):
        """Mix voiceover audio into silent video."""
        self._run_ffmpeg([
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            output_path
        ], "mix voiceover")

    def _add_music(self, video_path: str, music_path: str, output_path: str):
        """Add background music at low volume under voiceover."""
        # Get video duration
        duration = _ffprobe_duration(video_path)

        self._run_ffmpeg([
            "-i", video_path,
            "-stream_loop", "-1", "-i", music_path,
            "-filter_complex",
            # Voice at 100%, music at 8%, fade music out last 3 seconds
            f"[1:a]volume=0.08,afade=t=out:st={max(0, duration-3)}:d=3[music];"
            "[0:a][music]amix=inputs=2:duration=first[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-t", str(duration),
            output_path
        ], "add background music")

    def _find_music(self) -> Path | None:
        """Find a background music file from the assets directory."""
        if not MUSIC_DIR.exists():
            return None
        for ext in ["*.mp3", "*.wav", "*.m4a"]:
            files = list(MUSIC_DIR.glob(ext))
            if files:
                return files[0]
        return None

    def _run_ffmpeg(self, args: list, label: str = ""):
        """Run ffmpeg with given args, raise on failure."""
        cmd = [FFMPEG_BIN, "-y", "-loglevel", "error"] + args
        self.logger.debug(f"[render] ffmpeg {label}: {' '.join(cmd[-4:])}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg {label} failed:\n{result.stderr[-500:]}")


if __name__ == "__main__":
    RenderAgent("render_agent").run()
