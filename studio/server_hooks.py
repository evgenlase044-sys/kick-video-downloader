"""Helpers called from the patched server.py (never imports server)."""
from __future__ import annotations

import glob
import os
import uuid
from fractions import Fraction

from fastapi import HTTPException

from studio import ffmpeg_caps
from studio.render_ws import ws_render  # noqa: F401
from studio.security import check_import_path as _check_import_path, is_allowed_media_host, remember_playlist_urls
from studio.timeremap import RAMP_IN_SPEED, ramp_breakpoints

DOWNLOAD_PEAK_FACTOR = 2.0   # segments + merged MP4 exist at once


def code_mtime_ms(base_dir):
    files = [os.path.join(base_dir, "server.py"), os.path.join(base_dir, "studio_server.py")]
    files += glob.glob(os.path.join(base_dir, "studio", "*.py"))
    files = [f for f in files if os.path.exists(f)]
    return int(max(os.path.getmtime(f) for f in files) * 1000) if files else 0


def download_headers(extractor):
    try:
        h = extractor.get_size_headers()
        return dict(h) if h else None
    except Exception:
        return None


def size_calculator(extractor, fallback):
    headers = download_headers(extractor)
    if not headers:
        return fallback
    try:
        from size_calculator import SizeCalculator
        return SizeCalculator(headers=headers)
    except Exception:
        return fallback


def remember_playlists(qualities):
    remember_playlist_urls(q.get("playlist_url") for q in qualities or [])


def validate_download_request(req):
    url = (getattr(req, "playlist_url", "") or "").strip()
    if not is_allowed_media_host(url):
        raise HTTPException(status_code=400, detail="playlist_url не относится к Kick/CDN (защита от SSRF). Сначала выполните анализ ссылки.")
    st, en = getattr(req, "start_time", None), getattr(req, "end_time", None)
    if (st is None) != (en is None):
        raise HTTPException(status_code=400, detail="Для фрагмента нужны и start_time, и end_time")
    if st is not None and (st < 0 or en <= st):
        raise HTTPException(status_code=400, detail="Некорректный диапазон: 0 ≤ начало < конец")


def parse_rate(value, default=0.0):
    try:
        s = str(value or "").strip()
        f = float(Fraction(s)) if "/" in s else float(s)
        return f if f > 0 else default
    except (ValueError, ZeroDivisionError):
        return default


def stream_fps(stream):
    """Exact fps + rational string. avg_frame_rate preferred (VFR streams
    report the timebase as r_frame_rate)."""
    avg, r = stream.get("avg_frame_rate") or "", stream.get("r_frame_rate") or ""
    fa, fr = parse_rate(avg), parse_rate(r)
    for text, val in ((avg, fa), (r, fr)):
        if 1.0 <= val <= 240.0:
            q = (Fraction(text) if "/" in text else Fraction(val)).limit_denominator(1001)
            return round(val, 4), f"{q.numerator}/{q.denominator}"
    return 60.0, "60/1"


def unique_id():
    return uuid.uuid4().hex


def enforce_min_word_duration(words, min_dur):
    """Stretch too-short words (never drop them: that loses speech)."""
    out = sorted((dict(w) for w in words if w.get("end", 0) >= w.get("start", 0)), key=lambda w: (w["start"], w["end"]))
    for i, w in enumerate(out):
        if w["end"] - w["start"] >= min_dur:
            continue
        nxt = out[i + 1]["start"] if i + 1 < len(out) else float("inf")
        w["end"] = max(w["end"], min(w["start"] + min_dur, nxt))
        if w["end"] - w["start"] < min_dur:
            prev_end = out[i - 1]["end"] if i > 0 else 0.0
            w["start"] = max(prev_end, w["end"] - min_dur, 0.0)
        w["start"], w["end"] = round(w["start"], 3), round(w["end"], 3)
        if "abs_start" in w:
            w["abs_start"], w["abs_end"] = w["start"], w["end"]
    return out


def check_import_path(path):
    try:
        return _check_import_path(path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def parse_queue_clips(clips, model):
    out = []
    for i, c in enumerate(clips or []):
        if isinstance(c, model):
            out.append(c)
            continue
        try:
            out.append(model(**c))
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"clip #{i + 1}: {exc}")
    return out


def fx_time_remap(kind, curr_v, tag, s0, e0):
    """freeze: drop frames in (s0, e0] -> CFR output holds the s0 frame.
    ramp: duration-preserving setpts re-time (0.35x then fast), same curve
    as web/core/timeRemap.js. In place (no split/overlay -> no buffering)."""
    BS = "\\"
    s0, e0 = float(s0), float(e0)
    if e0 - s0 < 1e-3:
        return [], curr_v
    tail = ",fps=source_fps" if ffmpeg_caps.fps_supports_source_fps() else ""
    label = f"[{tag}tr]"
    if kind == "freeze":
        expr = f"not(between(t{BS},{s0 + 0.0005:.4f}{BS},{e0 - 0.0005:.4f}))"
        return [f"{curr_v}select='{expr}'{tail}{label}"], label
    if kind == "ramp":
        h, k, b = ramp_breakpoints(e0 - s0)
        rel = f"(T-{s0:.4f})"
        inner = f"if(lt({rel}{BS},{k:.5f}){BS},{rel}/{RAMP_IN_SPEED:.4f}{BS},{h:.5f}+({rel}-{k:.5f})/{b:.5f})"
        expr = f"if(between(T{BS},{s0:.4f}{BS},{e0:.4f}){BS},({s0:.4f}+{inner})/TB{BS},PTS)"
        return [f"{curr_v}setpts='{expr}'{tail}{label}"], label
    return [], curr_v
