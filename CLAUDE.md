# Publisher Agent — Instagram Trial Reels (The AI KAT)

This folder auto-publishes Instagram **Trial Reels** for A/B testing hooks/captions,
via GitHub Actions cloud cron (computer can be off). This file is the operating
playbook: the mechanics, the safety rails, and — most importantly — the
**patterns we've proven with real data** about what gets reach vs. what dies.

---

## 🧠 CORRECTED DIAGNOSIS — why reels died (settled Aug 12 2026, evidence-based)

We spent a long investigation on "why 0 views + 'won't get much reach because it
looks like something you shared before'." Final, reconciled conclusion using ONLY
Meta-official sources + our own audit data (ignore SEO-blog lore / exact % thresholds):

1. **It is a PER-VIDEO duplicate throttle, NOT account-level jail.** Instagram's own
   **Account Status hub was all green** during the failures → the account was never
   suppressed. Only the individual *repeat-footage* reels get "shared before" + ~0 views.
2. **Duplicate detection = VISUAL + AUDIO fingerprint, NOT caption/overlay text.** The
   video pixels (and likely the audio) are what get matched. Changing the hook text or
   caption does NOT make a new video to the algorithm.
3. **First airing of a visual reaches; every REPOST of the same footage dies.** This is
   why Aug 4 (fresh-ish visuals) got 123K, and the later clone/avatar/burst2day reposts
   of the SAME footage all hit 0.
4. **Spacing/timing was NEVER the reach driver.** PROOF from `data/trial_reels_audit.csv`:
   the Aug 11 22:00 block was posted **~1–2 min apart (correct spacing)** and STILL got 0
   — because it was duplicate footage. (Spacing only ever mattered for avoiding the 403
   API-storm, not for reach.)
5. **Meta OFFICIAL original-content policy (2026):** watermarks, **changing playback
   speed**, mirroring, and reposting screenshots are **explicitly NOT enough** to count as
   original. → The "CapCut speed 101% + 1 frame + mirror" fingerprint-trick is officially
   worthless; don't do it. Only **material edits that meaningfully transform** (commentary,
   narration, creative graphics, contextual overlays, genuinely different footage) count.
6. **Account-level penalty DOES exist but only if "most" of your posts over a 30-day
   window are unoriginal** → then you lose recommendation eligibility (fatal for Trial
   Reels, which show ONLY to non-followers). We were NOT in this state (status green).
   Recovery if ever flagged: make most posts original for 30 days; can remove unoriginal
   posts + appeal in Account Status.

### THE STRATEGIC SHIFT (do this from now on)
**STOP "1 great clip → 20 hooks". START "20 distinct footage pieces → 1 hook each."**
Trial Reels are a CONTENT test (is this whole reel good?), not a clean single-variable
hook test. True same-video/different-hook A/B testing is impossible organically without
tripping the fingerprint — do that in **Meta Ads Manager** instead. Batch-shoot many
distinct visuals, one caption each. This never triggers the duplicate throttle AND gives
real per-reel signal.

### Audit tooling
`_export_zeros.py` → `data/trial_reels_audit.csv` = authoritative pull from IG (all live
media, exact `timestamp`, views, permalink). Use it to verify what actually posted and to
find 0-view duplicates before deleting them in-app.

---

## Golden rules (hard constraints)

- **Max 25 reels/day.** Never exceed. `MAX_PER_RUN=25` is the hard cap in the workflow.
- **Never clone-burst.** Posting the same *visual* many times in one window = 0 reach (proven, see below).
- **🔒 IMMUTABLE WINNING FORMAT — DO NOT CHANGE THE SPACING. EVER.** Measured from the 123K batch via Instagram's own `timestamp` field (not our planned `scheduled_time`, which lies): **19 reels posted ~46 seconds apart in ONE ~14-minute burst, 07:24→07:38 UTC = 09:24 Madrid.** Replicate exactly: queue jobs **~1 minute apart, morning burst starting 09:24 Madrid.** This caused ZERO issues and got 123K + 46K.
  - The ~1-min queue spacing is what keeps the API calls spread across cron runs. Do NOT schedule many jobs at the **same second** — that (plus 51MB long-form files hitting the processing timeout) caused `403 Application request limit reached` and failed all 23 on Aug 11. The burst itself was never the problem; the same-instant API storm was.
  - `MAX_PER_RUN=10`, container `timeout_sec=480`/`poll_interval_sec=15` support this. Don't lower the spacing to "fix" anything — fix the API-call rate instead.
- **Instagram penalizes duplicate VISUAL + AUDIO fingerprints (the video pixels & sound), NOT overlay text or captions.** Diversify the underlying footage, not just the words. (See CORRECTED DIAGNOSIS above.)
- **Each caption/hook is single-use.** Once a specific text is posted it's spent — don't reuse.
- **Delete:** our publisher/API has **NO delete endpoint** — the code can only publish. But **Kat CAN delete manually in the IG app** (she did). "Once live it's permanent" applies to *our automation*, not to her. Removing unoriginal posts can even help eligibility.
- **Target audience = USA.** Post at **16:00 Madrid = 10am US Eastern / 7am Pacific**.
- **Security:** never print/reveal `.env` credential values. Only check key *presence* or report failures.

