#!/usr/bin/env python3
"""Make one vertical 9:16 short from a long talk, podcast or interview.

Jump cuts on word timestamps, full-bleed face-tracked crop with punch-ins, word-by-word
captions (Pillow, so it works on an ffmpeg without drawtext/libass), a hook title band,
loudnorm audio. Config driven: nothing about a specific talk lives in this file.

usage: make_short.py PROJECT_DIR NN [--dry] [--out-dir DIR]
  PROJECT_DIR holds project.json (source, brand, tracker) and shorts.json (the clip list).
  --dry prints the cut plan and caption groups only.
See references/config.md for every key.
"""
import json, os, re, subprocess, sys, shutil
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
SR = 48000
W, H = 1080, 1920

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Impact.ttf",
    "/Library/Fonts/Impact.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/Impact.ttf",
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/impact.ttf",
]
SMALL_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]

# Filled in by setup(): everything that used to be hardcoded for one talk.
SRC = WORK = TOOLS = OUT_DIR = CACHE_DIR = ""
SW, SH = 1920, 1080          # source size, probed
FPS = 25
SPF = SR // FPS
FORBIDDEN = []
FONT_CAP = FONT_TITLE = FONT_SMALL = ""
YELLOW = (255, 230, 0)
GREEN = (57, 255, 90)
BAND = (10, 10, 14, 200)
CREDIT = ""
GAP_CUT = 0.35      # remove silences longer than this
PAD = 0.09          # keep this much air around words at a cut
FILLERS = {"um", "uh", "umm", "uhh", "erm", "hmm"}
WORD_FIX = {}
PRESERVE_CASE = set()
KEEP_TOGETHER = []   # phrases that must not split across caption groups, e.g. ["Jai Hind"]
BASE_CROP_H = 760   # source px of height shown at zoom 1.0 (about head to knees)
FACE_Y = 0.31       # face centre at 31% of frame height (below title band, upper third)
CAP_Y = 0.665       # caption centre
TITLE_Y = 0.15      # title band centre
TRACK = {}


def first_existing(paths):
    for p in paths:
        if p and os.path.exists(p):
            return p
    sys.exit("no usable font found; set brand.caption_font / title_font / small_font in project.json")


def probe_source(src):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,r_frame_rate", "-of", "json", src], capture_output=True, text=True)
    st = json.loads(r.stdout)["streams"][0]
    n, d = st["r_frame_rate"].split("/")
    return int(st["width"]), int(st["height"]), float(n) / float(d)


