"""Stage the 17-Sept batch as a 9-day drip: 2 trial reels/day (morning + evening),
all 18 files used, no clip repeated on the same day. Future-dated jobs — the cron
fires each one on its day. No manual dispatch needed."""
import json, shutil, datetime, uuid
from pathlib import Path

SRC = Path("/Volumes/KINGSTON/Claude/AGENTS/VIDEO-CREATION/video editor/Text on screen automation/batch 17 sep /output")
VID = Path("videos/batch_17-09")
RAW = "https://raw.githubusercontent.com/katerini007/publisher_automatic/main/videos/batch_17-09"

# ---- captions (cleaned families reused; AIEMP = Kat's new AI-agent-employee caption) ----
A = ("The #1 AI skill for business owners in 2026 isn't a tool 👇\n\nIt's knowing WHERE to use it.\n\n"
"Tools change every single day. Chasing every shiny new one is a waste of time.\n\n"
"Do this instead: look at where your team loses the most hours. Uploading and scheduling alone can eat ~3 hours a week. "
"An AI agent can do that part on autopilot.\n\nFind the problem first. Then pick the tool — not the other way around.\n\n"
"Comment AUTOMATION and I'll show you where to start.\n\n#aiforbusiness #contentautomation #smallbusinessowner #aitools #reels")
B = ("This AI workflow makes 30 Reels in 5 minutes 👇\n\nYou don't need 30 finished masterpieces — you need 30 tested versions.\n\n"
"I make one strong idea, then AI spins it into lots of hooks and cuts. Then I test them to find the one that flies.\n\n"
"That's how a brand new account can post every day without a big team.\n\n"
"Comment AUTOMATION and I'll show you the workflow.\n\n#aiautomation #reelsstrategy #contentcreation #aiforbusiness #reels")
C = ("If you could learn only ONE AI tool this year, make it this 👇\n\nClaude.\n\n"
"For a business owner it can write your content, sort your messy ideas, build little \"skills\" that do the same job again and again, "
"and take the boring tasks off your plate.\n\nYou don't need 20 tools. You need one you actually use well.\n\n"
"Comment AUTOMATION and I'll show you how I use it for my business.\n\n#claudeai #aiforbusiness #aitools #productivity #reels")
D = ("The smart ones don't use AI to write faster — they use it to build 👇\n\nOne tool, set up the right way, can:\n"
"• research what your audience wants\n• write the scripts\n• build simple agents that post and track results\n\n"
"It's like having a small content team that never sleeps.\n\nYou still bring the strategy and the personal touch — that's what makes it YOURS.\n\n"
"Comment AUTOMATION and I'll show you how.\n\n#claudeai #aiautomation #contentcreation #aiforbusiness #reels")
E = ("Still comfortable without AI? By 2027 that gets expensive 👇\n\n"
"Not because AI is magic, but because your competitors will post more, test faster, and learn quicker than you ever could by hand.\n\n"
"The winners won't have the biggest team. They'll have the best system.\n\nGood news: you can start small this year.\n\n"
"Comment AUTOMATION and I'll show you the first step.\n\n#aiforbusiness #futureofmarketing #contentsystem #businessgrowth #reels")
F = ("If you don't always have time to get ready for the perfect video…\n\n"
"If you're a USA-based founder making $30K+ a month, chances are you're always busy — "
"and maybe today you're not looking your best, but you still have to film again for your team.\n\n"
"Social media won't run without you.\n\nThere's a way to create content faster, with the same quality — and you should be using it. "
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
NVIEW = ("Connect Instagram to Claude and it can basically run your content department 👇\n\n"
"Here's how you can get REAL insights from Instagram without taking a single screenshot. "
"I tried it all — Apify, Zapier — and they work, but they don't always pull the right data. "
"What works best is the official way, and I found it: it's Meta.\n\n"
"One tool, set up the right way, can research what your audience wants, write the scripts, and build simple agents that post and track results.\n\n"
"Comment TUTORIAL and I'll show you how to connect.\n\n#claudeai #aiautomation #contentcreation #aiforbusiness #reels")
AIEMP = ("Have you been wondering if I actually built a real AI agent — not a chatbot you ask questions, but something that works for me?\n\n"
"Here's what most people still don't get: an AI agent isn't a tool you poke at. It's an employee you give a job to — and it goes and does it. On its own. While you sleep.\n\n"
"For social media, that quietly changes everything. Instead of you doing all of it, agents split the work — and each one gets scary good at its one thing.\n\n"
"I didn't hire a team. I built one:\n— one that edits my videos\n— one that writes\n— one that plans my captions (yes — this one 👀)\n— one that uploads them for me\n\n"
"So while you're reading this, my \"team\" is already working on the next one.\n\n"
"Want the breakdown of how each agent actually works? Comment AGENT ⬇️")

# clip -> (v1 filename, v1 caption), (v2 filename, v2 caption)
CLIPS = [
 ("73F68010-C843-43BE-8882-DD54AE5839DB - v1 126K-views.mp4", N126,
  "73F68010-C843-43BE-8882-DD54AE5839DB - v2 AI-employee.mp4", AIEMP),
 ("2026-09-06 11-58-27 - v1 avatar-effort.mp4", F,
  "2026-09-06 11-58-27 - v2 avatar-keeps-you-busy.mp4", F),
 ("E2E0EF12-3A6F-4CCC-9520-24E11B8D07DD - v1 camera-ready-hour.mp4", F,
  "E2E0EF12-3A6F-4CCC-9520-24E11B8D07DD - v2 CEO-calendar.mp4", F),
 ("IMG_0022 - v1 not-a-tool.mp4", A,
  "IMG_0022 - v2 one-AI-tool.mp4", C),
 ("IMG_9834 - v1 30-reels.mp4", B,
  "IMG_9834 - v2 smart-ones-build.mp4", D),
 ("IMG_9836 - v1 biggest-mistake.mp4", G,
  "IMG_9836 - v2 still-comfortable.mp4", E),
 ("IMG_9972 - v1 connect-IG-Claude.mp4", NVIEW,
  "IMG_9972 - v2 30-reels-howto.mp4", B),
 ("IMG_9973 - v1 biggest-mistake.mp4", G,
  "IMG_9973 - v2 one-AI-tool.mp4", C),
 ("video-output-72317469-FA95-4DA3-B759-8EC7357EBEAA - v1 still-comfortable.mp4", E,
  "video-output-72317469-FA95-4DA3-B759-8EC7357EBEAA - v2 AI-employee.mp4", AIEMP),
]

# 9-day schedule: morning day d = clip d v1; evening day d = clip (d+4 mod 9) v2.
# offset 4 guarantees morning clip != evening clip, and spreads each clip's two
# same-footage variants ~4-5 days apart.
START = datetime.date(2026, 9, 18)
MORNING = "09:24:00"   # proven winner slot (Madrid)
EVENING = "20:30:00"   # ~2:30pm US Eastern — good for the USA audience

VID.mkdir(parents=True, exist_ok=True)
q = json.load(open("data/queue.json"))
jobs = q["jobs"] if isinstance(q, dict) and "jobs" in q else q
now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
plan = []
n = 9
idx = 0
def mkjob(fname, cap, dt, tag):
    global idx; idx += 1
    src = SRC / fname
    assert src.exists(), f"MISSING {fname}"
    dest = VID / f"reel{idx:02d}.mp4"
    shutil.copy2(src, dest)
    return {
        "id": f"b1709_{idx:02d}_{uuid.uuid4().hex[:8]}",
        "created_at": now,
        "scheduled_time": dt,
        "status": "scheduled", "trial": True, "media_type": "REELS",
        "video_url": f"{RAW}/reel{idx:02d}.mp4",
        "caption": cap,
        "_hook": fname.split(" - ",1)[-1].replace(".mp4",""),
        "_slot": tag, "_batch": "batch_17-09", "attempts": 0,
    }

new = []
for d in range(n):
    day = START + datetime.timedelta(days=d)
    m_fname, m_cap = CLIPS[d][0], CLIPS[d][1]
    e_clip = (d + 4) % n
    e_fname, e_cap = CLIPS[e_clip][2], CLIPS[e_clip][3]
    jm = mkjob(m_fname, m_cap, f"{day.isoformat()}T{MORNING}", "morning")
    je = mkjob(e_fname, e_cap, f"{day.isoformat()}T{EVENING}", "evening")
    new += [jm, je]
    plan.append((day.isoformat(), m_fname.split(' - ')[-1].replace('.mp4',''), e_fname.split(' - ')[-1].replace('.mp4','')))

jobs.extend(new)
json.dump(q, open("data/queue.json","w"), indent=2, ensure_ascii=False)
print(f"staged {len(new)} jobs across {n} days (2/day, trial REELS)\n")
print("day        | morning                        | evening")
for day,m,e in plan:
    print(f"{day} | {m:30} | {e}")
