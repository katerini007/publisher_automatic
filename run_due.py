"""
Publishes any queued job whose scheduled_time has arrived.

This is the only script in this module that actually calls the Meta Graph
API. Nothing gets published until this runs — there is no server-side
"schedule for later" in the Instagram API, so this has to be triggered
periodically. Two ways to do that, both $0, both local:

  1. cron (recommended — sleeps when your machine is idle, no Python process
     has to stay alive):
       */5 * * * * cd /path/to/scheduler && /path/to/venv/bin/python run_due.py >> data/run_due.log 2>&1

  2. A foreground loop, if you'd rather just leave a terminal open:
       python run_due.py --loop --interval 300

Usage:
    python run_due.py            # check once, publish anything due, exit
    python run_due.py --loop     # check every --interval seconds, forever
    python run_due.py --dry-run  # show what's due without calling the API
"""

import argparse
import os
import sys
import time
from datetime import datetime

from dotenv import load_dotenv
from rich.console import Console

import queue_store
import meta_api

console = Console()
load_dotenv(override=True)

# ---------------------------------------------------------------------------
# SAFETY LIMITS — these make an *accidental* mass-publish impossible.
# Defaults: a run posts at most 1 reel, skips jobs >45min late (marks "missed"),
# and won't post if one went out in the last 25min. Scheduled cron runs use
# these defaults and can never dump the queue.
#
# A DELIBERATE burst is still possible, but only by explicitly overriding these
# via env vars on a manual run (e.g. MAX_PER_RUN=10 MIN_GAP_MIN=0). The env is
# only set by the manual "burst" workflow_dispatch — never by the schedule.
# ---------------------------------------------------------------------------
def _env_int(name, default):
    v = os.environ.get(name, "").strip()
    try:
        return int(v) if v else default
    except ValueError:
        return default


MAX_PER_RUN = _env_int("MAX_PER_RUN", 1)        # hard cap on reels published in one invocation
STALE_GRACE_MIN = _env_int("STALE_GRACE_MIN", 45)  # a job later than this past its time is SKIPPED (marked "missed")
MIN_GAP_MIN = _env_int("MIN_GAP_MIN", 25)       # refuse to post if the last published reel is newer than this


def _last_published_at():
    """Most recent published job's scheduled_time (proxy for last post), or None."""
    times = [
        datetime.fromisoformat(j["scheduled_time"])
        for j in queue_store.load_all()
        if j.get("status") == "published"
    ]
    return max(times) if times else None


def publish_job(creds: meta_api.Credentials, job: dict) -> None:
    job_id = job["id"]
    queue_store.update_job(job_id, status="publishing", attempts=job.get("attempts", 0) + 1)
    console.print(f"[bold]{job_id}[/bold] — publishing ({job['media_type']})...")

    try:
        limit = meta_api.check_publishing_limit(creds)
        used, quota = limit.get("quota_usage"), limit.get("config", {}).get("quota_total")
        if used is not None and quota is not None and used >= quota:
            raise meta_api.MetaAPIError(
                f"Publishing rate limit reached ({used}/{quota} in rolling 24h window). Will retry next run."
            )

        container_id = job.get("container_id")
        if not container_id:
            container_id = meta_api.create_container(
                creds,
                caption=job["caption"],
                media_type=job["media_type"],
                video_path=job.get("video_path"),
                image_path=job.get("image_path"),
                video_url=job.get("video_url"),
                image_url=job.get("image_url"),
                trial=job.get("trial", False),
                graduation_strategy=job.get("graduation_strategy", "MANUAL"),
            )
            queue_store.update_job(job_id, container_id=container_id)
            console.print(f"  container created: {container_id}")

            if job.get("video_path"):
                console.print("  uploading video bytes...")
                meta_api.upload_video_resumable(creds, container_id, job["video_path"])

        console.print("  waiting for Meta to finish processing...")
        meta_api.wait_for_finished(creds, container_id)

        media_id = meta_api.publish_container(creds, container_id)
        permalink = meta_api.get_permalink(creds, media_id)

        queue_store.update_job(
            job_id, status="published", media_id=media_id, permalink=permalink, error=None
        )
        console.print(f"  [bold green]✓ published[/bold green] {permalink or media_id}")

    except meta_api.MetaAPIError as e:
        queue_store.update_job(job_id, status="failed", error=str(e))
        console.print(f"  [bold red]✗ failed:[/bold red] {e}")


def run_once(dry_run: bool = False) -> int:
    now = datetime.now()
    due = queue_store.due_jobs(now)
    if not due:
        console.print(f"[dim]{now.strftime('%Y-%m-%d %H:%M:%S')} — nothing due.[/dim]")
        return 0

    # SAFETY 1 — drop stale jobs. A job that missed its slot by more than
    # STALE_GRACE_MIN is NOT published late; it's marked "missed". This is what
    # stops a whole past-dated day of jobs from firing in one catch-up burst.
    fresh = []
    for job in sorted(due, key=lambda j: j["scheduled_time"]):
        late_min = (now - datetime.fromisoformat(job["scheduled_time"])).total_seconds() / 60
        if late_min > STALE_GRACE_MIN:
            if not dry_run:
                queue_store.update_job(job["id"], status="missed",
                                       error=f"skipped: {int(late_min)}min past window (> {STALE_GRACE_MIN})")
            console.print(f"[yellow]skip[/yellow] {job['id']} — {int(late_min)}min stale, marked missed")
        else:
            fresh.append(job)

    if not fresh:
        console.print(f"[dim]{now.strftime('%H:%M:%S')} — nothing fresh to publish.[/dim]")
        return 0

    # SAFETY 2 — minimum gap. Never post if a reel went out very recently.
    last = _last_published_at()
    if last is not None:
        gap_min = (now - last).total_seconds() / 60
        if gap_min < MIN_GAP_MIN:
            console.print(f"[yellow]hold[/yellow] — last post {int(gap_min)}min ago (< {MIN_GAP_MIN}); skipping this run.")
            return 0

    # SAFETY 3 — hard per-run cap. At most MAX_PER_RUN reels leave in one run.
    batch = fresh[:MAX_PER_RUN]
    if len(fresh) > MAX_PER_RUN:
        console.print(f"[dim]{len(fresh)} fresh due; capping to {MAX_PER_RUN} this run.[/dim]")

    if dry_run:
        for job in batch:
            console.print(f"[yellow]would publish[/yellow] {job['id']} ({job['media_type']}) — no API calls made")
        return len(batch)

    try:
        creds = meta_api.load_credentials()
    except meta_api.MetaAPIError as e:
        console.print(f"[bold red]{e}[/bold red]")
        sys.exit(1)

    for job in batch:
        publish_job(creds, job)
    return len(batch)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--loop", action="store_true", help="Run forever, checking every --interval seconds")
    parser.add_argument("--interval", type=int, default=300, help="Seconds between checks in --loop mode (default 300)")
    parser.add_argument("--dry-run", action="store_true", help="Show what's due, make no API calls")
    args = parser.parse_args()

    if not args.loop:
        run_once(dry_run=args.dry_run)
        return

    console.print(f"[bold cyan]Watching queue every {args.interval}s. Ctrl+C to stop.[/bold cyan]")
    try:
        while True:
            run_once(dry_run=args.dry_run)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped.[/dim]")


if __name__ == "__main__":
    main()
