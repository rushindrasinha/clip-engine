#!/usr/bin/env python3
"""QA one short: ffprobe checks, 6 frames and a contact sheet into <shorts dir>/qa/.

usage: qa_short.py shorts/NN_slug.mp4 [extra_t_seconds ...]
Exit code 1 if the file is not 1080x1920 with audio and under 50 MB. Looking at the frames is still on you.
"""
import json, os, subprocess, sys

f = sys.argv[1]
nn = os.path.basename(f).split("_")[0]
q = os.path.join(os.path.dirname(os.path.abspath(f)), "qa")
os.makedirs(q, exist_ok=True)
pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate",
                                "-of", "json", f], capture_output=True, text=True).stdout)
dur = float(pr["format"]["duration"])
size_mb = int(pr["format"]["size"]) / 1e6
v = next(s for s in pr["streams"] if s["codec_type"] == "video")
has_audio = any(s["codec_type"] == "audio" for s in pr["streams"])
ok = (v["width"], v["height"]) == (1080, 1920) and has_audio and size_mb < 50
print(json.dumps({"file": os.path.basename(f), "w": v["width"], "h": v["height"], "fps": v["r_frame_rate"], "codec": v["codec_name"],
                  "audio": has_audio, "duration_s": round(dur, 2), "size_mb": round(size_mb, 1), "ok": ok}))
ts = [0.5] + [dur * k / 6 for k in range(1, 5)] + [max(dur - 0.4, 0.5)] + [float(x) for x in sys.argv[2:]]
outs = []
for i, t in enumerate(ts):
    o = f"{q}/{nn}_{i}_{t:05.2f}.jpg"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", f, "-frames:v", "1", "-q:v", "3", o], check=True)
    outs.append(o)
args = sum((["-i", o] for o in outs), [])
n = len(outs)
fc = "".join(f"[{i}]scale=360:640[s{i}];" for i in range(n)) + "".join(f"[s{i}]" for i in range(n)) + f"hstack={n}"
subprocess.run(["ffmpeg", "-v", "error", "-y"] + args + ["-filter_complex", fc, f"{q}/{nn}_sheet.jpg"], check=True)
print(f"{q}/{nn}_sheet.jpg")
sys.exit(0 if ok else 1)
