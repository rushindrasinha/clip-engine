# The viral shorts recipe

What `make_short.py` does to a clip, in order. Every number is a config default you can override.

1. **Open on the hook.** Trim the clip so the first spoken word is the strongest line. Drop dangling fragments at both ends. Target 25 to 60 s, hard max 75 s.
2. **Jump cuts from word timestamps.** Silences longer than 0.35 s are removed (`gap_cut`), with 0.09 s of air kept at each cut (`pad`). Fillers (um, uh, erm) are removed only where it makes no visible glitch. Whisper stretches a word over a pause, so the renderer also runs a real audio silence detector (-38 dB) and cuts those too. Audio gets 12 ms crossfades at each cut so nothing clicks.
3. **Full-bleed vertical.** A 9:16 window is cut from the wide frame, about waist up (`base_crop_h` source pixels tall), with the face at 31% of frame height. The face is tracked every 0.25 s, smoothed, and the camera holds still until the speaker drifts more than 25 px. Light unsharp mask after the upscale.
4. **Punch-ins.** Zoom steps between 1.0 and 1.1 on cuts and on emphasis words, never more often than every 1.6 s, plus a slow 1.2% push so long takes still move.
5. **Word-by-word captions.** One to three words on screen, Impact-style, white with a thick black stroke and soft shadow, the spoken word in yellow. Numbers and `emph` words pop in green with a scale-in. Centered at 66% of frame height so the face stays clear. Names that must not split (`keep_together`) stay on one line.
6. **Hook title band.** Three to seven words at the top on a dark band with a yellow rule, `*word*` marks the highlighted word. Write a better one than the working title if you can.
7. **Audio.** High-pass 80 Hz, light denoise, two-pass loudnorm to -14 LUFS, true peak -1.5 dB. Speech stays natural.
8. **Credit line.** Optional small text in the lower corner for the first 3 s only (`credit`).
9. **End.** Hold on the last line. No outro card.

Why captions are images: many ffmpeg builds ship without drawtext or libass. Rendering each caption state with Pillow and compositing it frame by frame works everywhere and gives full control of the stroke, shadow and pop animation.
