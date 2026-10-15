# Config reference

## project.json
```json
{
  "source": "talk.mp4",
  "transcript": "transcript.json",
  "credit": "Speaker Name · Event Name",
  "forbidden": [[112, 268], [1745, 1970]],
  "word_fix": {"price": "prize", "jayhand": "Jai Hind"},
  "keep_together": ["Jai Hind"],
  "preserve_case": [],
  "fps": 25,
  "gap_cut": 0.35,
  "pad": 0.09,
  "brand": {
    "caption_font": "/path/to/Impact.ttf",
    "title_font": "/path/to/Impact.ttf",
    "small_font": "/path/to/Arial Bold.ttf",
    "highlight": [255, 230, 0],
    "emphasis": [57, 255, 90],
    "band": [10, 10, 14, 200]
  },
  "framing": {"base_crop_h": 760, "face_y": 0.31, "cap_y": 0.665, "title_y": 0.15},
  "tracker": {"mode": "vision", "face_max_w": 0.052, "face_min_y": 0.25}
}
```
- `source`: path, absolute or relative to the project folder. Never modified.
- `forbidden`: `[start_s, end_s]` ranges of third-party footage. A short that overlaps one will not render.
- `word_fix`: whole-word replacements applied to captions only (case-insensitive key). Fix what Whisper misheard.
- `fps`: default is 25 for 25 or 50 fps sources, else 30.
- `framing.base_crop_h`: how many source pixels tall the crop is at zoom 1.0. Smaller means tighter on the face. A 1080p wide shot of a stage is about 760. A close-up interview is about 500.
- `tracker.mode`: `vision` (macOS Apple Vision, compiled on first use with swiftc), `opencv` (Haar cascade, any OS), `static` (set `static_x`, `static_y` in source pixels for a locked camera).
- `tracker.face_max_w`, `face_min_y`: ignore detections wider than this share of the frame or higher than this line (screens on the wall showing faces). Defaults are tuned for a small speaker in a wide hall (vision) and a large face (opencv).
- Fonts: if unset, the renderer looks for Impact or Arial Black, then DejaVu Sans Bold. Use a font you are licensed to use.

## shorts.json
```json
{
  "04": {
    "slug": "elephant",
    "in": 1149.0,
    "out": 1172.75,
    "title": "THEY MOCKED US FOR BEING *INDIAN*",
    "emph": ["elephant", "internet"],
    "replace": [[834.4, 838.1, "Corrected line as actually said", [834.44, 834.64]]],
    "drop": [1160.12],
    "drop_ranges": [[1163.0, 1164.2]],
    "face_dy": 0,
    "zoom_levels": [1.0, 1.1]
  }
}
```
- `in`, `out`: seconds in the source. The cut plan can only shorten this window.
- `title`: `*word*` renders in the highlight colour.
- `emph`: extra words that get the green pop (numbers and currency are automatic).
- `replace`: `[start, end, "text", [optional per-word start times]]` swaps every word that starts in the window for your text. Use it when a second Whisper pass or your own ears say the first pass was wrong. Never use it to change meaning.
- `drop`: word start times to remove. `drop_ranges`: ranges whose words are removed.
- `face_dy`: nudge the crop vertically in source pixels.

## copy.json (used by queue_plan.py)
```json
{"04": {"title": "YouTube title under 70 chars", "ig": "Instagram caption\nline two\n#tags", "yt_desc": "description #shorts", "tags": ["tag"]}}
```
## approved.json
`["04", "01"]`. The shorts a human approved, in posting order.
