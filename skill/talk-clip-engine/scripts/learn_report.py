#!/usr/bin/env python3
"""Turn snapshots.jsonl into a leaderboard and a learnings stub. Read-only, no network.

usage: learn_report.py snapshots.jsonl [--out-dir DIR] [--tz-label IST]
Each snapshot line: {"ts","post_id","age_h","clip","hook","platform","slot_ist","duration_s","views","reach","likes","comments","shares","saves"}
(see references/learning-loop.md). Writes leaderboard.md and LEARNINGS_DRAFT.md with the comparisons worth looking at.
Confidence stays LOW until at least 15 posts per platform have a 24h reading.
"""
import argparse, collections, json, os, statistics, datetime
ap = argparse.ArgumentParser()
ap.add_argument("snapshots")
ap.add_argument("--out-dir", default=None)
ap.add_argument("--tz-label", default="UTC")
a = ap.parse_args()
out = a.out_dir or os.path.dirname(os.path.abspath(a.snapshots))
rows = [json.loads(l) for l in open(a.snapshots) if l.strip()]
latest = {}
for r in rows:
    if r["post_id"] not in latest or r["ts"] >= latest[r["post_id"]]["ts"]:
        latest[r["post_id"]] = r

slot = lambda r: r.get("slot_local") or r["slot_ist"]


def at24(pid):
    c = [r for r in rows if r["post_id"] == pid and r["age_h"] >= 20]
    return min(c, key=lambda r: abs(r["age_h"] - 24)) if c else None

stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M ") + a.tz_label
md = [f"# Leaderboard\nGenerated {stamp}. '24h views' is the snapshot closest to 24h age, blank until 20h old.\n"]
learn = [f"# Learnings draft ({stamp})\n"]
for plat in sorted({r["platform"] for r in latest.values()}):
    L = sorted([r for r in latest.values() if r["platform"] == plat], key=lambda r: -r.get("views", 0))
    md.append(f"\n## {plat} ({len(L)} posts)\n\n| # | clip | slot | dur | age h | views | 24h views | reach | likes | shares | saves | hook |\n|---|---|---|---|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(L, 1):
        s = at24(r["post_id"])
        md.append(f"| {i} | {r['clip']} | {slot(r)[5:]} | {r.get('duration_s')} | {r['age_h']} | {r.get('views', 0)} | {s.get('views') if s else ''} | "
                  f"{r.get('reach', '')} | {r.get('likes', 0)} | {r.get('shares', '')} | {r.get('saves', '')} | {r['hook'][:60]} |")
    with24 = [(r, at24(r["post_id"])) for r in L if at24(r["post_id"])]
    learn.append(f"\n## {plat}: {len(with24)} of {len(L)} posts have a 24h reading. Confidence: {'LOW' if len(with24) < 15 else 'usable'}.")
    if len(with24) >= 4:
        v = sorted(with24, key=lambda x: -x[1].get("views", 0))
        learn.append("Top by 24h views: " + "; ".join(f"{r['clip']} {s['views']}" for r, s in v[:3]))
        learn.append("Bottom: " + "; ".join(f"{r['clip']} {s['views']}" for r, s in v[-3:]))
        short = [s["views"] for r, s in with24 if (r.get("duration_s") or 99) < 35]
        long_ = [s["views"] for r, s in with24 if (r.get("duration_s") or 0) >= 35]
        if short and long_:
            learn.append(f"Median 24h views, under 35 s: {statistics.median(short):.0f} (n={len(short)}), 35 s and over: {statistics.median(long_):.0f} (n={len(long_)})")
        byhour = collections.defaultdict(list)
        for r, s in with24:
            byhour[int(slot(r)[11:13])].append(s["views"])
        hrs = [(h, x) for h, x in sorted(byhour.items()) if len(x) >= 3]
        learn.append("Median 24h views by slot hour (hours with 3+ posts only): " + (", ".join(f"{h:02d}h {statistics.median(x):.0f} (n={len(x)})" for h, x in hrs) or "not enough posts per hour yet, do not read anything into slot time"))
learn.append("\nTo fill in by hand: which hook patterns won, one hypothesis per pattern, one change to test in the next batch. Hypotheses stay hypotheses until n is large.")
os.makedirs(out, exist_ok=True)
open(os.path.join(out, "leaderboard.md"), "w").write("\n".join(md) + "\n")
open(os.path.join(out, "LEARNINGS_DRAFT.md"), "w").write("\n".join(learn) + "\n")
print("wrote", os.path.join(out, "leaderboard.md"), "and LEARNINGS_DRAFT.md")
