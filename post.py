"""
Queue a Reel or post to publish on Instagram at a specific date/time.

This does NOT talk to the Graph API at all — it only writes a row to the
local queue (data/queue.json). Meta expires unpublished media containers
after 24 hours, so we can't create the container now for a post that's
days out. The actual create-container -> upload -> publish sequence runs
in run_due.py, right when the scheduled time arrives (via cron or --loop).

Usage:
    python post.py --video myvideo.mp4 --caption "text here" --time "2026-07-31 18:00"
    python post.py --video myvideo.mp4 --caption "..." --time "..." --type post
    python post.py --image photo.jpg --caption "..." --time "..." --type post
    python post.py --video-url https://cdn.example.com/v.mp4 --caption "..." --time "..."
    python post.py --cancel 20260731180000-a1b2c3
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

import queue_store
import meta_api

console = Console()
load_dotenv(override=True)

VIDEO_EXTS = {".mp4", ".mov"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
TIME_FORMATS = ["%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"]


def parse_time(raw: str) -> datetime:
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise SystemExit(
        f"Could not parse --time '{raw}'. Use 'YYYY-MM-DD HH:MM' (your machine's local time)."
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--video", help="Path to a local video file")
    p.add_argument("--image", help="Path to a local image file (feed posts only)")
    p.add_argument("--video-url", help="Public URL of a video, instead of --video")
    p.add_argument("--image-url", help="Public URL of an image, instead of --image")
    p.add_argument("--caption", help="Post caption")
    p.add_argument("--time", dest="time_str", help="Scheduled local time: 'YYYY-MM-DD HH:MM'")
    p.add_argument(
        "--type", dest="post_type", choices=["reel", "post"], default="reel",
        help="'reel' publishes to the Reels tab, 'post' is a regular feed post (default: reel)",
    )
    p.add_argument("--cancel", metavar="JOB_ID", help="Cancel a scheduled job by id instead of queueing one")
    return p


def cancel(job_id: str) -> None:
    job = queue_store.get_job(job_id)
    if not job:
        console.print(f"[red]No job found with id {job_id}[/red]")
        sys.exit(1)
    if job["status"] != "scheduled":
        console.print(f"[yellow]Job {job_id} is '{job['status']}', not 'scheduled' — nothing to cancel.[/yellow]")
        sys.exit(1)
    queue_store.update_job(job_id, status="cancelled")
    console.print(f"[green]✓[/green] Cancelled {job_id}")


def resolve_media(args) -> dict:
    sources = [args.video, args.image, args.video_url, args.image_url]
    provided = [s for s in sources if s]
    if len(provided) != 1:
        raise SystemExit("Provide exactly one of --video, --image, --video-url, --image-url.")

    if args.video:
        path = Path(args.video).expanduser().resolve()
        if not path.exists():
            raise SystemExit(f"Video not found: {path}")
        if path.suffix.lower() not in VIDEO_EXTS:
            raise SystemExit(f"Unsupported video type '{path.suffix}'. Use one of {sorted(VIDEO_EXTS)}.")
        media_type = "REELS" if args.post_type == "reel" else "VIDEO"
        return {"media_type": media_type, "video_path": str(path), "image_path": None,
                "video_url": None, "image_url": None}

    if args.image:
        path = Path(args.image).expanduser().resolve()
        if not path.exists():
            raise SystemExit(f"Image not found: {path}")
        if path.suffix.lower() not in IMAGE_EXTS:
            raise SystemExit(f"Unsupported image type '{path.suffix}'. Use one of {sorted(IMAGE_EXTS)}.")
        if args.post_type == "reel":
            raise SystemExit("Images can't be published as Reels — use --type post.")
        console.print(
            "[yellow]Note:[/yellow] the Graph API doesn't support resumable upload for images. "
            "This local image path will need to be reachable at publish time via a public URL instead — "
            "use --image-url if this fails."
        )
        return {"media_type": "IMAGE", "video_path": None, "image_path": str(path),
                "video_url": None, "image_url": None}

    if args.video_url:
        media_type = "REELS" if args.post_type == "reel" else "VIDEO"
        return {"media_type": media_type, "video_path": None, "image_path": None,
                "video_url": args.video_url, "image_url": None}

    # args.image_url
    if args.post_type == "reel":
        raise SystemExit("Images can't be published as Reels — use --type post.")
    return {"media_type": "IMAGE", "video_path": None, "image_path": None,
            "video_url": None, "image_url": args.image_url}


def main():
    args = build_parser().parse_args()

    if args.cancel:
        cancel(args.cancel)
        return

    if not args.caption or not args.time_str:
        raise SystemExit("--caption and --time are required (unless using --cancel).")

    scheduled_time = parse_time(args.time_str)
    if scheduled_time <= datetime.now():
        raise SystemExit(f"--time {args.time_str} is in the past. Pick a future local time.")

    # Fail fast on missing credentials — better to find out now than at publish time.
    try:
        meta_api.load_credentials()
    except meta_api.MetaAPIError as e:
        console.print(f"[bold red]{e}[/bold red]")
        sys.exit(1)

    media = resolve_media(args)

    job_id = queue_store.new_job_id(scheduled_time)
    job = {
        "id": job_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "scheduled_time": scheduled_time.isoformat(timespec="seconds"),
        "caption": args.caption,
        "status": "scheduled",
        "container_id": None,
        "media_id": None,
        "permalink": None,
        "error": None,
        "attempts": 0,
        **media,
    }
    queue_store.add_job(job)

    table = Table(show_header=False, box=None)
    table.add_row("Job ID", job_id)
    table.add_row("Type", media["media_type"])
    table.add_row("Scheduled for", scheduled_time.strftime("%Y-%m-%d %H:%M"))
    table.add_row("Caption", (args.caption[:60] + "…") if len(args.caption) > 60 else args.caption)
    console.print("[bold green]✓ Queued[/bold green]")
    console.print(table)
    console.print(
        "\n[dim]Nothing is sent to Meta until this comes due. "
        "Run 'python run_due.py' periodically (cron) or 'python run_due.py --loop' "
        "to actually publish it.[/dim]"
    )


if __name__ == "__main__":
    main()
