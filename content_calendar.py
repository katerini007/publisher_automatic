"""
Lists all scheduled and published posts (and failed/cancelled ones) from
the local queue. Pure local read — no API calls, no credentials needed.

Usage:
    python calendar.py                  # everything, soonest first
    python calendar.py --status scheduled
    python calendar.py --status published
    python calendar.py --upcoming       # only scheduled jobs still in the future
"""

import argparse
from datetime import datetime

from rich.console import Console
from rich.table import Table

import queue_store

console = Console()

STATUS_STYLE = {
    "scheduled": "cyan",
    "publishing": "yellow",
    "published": "green",
    "failed": "red",
    "cancelled": "dim",
}


def truncate(text: str, n: int = 40) -> str:
    text = text or ""
    return text if len(text) <= n else text[: n - 1] + "…"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--status", choices=["scheduled", "publishing", "published", "failed", "cancelled"])
    parser.add_argument("--upcoming", action="store_true", help="Only future scheduled jobs")
    args = parser.parse_args()

    jobs = queue_store.list_jobs(status=args.status)
    if args.upcoming:
        now = datetime.now()
        jobs = [j for j in jobs if j["status"] == "scheduled" and datetime.fromisoformat(j["scheduled_time"]) > now]

    if not jobs:
        console.print("[dim]No posts match.[/dim]")
        return

    table = Table(title="Content Calendar")
    table.add_column("When")
    table.add_column("Status")
    table.add_column("Type")
    table.add_column("Caption")
    table.add_column("Link / Note")

    for j in jobs:
        when = datetime.fromisoformat(j["scheduled_time"]).strftime("%Y-%m-%d %H:%M")
        status = j["status"]
        style = STATUS_STYLE.get(status, "white")
        note = ""
        if status == "published":
            note = j.get("permalink") or j.get("media_id") or ""
        elif status == "failed":
            note = truncate(j.get("error", ""), 50)
        table.add_row(
            when,
            f"[{style}]{status}[/{style}]",
            j.get("media_type", ""),
            truncate(j.get("caption", "")),
            note,
        )

    console.print(table)

    counts = {}
    for j in jobs:
        counts[j["status"]] = counts.get(j["status"], 0) + 1
    summary = "  ".join(f"{k}: {v}" for k, v in counts.items())
    console.print(f"[dim]{len(jobs)} total — {summary}[/dim]")


if __name__ == "__main__":
    main()
