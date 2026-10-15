# QA checklist (every short, no exceptions)

Run `scripts/qa_short.py shorts/NN_slug.mp4`, then open `shorts/qa/NN_sheet.jpg` and look.

**Automatic (exit code 1 if any fail)**
- 1080x1920, h264 video, audio present, file under 50 MB.
- Duration is what the dry run said, within a frame or two.

**By eye on the 6 frames (first, four evenly spaced, last)**
- The speaker's face is in frame, not cut off, in the upper third.
- Captions are legible and never cover the face.
- The title band is readable and has no typo.
- No frozen or black frame at a jump cut.
- Nothing from a forbidden range, no other person's footage, no on-screen text that should not be public (dashboards, names, numbers).

**By ear / by text**
- Names, numbers and brand names in the captions match what is actually said. Whisper gets Indian names, game titles and acronyms wrong. Listen to every proper noun.
- Hinglish or other-language lines: re-listen with a second Whisper pass on that slice only (`transcribe.py --start --end --model large-v3`), caption in the script the speaker's audience reads.

**Sync**
- `scripts/sync_check.py shorts/NN_slug.mp4` re-transcribes the finished short and compares caption times to heard times. Pass is median offset under 0.15 s and worst under 0.3 s. Look at the two crops it writes.

Anything that fails: fix config, re-render, re-check. Do not hand-patch an mp4.
