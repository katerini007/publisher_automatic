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
INTER_POST_SLEEP_SEC = _env_int("INTER_POST_SLEEP_SEC", 0)  # pause between posts in one run (avoids Meta velocity throttle)
MAX_ATTEMPTS = _env_int("MAX_ATTEMPTS", 5)      # transient failures auto-retry on later runs up to this many tries
RETRY_BACKOFF_MIN = _env_int("RETRY_BACKOFF_MIN", 20)  # wait this many min before a transient retry (× attempt)


def _is_transient(msg: str) -> bool:
    """Meta 5xx / 'please retry' / rate-limit — worth an automatic later retry."""
    m = msg.lower()
    return any(s in m for s in (
        "(500)", "(502)", "(503)", "unexpected error", "please retry",
        "application request limit", "rate limit", "network error",
    ))


def _find_orphan_post(creds, known_permalinks):
    """After a publish error (or before a retry), check if the media actually went
    live anyway. Because we publish strictly ONE at a time, any recent post that
    isn't already recorded in the queue IS this job. Returns its permalink or None.
    This is what makes a 500-but-live post safe — we never republish it."""
    for m in meta_api.get_recent_media(creds, limit=8):
        pl = m.get("permalink")
        if pl and pl not in known_permalinks:
            return pl
    return None


def _last_published_at():
    """Most recent published job's scheduled_time (proxy for last post), or None."""
    times = [
        datetime.fromisoformat(j["scheduled_time"])
        for j in queue_store.load_all()
        if j.get("status") == "published"
    ]
    return max(times) if times else None


def _known_permalinks() -> set:
    return {j.get("permalink") for j in queue_store.load_all() if j.get("permalink")}


def _retry_or_fail(job_id: str, attempts: int, err: str) -> None:
    """Transient error → keep the job 'scheduled' so a LATER cron run retries it
    automatically (no human, no hammering). Permanent error or attempts exhausted
    → mark 'failed'."""
    if _is_transient(err) and attempts < MAX_ATTEMPTS:
        from datetime import timedelta
        not_before = datetime.now() + timedelta(minutes=RETRY_BACKOFF_MIN * attempts)
        queue_store.update_job(
            job_id, status="scheduled", error=f"transient (attempt {attempts}): {err}",
            retry_after=not_before.strftime("%Y-%m-%dT%H:%M:%S"),
        )
        console.print(f"  [yellow]↻ transient — will auto-retry after {not_before:%H:%M}[/yellow]")
    else:
        queue_store.update_job(job_id, status="failed", error=err)
        console.print(f"  [bold red]✗ failed:[/bold red] {err}")


def publish_job(creds: meta_api.Credentials, job: dict) -> None:
    job_id = job["id"]
    attempts = job.get("attempts", 0) + 1

    # IDEMPOTENCY GUARD: on any retry (attempts>1 or a container already exists),
    # first check whether this job's media already went live on a prior attempt
    # that errored after publishing. We publish one at a time, so any recent post
    # not yet recorded in the queue is THIS job — adopt it, never republish.
    if job.get("attempts", 0) > 0 or job.get("container_id"):
        orphan = _find_orphan_post(creds, _known_permalinks())
        if orphan:
            queue_store.update_job(job_id, status="published", permalink=orphan, error=None)
            console.print(f"  [bold green]✓ already live[/bold green] (dedupe) {orphan}")
            return

    queue_store.update_job(job_id, status="publishing", attempts=attempts)
    console.print(f"[bold]{job_id}[/bold] — publishing ({job['media_type']}, attempt {attempts})...")

    try:
        limit = meta_api.check_publishing_limit(creds)
        used, quota = limit.get("quota_usage"), limit.get("config", {}).get("quota_total")
        if used is not None and quota is not None and used >= quota:
            raise meta_api.MetaAPIError(
                f"Publishing rate limit reached ({used}/{quota} in rolling 24h window). Will retry next run."
            )

        # Reuse an existing container across retries (do NOT recreate — a second
        # container is a second post waiting to happen).
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
        err = str(e)
        # The publish call may have 500'd AFTER the media actually went live.
        # Reconcile against reality before deciding it failed.
        orphan = _find_orphan_post(creds, _known_permalinks())
        if orphan:
            queue_store.update_job(job_id, status="published", permalink=orphan, error=None)
            console.print(f"  [bold green]✓ published[/bold green] (recovered from 5xx) {orphan}")
            return
        _retry_or_fail(job_id, attempts, err)


def run_once(dry_run: bool = False) -> int:
    now = datetime.now()
    due = queue_store.due_jobs(now)
    if not due:
        console.print(f"[dim]{now.strftime('%Y-%m-%d %H:%M:%S')} — nothing due.[/dim]")
        return 0

    # SAFETY 1 — drop stale jobs. A job that missed its slot by more than
    # STALE_GRACE_MIN is NOT published late; it's marked "missed". This is what
    # stops a whole past-dated day of jobs from firing in one catch-up burst.
    # Honor per-job retry backoff: a transiently-failed job carries a retry_after
    # timestamp; skip it until then so we never hammer Meta's throttle.
    due = [j for j in due
           if not j.get("retry_after")
           or datetime.fromisoformat(j["retry_after"]) <= now]
    if not due:
        console.print(f"[dim]{now.strftime('%H:%M:%S')} — nothing due (all in retry backoff).[/dim]")
        return 0

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

    for i, job in enumerate(batch):
        publish_job(creds, job)
        # Pace posts to stay under Meta's publish-velocity throttle (the 5xx storm).
        if INTER_POST_SLEEP_SEC and i < len(batch) - 1:
            console.print(f"  [dim]…pausing {INTER_POST_SLEEP_SEC}s before next post[/dim]")
            time.sleep(INTER_POST_SLEEP_SEC)
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