def setup(project_dir, out_dir=None):
    """load project.json and set the module globals"""
    global SRC, WORK, TOOLS, OUT_DIR, CACHE_DIR, SW, SH, FPS, SPF, FORBIDDEN, FONT_CAP, FONT_TITLE, FONT_SMALL
    global YELLOW, GREEN, BAND, CREDIT, GAP_CUT, PAD, WORD_FIX, PRESERVE_CASE, KEEP_TOGETHER
    global BASE_CROP_H, FACE_Y, CAP_Y, TITLE_Y, TRACK, FILLERS
    WORK = os.path.abspath(project_dir)
    pj = json.load(open(os.path.join(WORK, "project.json")))
    SRC = pj["source"] if os.path.isabs(pj["source"]) else os.path.join(WORK, pj["source"])
    SRC = os.path.expanduser(SRC)
    if not os.path.exists(SRC):
        sys.exit(f"source video not found: {SRC}")
    OUT_DIR = out_dir or os.path.join(WORK, "shorts")
    os.makedirs(os.path.join(OUT_DIR, "qa"), exist_ok=True)
    TOOLS = os.path.join(WORK, ".work")
    CACHE_DIR = os.path.join(TOOLS, "track_cache")
    os.makedirs(CACHE_DIR, exist_ok=True)
    SW, SH, sfps = probe_source(SRC)
    FPS = int(pj.get("fps") or (25 if abs(sfps / 25 - round(sfps / 25)) < 0.03 else 30))   # 25/50 fps sources -> 25, everything else -> 30
    SPF = SR // FPS
    FORBIDDEN = [tuple(x) for x in pj.get("forbidden", [])]
    br = pj.get("brand", {})
    FONT_CAP = os.path.expanduser(br.get("caption_font") or first_existing(FONT_CANDIDATES))
    FONT_TITLE = os.path.expanduser(br.get("title_font") or FONT_CAP)
    FONT_SMALL = os.path.expanduser(br.get("small_font") or first_existing(SMALL_CANDIDATES))
    YELLOW = tuple(br.get("highlight", YELLOW))
    GREEN = tuple(br.get("emphasis", GREEN))
    BAND = tuple(br.get("band", BAND))
    CREDIT = pj.get("credit", "")
    GAP_CUT = pj.get("gap_cut", GAP_CUT)
    PAD = pj.get("pad", PAD)
    FILLERS = set(pj.get("fillers", FILLERS))
    WORD_FIX = {k.lower(): v for k, v in pj.get("word_fix", {}).items()}
    PRESERVE_CASE = set(pj.get("preserve_case", [])) | {v for v in WORD_FIX.values() if v != v.upper() and v != v.lower() and " " not in v and v[1:] != v[1:].lower()}
    KEEP_TOGETHER = [p.upper().split() for p in pj.get("keep_together", [])]
    fr = pj.get("framing", {})
    BASE_CROP_H = fr.get("base_crop_h", BASE_CROP_H)
    FACE_Y = fr.get("face_y", FACE_Y)
    CAP_Y = fr.get("cap_y", CAP_Y)
    TITLE_Y = fr.get("title_y", TITLE_Y)
    TRACK = pj.get("tracker", {"mode": "static"})
    TRACK["transcript"] = os.path.join(WORK, pj.get("transcript", "transcript.json"))
    return pj


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, **kw)
    if r.returncode:
        sys.exit((r.stderr or b"")[-3000:].decode(errors="replace"))
    return r


# ---------------------------------------------------------------- words + cut plan

def load_words(a, b):
    d = json.load(open(TRACK["transcript"]))
    out = []
    for seg in d["segments"]:
        for w in seg.get("words", []):
            if w["start"] >= a - 0.05 and w["start"] < b:
                t = w["word"].strip()
                if not t:
                    continue
                # whisper splits "2005-2006", "10,000" into pieces; glue them back
                if out and (t[:1] == "-" or re.match(r",\d", t)):
                    out[-1]["w"] += t
                    out[-1]["e"] = w["end"]
                    continue
                out.append({"w": t, "s": max(w["start"], a), "e": min(w["end"], b)})
    return out


def apply_fixes(words, cfg):
    # LINE fixes: replace every word starting inside [s, e) with the given words, timed evenly
    for rep in cfg.get("replace", []):
        s, e, text = rep[:3]
        times = rep[3] if len(rep) > 3 else None  # optional per-word start times (from a second-pass listen)
        idx = [i for i, w in enumerate(words) if s <= w["s"] < e]
        if not idx:
            continue
        ws, we = words[idx[0]]["s"], words[idx[-1]]["e"]
        new = text.split()
        step = (we - ws) / len(new)
        if times:
            ends = times[1:] + [we]
            repl = [{"w": t, "s": times[k], "e": ends[k], "fixed": True} for k, t in enumerate(new)]
        else:
            repl = [{"w": t, "s": ws + k * step, "e": ws + (k + 1) * step, "fixed": True} for k, t in enumerate(new)]
        words = words[:idx[0]] + repl + words[idx[-1] + 1:]
    for w in words:
        if w.get("fixed"):
            continue
        core = re.sub(r"[^\w'-]", "", w["w"]).lower()
        if core in WORD_FIX:
            w["w"] = re.sub(re.escape(re.sub(r"[^\w'-]", "", w["w"])), WORD_FIX[core], w["w"], flags=re.I)
    return words


