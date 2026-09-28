"""PR #9 export-side FX helpers, called from the patched server.py through
studio.server_hooks (they never import server).

* lens_punch_parts   - Lens Punch that matches the preview kernel
                        (web/core/render/lens.js lensMap): same k1 bell, same
                        auto-overscan ``norm`` (no dark corners for k1 > 0),
                        chroma shift in YUV (chromashift) instead of
                        rgbashift, which pushed the WHOLE clip through RGB.
                        Every filter is enable-gated: frames outside the
                        interval are bit-identical to the input.
* motion_blur_parts  - temporal trail (tmix, newest frame dominant) blended
                        back ONLY inside the motion interval. tmix itself
                        cannot be enable-gated (it drops frames), so it runs
                        on a branch and an enable-gated overlay picks it.
* grade_bands        - split layout: facecam band and gameplay band are
                        graded separately; the facecam band gets skin
                        protect (hsvkey mask keeps skin tones out of the LUT
                        push), the gameplay band gets the full grade.
"""
from __future__ import annotations

import math
import shutil
import subprocess
from functools import lru_cache
from typing import Any, Callable, Dict, List, Optional, Tuple

# preview bell (canvasMonitor / lens.js lensPunch): peak at 32 % of the interval
LENS_PEAK_POS = 0.32
LENS_BELL_WIDTH = 0.35
LENS_STEPS = 6


def lens_bell(p: float) -> float:
    if p <= 0.0 or p >= 1.0 + 1e-9:
        return 0.0
    return math.exp(-((p - LENS_PEAK_POS) / LENS_BELL_WIDTH) ** 2)


def lens_js_rcorner2(aspect: float) -> float:
    """rCorner^2 exactly as web/core/render/lens.js computes it (cx = cy = 0.5)."""
    return max(0.5, aspect - 0.5) ** 2 + 0.25


def lens_true_corner2(aspect: float) -> float:
    """Squared distance centre->corner in lens.js units (height = 1, x scaled by aspect)."""
    return (0.5 * aspect) ** 2 + 0.25


def lens_step_params(k1: float, aspect: float) -> Tuple[float, float]:
    """(k1 for ffmpeg lenscorrection, zoom factor) equivalent to lens.js lensMap.

    lens.js: src = c + d * (1 + k1*r^2) / norm, r in (height = 1) units,
    norm = 1 + k1*rCorner^2. ffmpeg lenscorrection normalises r so that the
    corner has r = 1, i.e. k1_ff = k1 * r_corner_true^2; the division by norm
    is a uniform magnification by ``norm`` about the centre."""
    k_ff = max(-1.0, min(1.0, k1 * lens_true_corner2(aspect)))
    norm = 1.0 + k1 * lens_js_rcorner2(aspect)
    return k_ff, norm


def lens_punch_parts(curr_v: str, tag: str, s0: float, e0: float, peak: Optional[float],
                     out_w: int, out_h: int, steps: int = LENS_STEPS) -> Tuple[List[str], str]:
    parts: List[str] = []
    d = max(1e-3, e0 - s0)
    k1p = max(-0.45, min(0.45, float(peak if peak is not None else 0.12) or 0.12))
    aspect = out_w / float(out_h)
    for si in range(steps):
        t0 = s0 + d * si / steps
        t1 = e0 if si == steps - 1 else s0 + d * (si + 1) / steps
        k = k1p * lens_bell((si + 0.5) / steps)
        if abs(k) < 0.004:
            continue
        k_ff, norm = lens_step_params(k, aspect)
        sen = f"'gte(t,{t0:.3f})*lt(t,{t1:.3f})'"
        chain = [f"lenscorrection=k1={k_ff:.5f}:k2=0:cx=0.5:cy=0.5:i=bilinear:enable={sen}"]
        if norm > 1.0005:
            # auto-overscan (lens.js `norm`): magnify by norm about the centre,
            # frame size unchanged -> the barrel's empty corners never show
            m = (1.0 - 1.0 / norm) / 2.0
            a, b = f"{m:.6f}", f"{1.0 - m:.6f}"
            chain.append(f"perspective=x0=W*{a}:y0=H*{a}:x1=W*{b}:y1=H*{a}:"
                         f"x2=W*{a}:y2=H*{b}:x3=W*{b}:y3=H*{b}:interpolation=cubic:enable={sen}")
        # CA follows k1 (preview: 3 px @1080 at the bell peak), chroma planes only
        ca = max(1, int(round(abs(k) / max(1e-6, abs(k1p)) * 3.0 * out_w / 1080.0 / 2.0)))
        chain.append(f"chromashift=cbh=-{ca}:crh={ca}:enable={sen}")
        lbl = f"[{tag}l{si}]"
        parts.append(f"{curr_v}{','.join(chain)}{lbl}")
        curr_v = lbl
    return parts, curr_v


