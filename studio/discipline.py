"""Discipline-edit planner (viral motivational edits).

Formula reverse-engineered from the user's reference outputs
(video_2026-09-29_15-19-*.mp4, 576x1024@30, ~20s, one hardtekk track):
  * fullscreen vertical, NO karaoke subtitles;
  * intro: 2-5 lifestyle VIDEO clips hard-cut ON BEATS, each with a push-in
    (alternating push-out), white flash on the internal cuts;
  * THE signature transition at the drop: a still card pops in SMALL
    (centered, ~0.2 of the frame) over the still-playing video and scales up
    to fullscreen in ~1s (scale_from takeover);
  * body: picture cards cut on beats, each with a small beat-pop
    (0.85 -> 1.0), red/bw duotone tints for contrast against the video,
    short video hits between them;
  * outro: black typographic slides (hook word / repeated-word wall /
    highlight end card) generated with PIL;
  * music is the ONLY audio (clip voices muted), same track every time.

Stills are materialized as short mp4 loops (2.5s) so the export pipeline
(which expects video inputs) needs no changes.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
from typing import Any, Dict, List, Optional, Tuple

HOP_S = 0.1
MIN_CUT_GAP = 0.8
DEFAULT_MUSIC_BASENAME = "discipline_music.mp4"
TAKEOVER_S = 1.0          # card grows from 0.2 to fullscreen over the video
OUTRO_MAX_S = 6.0         # typographic slides block
SLIDE_W, SLIDE_H = 1080, 1920
ACCENT = (232, 255, 42)   # acid yellow (matches the app subtitle style)


# ── music analysis ───────────────────────────────────────────────────
def _rms_series(path: str, hop: float = HOP_S, sr: int = 8000,
                ffmpeg: str = "ffmpeg", timeout: int = 300) -> List[float]:
    n = max(1, int(sr * hop))
    af = (f"aresample={sr},aformat=channel_layouts=mono,asetnsamples=n={n}:p=0,"
          "astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-")
    cmd = [ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error",
           "-i", path, "-vn", "-af", af, "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0 and not r.stdout:
        raise RuntimeError(f"ffmpeg astats failed: {r.stderr[-300:]}")
    import re
    out = []
    for m in re.finditer(r"lavfi\.astats\.Overall\.RMS_level=(-?[0-9.]+|-inf)", r.stdout):
        v = m.group(1)
        out.append(-90.0 if v == "-inf" else max(-90.0, float(v)))
    return out


def analyze_music(path: str) -> Dict[str, Any]:
    """Onsets (cuts) + drop (biggest energy jump) of the music track."""
    rms = _rms_series(path)
    hop = HOP_S
    d = [rms[i + 1] - rms[i] for i in range(len(rms) - 1)]
    pos = sorted((v for v in d if v > 0))
    thr = pos[int(len(pos) * 0.90)] if pos else 3.0
    onsets: List[float] = []
    last = -10.0
    for i in range(1, len(d) - 1):
        if d[i] > thr and d[i] >= d[i - 1] and d[i] > d[i + 1]:
            t = i * hop
            if t - last >= MIN_CUT_GAP:
                onsets.append(round(t, 2))
                last = t
    # drop = max mean-energy jump between consecutive 2s windows in first 40s
    drop = 0.0
    best = 0.0
    per = max(1, int(2.0 / hop))
    for i in range(0, min(len(rms) - 2 * per, int(40 / hop))):
        a = sum(rms[i:i + per]) / per
        b = sum(rms[i + per:i + 2 * per]) / per
        if b - a > best:
            best = b - a
            drop = round((i + per) * hop, 2)
    dur = len(rms) * hop
    return {"duration": round(dur, 2), "onsets": onsets, "drop": drop,
            "drop_gain_db": round(best, 2)}


def music_cache_path(downloads_dir: str, music_file: str) -> str:
    return os.path.join(downloads_dir, ".discipline_music.json")


def get_music_analysis(downloads_dir: str, music_file: str) -> Dict[str, Any]:
    path = os.path.join(downloads_dir, os.path.basename(music_file))
    cp = music_cache_path(downloads_dir, music_file)
    key = f"{os.path.basename(path)}:{os.path.getsize(path)}:{int(os.path.getmtime(path))}"
    try:
        with open(cp, "r", encoding="utf-8") as fh:
            cached = json.load(fh)
        if cached.get("key") == key:
            return cached["analysis"]
    except Exception:
        pass
    analysis = analyze_music(path)
    try:
        with open(cp, "w", encoding="utf-8") as fh:
            json.dump({"key": key, "analysis": analysis}, fh)
    except Exception:
        pass
    return analysis


# ── stills from video resources ──────────────────────────────────────
def _sharpness(cv2, frame) -> float:
    g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, (288, 512))
    lap = cv2.Laplacian(g, cv2.CV_64F)
    return float(lap.var())


def extract_stills(src_path: str, out_dir: str, n: int = 6,
                   min_gap_s: float = 2.0,
                   prefix: str = "discipline_still_") -> List[Dict[str, Any]]:
    """Sharp, non-black frames spread over the video -> PNG paths + scores."""
    import cv2
    os.makedirs(out_dir, exist_ok=True)
    cap = cv2.VideoCapture(src_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    dur = total / max(1.0, fps)
    if dur <= 0:
        return []
    # candidate grid: ~1 per second, skip first/last 5%
    cands = []
    t = dur * 0.05
    while t < dur * 0.95 and len(cands) < 400:
        cands.append(t)
        t += 1.0
    scored = []
    for tt in cands:
        cap.set(cv2.CAP_PROP_POS_MSEC, tt * 1000.0)
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        mean = float(frame.mean())
        if mean < 12.0:  # black / fade
            continue
        scored.append((tt, _sharpness(cv2, frame)))
    cap.release()
    if not scored:
        return []
    scored.sort(key=lambda x: -x[1])
    picked: List[Tuple[float, float]] = []
    for tt, sc in scored:
        if all(abs(tt - p[0]) >= min_gap_s for p in picked):
            picked.append((tt, sc))
        if len(picked) >= n:
            break
    picked.sort(key=lambda x: x[0])
    out = []
    base = os.path.splitext(os.path.basename(src_path))[0]
    safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in base)[:24]
    cap = cv2.VideoCapture(src_path)
    for i, (tt, sc) in enumerate(picked):
        cap.set(cv2.CAP_PROP_POS_MSEC, tt * 1000.0)
        ok, frame = cap.read()
        if not ok:
            continue
        name = f"{prefix}{safe}_{i:02d}_t{tt:.1f}.png"
        p = os.path.join(out_dir, name)
        cv2.imwrite(p, frame)
        out.append({"png": p, "t": round(tt, 2), "score": round(sc, 1)})
    cap.release()
    return out


def ensure_music_track(source_path: str, downloads_dir: str,
                       out_name: str = "discipline_music.m4a") -> str:
    """Copy the (user-fixed) music source audio into downloads/ as .m4a.

    .m4a routes to an audio timeline track (isAudioFile by extension) and
    keeps the original AAC without re-encode when possible.
    """
    out = os.path.join(downloads_dir, out_name)
    if os.path.exists(out) and os.path.getsize(out) > 1024:
        return out_name
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", source_path,
           "-vn", "-c:a", "aac", "-b:a", "192k", out]
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                       text=True, timeout=300)
    if r.returncode != 0 or not os.path.exists(out):
        raise RuntimeError(f"music extract failed: {(r.stderr or '')[-200:]}")
    return out_name


def still_to_loop(png_path: str, mp4_path: str, dur: float = 6.0, fps: int = 30) -> bool:
    """One PNG -> short mp4 loop (export pipeline eats video, not images)."""
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", png_path,
           "-t", f"{dur:.2f}", "-r", str(fps),
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
           "-pix_fmt", "yuv420p", "-colorspace", "bt709",
           "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
           "-movflags", "+faststart", mp4_path]
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                       text=True, timeout=120)
    return r.returncode == 0 and os.path.exists(mp4_path) and os.path.getsize(mp4_path) > 1024


# ── plan ─────────────────────────────────────────────────────────────
def _snap_to_onset(t: float, onsets: List[float], tol: float = 0.6) -> float:
    best, bd = None, tol
    for o in onsets:
        d = abs(o - t)
        if d < bd:
            bd, best = d, o
    return round(best, 2) if best is not None else round(t, 2)


def _merge_close(bounds: List[float], min_gap: float = 0.9) -> List[float]:
    out: List[float] = []
    for b in bounds:
        if out and b - out[-1] < min_gap:
            continue
        out.append(b)
    return out


def _split_long_slots(bounds: List[float], max_slot: float = 4.5) -> List[float]:
    """Sparse onsets must not leave multi-second static slots: subdivide."""
    out: List[float] = []
    for a, b in zip(bounds, bounds[1:]):
        out.append(a)
        gap = b - a
        if gap > max_slot:
            parts = int(math.ceil(gap / max_slot))
            for k in range(1, parts):
                out.append(round(a + gap * k / parts, 2))
    out.append(bounds[-1])
    return out


def probe_duration(path: str) -> float:
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", path], capture_output=True, text=True, timeout=30)
        return max(0.0, float((r.stdout or "").strip() or 0))
    except Exception:
        return 0.0


def _video_hit(materials: List[Dict[str, Any]], k: int, slot: float,
               reserve_tail: float = 0.0) -> Dict[str, Any]:
    """A short video segment for slot seconds (varied src window, k = usage counter)."""
    m = materials[k % len(materials)]
    mdur = max(1.0, float(m.get("duration") or 10.0))
    seg = min(slot, max(0.5, mdur - 0.2 - reserve_tail))
    fracs = (0.15, 0.45, 0.75, 0.30)
    frac = fracs[k % len(fracs)]
    src_in = round(max(0.0, (mdur - seg - reserve_tail) * frac), 2)
    return {"filename": m["filename"], "src_in": src_in, "mdur": mdur,
            "duration": round(seg, 2)}


def _src_tag(filename: str) -> str:
    """'Download (1).mp4' -> 'download1' (matches still-loop name tags)."""
    base = os.path.splitext(os.path.basename(filename))[0]
    return "".join(c for c in base.lower() if c.isalnum())


def _pick_takeover_pic(pics: List[str], last_clip_file: str) -> str:
    """Takeover card must CONTRAST with the video it lands over: prefer a
    still extracted from a different source material."""
    if not pics:
        return ""
    want = _src_tag(last_clip_file or "")
    for p in pics:
        tag = _src_tag(p).replace("disciplinestill", "")
        if want and not tag.startswith(want[:10]):
            return p
    return pics[0]


# ── typographic slides (outro) ───────────────────────────────────────
def _load_font(size: int):
    from PIL import ImageFont
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name in ("montserrat-montserrat-extrabold.ttf",
                 "firasans-FiraSans-ExtraBold.ttf",
                 "anton-Anton-Regular.ttf"):
        p = os.path.join(here, "fonts", name)
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _fit_font(text: str, max_w: int, start_size: int) -> Any:
    size = start_size
    while size > 28:
        f = _load_font(size)
        try:
            w = f.getbbox(text)[2] - f.getbbox(text)[0]
        except Exception:
            w = f.getsize(text)[0]
        if w <= max_w:
            return f
        size = int(size * 0.92)
    return _load_font(28)


def _draw_center(draw, y: int, text: str, font, fill, max_w: int,
                 highlight: bool = False) -> int:
    try:
        bb = font.getbbox(text)
        w, h = bb[2] - bb[0], bb[3] - bb[1]
    except Exception:
        w, h = font.getsize(text)
    x = (SLIDE_W - w) // 2
    if highlight:
        pad = 18
        draw.rectangle([x - pad, y - pad, x + w + pad, y + h + pad], fill=ACCENT)
        draw.text((x, y), text, font=font, fill=(10, 10, 10))
    else:
        draw.text((x, y), text, font=font, fill=(255, 255, 255))
    return h


def make_type_slides(work_dir: str, hook: str = "ДИСЦИПЛИНА",
                     caption: str = "НАЧНИ СЕГОДНЯ") -> List[str]:
    """Three black typographic slides (1080x1920): hook, repeated-word wall
    with one highlighted row, end card with a yellow underline bar."""
    from PIL import Image, ImageDraw
    import zlib
    os.makedirs(work_dir, exist_ok=True)
    ascii_safe = "".join(c for c in (hook or "EDIT").upper() if c.isascii() and c.isalnum())[:12]
    if len(ascii_safe) < 3:
        ascii_safe = "s" + format(zlib.crc32((hook or "EDIT").encode("utf-8")) % 100000, "05d")
    safe = ascii_safe
    paths = []

    def _save(img: "Image.Image", tag: str) -> str:
        p = os.path.join(work_dir, f"discipline_slide_{safe}_{tag}.png")
        img.save(p)
        paths.append(p)
        return p

    hook_u = (hook or "ДИСЦИПЛИНА").upper().strip()

    # 1. hook word, huge
    img = Image.new("RGB", (SLIDE_W, SLIDE_H), (8, 8, 8))
    d = ImageDraw.Draw(img)
    f = _fit_font(hook_u, SLIDE_W - 160, 190)
    _draw_center(d, SLIDE_H // 2 - 160, hook_u, f, (255, 255, 255), SLIDE_W - 160)
    if caption:
        fc = _load_font(44)
        _draw_center(d, SLIDE_H // 2 + 140, caption.upper(), fc, (150, 155, 160), SLIDE_W - 200)
    _save(img, "hook")

    # 2. repeated-word wall, one highlighted row (CONSISTENCY-style)
    img = Image.new("RGB", (SLIDE_W, SLIDE_H), (8, 8, 8))
    d = ImageDraw.Draw(img)
    rows = 7
    fr = _fit_font(hook_u, SLIDE_W - 220, 92)
    rh = 210
    y0 = (SLIDE_H - rows * rh) // 2 + 80
    for i in range(rows):
        fade = max(0.10, 1.0 - i * (0.92 / rows))
        y = y0 + i * rh
        if i == 2:
            _draw_center(d, y, hook_u, fr, (255, 255, 255), SLIDE_W - 220, highlight=True)
        else:
            col = int(255 * fade)
            try:
                d.text((SLIDE_W // 2, y), hook_u, font=fr, fill=(col, col, col), anchor="ma")
            except Exception:
                _draw_center(d, y, hook_u, fr, (col, col, col), SLIDE_W - 220)
    _save(img, "wall")

    # 3. end card: hook + yellow bar + caption
    img = Image.new("RGB", (SLIDE_W, SLIDE_H), (8, 8, 8))
    d = ImageDraw.Draw(img)
    f = _fit_font(hook_u, SLIDE_W - 160, 168)
    bb = f.getbbox(hook_u)
    h = bb[3] - bb[1]
    y = SLIDE_H // 2 - h // 2 - 40
    _draw_center(d, y, hook_u, f, (255, 255, 255), SLIDE_W - 160)
    pad = 70
    d.rectangle([SLIDE_W // 2 - pad, y + h + 42, SLIDE_W // 2 + pad, y + h + 58], fill=ACCENT)
    if caption:
        fc = _load_font(48)
        _draw_center(d, y + h + 130, caption.upper(), fc, (150, 155, 160), SLIDE_W - 200)
    _save(img, "end")
    return paths


def _slide_loops(work_dir: str, hook: str, caption: str, dur: float = 1.6) -> List[str]:
    """PNG slides -> mp4 loops in downloads/ (cached by name)."""
    out = []
    for png in make_type_slides(work_dir, hook, caption):
        mp4 = os.path.splitext(png)[0] + ".mp4"
        png_mtime = os.path.getmtime(png)
        if not (os.path.exists(mp4) and os.path.getsize(mp4) > 1024
                and os.path.getmtime(mp4) >= png_mtime):
            if not still_to_loop(png, mp4, dur=dur):
                continue
        out.append(os.path.basename(mp4))
    return out


def plan_discipline(*, materials: List[Dict[str, Any]], music_file: str,
                    music_offset: float = 0.0, target_dur: float = 21.0,
                    n_pics: int = 4, hook_text: str = "ДИСЦИПЛИНА",
                    pic_loops: Optional[List[str]] = None,
                    push_peak: float = 0.08,
                    analysis: Optional[Dict[str, Any]] = None,
                    work_dir: Optional[str] = None,
                    slide_caption: str = "НАЧНИ СЕГОДНЯ") -> Dict[str, Any]:
    """Build the edit: beat-cut videos -> card takeover on the drop -> beat
    cards with tints -> typographic outro.

    materials: [{filename, duration}] (files live in downloads/).
    Returns timeline-ready spec: clips (base track), cards (cards track,
    with scale_from/scale_in/tint), fx (per track), sounds, music.
    """
    target_dur = max(8.0, min(60.0, float(target_dur or 21.0)))
    onsets = [float(o) + music_offset for o in ((analysis or {}).get("onsets") or [])]
    drop = float((analysis or {}).get("drop") or 8.0) + music_offset
    drop = max(4.0, min(target_dur - 6.0, drop))

    fx: List[Dict[str, Any]] = []
    sounds: List[Dict[str, Any]] = []
    clips: List[Dict[str, Any]] = []
    cards: List[Dict[str, Any]] = []

    # ── outro slides first: they decide where part B ends ───────────────
    slides: List[str] = []
    if work_dir:
        try:
            slides = _slide_loops(work_dir, hook_text or "ДИСЦИПЛИНА", slide_caption)
        except Exception:
            slides = []
    outro_len = min(OUTRO_MAX_S, max(3.5, target_dur * 0.28)) if slides else 0.0
    outro_start = target_dur - outro_len

    # ── part A: beat-cut video intro [0, drop] ──────────────────────────
    pre_onsets = [o for o in onsets if 0.6 < o < drop - 0.4]
    n_seg = max(2, min(5, int(drop / 2.0)))
    bounds = [0.0]
    for i in range(1, n_seg):
        bounds.append(_snap_to_onset(drop * i / n_seg, pre_onsets))
    bounds = _merge_close(sorted(set(bounds + [drop])))
    if bounds[-1] < drop:
        bounds.append(drop)
    seg_reserve = TAKEOVER_S + 0.5
    for i in range(len(bounds) - 1):
        s, e = bounds[i], bounds[i + 1]
        if e - s < 0.6:
            continue
        hit = _video_hit(materials, i, e - s,
                         reserve_tail=seg_reserve if i == len(bounds) - 2 else 0.0)
        seg = min(e - s, max(0.5, hit["duration"]))
        clips.append({"filename": hit["filename"], "src_in": hit["src_in"],
                      "duration": round(seg, 2), "out_start": round(s, 2)})
    # the last intro clip keeps playing UNDER the takeover card
    if clips:
        last = clips[-1]
        room = max(0.0, last.get("mdur", 10.0) - last["src_in"] - last["duration"])
        extra = min(TAKEOVER_S + 0.4, room)
        last["duration"] = round(last["duration"] + extra, 2)
    for c in clips:
        c.pop("mdur", None)
    # push on every intro clip (alternating in/out) + flash/whoosh on cuts
    for i, c in enumerate(clips):
        fx.append({"kind": "push", "mode": "in" if i % 2 == 0 else "out",
                   "start": c["out_start"],
                   "end": round(c["out_start"] + c["duration"], 2),
                   "peak": round(push_peak + 0.03 + (i % 2) * 0.02, 3),
                   "track": "video"})
    for b in bounds[1:-1]:
        fx.append({"kind": "flash", "start": round(max(0.0, b - 0.06), 2),
                   "end": round(b + 0.07, 2), "peak": 0.85, "color": "white",
                   "track": "video"})
        sounds.append({"kind": "whoosh", "at": round(b, 2), "gain": 0.7})
    # pre-drop zoom punch + riser into the drop
    fx.append({"kind": "zoom", "start": round(max(0.0, drop - 0.55), 2),
               "end": round(drop - 0.05, 2), "peak": 0.17, "track": "video"})
    sounds.append({"kind": "riser", "at": round(max(0.0, drop - 1.3), 2), "gain": 0.8})
    sounds.append({"kind": "boom", "at": round(drop, 2), "gain": 1.2})

    # ── drop takeover: first card pops in small over the playing video ──
    pics = list(pic_loops or [])
    tints = ["none", "red", "bw", "blue"]
    takeover = None
    first_end = _snap_to_onset(drop + 2.2,
                               [o for o in onsets if drop + 1.4 < o < outro_start - 0.5],
                               tol=0.7)
    first_end = min(max(first_end, drop + 1.8), outro_start - 0.4)
    if pics:
        pic0 = _pick_takeover_pic(pics, clips[-1]["filename"] if clips else "")
        takeover = {"kind": "pic", "file": pic0, "src_in": 0,
                    "out_start": round(drop, 2),
                    "duration": round(first_end - drop, 2),
                    "scale_from": 0.20, "scale_in": TAKEOVER_S,
                    "tint": "none", "layer": "cards"}
        cards.append(takeover)
        fx.append({"kind": "shake", "start": round(drop, 2),
                   "end": round(drop + 0.45, 2), "amp": 14, "freq": 8,
                   "track": "cards"})

    # ── part B: beat cards + video hits [first_end, outro_start] ───────
    bo = [o for o in onsets if drop + 2.6 < o < outro_start - 0.7]
    step = max(1, len(bo) // max(2, n_pics * 2))
    bo = bo[::step][:max(2, n_pics + 2)]
    bbounds = _merge_close([round(drop, 2)] + [round(o, 2) for o in bo]
                           + [round(outro_start, 2)], min_gap=1.1)
    if bbounds[-1] < outro_start - 0.4:
        bbounds.append(round(outro_start, 2))
    if takeover:
        # the takeover card IS the first slot; later bounds must clear it
        bbounds = ([round(drop, 2), round(first_end, 2)]
                   + [b for b in bbounds[1:] if b > first_end + 0.6])
    # sparse onsets must not leave long static slots (visual monotony)
    bbounds = _split_long_slots(bbounds, max_slot=2.8)
    hit_k = len(clips)
    card_k = 1
    vid_k = 0
    slot_from = 0 if not takeover else 1
    for i in range(slot_from, len(bbounds) - 1):
        s, e = bbounds[i], bbounds[i + 1]
        if e - s < 0.7:
            continue
        slot_tint = tints[i % len(tints)]   # adjacent slots never repeat
        use_video = (i % 3 == 2) or (not pics and materials)
        if use_video and materials:
            hit = _video_hit(materials, hit_k, e - s)
            hit_k += 1
            vid_k += 1
            cards.append({"kind": "video", "filename": hit["filename"],
                          "src_in": hit["src_in"], "out_start": round(s, 2),
                          "duration": round(e - s, 2),
                          "scale_from": 0.0, "scale_in": 0.0,
                          "tint": slot_tint, "layer": "cards"})
            fx.append({"kind": "push", "start": round(s, 2),
                       "end": round(e, 2), "peak": 0.16, "track": "cards"})
            sounds.append({"kind": "whoosh", "at": round(s, 2), "gain": 0.6})
        else:
            card = (pics[card_k % len(pics)] if pics else None)
            entry = {"kind": "pic" if card else "video",
                     "file": card, "filename": None if card else materials[0]["filename"],
                     "src_in": 0 if card else 0.0,
                     "out_start": round(s, 2), "duration": round(e - s, 2),
                     "scale_from": 0.85, "scale_in": 0.28,
                     "tint": slot_tint, "layer": "cards"}
            if not card:
                mh = _video_hit(materials, hit_k, e - s)
                entry["filename"] = mh["filename"]
                entry["src_in"] = mh["src_in"]
            cards.append(entry)
            card_k += 1
            fx.append({"kind": "flash", "start": round(max(0.0, s - 0.05), 2),
                       "end": round(s + 0.08, 2), "peak": 0.30, "color": "white",
                       "track": "cards"} if card_k % 2 == 0 else
                      {"kind": "push", "start": round(s, 2),
                       "end": round(e, 2), "peak": 0.10, "track": "cards"})
            sounds.append({"kind": "hit_small", "at": round(s, 2), "gain": 0.9})

    # ── outro: typographic slides on black (slides were made first) ─────
    if slides:
        n_slides = len(slides)
        sl = (target_dur - outro_start) / n_slides
        for i, name in enumerate(slides):
            s = outro_start + i * sl
            cards.append({"kind": "pic", "file": name, "src_in": 0,
                          "out_start": round(s, 2), "duration": round(sl, 2),
                          "scale_from": 0.90, "scale_in": 0.25,
                          "tint": "none", "layer": "cards"})
            sounds.append({"kind": "boom" if i == n_slides - 1 else "hit_small",
                           "at": round(s, 2), "gain": 1.0 if i == n_slides - 1 else 0.7})
        # hard cut into the outro (no flash): the black slide IS the cut

    return {"format": "fullscreen", "fps": 30, "duration": round(target_dur, 2),
            "drop": round(drop, 2), "clips": clips, "cards": cards,
            "fx": fx, "sounds": sounds, "text": [], "slides": slides,
            "music": {"filename": os.path.basename(music_file),
                      "offset": round(music_offset, 2), "duration": round(target_dur, 2)},
            "subtitle_mode": "none"}
