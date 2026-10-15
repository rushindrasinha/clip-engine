#!/usr/bin/env python3
"""Caption sync check: re-transcribe the rendered short and compare caption word times to heard word times.
Prints the median offset and 2 spot checks, and writes crops of the caption area at those 2 spots to shorts/qa/.
usage: sync_check.py shorts/NN_slug.mp4        (needs shorts/qa/NN_plan.json written by make_short.py)
Pass: median offset under 0.15 s, worst spot under 0.3 s."""
import json, os, re, shutil, statistics, subprocess, sys, tempfile
f = os.path.abspath(sys.argv[1])
nn = os.path.basename(f).split("_")[0]
q = os.path.join(os.path.dirname(f), "qa")
plan = json.load(open(os.path.join(q, f"{nn}_plan.json")))
tmp = tempfile.mkdtemp()
wav = os.path.join(tmp, f"sync_{nn}.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f, "-ac", "1", "-ar", "16000", wav], check=True)
if shutil.which("mlx_whisper"):
    c = ["mlx_whisper", wav, "--model", "mlx-community/whisper-large-v3-turbo", "--word-timestamps", "True",
         "--language", "en", "--output-format", "json", "--output-dir", tmp]
else:
    c = ["whisper", wav, "--model", "base", "--word_timestamps", "True", "--language", "en", "--output_format", "json", "--output_dir", tmp]
subprocess.run(c, capture_output=True, check=True)
heard = [(re.sub(r"[^a-z0-9]", "", w["word"].lower()), w["start"])
         for s in json.load(open(os.path.join(tmp, f"sync_{nn}.json")))["segments"] for w in s["words"]]
caps = [(re.sub(r"[^a-z0-9]", "", t.lower()), s) for g in plan["captions"] for t, s in g["words"]]
deltas = []
for w, s in caps:
    if len(w) < 5:
        continue
    near = [h for h in heard if h[0] == w and abs(h[1] - s) < 1.5]
    if near:
        near.sort(key=lambda h: abs(h[1] - s))
        deltas.append((abs(near[0][1] - s), near[0][1] - s, w, s))
res = {"nn": nn, "matched": len(deltas), "median_offset_s": round(statistics.median(d[1] for d in deltas), 3) if deltas else None}
spots = []
if deltas:
    mid = sorted(deltas, key=lambda d: d[3])
    for d in (mid[len(mid) // 3], mid[2 * len(mid) // 3]):
        spots.append({"word": d[2], "caption_s": round(d[3], 2), "heard_s": round(d[3] + d[1], 2), "delta_s": round(d[1], 3)})
        o = os.path.join(q, f"{nn}_sync_{d[2]}_{d[3]:.2f}.jpg")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{d[3] + 0.06:.2f}", "-i", f, "-frames:v", "1",
                        "-vf", "crop=1080:330:0:1110,scale=540:165", o], check=True)
res["spots"] = spots
res["worst_abs_s"] = round(max(d[0] for d in deltas), 3) if deltas else None
res["pass"] = bool(deltas) and abs(res["median_offset_s"]) < 0.15 and res["worst_abs_s"] < 0.3
print(json.dumps(res))
shutil.rmtree(tmp, ignore_errors=True)
sys.exit(0 if res["pass"] else 1)
