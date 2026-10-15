#!/usr/bin/env python3
"""Pull per-post analytics from Postiz for every published post in queue.json and append snapshots.jsonl.
Read-only on Postiz. Run it daily (cron / launchd / your agent's scheduler), then run learn_report.py.

usage: snapshot_postiz.py PROJECT_DIR --ig ID --yt ID [--tz-label IST] [--utc-offset 5.5]
Matches Postiz posts to queue rows by their scheduled UTC slot. Needs `postiz` logged in.
"""
import argparse, datetime, json, os, subprocess, sys

ap = argparse.ArgumentParser()
ap.add_argument("project")
ap.add_argument("--ig", required=True)
ap.add_argument("--yt", required=True)
ap.add_argument("--tz-label", default="UTC")
ap.add_argument("--utc-offset", type=float, default=0.0)
a = ap.parse_args()
W = os.path.abspath(a.project)
Q = {q["utc"][:16]: q for q in json.load(open(os.path.join(W, "queue.json")))}
tz = datetime.timezone(datetime.timedelta(hours=a.utc_offset))
now = datetime.datetime.now(tz)

def cli(*args):
    r = subprocess.run(["postiz", *args], capture_output=True, text=True, timeout=90)
    t = r.stdout
    i = min([x for x in (t.find("{"), t.find("[")) if x >= 0] or [-1])
    if i < 0:
        raise RuntimeError((r.stdout + r.stderr)[-300:])
    return json.loads(t[i:])

start = (min(datetime.datetime.fromisoformat(q["utc"].replace("Z", "+00:00")) for q in Q.values()) - datetime.timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")
end = (now + datetime.timedelta(days=1)).astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT00:00:00Z")
posts = [p for p in cli("posts:list", "--startDate", start, "--endDate", end)["posts"] if p["integration"]["id"] in (a.ig, a.yt)]
n = 0
with open(os.path.join(W, "snapshots.jsonl"), "a") as out:
    for p in posts:
        q = Q.get(p["publishDate"][:16])
        if not q or p["state"] != "PUBLISHED":
            continue
        try:
            an = cli("analytics:post", p["id"])
        except Exception as e:
            print("ERR", p["id"], str(e)[:120])
            continue
        stats = {x["label"].lower(): int(float(x["data"][-1]["total"])) for x in an if x.get("data")}
        pub = datetime.datetime.fromisoformat(p["publishDate"].replace("Z", "+00:00"))
        slot = pub.astimezone(tz)
        row = {"ts": now.strftime("%Y-%m-%d %H:%M ") + a.tz_label, "post_id": p["id"], "age_h": round((now - pub).total_seconds() / 3600, 1),
               "url": p.get("releaseURL"), "clip": q["code"], "hook": q["ig"].split("\n")[0], "platform": "instagram" if p["integration"]["id"] == a.ig else "youtube",
               "slot_local": slot.strftime("%Y-%m-%d %H:%M"), "slot_hour": slot.hour, **stats}
        out.write(json.dumps(row) + "\n")
        n += 1
print(f"{n} snapshots appended")
