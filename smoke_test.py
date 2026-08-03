"""
Verifies the scheduler setup without publishing anything.
Run this after filling in .env and before your first real --time job.

Usage:
    python smoke_test.py          # files, imports, env vars only — no network
    python smoke_test.py --live   # also makes one read-only Graph API call
                                   # to confirm the token/IDs actually work
"""

import argparse
import sys
from pathlib import Path

from rich.console import Console

console = Console()


def check(label: str, condition: bool, hint: str = "") -> bool:
    if condition:
        console.print(f"  [green]✓[/green] {label}")
    else:
        console.print(f"  [red]✗[/red] {label}")
        if hint:
            console.print(f"    [dim]→ {hint}[/dim]")
    return condition


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Make one read-only API call to verify credentials")
    args = parser.parse_args()

    console.print("[bold cyan]Scheduler — Smoke Test[/bold cyan]\n")
    ok = True

    console.print("[bold]File structure[/bold]")
    root = Path(__file__).parent
    for f in ["post.py", "run_due.py", "content_calendar.py", "meta_api.py", "queue_store.py",
              "requirements.txt", ".env.example", ".gitignore"]:
        ok &= check(f, (root / f).exists())

    console.print("\n[bold]Python imports[/bold]")
    try:
        import requests, dotenv, rich, dateutil  # noqa
        ok &= check("requests, dotenv, rich, dateutil", True)
    except ImportError as e:
        ok &= check("supporting libs", False, f"pip install -r requirements.txt ({e})")

    console.print("\n[bold]Environment variables[/bold]")
    from dotenv import load_dotenv
    load_dotenv(root / ".env", override=True)
    import meta_api
    try:
        creds = meta_api.load_credentials()
        ok &= check("All 5 META_*/INSTAGRAM_*/FACEBOOK_* vars set", True)
    except meta_api.MetaAPIError as e:
        ok &= check("Env vars", False, str(e))
        creds = None

    console.print("\n[bold].gitignore[/bold]")
    gitignore = (root / ".gitignore").read_text() if (root / ".gitignore").exists() else ""
    ok &= check(".env is ignored", ".env" in gitignore, "add '.env' to scheduler/.gitignore")

    if args.live:
        console.print("\n[bold]Live credential check (read-only)[/bold]")
        if not creds:
            check("Skipped — fix env vars above first", False)
        else:
            import requests
            try:
                resp = requests.get(
                    f"{meta_api.GRAPH_HOST}/{meta_api.API_VERSION}/{creds.ig_user_id}",
                    params={"fields": "username"},
                    headers=meta_api._auth_header(creds),
                    timeout=15,
                )
                if resp.ok:
                    username = resp.json().get("username", "?")
                    ok &= check(f"Connected as @{username}", True)
                else:
                    ok &= check("Live API call", False, resp.json().get("error", {}).get("message", resp.text))
            except requests.exceptions.RequestException as e:
                ok &= check("Live API call", False, f"network error ({type(e).__name__})")

    console.print()
    if ok:
        console.print("[bold green]All checks passed.[/bold green] Try: python post.py --video test.mp4 --caption \"test\" --time \"...\"")
    else:
        console.print("[bold red]Some checks failed.[/bold red] Fix issues above before scheduling anything.")
        sys.exit(1)


if __name__ == "__main__":
    main()
