"""Discipline-edit planner (viral motivational edits).

Formula reverse-engineered from the user's reference outputs
(video_2026-09-29_15-19-*.mp4, 576x1024@30, ~20s, one hardtekk track):
  * fullscreen vertical, NO karaoke subtitles (still cards carry own text);
  * 2-3 lifestyle VIDEO clips with a slow push-in, then hard-cut PICTURE
    cards (~1.5-2.5s each, slight push) on the music beats;
  * music is the ONLY audio (clip voices muted), same track every time;
  * zoom punch right before the drop, tiny shake on peak hits, end card.

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


def still_to_loop(png_path: str, mp4_path: str, dur: float = 2.5, fps: int = 30) -> bool:
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
def _fit_cuts(onsets: List[float], start: float, end: float, count: int) -> List[float]:
    inside = [o for o in onsets if start + 0.3 < o < end - 0.3]
    if len(inside) >= count:
        # spread evenly
        idx = [round(i * (len(inside) - 1) / max(1, count - 1)) for i in range(count)] if count > 1 else [0]
        return [inside[i] for i in idx]
    # fall back to even grid
    return [round(start + (end - start) * (i + 1) / (count + 1), 2) for i in range(count)]


def probe_duration(path: str) -> float:
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", path], capture_output=True, text=True, timeout=30)
        return max(0.0, float((r.stdout or "").strip() or 0))
    except Exception:
        return 0.0


def plan_discipline(*, materials: List[Dict[str, Any]], music_file: str,
                    music_offset: float = 0.0, target_dur: float = 21.0,
                    n_pics: int = 4, hook_text: str = "ДИСЦИПЛИНА",
                    pic_loops: Optional[List[str]] = None,
                    push_peak: float = 0.08,
                    analysis: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build the edit: video part -> picture cards on beats -> end card.

    materials: [{filename, duration}] (files live in downloads/).
    Returns timeline-ready spec: clips, pics, fx, text, music, region.
    """
    target_dur = max(8.0, min(60.0, float(target_dur or 21.0)))
    onsets = list((analysis or {}).get("onsets") or [])
    drop = float((analysis or {}).get("drop") or 8.0) + music_offset
    drop = max(4.0, min(target_dur - 6.0, drop))

    # part A: video clips fill [0, drop]; part B: cards fill [drop, target]
    part_a = drop
    n_vid = max(1, min(3, len(materials)))
    # spread materials over part A
    clips = []
    t = 0.0
    per = part_a / n_vid
    for i in range(n_vid):
        m = materials[i % len(materials)]
        mdur = max(1.0, float(m.get("duration") or 10.0))
        seg = min(per, mdur)
        # take from the middle when the file is longer than the slot
        src_in = round(max(0.0, (mdur - seg) / 2.0), 2) if mdur > seg else 0.0
        clips.append({"filename": m["filename"], "src_in": src_in,
                      "duration": round(seg, 2), "out_start": round(t, 2)})
        t += seg
    # stretch last clip to exactly drop (avoid gaps)
    if clips:
        clips[-1]["duration"] = round(drop - clips[-1]["out_start"], 2)

    # part B: alternate pic cards and short video hits on beats
    pics = list(pic_loops or [])
    cuts = _fit_cuts([o + music_offset for o in onsets], drop, target_dur,
                     max(1, len(pics)))
    cards = []
    t = drop
    bounds = [drop] + cuts + [target_dur]
    for i in range(len(bounds) - 1):
        s, e = round(bounds[i], 2), round(bounds[i + 1], 2)
        if e - s < 0.5:
            continue
        if pics and i % 2 == 0:
            cards.append({"kind": "pic", "file": pics[(i // 2) % len(pics)],
                          "out_start": s, "duration": round(e - s, 2)})
        else:
            m = materials[(i + n_vid) % len(materials)]
            mdur = max(1.0, float(m.get("duration") or 10.0))
            seg = min(e - s, mdur)
            src_in = round(max(0.0, (mdur - seg) / 2.0), 2) if mdur > seg else 0.0
            cards.append({"kind": "video", "filename": m["filename"],
                          "src_in": src_in, "out_start": s,
                          "duration": round(seg, 2)})

    fx = []
    # slow push on every video clip + pic card
    for c in clips:
        fx.append({"kind": "push", "start": c["out_start"],
                   "end": round(c["out_start"] + c["duration"], 2),
                   "peak": push_peak})
    for c in cards:
        fx.append({"kind": "push", "start": c["out_start"],
                   "end": round(c["out_start"] + c["duration"], 2),
                   "peak": push_peak + 0.02})
    # punch right before the drop + shake on the first card hit
    fx.append({"kind": "zoom", "start": round(max(0.0, drop - 0.55), 2),
               "end": round(drop - 0.05, 2), "peak": 0.16})
    if cards:
        fx.append({"kind": "shake", "start": cards[0]["out_start"],
                   "end": round(cards[0]["out_start"] + 0.35, 2),
                   "amp": 12, "freq": 8})
    sounds = [{"kind": "hit_small", "at": round(max(0.0, drop - 0.55), 2), "gain": 1.0}]

    text = []
    if hook_text:
        text.append({"text": hook_text, "start": round(target_dur - 2.6, 2),
                     "end": round(target_dur - 0.1, 2), "x": 0.5, "y": 0.5,
                     "size": 84, "anim_in": "pop", "anim_out": "fade"})

    return {"format": "fullscreen", "fps": 30, "duration": round(target_dur, 2),
            "drop": round(drop, 2), "clips": clips, "cards": cards,
            "fx": fx, "sounds": sounds, "text": text,
            "music": {"filename": os.path.basename(music_file),
                      "offset": round(music_offset, 2), "duration": round(target_dur, 2)},
            "subtitle_mode": "none"}
