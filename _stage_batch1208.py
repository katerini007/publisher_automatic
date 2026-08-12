"""Stage the 12.08 batch: 25 new-visual reels, captions reused from master sheet.
Builds jobs with status 'staged' (run_due ignores them) so nothing fires until
we flip to 'scheduled' on GO. Spacing handled at publish time by sequential run."""
import json, csv, re, datetime, uuid

RAW = "https://raw.githubusercontent.com/katerini007/publisher_automatic/main/videos/batch_12-08"

rows = list(csv.DictReader(open("data/master_reels.csv")))
def norm(s):
    s = s.lower().replace("’","'").replace("“","").replace("”","")
    s = re.sub(r"[^a-z0-9 ]","",s)
    return re.sub(r"\s+"," ",s).strip()
capmap = {}
for r in rows:
    h, c = norm(r.get("hook","")), r.get("caption","").strip()
    if h and c and h not in capmap: capmap[h] = c
import difflib
def cap_for(h):
    nh = norm(h)
    if nh in capmap: return capmap[nh]
    m = difflib.get_close_matches(nh, list(capmap), n=1, cutoff=0.6)
    return capmap[m[0]] if m else None

# (reel#, length_sec, audio, hook)
plan = [
(1,3,"#1","The #1 AI skill for business owners in 2026 isn't a tool"),
(2,3,"#1","This AI workflow makes 30 Reels in 5 minutes"),
(3,3,"#1","Still comfortable without AI? Not for much longer."),
(4,3,"#1","If you could learn only ONE AI tool this year, make it this"),
(5,3,"#1","Most people use AI to write faster. The smart ones use it to"),
(6,3,"#1","This AI workflow creates 30 Reels in 5 minutes"),
(7,3,"#1","The biggest content creation mistake business owners make"),
(8,3,"#1","The AI skill every business owner needs in 2026"),
(9,4,"#1","The AI skill every female business owner needs in 2026"),
(10,4,"#2","I don't have time to get ready and film. So I stopped getting ready."),
(11,4,"#2","I filmed this looking like a mess. You'll never see that version."),
(12,4,"#2","I stopped wasting an hour getting camera-ready for a 30-second Reel."),
(13,4,"#2","I film once. My AI team makes me camera-ready and does the rest."),
(14,4,"#2","You don't need an AI avatar to replace you. You need one to replace the effort of being on camera."),
(15,4,"#2","Your business makes 50K/month. You shouldn't be spending an hour getting ready for a Reel."),
(16,4,"#2","I have 20 minutes to film. AI handles the hair, makeup and everything after."),
(17,5,"#2","Getting ready for Instagram is no longer on my CEO calendar."),
(18,5,"#2","I still film my content. I just outsourced looking camera-ready to AI."),
(19,5,"#2","The biggest content creation mistake business owners still make"),
(20,5,"#2","The AI skill every business owner needs in 2026"),
(21,5,"#2","This AI workflow creates 30 Reels in 5 minutes"),
(22,5,"#2","The #1 AI skill for business owners in 2026 isn't a tool"),
(23,5,"#2","This AI workflow makes 30 Reels in 5 minutes"),
(24,5,"#2","Still comfortable without AI? Not for much longer."),
(25,5,"#2","If you could learn only ONE AI tool this year, make it this"),
]

q = json.load(open("data/queue.json"))
jobs = q["jobs"] if isinstance(q, dict) and "jobs" in q else q
start = datetime.datetime.now().replace(microsecond=0)
new = []
missing = []
for n, length, audio, hook in plan:
    cap = cap_for(hook)
    if not cap:
        missing.append((n, hook)); continue
    sched = start + datetime.timedelta(minutes=(n-1))  # 1-min spacing markers
    new.append({
        "id": f"b1208_{n:02d}_{uuid.uuid4().hex[:8]}",
        "created_at": start.isoformat(),
        "scheduled_time": sched.strftime("%Y-%m-%dT%H:%M:%S"),
        "status": "staged",
        "video_url": f"{RAW}/reel{n:02d}.mp4",
        "caption": cap,
        "_hook": hook,
        "_audio": audio,
        "_len_sec": length,
        "_group": f"b1208_v{n:02d}",
        "_batch": "batch_12-08",
        "attempts": 0,
    })

if missing:
    print("MISSING CAPTIONS:", missing)
else:
    jobs.extend(new)
    json.dump(q, open("data/queue.json","w"), indent=2)
    print(f"staged {len(new)} jobs (status='staged', will not fire until flipped)")
    for j in new:
        print(f"  reel{j['id'][6:8]} aud{j['_audio']} {j['_len_sec']}s | {j['caption'][:45]}")
