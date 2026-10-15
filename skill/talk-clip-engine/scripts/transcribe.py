#!/usr/bin/env python3
"""Transcribe the project's source video with word-level timestamps, locally.

usage: transcribe.py PROJECT_DIR [--model NAME] [--language en] [--prompt "Names, Brands, Jargon"]
Writes PROJECT_DIR/transcript.json (segments[].words[] with start/end), transcript.md (timestamped, for reading)
and audio.wav. Uses mlx_whisper if installed (Apple Silicon), else the openai-whisper `whisper` CLI.
--prompt seeds the decoder with the proper nouns in the talk. This is what stops "Jai Hind" becoming "Jayhand".
Re-run only a slice with --start/--end (seconds) when one line is ambiguous: the slice is written to transcript_slice.json.
"""
import json, os, shutil, subprocess, sys, argparse

ap = argparse.ArgumentParser()
ap.add_argument("project")
ap.add_argument("--model", default=None)
ap.add_argument("--language", default="en")
ap.add_argument("--prompt", default="")
ap.add_argument("--start", type=float)
ap.add_argument("--end", type=float)
a = ap.parse_args()
W = os.path.abspath(a.project)
pj = json.load(open(os.path.join(W, "project.json")))
src = os.path.expanduser(pj["source"] if os.path.isabs(os.path.expanduser(pj["source"])) else os.path.join(W, pj["source"]))
slice_mode = a.start is not None
wav = os.path.join(W, "audio_slice.wav" if slice_mode else "audio.wav")
cmd = ["ffmpeg", "-v", "error", "-y"]
if slice_mode:
    cmd += ["-ss", str(a.start), "-t", str(a.end - a.start)]
subprocess.run(cmd + ["-i", src, "-vn", "-ac", "1", "-ar", "16000", wav], check=True)
outdir = os.path.join(W, ".work", "whisper_out")
os.makedirs(outdir, exist_ok=True)
base = os.path.splitext(os.path.basename(wav))[0]
if shutil.which("mlx_whisper"):
    c = ["mlx_whisper", wav, "--model", a.model or "mlx-community/whisper-large-v3-turbo", "--word-timestamps", "True",
         "--language", a.language, "--output-format", "json", "--output-dir", outdir]
    if a.prompt:
        c += ["--initial-prompt", a.prompt]
elif shutil.which("whisper"):
    c = ["whisper", wav, "--model", a.model or "large-v3", "--word_timestamps", "True", "--language", a.language,
         "--output_format", "json", "--output_dir", outdir]
    if a.prompt:
        c += ["--initial_prompt", a.prompt]
else:
    sys.exit("install mlx-whisper (pip install mlx-whisper) or openai-whisper (pip install openai-whisper)")
subprocess.run(c, check=True)
d = json.load(open(os.path.join(outdir, base + ".json")))
if slice_mode:
    for s in d["segments"]:
        s["start"] += a.start; s["end"] += a.start
        for w in s.get("words", []):
            w["start"] += a.start; w["end"] += a.start
    json.dump(d, open(os.path.join(W, "transcript_slice.json"), "w"))
    print("wrote transcript_slice.json: compare the ambiguous line, then fix it with `replace` in shorts.json")
    sys.exit(0)
json.dump(d, open(os.path.join(W, "transcript.json"), "w"))
mm = lambda t: f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"
open(os.path.join(W, "transcript.md"), "w").write(
    "\n".join(f"[{mm(s['start'])}] {s['text'].strip()}" for s in d["segments"]) + "\n")
print("wrote transcript.json, transcript.md")