---

## What WORKED vs what DIED (real data — `data/master_reels.csv` + `data/insights.csv`)

**Winners (Aug 4 batch — 36 reels, 3 distinct visuals, spread across the day, mixed):**
- 123,683 views · 46,377 views · then a long tail (5K, 1K, 900…).
- All breakouts were **short, 6.6–8.1s** value-caption clips.

**Total failures (0 reach):**
- **0808 clone-burst:** 10 copies of ONE visual posted together → **0 views on all 10**.
- **0810 avatar burst:** several **~22s** avatars fired at the same second → **0 views**.

### The two levers this proves
1. **Visual diversity** — a burst must be a MIX of distinct visuals. Keep the biggest single visual **≤ ~1/3** of the burst. Interleave so no two same-visual clips post back-to-back.
2. **Length** — every breakout was **sub-9-seconds**; the dead ones were ~22s. Favor short value-caption clips. (Still being confirmed as more data lands — long-form 15-hook test is running now.)

### The EXACT winning cadence (measured from Instagram timestamps, replicate this)
The 123K batch = **19 reels posted ~46 seconds apart in ONE ~14-min burst, 07:24→07:38 UTC (09:24 Madrid).** Verify with the Graph API `timestamp` field per media_id — NOT the queue's `scheduled_time` (those were planned 38-min slots that never actually fired; run_due published them all together in one catch-up run). The burst got 123K + 46K with no rate-limit issues because they were small fast clips trickling ~46s apart.

---

## The winning formula (use this to schedule)

- **~1 minute apart, one morning burst starting 09:24 Madrid** (the real winning cadence). Keep the burst tight; do NOT space out to minutes/hours and do NOT dump at the same second.
- Use a **mix of distinct visuals**; keep **biggest single visual ≤ ~1/3** of the day.
- **Interleave** visual types so identical visuals never sit adjacent, e.g. `short → long-form → avatar → short → …`.
- Prefer **short (6–9s) value-caption** clips as the backbone; mix in long-form + avatar for diversity.
- One post per unique caption/hook. ≤25/day.

---

## Current state (as of Aug 11 2026)

- **Queue:** `data/queue.json` — 112 jobs: 55 published, 45 scheduled (`_batch=burst2day`), 12 paused.
- **Scheduled bursts:**
  - **Aug 11 16:00** — 23 reels, 9 distinct visuals, biggest 34% (shorts h2 + founders long-form h02–09 + av2 h02–09).
  - **Aug 12 16:00** — 22 reels, 9 distinct visuals, biggest 40% (shorts h3 + founders h10–15 + av2 h10–18).
- **Long-form founders (15 hooks):** hook01 published, hook02–15 scheduled across the two days. All 15 covered.
- **Paused (12) = intentional stale duplicates:** 8 old failed-clone avatars (`copy_5d1b5d34…`) + 4 founders h02–05 leftovers from day-1 staging (re-scheduled fresh in the burst). Paused = never fires. Kept on purpose as reference material.

---

## Mechanics / files

- `data/queue.json` — the queue. Job schema fields include: `scheduled_time` (naive **local Madrid** time), `status`, `video_url` (raw.githubusercontent public URL), `caption`, `_hook`, `_group` (visual family), `_batch`.
- `run_due.py` — publishes due jobs. Safety guards: `STALE_GRACE_MIN=45` (>45min-late → marked `missed`, so a past-dated backlog can NEVER dump), `MIN_GAP_MIN`, `MAX_PER_RUN`. Due jobs sorted by `scheduled_time` (stable sort preserves queue order for identical times).
- `.github/workflows/publish.yml` — cron `*/10 * * * *`, `TZ=Europe/Madrid`, `MAX_PER_RUN=25`, `MIN_GAP_MIN=0` (burst-on-schedule). Commits queue status back with `[skip ci]`. `workflow_dispatch` allows a manual override burst.
- `pull_insights.py` — READ-ONLY. Pulls views/reach/likes/etc into `data/insights.csv`. Needs `load_dotenv(override=True)`.
- `data/master_reels.csv` — master strategy sheet (all reels: type, exact length_sec, hook, caption, performance, when posted). Feed to the analytics agent; regenerate after new data lands.
- Videos live in `videos/` and are served publicly via `raw.githubusercontent.com`. **GitHub limit 100MB/file** (warns at 50MB) — compress 4K→1080p CRF18 with the static ffmpeg at `/Volumes/KINGSTON/Claude/AGENTS/VIDEO-CREATION/nutrition-channel/assets/bin/ffmpeg` before committing.

## Git hygiene
The Actions bot commits `queue.json` back after every run. **Before editing the queue locally: `git fetch && git pull --ff-only`.** Never `git rebase` the queue (caused an ambiguous `--ours/--theirs` conflict once). If diverged and local is the authoritative superset, `git merge -s ours origin/main`.

## Common tasks
- **Add a batch:** compress videos → commit to `videos/` → add jobs to `queue.json` (same `scheduled_time` for a burst, diluted mix, ≤1/3 per visual, interleaved) → pull/merge → commit → push.
- **Check performance:** run `pull_insights.py`, then regenerate `master_reels.csv`.
- **Never** clone-burst, exceed 25/day, or reuse a spent caption.