def plan(words, cfg, a, b):
    drop = {round(x, 2) for x in cfg.get("drop", [])}
    dr = cfg.get("drop_ranges", [])
    keep = [w for w in words
            if re.sub(r"[^\w]", "", w["w"]).lower() not in FILLERS and round(w["s"], 2) not in drop
            and not any(x <= w["s"] < y for x, y in dr)]
    segs = []
    for w in keep:
        s, e = max(w["s"] - PAD, a), min(w["e"] + PAD, b)
        if segs and w["s"] - segs[-1]["last_e"] <= GAP_CUT:
            segs[-1]["e"] = max(segs[-1]["e"], e)
        else:
            if segs:  # don't let padding overlap the previous segment
                s = max(s, segs[-1]["e"])
            segs.append({"s": s, "e": e})
        segs[-1]["last_e"] = w["e"]
    # whisper often stretches a word over a pause, so also cut real (audio-level) silences > GAP_CUT
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-ss", f"{a}", "-i", SRC, "-t", f"{b - a}", "-vn",
                        "-af", f"highpass=f=80,silencedetect=n=-38dB:d={GAP_CUT}", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    st = [a + float(x) for x in re.findall(r"silence_start: ([-\d.]+)", r)]
    en = [a + float(x) for x in re.findall(r"silence_end: ([-\d.]+)", r)]
    for s0, s1 in zip(st, en):
        c0, c1 = s0 + PAD, s1 - PAD
        if c1 - c0 < 0.15:
            continue
        nxt = []
        for sg in segs:
            if sg["e"] <= c0 or sg["s"] >= c1:
                nxt.append(sg)
                continue
            if sg["s"] < c0:
                nxt.append({"s": sg["s"], "e": c0, "last_e": c0})
            if sg["e"] > c1:
                nxt.append({"s": c1, "e": sg["e"], "last_e": sg["last_e"]})
        segs = nxt
    # snap to the frame grid (relative to a)
    out, k = [], 0
    for sg in segs:
        k0 = int(np.floor((sg["s"] - a) * FPS))
        k1 = int(np.ceil((sg["e"] - a) * FPS))
        k0 = max(k0, out[-1]["k1"] if out else 0)
        if k1 > k0:
            out.append({"k0": k0, "k1": k1, "o0": k})
            k += k1 - k0
    return keep, out, k


def src_to_out(t, segs, a):
    """map a source time to output time; None if it falls in a cut gap"""
    f = (t - a) * FPS
    for sg in segs:
        if sg["k0"] <= f < sg["k1"]:
            return (sg["o0"] + f - sg["k0"]) / FPS
    return None


def snap_out(t, segs, a, after=True):
    o = src_to_out(t, segs, a)
    if o is not None:
        return o
    f = (t - a) * FPS
    for sg in segs:  # first kept frame after t (or last before)
        if after and sg["k0"] >= f:
            return sg["o0"] / FPS
    for sg in reversed(segs):
        if sg["k1"] <= f:
            return (sg["o0"] + sg["k1"] - sg["k0"]) / FPS
    return 0.0


# ---------------------------------------------------------------- captions

def cap_text(t):
    t = re.sub(r"[,.;:\"“”]", "", t)
    t = t.replace("…", "")
    return " ".join(x if x in PRESERVE_CASE else x.upper() for x in t.split(" "))


def is_emph(word, cfg):
    core = re.sub(r"[^\w$%]", "", word).upper()
    if re.search(r"\d", core) or "$" in core:
        return True
    return core in {k.upper() for k in cfg.get("emph", [])}


