# Proof: the generalised renderer matches the original

`make_short.py` here was generalised from a one-off script that rendered 12 shorts from a single talk. To check nothing was lost, short 04 of that talk was rendered again with the config driven script and compared with the original render.

| | original render | config-driven render |
|---|---|---|
| video | h264 1080x1920 25 fps | h264 1080x1920 25 fps |
| audio | aac | aac |
| duration | 22.92 s | 22.92 s |
| size | 13.8 MB | 13.8 MB |

Frame comparison (PSNR in dB, higher is closer, at 6 timestamps): identical at 0.5 s, then 38.2, 38.0, 37.1, 37.7, 37.2. The frame at 0.5 s is pixel identical. The rest differ slightly because the face tracker was run again and the camera framing and encoder noise are not bit for bit the same. Captions and cuts are the same, see the two contact sheets: `04_original_sheet.jpg` and `04_new_sheet.jpg`.

`sync_check.py` on the new render: 29 caption words matched, median offset 0.02 s, worst 0.28 s, pass.

Files: `compare_04.json` (the numbers), `04_plan.json` (cut map and caption groups the renderer wrote), `project.jaihind.json` and `shorts.jaihind.json` (the config used, with the source path made relative).
