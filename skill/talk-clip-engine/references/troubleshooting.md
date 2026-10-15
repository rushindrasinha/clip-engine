# What goes wrong, and the fix

- **Whisper mishears names and numbers** ("Jai Hind" as "Jayhand", "prize" as "price"). Seed `transcribe.py --prompt` with the proper nouns, list fixes in `word_fix`, re-listen to ambiguous slices with `--start/--end --model large-v3`.
- **ffmpeg has no drawtext or libass.** Not a problem: captions here are Pillow images composited frame by frame.
- **Face tracker locks onto a screen or poster behind the speaker.** Raise `tracker.face_min_y`, lower `face_max_w`, or use `static` with `static_x`.
- **Crop looks soft.** Raise `base_crop_h` (a wider crop means less upscaling). The unsharp pass already runs. A 1080p source is the practical floor.
- **Caption covers the face.** Move `framing.cap_y` down or raise `face_y`.
- **Captions drift after jump cuts.** Run `sync_check.py`. If the median offset is over 0.15 s, the Whisper word times for that clip are bad: re-run `transcribe.py` on that slice.
- **Audio pumps after loudnorm.** Raise `gap_cut` so fewer cuts land, or lower noise reduction in `build_audio`.
- **Scheduler subscription lapsed.** Renew before posting day. `postiz auth:status` first.
- **File too big for a platform.** The default CRF 19 with a 4.5 Mbit cap keeps 60 s shorts well under 50 MB.