def motion_blur_parts(curr_v: str, tag: str, t0: float, t1: float,
                      frames: int = 4) -> Tuple[List[str], str]:
    """Blend a temporal trail over [t0, t1] only (frames outside are untouched)."""
    if t1 - t0 < 1e-3:
        return [], curr_v
    n = max(2, min(8, int(frames)))
    weights = " ".join(["1"] * (n - 2) + ["2", "4"]) if n >= 3 else "1 2"
    en = f"'between(t,{t0:.4f},{t1:.4f})'"
    parts = [
        f"{curr_v}split=2[{tag}mba][{tag}mbb]",
        f"[{tag}mbb]tmix=frames={n}:weights='{weights}'[{tag}mbt]",
        f"[{tag}mba][{tag}mbt]overlay=0:0:format=auto:enable={en}[{tag}mb]",
    ]
    return parts, f"[{tag}mb]"


def zoom_blur_window(s0: float, e0: float) -> Tuple[float, float]:
    """The zoom envelope 1+a*(0.12+0.88*exp(-3*(t-s0)/d)) moves fastest right
    after the punch: blur from the punch frame to 35 % of the interval."""
    d = max(1e-3, e0 - s0)
    return s0, s0 + 0.35 * d


@lru_cache(maxsize=8)
def _have_filter(name: str) -> bool:
    exe = shutil.which("ffmpeg")
    if not exe:
        return False
    try:
        out = subprocess.run([exe, "-hide_banner", "-filters"], capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return False
    return any(line.split()[1:2] == [name] for line in out.splitlines() if len(line.split()) > 2)


def skin_protect_available() -> bool:
    return _have_filter("hsvkey")


def split_top_h(ns: Dict[str, Any]) -> int:
    """Facecam band height for the split layout, read from the caller's locals
    (server.py call sites: fmt / clip.format / req.format and top_h)."""
    fmt = ns.get("fmt")
    if not fmt:
        for k in ("clip", "req"):
            fmt = getattr(ns.get(k), "format", None)
            if fmt:
                break
    if fmt != "split_adhd":
        return 0
    try:
        return int(ns.get("top_h") or 0)
    except (TypeError, ValueError):
        return 0


def grade_bands(grade_fn: Callable[..., List[str]], src: str, dst: str, out_w: int, out_h: int,
                top_h: int, skin_protect: bool = True) -> List[str]:
    """Split layout -> grade the facecam band and the gameplay band separately.
    top_h <= 0 (not a split) -> one grade for the frame (old path)."""
    if not top_h or top_h <= 0 or top_h >= out_h:
        return grade_fn(src, dst, is_vertical=(out_w < out_h))
    t = dst.strip("[]") + "_"
    parts = [f"{src}split=2[{t}top0][{t}bot0]",
             f"[{t}top0]crop={out_w}:{top_h}:0:0[{t}top1]",
             f"[{t}bot0]crop={out_w}:{out_h - top_h}:0:{top_h}[{t}bot1]"]
    parts += grade_fn(f"[{t}bot1]", f"[{t}botg]", is_vertical=(out_w < out_h))
    if skin_protect and skin_protect_available():
        parts.append(f"[{t}top1]split=2[{t}topa][{t}topb]")
        parts += grade_fn(f"[{t}topa]", f"[{t}topg]", is_vertical=(out_w < out_h))
        # skin hues (~20 deg, moderate sat) of the GRADED band become
        # transparent -> the ungraded skin underneath shows through (soft edge)
        parts.append(f"[{t}topg]format=yuva444p,hsvkey=hue=20:sat=0.35:val=0.55:similarity=0.22:blend=0.18[{t}topk]")
        parts.append(f"[{t}topb]setparams=range=tv:colorspace=bt709:color_primaries=bt709:color_trc=bt709,"
                     f"format=gbrp[{t}topu]")
        parts.append(f"[{t}topu][{t}topk]overlay=0:0:format=gbrp[{t}topgs]")
        top = f"[{t}topgs]"
    else:
        parts += grade_fn(f"[{t}top1]", f"[{t}topg]", is_vertical=(out_w < out_h))
        top = f"[{t}topg]"
    parts.append(f"{top}[{t}botg]vstack=inputs=2,format=gbrp{dst}")
    return parts
