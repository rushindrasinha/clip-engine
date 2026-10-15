#!/usr/bin/env python3
"""Build a paced posting queue from approved shorts. Plans only. Never posts anything.

usage: queue_plan.py PROJECT_DIR --start "2026-10-20 09:00" [--tz Asia/Kolkata] [--every-hours 1] [--quiet 23-06]
Reads  PROJECT_DIR/approved.json   ["04","01",...]  the shorts the human said yes to, in the order to post
       PROJECT_DIR/copy.json       {"04": {"title": "...", "ig": "caption", "yt_desc": "...", "tags": ["a","b"]}, ...}
Writes PROJECT_DIR/queue.json      one row per short with a UTC slot, one slot per --every-hours, quiet hours skipped.
Refuses to run without approved.json. Approval is a human act, not a default.
"""
import argparse, datetime, glob, json, os, sys
from zoneinfo import ZoneInfo

ap = argparse.ArgumentParser()
ap.add_argument("project")
ap.add_argument("--start", required=True, help="local time of the first slot, YYYY-MM-DD HH:MM")
ap.add_argument("--tz", default="UTC")
ap.add_argument("--every-hours", type=float, default=1.0)
ap.add_argument("--quiet", default="", help="local hours to skip, e.g. 23-06 skips 23:00 to 06:59")
a = ap.parse_args()
if a.every_hours < 1:
    sys.exit("pacing floor is one post per hour per account; lower than that reads as spam")
W = os.path.abspath(a.project)
if not os.path.exists(os.path.join(W, "approved.json")):
    sys.exit("no approved.json. Nothing is scheduled until a human approves specific shorts.")
approved = json.load(open(os.path.join(W, "approved.json")))
copy = json.load(open(os.path.join(W, "copy.json")))
tz = ZoneInfo(a.tz)
t = datetime.datetime.strptime(a.start, "%Y-%m-%d %H:%M").replace(tzinfo=tz)
qa, qb = (int(x) for x in a.quiet.split("-")) if a.quiet else (None, None)

def quiet(dt):
    if qa is None:
        return False
    return (dt.hour >= qa or dt.hour < qb) if qa > qb else (qa <= dt.hour < qb)

rows = []
for nn in approved:
    nn = str(nn).zfill(2)
    while quiet(t):
        t += datetime.timedelta(hours=1)
    files = glob.glob(os.path.join(W, "shorts", f"{nn}_*.mp4"))
    if not files:
        sys.exit(f"approved short {nn} has no rendered file")
    c = copy[nn]
    rows.append({"n": len(rows) + 1, "code": nn, "file": files[0], "slot_local": t.strftime("%Y-%m-%d %H:%M"),
                 "utc": t.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                 "title": c["title"], "ig": c["ig"], "desc": c.get("yt_desc", c["title"]), "tags": c.get("tags", [])})
    t += datetime.timedelta(hours=a.every_hours)
json.dump(rows, open(os.path.join(W, "queue.json"), "w"), indent=1)
print(f"{len(rows)} shorts planned, {rows[0]['slot_local']} to {rows[-1]['slot_local']} ({a.tz}). Nothing has been posted.")
