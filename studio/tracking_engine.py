"""Object Tracking Engine (PLAN §10).

Manual target tracking inside a manual search zone via NCC template
matching with subpixel peak, anchored anti-drift template, and One Euro
filtering per run. Also supports OpenCV CSRT where available.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from pydantic import BaseModel


class Box(BaseModel):
    """Normalized 0..1 box in source space."""
    x: float
    y: float
    w: float
    h: float


class ZoneKey(Box):
    t: float


class TrackRequest(BaseModel):
    filename: str
    t_from: float
    t_to: float
    t_anchor: float                       # frame carrying the target box
    target: Optional[Box] = None          # required (fallback: x/y/w/h legacy)
    zone: Optional[Box] = None            # static zone
    zone_keys: Optional[List[ZoneKey]] = None   # or animated zone
    manual_keys: List[ZoneKey] = []       # hard user keys
    mode: str = "ncc"                     # ncc | csrt
    fps: float = 0                        # 0 = native region fps (clamped)
    analysis_width: int = 960
    scale_search: bool = False            # multiscale 0.97/1/1.03
    min_conf: float = 0.55
    # legacy single-box API (pre-§10 clients)
    start_time: Optional[float] = None
    duration: Optional[float] = None
    x: Optional[float] = None
    y: Optional[float] = None
    w: Optional[float] = None
    h: Optional[float] = None
    sample_fps: float = 12.0


class _LowPass:
    def __init__(self) -> None:
        self.y: Optional[float] = None

    def __call__(self, x: float, alpha: float) -> float:
        self.y = x if self.y is None else alpha * x + (1.0 - alpha) * self.y
        return self.y


class _OneEuro:
    """PLAN §10.3: One Euro (minCutoff 1.0 Hz, beta 0.02, dCutoff 1.0)."""
    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.02, d_cutoff: float = 1.0) -> None:
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.xf = _LowPass()
        self.df = _LowPass()
        self.xprev: Optional[float] = None

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        tau = 1.0 / (2.0 * math.pi * max(1e-6, cutoff))
        return 1.0 / (1.0 + tau / max(1e-6, dt))

    def __call__(self, x: float, dt: float) -> float:
        dx = 0.0 if self.xprev is None else (x - self.xprev) / max(1e-6, dt)
        self.xprev = x
        edx = self.df(dx, self._alpha(self.d_cutoff, dt))
        cutoff = self.min_cutoff + self.beta * abs(edx)
        return self.xf(x, self._alpha(cutoff, dt))


def _probe_video_size(video_path: str) -> tuple:
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,avg_frame_rate", "-of", "json", video_path],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=30)
    w, h, fr = 0, 0, ""
    try:
        st = json.loads(res.stdout or "{}")["streams"][0]
        w, h = int(st.get("width", 0)), int(st.get("height", 0))
        fr = st.get("avg_frame_rate", "") or ""
    except Exception:
        pass
    if not (w and h):
        raise HTTPException(status_code=500, detail="Не удалось определить размер видео")
    return w, h, fr


def _iter_gray_frames(video_path: str, t_from: float, t_to: float, fps: float,
                      analysis_width: int):
    """Yield (t, np.ndarray HxW gray) frames via ffmpeg pipe — no temp JPEGs (§10.3)."""
    import numpy as np
    src_w, src_h, _ = _probe_video_size(video_path)
    out_w = max(32, min(analysis_width, src_w))
    out_h = max(32, int(round(src_h * out_w / src_w / 2.0)) * 2)
    dur = max(0.0, t_to - t_from)
    cmd = ["ffmpeg", "-loglevel", "error", "-ss", f"{max(0.0, t_from):.3f}",
           "-t", f"{dur:.3f}", "-i", video_path,
           "-vf", f"fps={fps},scale={out_w}:{out_h},format=gray",
           "-f", "rawvideo", "pipe:1"]
    frame_bytes = out_w * out_h
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    idx = 0
    try:
        while True:
            buf = proc.stdout.read(frame_bytes)
            if not buf or len(buf) < frame_bytes:
                break
            yield (idx / fps, np.frombuffer(buf, dtype=np.uint8).reshape(out_h, out_w))
            idx += 1
    finally:
        try:
            proc.stdout.close()
        except Exception:
            pass
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()


def _zone_at_time(zone: Optional[Box], zone_keys: Optional[List[ZoneKey]], t: float,
                  frame_w: int, frame_h: int) -> tuple:
    """Absolute zone box in normalized coords -> (x0,y0,x1,y1) px, clamped to frame."""
    if zone_keys:
        zk = sorted(zone_keys, key=lambda k: k.t)
        if t <= zk[0].t:
            b = zk[0]
        elif t >= zk[-1].t:
            b = zk[-1]
        else:
            a = zk[0]; b = zk[-1]
            for i in range(len(zk) - 1):
                if zk[i].t <= t <= zk[i + 1].t:
                    a, b = zk[i], zk[i + 1]
                    break
            f = (t - a.t) / max(1e-6, (b.t - a.t))
            b = Box(x=a.x + (b.x - a.x) * f, y=a.y + (b.y - a.y) * f,
                    w=a.w + (b.w - a.w) * f, h=a.h + (b.h - a.h) * f)
    elif zone is not None:
        b = zone
    else:
        b = Box(x=0.0, y=0.0, w=1.0, h=1.0)
    x0 = max(0.0, b.x) * frame_w
    y0 = max(0.0, b.y) * frame_h
    x1 = min(1.0, b.x + b.w) * frame_w
    y1 = min(1.0, b.y + b.h) * frame_h
    if x1 - x0 < 8 or y1 - y0 < 8:      # degenerate zone -> whole frame
        x0, y0, x1, y1 = 0.0, 0.0, float(frame_w), float(frame_h)
    return x0, y0, x1, y1


def _clamp_box_into_zone(nx: float, ny: float, nw: float, nh: float, zone_px: tuple,
                         fw: int, fh: int) -> tuple:
    """Hard limit: the box must lie fully inside the zone (§10.3)."""
    zx0, zy0, zx1, zy1 = zone_px
    px = nx * fw; py = ny * fh; pw = nw * fw; ph = nh * fh
    pw = min(pw, zx1 - zx0); ph = min(ph, zy1 - zy0)
    px = min(max(px, zx0), max(zx0, zx1 - pw))
    py = min(max(py, zy0), max(zy0, zy1 - ph))
    return px, py, pw, ph


def _track_feature(img):
    """§10.3 feature: luma + Sobel magnitude. Pure-luma templates with almost
    no variance (flat patches) make TM_CCOEFF_NORMED numerically unstable."""
    import cv2
    import numpy as np
    gx = cv2.Sobel(img, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(img, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(gx, gy)
    feat = 0.5 * img.astype(np.float32) + 0.5 * np.clip(mag, 0.0, 255.0)
    return feat.astype(np.uint8)


def _patch_shape_ok(shape, tw, th):
    return tuple(shape) == (th, tw)


def _ncc_track_run(frames_iter, fps: float, start_box_norm: tuple, start_t: float,
                   req: TrackRequest, zone_args: tuple,
                   forward: bool = True) -> List[Dict[str, Any]]:
    """NCC template matching with subpixel peak, anchored template, lost state (§10.3).
    Frame size is taken from the actual analysis frames (start box is normalized)."""
    import cv2
    import numpy as np
    frame_w = frame_h = None
    template_t0 = None          # anchor template against drift
    template = None
    cx = cy = 0.0
    scale = 1.0
    lost = False
    lost_streak = 0
    found_streak = 0
    out: List[Dict[str, Any]] = []
    min_conf = max(0.05, min(0.95, req.min_conf))

    for t, frame in frames_iter:
        frame = _track_feature(frame)
        if frame_w is None:
            frame_h, frame_w = frame.shape[:2]
        if template is None:
            bx, by, bw_n, bh_n = start_box_norm
            x0 = int(round(bx * frame_w)); y0 = int(round(by * frame_h))
            pw0 = max(8, int(round(bw_n * frame_w))); ph0 = max(8, int(round(bh_n * frame_h)))
            x0 = min(max(0, x0), frame_w - pw0); y0 = min(max(0, y0), frame_h - ph0)
            abs_t = start_t + (t if forward else -t)
            patch = frame[y0:y0 + ph0, x0:x0 + pw0]
            if patch.size == 0:
                continue
            template_t0 = patch.astype(np.float32)
            template = patch.copy()
            cx = x0 + pw0 / 2.0
            cy = y0 + ph0 / 2.0
            out.append({"t": round(abs_t, 3),
                        "x": round(x0 / frame_w, 5), "y": round(y0 / frame_h, 5),
                        "w": round(pw0 / frame_w, 5), "h": round(ph0 / frame_h, 5),
                        "conf": 1.0, "lost": False, "_fw": frame_w, "_fh": frame_h})
            continue
        abs_t = start_t + (t if forward else -t)
        zone_px = _zone_at_time(zone_args[0], zone_args[1], abs_t, frame_w, frame_h)
        found = False
        conf = 0.0
        best = None
        pw0 = template.shape[1]; ph0 = template.shape[0]
        tw = max(8, int(round(pw0 * scale))); th = max(8, int(round(ph0 * scale)))
        tmpl = cv2.resize(template, (tw, th), interpolation=cv2.INTER_AREA)
        sx0 = int(max(zone_px[0], cx - 1.5 * tw))
        sy0 = int(max(zone_px[1], cy - 1.5 * th))
        sx1 = int(min(zone_px[2], cx + 1.5 * tw))
        sy1 = int(min(zone_px[3], cy + 1.5 * th))
        sx0 = max(0, sx0); sy0 = max(0, sy0)
        sx1 = min(frame_w, sx1); sy1 = min(frame_h, sy1)
        if sx1 - sx0 >= tw and sy1 - sy0 >= th and tmpl.shape[0] <= th + 1 and tmpl.size:
            search = frame[sy0:sy1, sx0:sx1]
            scales = [0.97, 1.0, 1.03] if req.scale_search else [1.0]
            for sc in scales:
                tw_s = max(8, int(round(pw0 * scale * sc)))
                th_s = max(8, int(round(ph0 * scale * sc)))
                if tw_s >= search.shape[1] or th_s >= search.shape[0]:
                    continue
                t_s = cv2.resize(template, (tw_s, th_s), interpolation=cv2.INTER_AREA) if sc != 1.0 else tmpl
                res = cv2.matchTemplate(search, t_s, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                if best is None or max_val > best[0]:
                    best = (max_val, max_loc, tw_s, th_s, sc, res)
        if best is not None and best[0] > 0.0:
            max_val, (mlx, mly), tw_b, th_b, sc, res = best
            conf = float(max_val)
            if conf > min_conf:
                found = True
                dx = dy = 0.0
                rh, rw = res.shape
                if 0 < mlx < rw - 1:
                    l, c, r = float(res[mly, mlx - 1]), float(res[mly, mlx]), float(res[mly, mlx + 1])
                    den = l - 2.0 * c + r
                    if abs(den) > 1e-6:
                        dx = max(-0.5, min(0.5, 0.5 * (l - r) / den))
                if 0 < mly < rh - 1:
                    u, c, d = float(res[mly - 1, mlx]), float(res[mly, mlx]), float(res[mly + 1, mlx])
                    den = u - 2.0 * c + d
                    if abs(den) > 1e-6:
                        dy = max(-0.5, min(0.5, 0.5 * (u - d) / den))
                cx = sx0 + mlx + dx + tw_b / 2.0
                cy = sy0 + mly + dy + th_b / 2.0
                if req.scale_search:
                    scale = 0.8 * scale + 0.2 * (scale * sc)
                nx0 = int(max(0, cx - tw_b / 2.0)); ny0 = int(max(0, cy - th_b / 2.0))
                nx1 = int(min(frame_w, nx0 + tw_b)); ny1 = int(min(frame_h, ny0 + th_b))
                if nx1 - nx0 > 7 and ny1 - ny0 > 7 and conf > 0.92 and _patch_shape_ok(template.shape, tw_b, th_b):
                    patch = frame[ny0:ny1, nx0:nx1].astype(np.float32)
                    if template_t0 is not None:
                        t0r = cv2.resize(template_t0, (patch.shape[1], patch.shape[0]))
                        anchor_ncc = float(cv2.matchTemplate(
                            patch - patch.mean(), t0r - t0r.mean(), cv2.TM_CCOEFF_NORMED)[0, 0])
                        if anchor_ncc > 0.5:
                            template = (0.9 * template.astype(np.float32) + 0.1 * patch).astype(np.uint8)
        if found and conf > min_conf:
            found_streak += 1
            lost_streak = 0
            if lost and found_streak >= 3:
                lost = False
        else:
            found_streak = 0
            lost_streak += 1
            if not lost and lost_streak >= 3:
                lost = True
        px, py, pw_f, ph_f = _clamp_box_into_zone(
            (cx - tw / 2.0) / frame_w, (cy - th / 2.0) / frame_h,
            tw / frame_w, th / frame_h, zone_px, frame_w, frame_h)
        if not lost:
            cx = px + pw_f / 2.0
            cy = py + ph_f / 2.0
        out.append({
            "t": round(abs_t, 3),
            "x": round(px / frame_w, 5), "y": round(py / frame_h, 5),
            "w": round(pw_f / frame_w, 5), "h": round(ph_f / frame_h, 5),
            "conf": round(conf, 4), "lost": bool(lost),
            "_fw": frame_w, "_fh": frame_h,
        })
    return out


def _csrt_track_run(frames_iter, fps: float, start_box_norm: tuple, start_t: float,
                    req: TrackRequest, zone_args: tuple,
                    forward: bool = True) -> List[Dict[str, Any]]:
    """CSRT tracker on frames cropped to the zone; coordinates mapped back (§10.3)."""
    import cv2
    import numpy as np
    try:
        ctor = getattr(cv2, "TrackerCSRT", None)
        tracker = ctor.create() if ctor is not None and hasattr(ctor, "create") else cv2.TrackerCSRT_create()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"CSRT недоступен в этой сборке OpenCV: {exc}")
    frame_w = frame_h = None
    out: List[Dict[str, Any]] = []
    initialized = False
    lost = False
    for t, frame in frames_iter:
        frame = _track_feature(frame)
        if frame_w is None:
            frame_h, frame_w = frame.shape[:2]
        abs_t = start_t + (t if forward else -t)
        zone_px = _zone_at_time(zone_args[0], zone_args[1], abs_t, frame_w, frame_h)
        zx0, zy0, zx1, zy1 = [int(v) for v in zone_px]
        crop = frame[zy0:zy1, zx0:zx1]
        if crop.size == 0:
            continue
        bx, by = None, None
        ok = False
        if not initialized:
            x0 = int(round(start_box_norm[0] * frame_w)) - zx0
            y0 = int(round(start_box_norm[1] * frame_h)) - zy0
            pw0 = max(8, int(round(start_box_norm[2] * frame_w)))
            ph0 = max(8, int(round(start_box_norm[3] * frame_h)))
            bb = (max(0, x0), max(0, y0), min(pw0, crop.shape[1] - 1), min(ph0, crop.shape[0] - 1))
            if bb[2] > 7 and bb[3] > 7:
                tracker.init(crop, bb)
                initialized = True
                ok = True
        else:
            ok, bb = tracker.update(crop)
        if initialized and ok:
            x0 = zx0 + int(bb[0]); y0 = zy0 + int(bb[1])
            pw0 = max(8, int(bb[2])); ph0 = max(8, int(bb[3]))
            conf = 1.0
        else:
            x0, y0, pw0, ph0 = int(round(start_box_norm[0] * frame_w)), int(round(start_box_norm[1] * frame_h)), 8, 8
            conf = 0.0
        px, py, pw_f, ph_f = _clamp_box_into_zone(
            x0 / frame_w, y0 / frame_h, pw0 / frame_w, ph0 / frame_h, zone_px, frame_w, frame_h)
        out.append({
            "t": round(abs_t, 3),
            "x": round(px / frame_w, 5), "y": round(py / frame_h, 5),
            "w": round(pw_f / frame_w, 5), "h": round(ph_f / frame_h, 5),
            "conf": round(conf, 4), "lost": bool(initialized and not ok),
            "_fw": frame_w, "_fh": frame_h,
        })
    return out


def _track_full_range(file_path: str, req: TrackRequest) -> List[Dict[str, Any]]:
    """Plan §10.2/10.3: split [t_from, t_to] by anchor+manual keys, track each run."""
    fw_src, fh_src, _ = _probe_video_size(file_path)
    hard_keys: List[tuple] = []
    if req.target is not None:
        hard_keys.append((max(req.t_from, min(req.t_to, req.t_anchor)), req.target))
    for mk in sorted(req.manual_keys, key=lambda k: k.t):
        tk = max(req.t_from, min(req.t_to, mk.t))
        hard_keys.append((tk, Box(x=mk.x, y=mk.y, w=mk.w, h=mk.h)))
    hard_keys.sort(key=lambda k: k[0])
    if not hard_keys:
        raise HTTPException(status_code=400, detail="Нужна рамка цели (target) или manual_keys")

    fps = req.fps if req.fps and req.fps > 0 else req.sample_fps
    fps = max(2.0, min(30.0, float(fps)))
    keys: Dict[float, Dict[str, Any]] = {}

    def run_segment(t_start: float, t_end: float, box: Box, forward: bool) -> None:
        start_box_norm = (box.x, box.y, box.w, box.h)
        zone_args = (req.zone, req.zone_keys)
        it = _iter_gray_frames(file_path, min(t_start, t_end), max(t_start, t_end) + 0.0001, fps, req.analysis_width)
        if req.mode == "csrt":
            raw = _csrt_track_run(it, fps, start_box_norm, t_start, req, zone_args, forward=forward)
        else:
            raw = _ncc_track_run(it, fps, start_box_norm, t_start, req, zone_args, forward=forward)
        if raw:
            fw0 = next((k["_fw"] for k in raw if k.get("_fw")), 960)
            fh0 = next((k["_fh"] for k in raw if k.get("_fh")), 540)
            filt = {k: _OneEuro() for k in ("x", "y", "w", "h")}
            prev_t = None
            for k in raw:
                dt = 1.0 / fps if prev_t is None else max(1e-3, k["t"] - prev_t)
                prev_t = k["t"]
                px_units = {"x": k["x"] * fw0, "y": k["y"] * fh0,
                            "w": k["w"] * fw0, "h": k["h"] * fh0}
                sm = {key: filt[key](px_units[key], dt) for key in ("x", "y", "w", "h")}
                k["x"] = round(sm["x"] / fw0, 5); k["y"] = round(sm["y"] / fh0, 5)
                k["w"] = round(sm["w"] / fw0, 5); k["h"] = round(sm["h"] / fh0, 5)
            for k in raw:
                kt = round(k["t"], 3)
                existing = keys.get(kt)
                if existing and existing.get("manual"):
                    continue
                k.pop("_fw", None); k.pop("_fh", None)
                keys[kt] = k

    for i, (tk, box) in enumerate(hard_keys):
        keys[round(tk, 3)] = {"t": round(tk, 3), "x": round(box.x, 5), "y": round(box.y, 5),
                              "w": round(box.w, 5), "h": round(box.h, 5),
                              "conf": 1.0, "lost": False, "manual": True}
        t_next = hard_keys[i + 1][0] if i + 1 < len(hard_keys) else req.t_to
        if t_next - tk > 1.0 / fps:
            run_segment(tk, t_next, box, forward=True)
    t_first = hard_keys[0][0]
    if t_first - req.t_from > 1.0 / fps:
        run_segment(t_first, req.t_from, hard_keys[0][1], forward=False)
    return [keys[k] for k in sorted(keys.keys())]


def track_object_handler(req: TrackRequest, downloads_dir: str):
    """
    Track a manual target box inside a manual search zone (PLAN §10).
    Returns normalized keyframes [{t, x, y, w, h, conf, lost, manual}] in
    absolute source time (`keyframes` keeps legacy clip-relative `t`).
    """
    base_name = os.path.basename(req.filename)
    file_path = os.path.join(downloads_dir, base_name)
    if not os.path.exists(file_path):
        # studio:no-abs-paths-file (only files inside downloads/)
        raise HTTPException(status_code=404, detail=f"Медиафайл {base_name} не найден")

    if req.target is None and req.x is not None:
        req.t_from = req.start_time if req.start_time is not None else 0.0
        dur = req.duration if req.duration and req.duration > 0 else 10.0
        req.t_to = req.t_from + dur
        req.t_anchor = req.t_from
        req.target = Box(x=req.x, y=req.y, w=req.w or 0.1, h=req.h or 0.1)
        req.zone = None
    if req.target is None:
        raise HTTPException(status_code=400, detail="Не задана рамка цели (target)")
    if not (0 <= req.target.x <= 1 and 0 <= req.target.y <= 1 and 0 < req.target.w <= 1 and 0 < req.target.h <= 1):
        raise HTTPException(status_code=400, detail="Некорректная рамка цели")
    if req.t_to <= req.t_from:
        raise HTTPException(status_code=400, detail="t_to должен быть больше t_from")
    if req.mode not in ("ncc", "csrt"):
        raise HTTPException(status_code=400, detail="mode должен быть ncc или csrt")
    if req.t_anchor < req.t_from or req.t_anchor > req.t_to:
        req.t_anchor = max(req.t_from, min(req.t_to, req.t_anchor))

    try:
        keys = _track_full_range(file_path, req)
        fw_src, fh_src, _ = _probe_video_size(file_path)
        for k in keys:
            zone_px = _zone_at_time(req.zone, req.zone_keys, k["t"], fw_src, fh_src)
            px, py, pw_f, ph_f = _clamp_box_into_zone(k["x"], k["y"], k["w"], k["h"], zone_px, fw_src, fh_src)
            k["x"] = round(px / fw_src, 5); k["y"] = round(py / fh_src, 5)
            k["w"] = round(pw_f / fw_src, 5); k["h"] = round(ph_f / fh_src, 5)
        t_from = req.t_from
        legacy = [{"t": round(k["t"] - t_from, 3), "x": k["x"], "y": k["y"],
                   "w": k["w"], "h": k["h"]} for k in keys]
        return {"status": "ok", "fps": (req.fps if req.fps and req.fps > 0 else req.sample_fps),
                "mode": req.mode, "keys": keys, "keyframes": legacy}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка трекинга: {str(e)}")
