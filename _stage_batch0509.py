"""Stage the 5-Sept experiment: all 18 files (same-footage variants included, as a
deliberate duplicate-fingerprint test). Cleaned captions, greedy-interleaved so no
two clips from the same source are adjacent, past timestamps (all due), trial REELS."""
import json, shutil, datetime, uuid, re
from pathlib import Path

SRC = Path("/Volumes/KINGSTON/Claude/AGENTS/VIDEO-CREATION/video editor/Text on screen automation/output")
VID = Path("videos/batch_05-09")
RAW = "https://raw.githubusercontent.com/katerini007/publisher_automatic/main/videos/batch_05-09"

# ---- cleaned captions ----
A = ("The #1 AI skill for business owners in 2026 isn't a tool 👇\n\nIt's knowing WHERE to use it.\n\n"
"Tools change every single day. Chasing every shiny new one is a waste of time.\n\n"
"Do this instead: look at where your team loses the most hours. Uploading and scheduling alone can eat ~3 hours a week. "
"An AI agent can do that part on autopilot.\n\nFind the problem first. Then pick the tool — not the other way around.\n\n"
"AI is a tool, not a buzzword.\n\nComment AUTOMATION and I'll show you where to start.\n\n"
"#aiforbusiness #contentautomation #smallbusinessowner #aitools #reels")

B = ("This AI workflow makes 30 Reels in 5 minutes 👇\n\n"
"You don't need 30 finished masterpieces — you need 30 tested versions.\n\n"
"I make one strong idea, then AI spins it into lots of hooks and cuts. Then I test them to find the one that flies.\n\n"
"Recently one went to 20K views, and I'll be testing this hook with other videos to see if the hook is the winning element.\n\n"
"That's how a brand new account can post every day without a big team.\n\n"
"Comment AUTOMATION and I'll show you the workflow.\n\n#aiautomation #reelsstrategy #contentcreation #aiforbusiness #reels")

C = ("If you could learn only ONE AI tool this year, make it this 👇\n\nClaude.\n\n"
"For a business owner it can write your content, sort your messy ideas, build little \"skills\" that do the same job again and again, "
"and take the boring tasks off your plate.\n\nYou don't need 20 tools. You need one you actually use well.\n\n"
"Comment AUTOMATION and I'll show you how I use it for my business.\n\n#claudeai #aiforbusiness #aitools #productivity #reels")

D = ("Claude can basically run your content department now 👇\n\nOne tool, set up the right way, can:\n"
"• research what your audience wants\n• write the scripts\n• build simple agents that post and track results\n\n"
"It's like having a small content team that never sleeps.\n\n"
"You still bring the strategy and the personal touch — that's what makes it YOURS.\n\n"
"Comment AUTOMATION and I'll show you how.\n\n#claudeai #aiautomation #contentcreation #aiforbusiness #reels")

E = ("By 2027, businesses without an AI content system will struggle to keep up 👇\n\n"
"Not because AI is magic, but because your competitors will post more, test faster, and learn quicker than you ever could by hand.\n\n"
"The winners won't have the biggest team. They'll have the best system.\n\nGood news: you can start small this year.\n\n"
"Comment AUTOMATION and I'll show you the first step.\n\n#aiforbusiness #futureofmarketing #contentsystem #businessgrowth #reels")

F = ("If you don't always have time to get ready for the perfect video…\n\n"
"If you're a USA-based founder making $30K+ a month, chances are you're always busy — "
"and maybe today you're not looking your best, but you still have to film again for your team.\n\n"
"Social media won't run without you.\n\n"
"There's a way to create content faster, with the same quality — and you should be using it. "
"You can post 30 reels a day, testing what works, in about 10 minutes a day. I'm not even joking — that's exactly what this reel is right now.\n\n"
"Comment AUTOMATION and I'll tell you how.")

G = ("The biggest content mistake business owners still make 👇\n\nPosting one reel a week and hoping it grows.\n\nIt won't.\n\n"
"You grow 10x faster when you post more, test what works, and double down on your best patterns.\n\n"
"And even if you want to stay 100% authentic — AI can still do the ideas, the editing and the uploading, so you post more without burning out.\n\n"
"Comment AUTOMATION and I'll show you the system.\n\n#contentstrategy #aiforbusiness #reelsgrowth #smallbusiness #reels")

N126 = ("The easiest reel I've ever made just hit 126K views 👇\n\n"
"The talking heads are great, but what's growing this new account RIGHT NOW are my trial reels. "
"And the best part — I'm not even making them fully myself. One AI agent adds the text, another structures it, and the last one publishes. I just check.\n\n"
"That's the whole game now: keep it simple, test fast, double down on the winner.\n\n"
"Comment AUTOMATION and I'll show you the exact workflow.\n\n#aiforbusiness #contentstrategy #reels")

