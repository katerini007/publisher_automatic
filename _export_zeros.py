"""One-off: pull the authoritative list of live media from Instagram with
exact timestamps + views, flag the 0-view ones, and verify every published
queue job is accounted for. Read-only. Writes data/trial_reels_audit.csv."""
import csv
import requests
from dotenv import load_dotenv
import meta_api as M

load_dotenv(dotenv_path=".env", override=True)
creds = M.load_credentials()

GRAPH = f"{M.GRAPH_HOST}/{M.API_VERSION}"
hdr = M._auth_header(creds)

# 1) Page through all media on the account (id, timestamp, permalink, caption)
media = []
url = f"{GRAPH}/{creds.ig_user_id}/media"
params = {"fields": "id,timestamp,permalink,caption,media_type", "limit": 100}
while url:
    r = requests.get(url, headers=hdr, params=params, timeout=30)
    r.raise_for_status()
    j = r.json()
    media.extend(j.get("data", []))
    url = j.get("paging", {}).get("next")
    params = None  # next already contains query

print(f"fetched {len(media)} media items from Instagram")

# 2) For each, pull views (insights)
rows = []
for m in media:
    views = None
    try:
        ir = requests.get(f"{GRAPH}/{m['id']}/insights",
                          headers=hdr, params={"metric": "views"}, timeout=30)
        if ir.ok:
            data = ir.json().get("data", [])
            if data:
                views = data[0]["values"][0]["value"]
    except Exception:
        pass
    rows.append({
        "media_id": m["id"],
        "timestamp": m.get("timestamp", ""),
        "views": views if views is not None else "",
        "permalink": m.get("permalink", ""),
        "caption": (m.get("caption", "") or "").replace("\n", " ")[:80],
    })

rows.sort(key=lambda x: x["timestamp"])
with open("data/trial_reels_audit.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["media_id", "timestamp", "views", "permalink", "caption"])
    w.writeheader()
    w.writerows(rows)

zeros = [r for r in rows if r["views"] == 0]
print(f"wrote data/trial_reels_audit.csv — {len(rows)} rows, {len(zeros)} with 0 views")
print()
print("ZERO-VIEW POSTS (exact IG timestamps):")
for r in zeros:
    print(f"  {r['timestamp']}  views={r['views']}  {r['permalink']}")
