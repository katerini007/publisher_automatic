"""READ-ONLY performance puller.

Fetches Instagram insights (views/reach/likes/shares/saves) for every
published reel in the queue and prints a table joined with our own
_batch/_hook/_group tags. Makes ONLY GET calls — never publishes or writes
anything to Instagram. Writes a local CSV for the record.
"""
import csv
import json
import sys

from dotenv import load_dotenv

import meta_api

load_dotenv(override=True)

METRICS = ["views", "reach", "likes", "comments", "shares", "saved", "total_interactions"]


def fetch_one(creds, media_id):
    url = f"{meta_api.GRAPH_HOST}/{meta_api.API_VERSION}/{media_id}/insights"
    try:
        resp = meta_api._request(
            "GET", url, context="Insights",
            params={"metric": ",".join(METRICS)},
            headers=meta_api._auth_header(creds), timeout=30,
        )
    except meta_api.MetaAPIError as e:
        return {"_error": str(e)}
    out = {}
    for row in resp.json().get("data", []):
        vals = row.get("values", [])
        out[row["name"]] = vals[0].get("value") if vals else None
    return out


def main():
    jobs = json.load(open("data/queue.json"))
    pub = [j for j in jobs if j.get("status") == "published" and j.get("media_id")]
    creds = meta_api.load_credentials()

    rows = []
    for j in pub:
        ins = fetch_one(creds, j["media_id"])
        rows.append({
            "batch": j.get("_batch", ""),
            "group": j.get("_group", ""),
            "scheduled_time": j.get("scheduled_time", ""),
            "hook": (j.get("_hook") or "")[:55],
            "views": ins.get("views"),
            "reach": ins.get("reach"),
            "likes": ins.get("likes"),
            "shares": ins.get("shares"),
            "saved": ins.get("saved"),
            "permalink": j.get("permalink", ""),
            "error": ins.get("_error", ""),
        })

    rows.sort(key=lambda r: (r["views"] or -1), reverse=True)

    with open("data/insights.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    def n(v):
        return f"{v:>7,}" if isinstance(v, int) else f"{str(v):>7}"

    print(f"{'views':>8} {'reach':>7} {'lk':>4} {'sh':>4} {'sv':>4}  batch/group        hook")
    print("-" * 100)
    for r in rows:
        if r["error"]:
            print(f"{'ERR':>8}  {r['batch']}  {r['error'][:60]}")
            continue
        print(f"{n(r['views'])} {n(r['reach'])} {n(r['likes']):>4} "
              f"{n(r['shares']):>4} {n(r['saved']):>4}  "
              f"{(r['batch']+'/'+r['group'])[:18]:<18} {r['hook']}")
    print(f"\nSaved -> data/insights.csv  ({len(rows)} reels)")


if __name__ == "__main__":
    main()