def groups(keep, segs, a, cfg, total):
    items = []
    for w in keep:
        s = snap_out(w["s"], segs, a, True)
        e = snap_out(w["e"], segs, a, False)
        txt = cap_text(w["w"])
        if not txt.strip():
            continue
        items.append({"t": txt, "s": s, "e": max(e, s + 0.08), "raw": w["w"], "emph": is_emph(w["w"], cfg)})
    # keep names that must not split across caption groups together as one item
    merged, i = [], 0
    while i < len(items):
        hit = None
        for ph in KEEP_TOGETHER:
            n = len(ph)
            if [re.sub(r"[^\w$%']", "", x["t"]) for x in items[i:i + n]] == [re.sub(r"[^\w$%']", "", x) for x in ph]:
                hit = n
                break
        if hit:
            chunk = items[i:i + hit]
            merged.append(dict(chunk[0], t=" ".join(x["t"] for x in chunk), e=chunk[-1]["e"], raw=chunk[-1]["raw"],
                               emph=any(x["emph"] for x in chunk)))
            i += hit
        else:
            merged.append(items[i])
            i += 1
    items = merged
    gs, cur = [], []
    for i, it in enumerate(items):
        nxt = items[i + 1] if i + 1 < len(items) else None
        # keep "$25 MILLION", "13 CRORES" etc. together
        glue = nxt and it["emph"] and re.fullmatch(r"(MILLION|BILLION|CRORES?|LAKHS?|THOUSAND|HUNDRED|DOLLARS|K|YEARS?|HOURS)", nxt["t"])
        cur.append(it)
        chars = sum(len(x["t"]) + 1 for x in cur)
        nchars = chars + (len(nxt["t"]) if nxt else 0)
        brk = (nxt is None or re.search(r"[.?!,]$", it["raw"]) or nxt["s"] - it["e"] > 0.3
               or len(cur) >= 3 or nchars > 15 or (it["emph"] and not (nxt and nxt["emph"] and len(cur) < 2)))
        if glue:
            brk = False
        if brk:
            gs.append(cur)
            cur = []
    if cur:
        gs.append(cur)
    out = []
    for i, g in enumerate(gs):
        s = g[0]["s"]
        nxt = gs[i + 1][0]["s"] if i + 1 < len(gs) else total
        e = min(max(g[-1]["e"] + 0.25, s + 0.4), nxt, total)
        out.append({"words": g, "s": s, "e": e})
    return out


_font_cache = {}


def font(path, size):
    k = (path, size)
    if k not in _font_cache:
        _font_cache[k] = ImageFont.truetype(path, size)
    return _font_cache[k]


def render_group(g, active, scale):
    """RGBA caption image for a group with word `active` highlighted"""
    size = int(108 * scale)
    words = [w["t"] for w in g["words"]]
    f = font(FONT_CAP, size)
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    space = tmp.textlength(" ", font=f)
    widths = [tmp.textlength(t, font=f) for t in words]
    while sum(widths) + space * (len(words) - 1) > W - 110 and size > 60:
        size -= 4
        f = font(FONT_CAP, size)
        space = tmp.textlength(" ", font=f)
        widths = [tmp.textlength(t, font=f) for t in words]
    total = sum(widths) + space * (len(words) - 1)
    ch = int(size * 1.5)
    img = Image.new("RGBA", (W, ch + 40), (0, 0, 0, 0))
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d, ds = ImageDraw.Draw(img), ImageDraw.Draw(sh)
    x = (W - total) / 2
    y = 20 + (ch - size * 1.18) / 2
    sw = max(6, size // 11)
    for i, t in enumerate(words):
        if i == active:
            col = GREEN if g["words"][i]["emph"] else YELLOW
        else:
            col = (255, 255, 255)
        ds.text((x + 4, y + 9), t, font=f, fill=(0, 0, 0, 190), stroke_width=sw, stroke_fill=(0, 0, 0, 190))
        d.text((x, y), t, font=f, fill=col, stroke_width=sw, stroke_fill="black")
        x += widths[i] + space
    sh = sh.filter(ImageFilter.GaussianBlur(7))
    return Image.alpha_composite(sh, img)


def render_title(title):
    """title band: full-width dark band, white Impact text, *word* in yellow"""
    toks = title.split()
    size = 92
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))

    def lay(size):
        f = font(FONT_TITLE, size)
        sp = tmp.textlength(" ", font=f)
        lines, cur, cw = [], [], 0
        for t in toks:
            tw = tmp.textlength(t.strip("*"), font=f)
            if cur and cw + sp + tw > W - 120:
                lines.append(cur)
                cur, cw = [], 0
            cur.append((t, tw))
            cw += (sp if cw else 0) + tw
        lines.append(cur)
        return f, sp, lines

    f, sp, lines = lay(size)
    while len(lines) > 2 and size > 60:
        size -= 4
        f, sp, lines = lay(size)
    lh = int(size * 1.12)
    bh = lh * len(lines) + 46
    img = Image.new("RGBA", (W, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, bh], fill=(10, 10, 14, 200))
    d.rectangle([0, bh - 8, W, bh], fill=YELLOW + (255,))
    y = 18
    hi = False
    for ln in lines:
        lw = sum(tw for _, tw in ln) + sp * (len(ln) - 1)
        x = (W - lw) / 2
        for t, tw in ln:
            if t.startswith("*"):
                hi = True
            col = YELLOW if hi else (255, 255, 255)
            if t.endswith("*"):
                hi = False
            d.text((x, y), t.strip("*"), font=f, fill=col, stroke_width=3, stroke_fill="black")
            x += tw + sp
        y += lh
    return img


