---
name: talk-clip-engine
description: Turn a long talk, podcast, interview or lecture into captioned vertical shorts (9:16 with jump cuts, face tracking, word-by-word captions, hook title band, clean audio), get them approved by a human, schedule them one an hour, and learn from the numbers after 24h. Use when asked to "cut this talk into shorts", "clip engine this", "turn this video into reels/shorts", "make shorts from my podcast/talk/interview". NOT a live-stream or VOD highlight clipper (that is a different skill); this one is for existing long-form talking footage you own.
---

# Talk Clip Engine

Long-form talking video in, approved vertical shorts out, then paced posting and a 24h learning loop.
Everything is config driven and local. The only network pieces are the optional Postiz scheduling step.

## Rules that never bend
1. **Never reorder words.** Cuts only remove silence, filler and dead air. Meaning must survive every cut.
2. **No third-party footage.** If the source plays someone else's video, list the time range under `forbidden` and the renderer refuses it.
3. **Hook in 2 seconds.** Every short opens on its strongest line, not a polite lead-in.
4. **Caption accuracy beats speed.** Whisper mishears names and numbers. Fix them in config before rendering, never after posting.
5. **One post an hour per account.** Faster reads as spam. Instagram as Trial Reels first, YouTube Shorts on the same cadence.
6. **Approval before anything posts.** Nothing is scheduled, queued or published until a human names the approved shorts. `queue_plan.py` refuses without `approved.json`.
7. **Never invent words.** Titles and captions quote the speaker. Sensitive claims get a flag, not a rewrite.

## The 10 steps
1. **Find raw material.** A talk, podcast, interview, long call you own. Check the licence and who appears in it.
2. **Transcribe locally** with word timestamps: `scripts/transcribe.py PROJECT --prompt "Name, Brand, Jargon"`.
3. **Mine the moments.** Read the transcript, write a content pack (`references/mining.md`): 20 to 60 s candidates, hook line, range, sensitivity flags, forbidden ranges, a list of misheard words.
4. **Set the project up** (`references/config.md`): `project.json` (source, brand, tracker, forbidden, word fixes) and `shorts.json` (one entry per short: in, out, title, emphasis words, line fixes).
5. **Render** `python3 scripts/make_short.py PROJECT NN` (add `--dry` first to read the cut plan and caption groups). Jump cuts, face-tracked crop, punch-ins, captions, title band, loudnorm.
6. **QA every short** (`references/qa-checklist.md`): `scripts/qa_short.py` gives ffprobe checks plus 6 frames and a contact sheet. Look at the frames. `scripts/sync_check.py` re-transcribes the output and checks caption timing. Re-render on any failure.
7. **Write the copy** in the speaker's voice (`references/copy-rules.md`): on-screen title, YouTube Shorts title, Instagram caption, tags. Put it in `copy.json`.
8. **Get approval.** Send the human the contact sheets and the copy. They name the approved shorts. Write `approved.json`.
9. **Schedule, paced.** `scripts/queue_plan.py` then `scripts/postiz_schedule.py` (dry run first, `--go` to create). One post an hour, quiet hours skipped (`references/posting-cadence.md`).
10. **Learn after 24h.** `scripts/snapshot_postiz.py` daily, then `scripts/learn_report.py` (`references/learning-loop.md`). Hypotheses stay hypotheses until the sample is real.

## Quick start
```bash
cp -r examples/project_template ~/clips/my_talk && cd ~/clips/my_talk
# edit project.json: source, brand, credit text, forbidden ranges, word_fix
python3 SKILL_DIR/scripts/transcribe.py . --prompt "Speaker Name, Event Name"
# read transcript.md, mine moments, fill shorts.json
python3 SKILL_DIR/scripts/make_short.py . 01 --dry
python3 SKILL_DIR/scripts/make_short.py . 01
python3 SKILL_DIR/scripts/qa_short.py shorts/01_*.mp4
python3 SKILL_DIR/scripts/sync_check.py shorts/01_*.mp4
```
Requirements: Python 3.9+, `ffmpeg` and `ffprobe`, `pip install numpy opencv-python pillow`, a Whisper (`pip install mlx-whisper` on Apple Silicon or `pip install openai-whisper`). The face tracker has three modes: `vision` (macOS, best), `opencv` (any OS), `static` (locked camera framing).
Scheduling is optional and needs the Postiz CLI (`npm i -g postiz`).

## When the agent runs this for someone
- Send nothing public. Deliver the shorts, contact sheets and copy to the human and ask which are approved.
- Report real numbers only, with a timestamp, and say which clips have a 24h reading.
- Flag, do not decide: named people, regulators, athlete or company numbers, anything dated ("this year"), IP or piracy angles, anything about family.
- Different tools: this is not a stream clipper (no highlight detection from chat or audio spikes) and not a graphic-overlay tool.
