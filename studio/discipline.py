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

HOP_S = 0.05
MIN_CUT_GAP = 0.8
DEFAULT_MUSIC_BASENAME = "discipline_music.mp4"
TAKEOVER_S = 1.0          # card grows from 0.2 to fullscreen over the video
ANALYSIS_VERSION = 3      # bump to invalidate cached .discipline_music.json


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


def _fine_onsets(rms: List[float], hop: float) -> Tuple[List[float], List[float]]:
    """Onsets with a fine 0.2s minimal gap + their strength (dB jump)."""
    d = [rms[i + 1] - rms[i] for i in range(len(rms) - 1)]
    pos = sorted(v for v in d if v > 0)
    thr = pos[int(len(pos) * 0.90)] if pos else 3.0
    ts: List[float] = []
    ss: List[float] = []
    for i in range(1, len(d) - 1):
        if d[i] > thr and d[i] >= d[i - 1] and d[i] > d[i + 1]:
            t = i * hop
            if not ts or t - ts[-1] >= 0.2:
                ts.append(round(t, 2))
                ss.append(d[i])
    return ts, ss


def _beat_grid(ts: List[float], ss: List[float], dur: float) -> Tuple[float, float, List[float]]:
    """Kick grid via comb scoring of the onset-strength pulse train: for every
    candidate period (0.30-0.60s) and phase, mean pulse at the grid points —
    robust to missing hits. Two passes: coarse 10ms, refined 2ms.
    Returns (period, phase, beats)."""
    hop = HOP_S
    n = int(dur / hop) + 1
    pulse = [0.0] * n
    for t, s in zip(ts, ss):
        i = int(round(t / hop))
        if 0 <= i < n:
            pulse[i] = s

    def best_phase(p: float) -> Tuple[float, float]:
        bs, bp = -1.0, 0.0
        k = 0
        while k * hop < p:
            ph = k * hop
            s = cnt = 0
            t = ph
            while t < dur:
                i = int(round(t / hop))
                if 0 <= i < n:
                    s += pulse[i]
                cnt += 1
                t += p
            s /= max(1, cnt)
            if s > bs:
                bs, bp = s, ph
            k += 1
        return bs, bp

    best = (-1.0, 0.45, 0.0)
    p = 0.30
    while p <= 0.60 + 1e-9:
        s, ph = best_phase(p)
        if s > best[0]:
            best = (s, p, ph)
        p += 0.01
    # refine around the winner
    p0 = best[1]
    p = p0 - 0.012
    while p <= p0 + 0.012 + 1e-9:
        s, ph = best_phase(p)
        if s > best[0]:
            best = (s, p, ph)
        p += 0.002
    per, phase = round(best[1], 3), round(best[2], 3)
    per = min(0.60, max(0.30, per))
    beats = [round(k * per + phase, 2) for k in range(int(dur / per) + 2)
             if k * per + phase <= dur]
    return per, phase, beats


def _accent_cadence(beats: List[float], drop: float, per: float,
                    dur: float) -> List[float]:
    """Мотивационные удары: a STEADY hit cadence (~every 2.2s) locked to the
    beat grid and anchored on the drop, so every impact SFX/visual lands on a
    kick for the whole track."""
    step = max(4, round(2.2 / per)) * per
    if drop <= 0:
        return [round(k * step, 2) for k in range(int(dur / step) + 1)]
    out: List[float] = []
    t = drop
    while t <= dur:
        out.append(round(t, 2))
        t += step
    t = drop - step
    while t >= 0:
        out.append(round(t, 2))
        t -= step
    return sorted(set(out))


def analyze_music(path: str) -> Dict[str, Any]:
    """Beats, accents (мотивационные удары), onsets and the drop of the track.

    beats   — the kick grid (period + phase), cut points snap to it;
    accents — a steady impact cadence (~every 2.2s) locked to the grid and
              anchored on the drop: each gets an impact SFX and a visual hit
              (zoom / shake / cut) in the edit.
    """
    rms = _rms_series(path)
    hop = HOP_S
    ts, ss = _fine_onsets(rms, hop)
    per, phase, beats = _beat_grid(ts, ss, len(rms) * hop)
    # sparse onsets for cut fallbacks (0.8s thinning, as before)
    onsets: List[float] = []
    last = -10.0
    for t in ts:
        if t - last >= MIN_CUT_GAP:
            onsets.append(t)
            last = t
    # drop = max mean-energy jump between consecutive 2s windows in first 40s
    drop = 0.0
    best = 0.0
    perw = max(1, int(2.0 / hop))
    for i in range(0, min(len(rms) - 2 * perw, int(40 / hop))):
        a = sum(rms[i:i + perw]) / perw
        b = sum(rms[i + perw:i + 2 * perw]) / perw
        if b - a > best:
            best = b - a
            drop = round((i + perw) * hop, 2)
    # snap the drop onto the grid
    if beats:
        nb = min(beats, key=lambda b: abs(b - drop))
        if abs(nb - drop) <= 0.25:
            drop = nb
    dur = len(rms) * hop
    accents = _accent_cadence(beats, drop, per, dur)
    return {"duration": round(dur, 2), "onsets": onsets, "drop": round(drop, 2),
            "drop_gain_db": round(best, 2), "beat_period": per,
            "beat_phase": phase, "beats": beats, "accents": accents}


