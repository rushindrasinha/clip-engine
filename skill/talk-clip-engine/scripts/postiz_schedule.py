#!/usr/bin/env python3
"""Schedule a planned queue through the Postiz CLI (https://postiz.com): Instagram Trial Reels + YouTube Shorts.

usage: postiz_schedule.py PROJECT_DIR --ig INTEGRATION_ID --yt INTEGRATION_ID [--only 1-5] [--go]
Default is a dry run that prints the exact `postiz posts:create` commands. --go creates the scheduled posts.
Prerequisites: `npm i -g postiz`, `postiz auth:login` (or POSTIZ_API_KEY), integration ids from `postiz integrations:list`.
Run it only after a human approved the shorts and the queue (see queue_plan.py). Stops on the first failure.
"""
import argparse, html, json, os, subprocess, sys

ap = argparse.ArgumentParser()
ap.add_argument("project")
ap.add_argument("--ig", required=True)
ap.add_argument("--yt", required=True)
ap.add_argument("--only", default="")
ap.add_argument("--go", action="store_true")
a = ap.parse_args()
W = os.path.abspath(a.project)
Q = json.load(open(os.path.join(W, "queue.json")))
lo, hi = (int(x) for x in a.only.split("-")) if a.only else (0, 10 ** 9)
P = lambda t: "".join(f"<p>{html.escape(l, quote=False)}</p>" for l in t.split("\n") if l.strip())
log = os.path.join(W, "created.log")

def upload(path):
    r = subprocess.run(["postiz", "upload", path], capture_output=True, text=True, timeout=300)
    out = r.stdout + r.stderr
    i = out.find("{")
    try:
        j = json.loads(out[i:])
        return j.get("path") or j.get("url")
    except Exception:
        sys.exit("upload failed: " + out[-300:])

for q in Q:
    if not lo <= q["n"] <= hi:
        continue
    if "media" not in q and a.go:
        q["media"] = upload(q["file"])
        json.dump(Q, open(os.path.join(W, "queue.json"), "w"), indent=1)
    for which in ("ig", "yt"):
        if which == "ig":
            content, integ = P(q["ig"]), a.ig
            st = {"__type": "instagram-standalone", "post_type": "post", "is_trial_reel": True, "graduation_strategy": "MANUAL"}
        else:
            content, integ = P(q["desc"]), a.yt
            st = {"__type": "youtube", "title": q["title"], "type": "public", "selfDeclaredMadeForKids": "no",
                  "tags": [{"value": t, "label": t} for t in q["tags"]]}
        cmd = ["postiz", "posts:create", "-c", content, "-m", q.get("media", "<uploaded url>"), "-i", integ, "-s", q["utc"],
               "-t", "schedule", "--shortLink", "false", "--settings", json.dumps(st)]
        if not a.go:
            print("DRY RUN", q["n"], which, q["slot_local"], q["title"][:50])
            continue
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        ok = r.returncode == 0 and "rror" not in (r.stdout + r.stderr)[:400]
        open(log, "a").write(json.dumps({"n": q["n"], "which": which, "ok": ok, "out": (r.stdout + r.stderr)[-400:]}) + "\n")
        print(q["n"], which, "ok" if ok else "FAILED")
        if not ok:
            sys.exit("stopped on first failure; see created.log")