def render_credit():
    if not CREDIT:
        return None
    img = Image.new("RGBA", (W, 90), (0, 0, 0, 0))
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    f = font(FONT_SMALL, 34)
    t = CREDIT
    ImageDraw.Draw(sh).text((52, 32), t, font=f, fill=(0, 0, 0, 220))
    sh = sh.filter(ImageFilter.GaussianBlur(4))
    ImageDraw.Draw(sh).text((50, 30), t, font=f, fill=(255, 255, 255, 235))
    return sh


def to_bgra(img):
    a = np.array(img)  # RGBA
    return a[:, :, [2, 1, 0]].astype(np.float32), a[:, :, 3:4].astype(np.float32) / 255.0


def blend(frame, ov, x, y):
    rgb, al = ov
    h, w = al.shape[:2]
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + w, W), min(y + h, H)
    if x1 <= x0 or y1 <= y0:
        return
    sub = frame[y0:y1, x0:x1].astype(np.float32)
    r = rgb[y0 - y:y1 - y, x0 - x:x1 - x]
    a = al[y0 - y:y1 - y, x0 - x:x1 - x]
    frame[y0:y1, x0:x1] = (sub * (1 - a) + r * a).astype(np.uint8)


# ---------------------------------------------------------------- tracking

def detect_boxes(files, mode):
    """per-image {"faces": [[x,y,w,h,conf]...], "humans": [...]} in normalised coords, origin top-left"""
    if mode == "vision":
        exe = os.path.join(TOOLS, "detect_people")
        if not os.path.exists(exe):
            if shutil.which("swiftc") is None:
                sys.exit("tracker mode 'vision' needs macOS swiftc; use mode 'opencv' or 'static'")
            run(["swiftc", "-O", os.path.join(HERE, "detect_people.swift"), "-o", exe])
        det = []
        for i in range(0, len(files), 100):
            r = run([exe] + files[i:i + 100], text=True)
            det += [json.loads(l) for l in r.stdout.splitlines() if l.strip()]
        return det
    cc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    det = []
    for f in files:
        g = cv2.cvtColor(cv2.imread(f), cv2.COLOR_BGR2GRAY)
        hh, ww = g.shape
        bx = cc.detectMultiScale(g, 1.1, 5, minSize=(ww // 40, ww // 40))
        det.append({"faces": [[x / ww, y / hh, w / ww, h / hh, float(w * h) / (ww * hh)] for x, y, w, h in bx], "humans": []})
    return det


def track(a, b, nn):
    """face centre (x, y) in source px every 0.25 s. mode vision (macOS Apple Vision), opencv (Haar), static"""
    mode = TRACK.get("mode", "static")
    if mode == "static":
        n = int((b - a) * 4)
        return [[a + (i + 0.5) / 4, TRACK.get("static_x", SW / 2), TRACK.get("static_y", SH * 0.43)] for i in range(n)]
    cache = os.path.join(CACHE_DIR, f"{nn}_{a:.2f}_{b:.2f}_{mode}.json")
    if os.path.exists(cache):
        return json.load(open(cache))
    d = os.path.join(TOOLS, "track_frames", nn)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, exist_ok=True)
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{a}", "-i", SRC, "-t", f"{b - a}",
         "-vf", "fps=4,scale=960:-2", "-q:v", "3", os.path.join(d, "f_%05d.jpg")])
    files = [os.path.join(d, f) for f in sorted(os.listdir(d))]
    det = detect_boxes(files, mode)
    fmax = TRACK.get("face_max_w", 0.052 if mode == "vision" else 0.5)   # face width as a fraction of frame
    fmin_y = TRACK.get("face_min_y", 0.25 if mode == "vision" else 0.0)  # ignore faces above this (e.g. screens on the wall)
    pts = []
    prev = None
    for i, r in enumerate(det):
        t = a + (i + 0.5) / 4
        faces = [f for f in r.get("faces", []) if f[2] < fmax and f[1] > fmin_y]
        humans = [h for h in r.get("humans", []) if h[1] + h[3] > 0.88 and h[2] < 0.25]
        p = None
        if faces:
            if prev:
                faces.sort(key=lambda f: abs(f[0] + f[2] / 2 - prev[0] / SW))
            else:
                faces.sort(key=lambda f: -f[4])
            f = faces[0]
            p = [(f[0] + f[2] / 2) * SW, (f[1] + f[3] / 2) * SH]
        elif humans:
            if prev:
                humans.sort(key=lambda h: abs(h[0] + h[2] / 2 - prev[0] / SW))
            h = humans[0]
            p = [(h[0] + h[2] / 2) * SW, (h[1] + 0.068) * SH]
        pts.append([t] + (p if p else [None, None]))
        if p:
            prev = p
    json.dump(pts, open(cache, "w"))
    return pts


