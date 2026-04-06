# SPDX-License-Identifier: AGPL-3.0-or-later
"""
upload_agent.py — YouTube upload phase.

Reads final_video.mp4 + metadata.json produced by earlier phases.
Uploads to YouTube at the scheduled time.
Produces: youtube_upload.json

Resume logic: if youtube_upload.json exists, skip entirely.
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.agent_base import AgentBase

SKILLS_DIR  = Path.home() / ".openclaw/skills/content-factory"
CREDS_FILE  = SKILLS_DIR / "youtube_credentials.json"
TOKEN_FILE  = SKILLS_DIR / "youtube_token.json"
SCHEDULE_FILE = SKILLS_DIR / "schedule.json"

DEFAULT_UPLOAD_TIME = "09:00"


def _load_schedule() -> dict:
    if SCHEDULE_FILE.exists():
        return json.loads(SCHEDULE_FILE.read_text())
    return {"upload_time": DEFAULT_UPLOAD_TIME, "timezone": "local"}


def _next_upload_time(time_str: str) -> datetime:
    """Return the next occurrence of HH:MM, at least 1 minute from now."""
    hh, mm = map(int, time_str.split(":"))
    now = datetime.now()
    scheduled = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if scheduled <= now + timedelta(minutes=1):
        scheduled += timedelta(days=1)
    return scheduled


class UploadAgent(AgentBase):

    @property
    def phase_name(self) -> str:
        return "uploading"

    @property
    def resource_class(self) -> str:
        return "light"

    def process_job(self, job: dict):
        job_id = job["job_id"]

        if self.artifact_exists(job_id, "youtube_upload.json"):
            self.logger.info("[upload] youtube_upload.json exists — skipping")
            return

        # Check credentials exist
        if not CREDS_FILE.exists():
            self.logger.warning("[upload] No YouTube credentials. Skipping upload.")
            self.logger.warning(f"[upload] Run: clawos youtube setup")
            # Write a skipped marker so we don't retry forever
            self.write_artifact(job_id, "youtube_upload.json", {
                "status": "skipped",
                "reason": "no_credentials",
                "message": "YouTube credentials not configured. Run: clawos youtube setup"
            })
            return

        # Check final video exists
        if not self.artifact_exists(job_id, "final_video.mp4"):
            raise RuntimeError("final_video.mp4 not found — render phase must complete first")

        # Load metadata
        metadata_raw = self.read_artifact(job_id, "metadata.json")
        metadata = json.loads(metadata_raw) if metadata_raw else {}

        # Load schedule
        schedule = _load_schedule()
        upload_time = schedule.get("upload_time", DEFAULT_UPLOAD_TIME)

        # Wait until scheduled time
        target = _next_upload_time(upload_time)
        now = datetime.now()
        wait_secs = (target - now).total_seconds()

        if wait_secs > 60:
            self.logger.info(
                f"[upload] Scheduled for {target.strftime('%Y-%m-%d %H:%M')} "
                f"({int(wait_secs/3600)}h {int((wait_secs%3600)/60)}m from now)"
            )
            # Sleep in chunks so heartbeat keeps working
            while wait_secs > 0:
                sleep_chunk = min(wait_secs, 30)
                time.sleep(sleep_chunk)
                wait_secs -= sleep_chunk
                self.logger.debug(f"[upload] waiting... {int(wait_secs/60)}min remaining")

        # Upload
        self.logger.info(f"[upload] Starting YouTube upload for job {job_id}")
        result = self._upload(job_id, metadata)
        self.write_artifact(job_id, "youtube_upload.json", result)
        self.logger.info(f"[upload] ✅ Published: {result.get('video_url')}")

    def _upload(self, job_id: str, metadata: dict) -> dict:
        """Perform the actual YouTube upload."""
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
        except ImportError:
            raise RuntimeError(
                "Missing packages. Run: pip install google-auth-oauthlib google-api-python-client"
            )

        SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
        creds  = None

        if TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow  = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
                creds = flow.run_local_server(port=0)
            TOKEN_FILE.write_text(creds.to_json())

        youtube   = build("youtube", "v3", credentials=creds)
        art_dir   = self.artifact_dir(job_id)
        video_file = art_dir / "final_video.mp4"

        title       = metadata.get("title", f"Video {job_id[:8]}")
        description = metadata.get("description", "")
        tags        = metadata.get("tags", [])

        body = {
            "snippet": {
                "title":       title,
                "description": description,
                "tags":        tags,
                "categoryId":  "22",
            },
            "status": {
                "privacyStatus":           "public",
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(
            str(video_file),
            mimetype="video/mp4",
            resumable=True,
            chunksize=10 * 1024 * 1024,
        )

        request  = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None

        while response is None:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                self.logger.info(f"[upload] {pct}%")

        video_id  = response["id"]
        video_url = f"https://youtu.be/{video_id}"

        # Upload thumbnail
        thumb = art_dir / "thumbnail.png"
        if thumb.exists():
            try:
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(str(thumb), mimetype="image/png")
                ).execute()
                self.logger.info("[upload] thumbnail set")
            except Exception as e:
                self.logger.warning(f"[upload] thumbnail failed: {e}")

        return {
            "status":      "published",
            "video_id":    video_id,
            "video_url":   video_url,
            "title":       title,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }


if __name__ == "__main__":
    UploadAgent("upload_agent").run()