NVIEW = ("Claude can basically run your content department now 👇\n\n"
"Here's how you can get REAL insights from Instagram without taking a single screenshot. "
"I tried it all — Apify, Zapier — and they work, but they don't always pull the right data. "
"What works best is the official way, and I found it: it's Meta.\n\n"
"One tool, set up the right way, can:\n• research what your audience wants\n• write the scripts\n• build simple agents that post and track results\n\n"
"It's like having a small content team that never sleeps.\n\nYou still bring the strategy and the personal touch.\n\n"
"Comment TUTORIAL and I'll show you how to connect.\n\n#claudeai #aiautomation #contentcreation #aiforbusiness #reels")

# (source_key, filename, caption)
FILES = [
 ("S1","5 sep 1 - v1 comfortable.mp4", E),
 ("S1","5 sep 1 - v2 one-tool.mp4", C),
 ("S2","5 sep 2 - v1 smart-build.mp4", D),
 ("S2","5 sep 2 - v2 avatar-replace.mp4", F),
 ("S2","5 sep 2 - v3 30reels-6min.mp4", B),
 ("S2","5 sep 2 - v4 easiest-126k.mp4", N126),
 ("S3","5 sep 3 - v1 camera-ready.mp4", F),
 ("S3","5 sep 3 - v2 connect-claude.mp4", D),
 ("S4","5 sep 4 - v1 30reels-howto.mp4", B),
 ("S4","5 sep 4 - v2 connect-claude-view.mp4", NVIEW),
 ("S5","5 sep 5 - v1 biggest-mistake.mp4", G),
 ("S5","5 sep 5 - v2 30reels-makes.mp4", B),
 ("S6","5 sep 6 - v1 num1-skill.mp4", A),
 ("S6","5 sep 6 - v2 ceo-calendar.mp4", F),
 ("IMG","IMG_4326 - v1 30reels-makes.mp4", B),
 ("IMG","IMG_4326 - v2 ceo-calendar.mp4", F),
 ("CP","copy_74648235-C27D-4948-9B8A-FF03AD3A877F - v1 biggest-mistake.mp4", G),
 ("CP","copy_74648235-C27D-4948-9B8A-FF03AD3A877F - v2 num1-skill.mp4", A),
]

# greedy interleave: never place two clips of the same source back-to-back
from collections import defaultdict, deque
buckets = defaultdict(deque)
for item in FILES:
    buckets[item[0]].append(item)
order = []
last = None
remaining = sum(len(v) for v in buckets.values())
while remaining:
    # pick source with most remaining, not equal to last
    cands = [(len(v), k) for k, v in buckets.items() if v and k != last]
    if not cands:  # forced to repeat (only same source left)
        cands = [(len(v), k) for k, v in buckets.items() if v]
    cands.sort(reverse=True)
    k = cands[0][1]
    order.append(buckets[k].popleft())
    last = k
    remaining -= 1

# verify no same-source adjacency
adj = [order[i][0] for i in range(len(order))]
bad = [i for i in range(1, len(adj)) if adj[i] == adj[i-1]]
print("interleave order sources:", adj, "| same-source adjacencies:", len(bad))

# copy files + build jobs, past timestamps 46s apart (all due)
VID.mkdir(parents=True, exist_ok=True)
q = json.load(open("data/queue.json"))
jobs = q["jobs"] if isinstance(q, dict) and "jobs" in q else q
now = datetime.datetime.now()
base = now - datetime.timedelta(seconds=46 * len(order) + 60)
new = []
for i, (src, fname, cap) in enumerate(order):
    srcpath = SRC / fname
    if not srcpath.exists():
        print("MISSING FILE:", fname); continue
    dest = VID / f"reel{i+1:02d}.mp4"
    shutil.copy2(srcpath, dest)
    sched = (base + datetime.timedelta(seconds=46 * i)).strftime("%Y-%m-%dT%H:%M:%S")
    new.append({
        "id": f"b0509_{i+1:02d}_{uuid.uuid4().hex[:8]}",
        "created_at": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "scheduled_time": sched,
        "status": "scheduled",
        "trial": True, "media_type": "REELS",
        "video_url": f"{RAW}/reel{i+1:02d}.mp4",
        "caption": cap,
        "_hook": fname.split(" - ",1)[-1].replace(".mp4",""),
        "_source": src,
        "_batch": "batch_05-09",
        "attempts": 0,
    })
jobs.extend(new)
json.dump(q, open("data/queue.json","w"), indent=2, ensure_ascii=False)
print(f"staged {len(new)} jobs (trial REELS, all due, 46s apart, interleaved)")