def smooth_track(pts, ts):
    t = np.array([p[0] for p in pts if p[1] is not None])
    x = np.array([p[1] for p in pts if p[1] is not None])
    y = np.array([p[2] for p in pts if p[1] is not None])
    if len(t) == 0:
        return np.full(len(ts), SW / 2), np.full(len(ts), SH * 0.43)
    # median filter to kill single bad detections
    def med(v, k=5):
        pad = np.pad(v, k // 2, mode="edge")
        return np.array([np.median(pad[i:i + k]) for i in range(len(v))])
    x, y = med(x), med(y, 9)
    xs, ys = np.interp(ts, t, x), np.interp(ts, t, y)
    # gaussian smoothing in source time (sigma 0.7 s for x, 2 s for y)
    def gs(v, sig):
        k = int(sig * FPS * 3)
        g = np.exp(-0.5 * (np.arange(-k, k + 1) / (sig * FPS)) ** 2)
        g /= g.sum()
        return np.convolve(np.pad(v, k, mode="edge"), g, mode="valid")
    dense_t = np.arange(ts.min() - 3, ts.max() + 3, 1 / FPS)
    dx, dy = gs(np.interp(dense_t, t, x), 0.7), gs(np.interp(dense_t, t, y), 2.0)
    xs, ys = np.interp(ts, dense_t, dx), np.interp(ts, dense_t, dy)
    # dead zone: hold the camera until he drifts > 25 px, then follow
    cam = xs.copy()
    for i in range(1, len(cam)):
        dlt = xs[i] - cam[i - 1]
        cam[i] = cam[i - 1] + (dlt - np.sign(dlt) * 25 if abs(dlt) > 25 else 0)
    return cam, ys


# ---------------------------------------------------------------- audio

def build_audio(a, b, segs, path):
    raw = run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{a}", "-i", SRC, "-t", f"{b - a + 1}",
               "-vn", "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"]).stdout
    au = np.frombuffer(raw, np.float32).reshape(-1, 2)
    fade = int(0.012 * SR)
    ramp = np.linspace(0, 1, fade, dtype=np.float32)[:, None]
    parts = []
    for sg in segs:
        p = au[sg["k0"] * SPF:sg["k1"] * SPF].copy()
        need = (sg["k1"] - sg["k0"]) * SPF
        if len(p) < need:
            p = np.vstack([p, np.zeros((need - len(p), 2), np.float32)])
        p[:fade] *= ramp
        p[-fade:] *= ramp[::-1]
        parts.append(p)
    cut = np.vstack(parts)
    tmp = path + ".raw.wav"
    import wave
    with wave.open(tmp, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes((np.clip(cut, -1, 1) * 32767).astype("<i2").tobytes())
    pre = "highpass=f=80,afftdn=nr=10:nf=-30"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", tmp, "-af", pre + ",loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True)
    m = json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])
    ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    run(["ffmpeg", "-hide_banner", "-y", "-i", tmp, "-af", pre + "," + ln + ",aresample=48000",
         "-ar", str(SR), "-c:a", "pcm_s16le", path])
    os.remove(tmp)
    return len(cut) / SR