def music_cache_path(downloads_dir: str, music_file: str) -> str:
    return os.path.join(downloads_dir, ".discipline_music.json")


def get_music_analysis(downloads_dir: str, music_file: str) -> Dict[str, Any]:
    path = os.path.join(downloads_dir, os.path.basename(music_file))
    cp = music_cache_path(downloads_dir, music_file)
    key = f"v{ANALYSIS_VERSION}:{os.path.basename(path)}:{os.path.getsize(path)}:{int(os.path.getmtime(path))}"
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
def _snap_beat(t: float, beats: List[float]) -> float:
    if not beats:
        return round(t, 2)
    return round(min(beats, key=lambda b: abs(b - t)), 2)


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


def plan_discipline(*, materials: List[Dict[str, Any]], music_file: str,
                    music_offset: float = 0.0, target_dur: float = 21.0,
                    n_pics: int = 4, hook_text: str = "",
                    pic_loops: Optional[List[str]] = None,
                    push_peak: float = 0.08,
                    analysis: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build the edit aligned to the track's kick grid: beat-cut videos ->
    card takeover on the drop -> beat cards with tints -> end on the final hit.

    No white-flash transitions, no text outro: every musical accent gets an
    impact SFX plus a visual hit (zoom / shake / picture change) — that is the
    whole point of the reference edits.

    materials: [{filename, duration}] (files live in downloads/).
    hook_text: deprecated (text outro removed), kept for API compatibility.
    """
    target_dur = max(8.0, min(60.0, float(target_dur or 21.0)))
    per = float((analysis or {}).get("beat_period") or 0.45)
    phase = float((analysis or {}).get("beat_phase") or 0.0)
    music_dur = float((analysis or {}).get("duration") or 0.0)
    off = round(phase + music_offset, 2)   # music-time -> video-time shift

    # duration = whole beats <= target: music starts AND ends on the grid
    n_beats = max(8, int(round(target_dur / per)))
    duration = round(n_beats * per, 2)
    while music_dur and off + duration > music_dur - 0.3 and n_beats > 8:
        n_beats -= 1
        duration = round(n_beats * per, 2)
    beats = [round(b - off, 2) for b in ((analysis or {}).get("beats") or [])
             if off <= b <= off + duration - 0.05]
    if not beats:
        beats = [round(k * per, 2) for k in range(n_beats + 1)]

    fx: List[Dict[str, Any]] = []
    sounds: List[Dict[str, Any]] = []
    clips: List[Dict[str, Any]] = []
    cards: List[Dict[str, Any]] = []

    def _snap(t: float) -> float:
        return _snap_beat(t, beats)

    # ── part A: beat-cut video intro [0, drop] ──────────────────────────
    drop = _snap(float((analysis or {}).get("drop") or 8.0) - off)
    drop = _snap(min(max(4.0, drop), duration - 4.0))
    n_seg = max(2, min(5, int(drop / 2.2)))
    bounds = [0.0]
    for i in range(1, n_seg):
        bounds.append(_snap(drop * i / n_seg))
    bounds = sorted(set(bounds + [drop]))
    bounds = _merge_close(bounds)
    if bounds[-1] < drop:
        if drop - bounds[-1] < 0.9:
            bounds[-1] = drop          # extend the last segment, never drop the drop
        else:
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
        last["duration"] = round(last["duration"] + min(TAKEOVER_S + 0.4, room), 2)
    for c in clips:
        c.pop("mdur", None)
    # hard cuts, no white flashes: movement comes from the alternating push
    for i, c in enumerate(clips):
        fx.append({"kind": "push", "mode": "in" if i % 2 == 0 else "out",
                   "start": c["out_start"],
                   "end": round(c["out_start"] + c["duration"], 2),
                   "peak": round(push_peak + 0.03 + (i % 2) * 0.02, 3),
                   "track": "video"})
    # pre-drop zoom punch + riser into the drop, boom ON the drop
    fx.append({"kind": "zoom", "start": round(max(0.0, drop - 0.55), 2),
               "end": round(drop - 0.05, 2), "peak": 0.17, "track": "video"})
    sounds.append({"kind": "riser", "at": round(max(0.0, drop - 1.3), 2), "gain": 0.8})
    sounds.append({"kind": "boom", "at": round(drop, 2), "gain": 1.2})

    # ── drop takeover: first card pops in small over the playing video ──
    pics = list(pic_loops or [])
    tints = ["none", "red", "bw", "blue"]
    takeover = None
    if pics:
        first_end = min(max(_snap(drop + 2.0), drop + 1.8), duration - 1.0)
    else:
        first_end = drop   # no card to cover [drop, first_end]: resume right there
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

    # ── part B: beat cards + video hits [first_end, end] ────────────────
    step = max(3, round(1.4 / per))   # beats between picture changes
    bbounds = [round(first_end, 2)]
    t = first_end
    while t < duration - 1.0:
        t = _snap(t + step * per)
        if t <= bbounds[-1]:
            t = round(bbounds[-1] + step * per, 2)
        bbounds.append(min(round(t, 2), duration))
    if bbounds and bbounds[-1] >= duration:
        bbounds[-1] = round(duration, 2)
    else:
        bbounds.append(round(duration, 2))
    # merge close bounds but NEVER drop the final one (a dropped end = a hole)
    head = _merge_close(bbounds[:-1], min_gap=0.9)
    if head and bbounds[-1] - head[-1] < 0.9:
        head[-1] = bbounds[-1]
    else:
        head.append(bbounds[-1])
    bbounds = head
    bbounds = _split_long_slots(bbounds, max_slot=2.8)
    bbounds_tail = bbounds[1:]
    if takeover:
        # the takeover card IS the first slot: slots resume at its end
        bbounds = [round(first_end, 2)] + [b for b in bbounds_tail
                                           if b > first_end + 0.6]
    hit_k = len(clips)
    card_k = 1
    vid_k = 0
    slot_i = 1 if takeover else 0
    for s, e in zip(bbounds, bbounds[1:]):
        if e - s < 0.7:
            continue
        slot_i += 1
        slot_tint = tints[slot_i % len(tints)]
        use_video = (slot_i % 3 == 0) or not pics
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
            # no extra FX here: the scale_in pop IS the beat hit, and the
            # total FX budget per graph must stay low (~12) or ffmpeg stalls

    # ── accent cadence: impact SFX + a visual hit on every musical удар ──
    accents = [round(a - off, 2) for a in ((analysis or {}).get("accents") or [])
               if 0.5 <= a - off <= duration - 0.2]
    bounds_all = bounds[1:-1] + bbounds
    zi = 0
    for a in accents:
        if abs(a - drop) < 0.1:
            continue   # the drop already has boom + shake + takeover
        if any(abs(a - b) < 0.12 for b in bounds_all):
            # the picture change on the beat IS the visual hit
            sounds.append({"kind": "hit_small", "at": round(a, 2), "gain": 0.55})
            continue
        if zi >= 4:
            sounds.append({"kind": "boom", "at": round(a, 2), "gain": 0.5})
            continue
        zi += 1
        fx_track = "cards" if a >= drop - 0.05 else "video"
        # cheap shake only: zoom chains (eval=frame scale + tmix) multiply the
        # graph cost and the exporter stalls past ~a dozen of them
        fx.append({"kind": "shake", "start": round(a, 2),
                   "end": round(a + 0.22, 2), "amp": 9, "freq": 9,
                   "track": fx_track})
        sounds.append({"kind": "boom", "at": round(a, 2), "gain": 0.5})
    # final hit: the edit ends ON the grid with a punch + impact
    fx.append({"kind": "zoom", "start": round(duration - 0.45, 2),
               "end": round(duration - 0.02, 2), "peak": 0.14, "track": "cards"})
    sounds.append({"kind": "boom", "at": round(duration - 0.03, 2), "gain": 0.9})

    return {"format": "fullscreen", "fps": 30, "duration": duration,
            "drop": round(drop, 2), "clips": clips, "cards": cards,
            "fx": fx, "sounds": sounds,
            "music": {"filename": os.path.basename(music_file),
                      "offset": off, "duration": duration},
            "subtitle_mode": "none"}
