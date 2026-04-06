# SPDX-License-Identifier: AGPL-3.0-or-later
#!/usr/bin/env python3
"""
youtube_upload.py — Upload assembled factory video to YouTube.
Usage:
  python3 youtube_upload.py --job-id <job_id> [--schedule HH:MM] [--test]
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

FACTORY_ROOT = Path(os.environ.get("FACTORY_ROOT", Path.home() / "factory"))
SKILLS_DIR   = Path.home() / ".openclaw/skills/content-factory"
CREDS_FILE   = SKILLS_DIR / "youtube_credentials.json"
TOKEN_FILE   = SKILLS_DIR / "youtube_token.json"


def get_youtube_service():
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        print("Missing packages. Run: pip install google-auth-oauthlib google-api-python-client")
        sys.exit(1)

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDS_FILE.exists():
                print(f"No credentials found at {CREDS_FILE}")
                print("Run: clawos youtube setup")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())

    return build("youtube", "v3", credentials=creds)


def get_job_artifacts(job_id: str) -> dict:
    """Find job artifacts directory and load metadata."""
    artifacts_dir = FACTORY_ROOT / "artifacts" / job_id
    if not artifacts_dir.exists():
        # Try completed jobs
        for job_dir in (FACTORY_ROOT / "jobs" / "completed").iterdir():
            if job_id in job_dir.name:
                artifacts_dir = FACTORY_ROOT / "artifacts" / job_dir.name
                job_id = job_dir.name
                break

    if not artifacts_dir.exists():
        raise FileNotFoundError(f"No artifacts found for job {job_id}")

    metadata_file = artifacts_dir / "metadata.json"
    edit_plan_file = artifacts_dir / "edit_plan.json"
    video_file = artifacts_dir / "final_video.mp4"
    thumbnail_file = artifacts_dir / "thumbnail.png"

    if not video_file.exists():
        raise FileNotFoundError(f"No final_video.mp4 found. Has the video been assembled?")

    metadata = {}
    if metadata_file.exists():
        metadata = json.loads(metadata_file.read_text())

    return {
        "job_id": job_id,
        "artifacts_dir": artifacts_dir,
        "video_file": video_file,
        "thumbnail_file": thumbnail_file if thumbnail_file.exists() else None,
        "metadata": metadata,
    }


def upload_video(job_id: str, publish_at: str = None):
    """Upload video to YouTube, optionally scheduled."""
    from googleapiclient.http import MediaFileUpload

    print(f"[youtube] Loading artifacts for {job_id}")
    artifacts = get_job_artifacts(job_id)
    metadata  = artifacts["metadata"]

    title       = metadata.get("title", f"Video {job_id}")
    description = metadata.get("description", "")
    tags        = metadata.get("tags", [])

    # Build scheduled publish time
    publish_at_iso = None
    if publish_at:
        now = datetime.utcnow()
        hh, mm = map(int, publish_at.split(":"))
        scheduled = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if scheduled <= now:
            scheduled += timedelta(days=1)
        publish_at_iso = scheduled.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        print(f"[youtube] Scheduling for {publish_at_iso}")

    status = "scheduled" if publish_at_iso else "public"

    body = {
        "snippet": {
            "title":       title,
            "description": description,
            "tags":        tags,
            "categoryId":  "22",  # People & Blogs
        },
        "status": {
            "privacyStatus":        status,
            "publishAt":            publish_at_iso,
            "selfDeclaredMadeForKids": False,
        },
    }

    print(f"[youtube] Uploading: {title}")
    youtube = get_youtube_service()

    media = MediaFileUpload(
        str(artifacts["video_file"]),
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024 * 10,  # 10MB chunks
    )

    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status_obj, response = request.next_chunk()
        if status_obj:
            pct = int(status_obj.progress() * 100)
            print(f"[youtube] Upload progress: {pct}%")

    video_id  = response["id"]
    video_url = f"https://youtu.be/{video_id}"
    print(f"[youtube] ✅ Uploaded: {video_url}")

    # Upload thumbnail if available
    if artifacts["thumbnail_file"]:
        print("[youtube] Uploading thumbnail...")
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(str(artifacts["thumbnail_file"]), mimetype="image/png")
            ).execute()
            print("[youtube] ✅ Thumbnail set")
        except Exception as e:
            print(f"[youtube] ⚠️ Thumbnail upload failed: {e}")

    # Save upload result
    result = {
        "video_id":  video_id,
        "video_url": video_url,
        "title":     title,
        "uploaded_at": datetime.utcnow().isoformat(),
        "scheduled_for": publish_at_iso,
    }
    upload_log = artifacts["artifacts_dir"] / "youtube_upload.json"
    upload_log.write_text(json.dumps(result, indent=2))

    return result


def test_connection():
    """Test YouTube API connection."""
    try:
        youtube = get_youtube_service()
        response = youtube.channels().list(part="snippet", mine=True).execute()
        channels = response.get("items", [])
        if channels:
            name = channels[0]["snippet"]["title"]
            print(f"✅ Connected to YouTube channel: {name}")
        else:
            print("✅ Connected but no channels found")
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id",   help="Factory job ID to upload")
    parser.add_argument("--schedule", help="Schedule upload at HH:MM (e.g. 09:00)")
    parser.add_argument("--test",     action="store_true", help="Test YouTube connection")
    args = parser.parse_args()

    if args.test:
        sys.exit(0 if test_connection() else 1)

    if not args.job_id:
        print("Error: --job-id required")
        sys.exit(1)

    result = upload_video(args.job_id, args.schedule)
    print(json.dumps(result, indent=2))