# ---------------------------------------------------------------- main

def main():
    args = [x for x in sys.argv[1:]]
    out_dir = None
    if "--out-dir" in args:
        i = args.index("--out-dir")
        out_dir = args[i + 1]
        del args[i:i + 2]
    dry = "--dry" in args
    args = [x for x in args if x != "--dry"]
    if len(args) < 2:
        sys.exit(__doc__)
    setup(args[0], out_dir)
    nn = args[1].zfill(2)
    cfg = json.load(open(os.path.join(WORK, "shorts.json")))[nn]
    a, b = float(cfg["in"]), float(cfg["out"])
    for fa, fb in FORBIDDEN:
        if a < fb and b > fa:
            sys.exit(f"range {a}-{b} overlaps third-party footage {fa}-{fb}")

    words = apply_fixes(load_words(a, b), cfg)
    keep, segs, nframes = plan(words, cfg, a, b)
    total = nframes / FPS
    gs = groups(keep, segs, a, cfg, total)
    if dry:
        print(f"clip {nn}: {a}-{b} raw {b - a:.1f}s -> {total:.1f}s, {len(segs)} segments")
        for g in gs:
            print(f"  {g['s']:6.2f}-{g['e']:6.2f}  " + " ".join(("*" + w["t"] if w["emph"] else w["t"]) for w in g["words"]))
        return

    slug = cfg["slug"]
    out = os.path.join(OUT_DIR, f"{nn}_{slug}.mp4")
    tmpd = os.path.join(TOOLS, "render", nn)
    os.makedirs(tmpd, exist_ok=True)
    wav = os.path.join(tmpd, "audio.wav")
    adur = build_audio(a, b, segs, wav)

    # per-output-frame source frame index, crop position and zoom
    src_k = np.concatenate([np.arange(sg["k0"], sg["k1"]) for sg in segs])
    src_t = a + src_k / FPS
    cam_x, cam_y = smooth_track(track(a, b, nn), src_t)
    cam_y = np.full_like(cam_y, np.median(cam_y))  # vertical held steady per clip
    cam_y += cfg.get("face_dy", 0)
    zoom = np.ones(nframes)
    levels = cfg.get("zoom_levels", [1.0, 1.1])
    li, last = 0, 0.0
    cut_frames = [sg["o0"] for sg in segs[1:]]
    emph_frames = sorted({int(round(w["s"] * FPS)) for g in gs for w in g["words"] if w["emph"]})
    events = sorted(set(cut_frames) | set(emph_frames))
    cur = levels[0]
    for f in range(nframes):
        if f in events and (f / FPS - last) >= 1.6:
            if f in emph_frames:
                cur = max(levels) + 0.04
            else:
                li = (li + 1) % len(levels)
                cur = levels[li]
            last = f / FPS
        zoom[f] = cur
    # gentle continuous push on top so long takes still feel alive
    zoom *= 1.0 + 0.012 * ((np.arange(nframes) / FPS) % 6.0) / 6.0

    # overlays
    title = to_bgra(render_title(cfg["title"]))
    _cr = render_credit()
    credit = to_bgra(_cr) if _cr is not None else None
    title_y = int(H * TITLE_Y - title[1].shape[0] / 2)
    cache = {}

    venc = subprocess.Popen(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-i", wav, "-map", "0:v", "-map", "1:a",
         "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-maxrate", "4500k", "-bufsize", "9000k",
         "-pix_fmt", "yuv420p", "-profile:v", "high", "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", "-shortest", out], stdin=subprocess.PIPE)
    dec = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{a}", "-i", SRC,
                            "-t", f"{b - a + 0.5}", "-vf", f"fps={FPS}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                           stdout=subprocess.PIPE)
    fsz = SW * SH * 3
    k, frame = -1, None
    gi = 0
    for f in range(nframes):
        want = src_k[f]
        while k < want:
            buf = dec.stdout.read(fsz)
            if len(buf) < fsz:
                break
            frame = np.frombuffer(buf, np.uint8).reshape(SH, SW, 3)
            k += 1
        S = H / BASE_CROP_H * zoom[f]
        fx, fy = cam_x[f], cam_y[f]
        x0 = fx - (W / 2) / S
        y0 = fy - (H * FACE_Y) / S
        x0 = min(max(x0, 0), SW - W / S)
        y0 = min(max(y0, 0), SH - H / S)
        M = np.float32([[S, 0, -S * x0], [0, S, -S * y0]])
        img = cv2.warpAffine(frame, M, (W, H), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REPLICATE)
        bl = cv2.GaussianBlur(img, (0, 0), 2.2)
        img = cv2.addWeighted(img, 1.55, bl, -0.55, 0)

        t = f / FPS
        while gi + 1 < len(gs) and gs[gi + 1]["s"] <= t:
            gi += 1
        g = gs[gi] if gs else None
        if g and g["s"] <= t < g["e"]:
            active = max([i for i, w in enumerate(g["words"]) if w["s"] <= t + 0.02] or [0])
            age = t - g["s"]
            wage = t - g["words"][active]["s"]
            sc = 1.0
            if age < 0.12:
                sc = 0.86 + 0.14 * (age / 0.12) + 0.05 * np.sin(np.pi * age / 0.12)
            if g["words"][active]["emph"] and wage < 0.16:
                sc = max(sc, 1.0 + 0.18 * (1 - wage / 0.16))
            sc = round(sc, 2)
            key = (gi, active, sc)
            if key not in cache:
                if len(cache) > 400:
                    cache.clear()
                cache[key] = to_bgra(render_group(g, active, sc))
            ov = cache[key]
            blend(img, ov, 0, int(H * CAP_Y - ov[1].shape[0] / 2))
        blend(img, title, 0, title_y)
        if credit is not None and t < 3.0:
            blend(img, credit, 0, H - 230)
        venc.stdin.write(img.tobytes())
    venc.stdin.close()
    venc.wait()
    dec.kill()

    meta = {"nn": nn, "slug": slug, "in": a, "out": b, "title": cfg["title"], "duration": round(total, 2),
            "audio_duration": round(adur, 2), "segments": len(segs),
            "captions": [{"s": round(g["s"], 2), "e": round(g["e"], 2),
                          "words": [[w["t"], round(w["s"], 2)] for w in g["words"]]} for g in gs],
            "cut_map": [[sg["k0"], sg["k1"], sg["o0"]] for sg in segs]}
    json.dump(meta, open(os.path.join(OUT_DIR, "qa", f"{nn}_plan.json"), "w"), indent=1)
    print(out, f"{total:.2f}s")


if __name__ == "__main__":
    main()
