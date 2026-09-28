"""Media utilities for Kick Clip Studio (PLAN §7.1).

Provides proxy generation, RMS audio waveform extraction for UI,
sanitized export file naming, and tracker expression generation.
"""
from __future__ import annotations

import os
import subprocess
import time
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import HTTPException
from pydantic import BaseModel

from downloader import sanitize_filename


class ProxyRequest(BaseModel):
    filename: str


def make_proxy_handler(req: ProxyRequest, downloads_dir: str, proxies_dir: str):
    """960x540 GOP-10 proxy for instant scrubbing; export always uses the original."""
    base_name = os.path.basename(req.filename)
    src = os.path.join(downloads_dir, base_name)
    if not os.path.exists(src):
        raise HTTPException(status_code=404, detail=f"Медиафайл {base_name} не найден")
    os.makedirs(proxies_dir, exist_ok=True)
    out = os.path.join(proxies_dir, os.path.splitext(base_name)[0] + "_proxy.mp4")
    if os.path.exists(out) and os.path.getsize(out) > 44:
        return {"status": "ok", "proxy": os.path.basename(out), "cached": True}
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", src,
           "-vf", "scale=960:-2:flags=lanczos", "-g", "10",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
           "-an", "-movflags", "+faststart", out]
    try:
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=1800)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка создания прокси: {e}")
    if res.returncode != 0 or not os.path.exists(out):
        raise HTTPException(status_code=500, detail=f"Прокси не создан: {(res.stderr or '')[-300:]}")
    return {"status": "ok", "proxy": os.path.basename(out), "cached": False}


class WaveformRequest(BaseModel):
    filename: str
    start: float = 0.0
    duration: float = 0.0
    points: int = 600


def waveform_handler(req: WaveformRequest, downloads_dir: str):
    """RMS envelope for DISPLAY ONLY (no auto decisions, PLAN §0/§7.1)."""
    base_name = os.path.basename(req.filename)
    src = os.path.join(downloads_dir, base_name)
    if not os.path.exists(src):
        raise HTTPException(status_code=404, detail=f"Медиафайл {base_name} не найден")
    n = max(50, min(4000, int(req.points or 600)))
    cmd = ["ffmpeg", "-loglevel", "error", "-ss", str(max(0.0, req.start))]
    if req.duration and req.duration > 0:
        cmd.extend(["-t", str(req.duration)])
    cmd.extend(["-i", src, "-map", "a:0?", "-f", "f32le", "-ac", "1", "-ar", "8000", "pipe:1"])
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=120)
        buf = res.stdout
    except Exception:
        buf = b""
    if not buf:
        return {"status": "ok", "points": [0.0] * n}
    data = np.frombuffer(buf[:len(buf) // 4 * 4], dtype=np.float32)
    if data.size == 0:
        return {"status": "ok", "points": [0.0] * n}
    chunks = np.array_split(data, n)
    rms = [float(np.sqrt(np.mean(c * c)) if c.size else 0.0) for c in chunks]
    peak = max(max(rms), 1e-6)
    rms = [round(r / peak, 4) for r in rms]
    return {"status": "ok", "points": rms, "sr_points": n}


def format_export_name(template: str, ctx: Dict[str, Any]) -> str:
    """{channel}_{date}_{n}_{title}; every part sanitized, fallbacks safe."""
    tpl = template or "{channel}_{date}_{n}_{title}"
    rep = {
        "channel": sanitize_filename(str(ctx.get("channel") or "clip").replace("@", "")) or "clip",
        "date": time.strftime("%Y%m%d"),
        "n": str(int(ctx.get("n") or 1)),
        "title": sanitize_filename(str(ctx.get("title") or "short"))[:40] or "short",
    }
    out = tpl
    for k, v in rep.items():
        out = out.replace("{" + k + "}", v)
    out = "".join(c for c in out if c not in '<>:"/\\|?*')
    return out.strip(". ") or "short"


def _downsample_track_path(path: List[Dict[str, Any]], max_points: int = 18) -> List[Dict[str, Any]]:
    if len(path) <= max_points:
        return sorted(path, key=lambda p: p["t"])
    step = len(path) / max_points
    idxs = [int(i * step) for i in range(max_points - 1)] + [len(path) - 1]
    return [path[i] for i in sorted(set(idxs))]


def _build_track_expr(points: List[Dict[str, Any]], axis: str, out_w: int, out_h: int) -> str:
    """Piecewise-linear ffmpeg expression for overlay x/y from tracked keyframes."""
    if not points:
        return "0"
    vals = []
    for p in points:
        if axis == "x":
            v = (p["x"] + p["w"] / 2.0) * out_w  # center x
        else:
            v = (p["y"] + p["h"] / 2.0) * out_h  # center y
        vals.append((float(p["t"]), v))
    vals.sort(key=lambda z: z[0])
    t_last, v_last = vals[-1]

    def lerp_expr(t0: float, v0: float, t1: float, v1: float) -> str:
        if t1 - t0 < 1e-6:
            return f"{v0:.2f}"
        alpha = f"((t-{t0:.3f})/{t1 - t0:.3f})"
        return f"({v0:.2f}+({v1 - v0:.2f})*{alpha})"

    expr = f"{v_last:.2f}"
    for i in range(len(vals) - 2, -1, -1):
        t0, v0 = vals[i]
        t1, v1 = vals[i + 1]
        cur = lerp_expr(t0, v0, t1, v1)
        expr = f"if(lt(t,{t1:.3f}),{cur},{expr})"
    t_first, v_first = vals[0]
    return f"if(lt(t,{t_first:.3f}),{v_first:.2f},{expr})"
