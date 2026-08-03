"""
Flat JSON-backed job queue. One file, one list of job dicts.

We deliberately don't create the Instagram media container at schedule
time — Meta expires unpublished containers after 24 hours, so a post
queued a week out would be dead before it ever ran. Containers are only
created by run_due.py, right when a job comes due.

Job shape:
{
    "id": "20260731180000-a1b2c3",
    "created_at": "2026-07-30T21:10:00",
    "scheduled_time": "2026-07-31T18:00:00",   # naive local time
    "media_type": "REELS" | "VIDEO" | "IMAGE",
    "video_path": "/abs/path/myvideo.mp4" | null,
    "image_path": "/abs/path/photo.jpg" | null,
    "video_url": "https://..." | null,          # alternative to *_path
    "caption": "text here",
    "status": "scheduled" | "publishing" | "published" | "failed" | "cancelled",
    "container_id": null,
    "media_id": null,
    "permalink": null,
    "error": null,
    "attempts": 0
}
"""

import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

QUEUE_PATH = Path(__file__).parent / "data" / "queue.json"


def _ensure_file() -> None:
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not QUEUE_PATH.exists():
        QUEUE_PATH.write_text("[]", encoding="utf-8")


def load_all() -> List[Dict[str, Any]]:
    _ensure_file()
    try:
        return json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # Corrupted queue file — back it up rather than silently losing jobs.
        backup = QUEUE_PATH.with_suffix(".corrupt.json")
        QUEUE_PATH.rename(backup)
        _ensure_file()
        return []


def save_all(jobs: List[Dict[str, Any]]) -> None:
    _ensure_file()
    QUEUE_PATH.write_text(json.dumps(jobs, indent=2, ensure_ascii=False), encoding="utf-8")


def new_job_id(scheduled_time: datetime) -> str:
    return f"{scheduled_time.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"


def add_job(job: Dict[str, Any]) -> Dict[str, Any]:
    jobs = load_all()
    jobs.append(job)
    save_all(jobs)
    return job


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    for j in load_all():
        if j["id"] == job_id:
            return j
    return None


def update_job(job_id: str, **fields) -> Optional[Dict[str, Any]]:
    jobs = load_all()
    updated = None
    for j in jobs:
        if j["id"] == job_id:
            j.update(fields)
            updated = j
            break
    if updated is not None:
        save_all(jobs)
    return updated


def due_jobs(now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Jobs still 'scheduled' whose time has passed."""
    now = now or datetime.now()
    result = []
    for j in load_all():
        if j["status"] != "scheduled":
            continue
        sched = datetime.fromisoformat(j["scheduled_time"])
        if sched <= now:
            result.append(j)
    return result


def list_jobs(status: Optional[str] = None) -> List[Dict[str, Any]]:
    jobs = load_all()
    if status:
        jobs = [j for j in jobs if j["status"] == status]
    return sorted(jobs, key=lambda j: j["scheduled_time"])
