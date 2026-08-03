# Scheduler — Instagram Reel/Post Scheduling

Queues Reels and feed posts, then publishes them at a specific local date/time
using the Meta Graph API directly. No third-party posting service, $0 cost —
Meta's API itself doesn't charge for content publishing.

Sibling to `trend-agent/`, not nested inside it — separate `.env`, separate
`requirements.txt`, own venv if you want one.

## How scheduling actually works here

The Instagram Graph API has **no native "publish later" parameter** — unlike
Facebook Page posts, there's no `scheduled_publish_time` field for Instagram
media. Two things follow from that:

1. **This tool queues locally, then publishes at the right moment.**
   `post.py` only writes a row to `data/queue.json`. `run_due.py` is what
   actually talks to Meta, and it only does so once a job's time has arrived.
2. **`run_due.py` has to be triggered periodically.** Nothing runs itself.
   Use cron (or Task Scheduler on Windows), or run it in a loop:

   ```bash
   # cron, every 5 minutes
   */5 * * * * cd /path/to/scheduler && /path/to/venv/bin/python run_due.py >> data/run_due.log 2>&1

   # or just leave a terminal open
   python run_due.py --loop --interval 300
   ```

   Your machine needs to be on and this needs to be running at (or shortly
   after) the scheduled time. There's no cloud-side timer — that's the
   trade-off for $0 and no third-party service.

Why not create the container ahead of time and just call "publish" later?
Meta expires unpublished containers after **24 hours**, so pre-creating a
container for something scheduled next week would just die before it ran.

## Setup

```bash
cd scheduler
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # then fill in the 5 values below
python smoke_test.py          # checks files/imports/env vars, no API calls
python smoke_test.py --live   # also confirms the token actually works
```

### The 5 credentials (all free, from developers.facebook.com)

| Key | Where to get it |
|---|---|
| `META_APP_ID` | Meta App → Settings → Basic |
| `META_APP_SECRET` | Same page |
| `META_PAGE_ACCESS_TOKEN` | Graph API Explorer → generate token (Page token; exchange for a long-lived one before relying on it — short-lived tokens expire in ~1 hour) |
| `INSTAGRAM_ACCOUNT_ID` | Graph API Explorer → `GET /<page-id>?fields=instagram_business_account` |
| `FACEBOOK_PAGE_ID` | Same query as above |

Required permissions on the app/token: `instagram_basic`, `instagram_content_publish`, `pages_read_engagement`.

`.env` is gitignored (see `.gitignore` in this folder). It's never read into
anything that gets logged or printed — `meta_api.py` only ever puts the
token in an `Authorization` header, never a URL or a stdout line.

### "You don't have access to this feature" when creating the app

This isn't a documented country restriction — Meta doesn't gate basic Graph
API / app-creation access by country for this use case. The far more common
causes, roughly in order of likelihood:

- **Business Verification not completed.** Required once your app needs
  Advanced Access or will be used by anyone without a role on it.
- **You're not added as a developer/tester on the app yet**, under App Roles.
- **The Instagram product hasn't been added to the app** in the dashboard
  (App → Add Product → Instagram).
- **Your Instagram account isn't a Business/Creator account connected to a
  Facebook Page** — personal accounts can't be linked to an app at all.
- **Page Publishing Authorization (PPA)** not completed on the Facebook Page.

Worth checking those in order before assuming it's regional. If you're still
blocked after all five, that's the point where it's worth asking in Meta's
developer community with your exact error text — the message often differs
by cause and that detail matters.

## Usage

```bash
# Queue a Reel
python post.py --video myvideo.mp4 --caption "text here" --time "2026-07-31 18:00"

# Queue a regular feed post instead of a Reel
python post.py --video myvideo.mp4 --caption "..." --time "..." --type post

# Already have it hosted somewhere public? Skip the local upload.
python post.py --video-url https://cdn.example.com/v.mp4 --caption "..." --time "..."

# Cancel a queued job
python post.py --cancel 20260731180000-a1b2c3

# See everything scheduled / published / failed
python content_calendar.py
python content_calendar.py --status scheduled
python content_calendar.py --upcoming

# Publish anything currently due (run this on a schedule — see above)
python run_due.py
python run_due.py --dry-run   # see what's due, no API calls
```

`--time` is your machine's local time, format `YYYY-MM-DD HH:MM`.

## Local video uploads

For `--video`, this uses Meta's **resumable upload** flow
(`upload_type=resumable` + `POST` to `rupload.facebook.com`), which sends
your file's bytes directly to Meta — no public hosting needed. If that ever
errors with a permission/login-type complaint, the fallback is hosting the
file yourself (S3, a spare web host, etc.) and using `--video-url` instead,
which skips the upload step entirely and has Meta fetch it directly.

Local **images** aren't supported by resumable upload on the Graph API —
`--image` will warn you and `--image-url` is the reliable path for photo
posts.

## Limits worth knowing

- **100 API-published posts per rolling 24 hours** per Instagram account.
  `run_due.py` checks this before each publish and defers (retries next run)
  if you're at the cap.
- **Containers expire in 24 hours** if unpublished — see above.
- Supported video formats: MP4, MOV.

## Project structure

```
scheduler/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── post.py          # CLI: queue a job
├── run_due.py        # publishes due jobs — trigger via cron or --loop
├── content_calendar.py   # lists scheduled/published/failed jobs
├── meta_api.py         # Graph API wrapper (containers, upload, publish)
├── queue_store.py      # JSON queue read/write
├── smoke_test.py        # setup verification, no spend
└── data/
    └── queue.json        # created on first `post.py` run
```
