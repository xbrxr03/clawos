"""upload_agent.py — YouTube upload (opt-in). Skips if credentials not configured."""
import json
import os
from pathlib import Path
from core.agent_base import AgentBase

CREDS_PATHS = [
    Path.home() / ".claw" / "skills" / "content-factory" / "youtube_credentials.json",
    Path.home() / ".openclaw" / "skills" / "content-factory" / "youtube_credentials.json",
]
SCHEDULE_PATHS = [
    Path.home() / ".claw" / "skills" / "content-factory" / "schedule.json",
    Path.home() / ".openclaw" / "skills" / "content-factory" / "schedule.json",
]

class UploadAgent(AgentBase):
    @property
    def phase_name(self): return "uploading"
    @property
    def resource_class(self): return "light"

    def process_job(self, job: dict):
        job_id = job["job_id"]

        # Check if upload is enabled in schedule.json
        for p in SCHEDULE_PATHS:
            if p.exists():
                sched = json.loads(p.read_text())
                if not sched.get("enabled", False):
                    self.logger.info("[upload] YouTube upload disabled — skipping (say 'youtube setup' to enable)")
                    return

        # Check credentials
        creds_path = None
        for p in CREDS_PATHS:
            if p.exists():
                creds_path = p
                break
        if not creds_path:
            self.logger.info("[upload] No YouTube credentials found — skipping")
            self.logger.info("[upload] To enable: tell Jarvis 'youtube setup'")
            return

        video = self.artifact_dir(job_id) / "final_video.mp4"
        if not video.exists():
            raise RuntimeError("final_video.mp4 not found — render must run first")

        metadata_raw = self.read_artifact(job_id, "metadata.json")
        metadata = json.loads(metadata_raw) if metadata_raw else {}
        title       = metadata.get("title", job.get("topic", "Untitled"))
        description = metadata.get("description", "")
        tags        = metadata.get("tags", [])

        self.logger.info(f"[upload] uploading: {title}")
        result = self._upload(str(video), title, description, tags, str(creds_path))
        self.write_artifact(job_id, "youtube_upload.json",
                            json.dumps(result, indent=2).encode())
        self.logger.info(f"[upload] uploaded: {result.get('url', 'unknown')}")

    def _upload(self, video_path, title, description, tags, creds_path):
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload

            creds = Credentials.from_authorized_user_file(creds_path)
            yt = build("youtube", "v3", credentials=creds)
            body = {
                "snippet": {"title": title, "description": description,
                            "tags": tags, "categoryId": "22"},
                "status": {"privacyStatus": "public"}
            }
            media = MediaFileUpload(video_path, mimetype="video/mp4",
                                    resumable=True, chunksize=1024*1024*5)
            req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
            resp = None
            while resp is None:
                _, resp = req.next_chunk()
            return {"video_id": resp["id"],
                    "url": f"https://youtube.com/watch?v={resp['id']}",
                    "title": title}
        except ImportError:
            raise RuntimeError(
                "Google API library not installed.\n"
                "Run: pip3 install google-auth-oauthlib google-api-python-client")

if __name__ == "__main__":
    UploadAgent("upload_agent").run()
