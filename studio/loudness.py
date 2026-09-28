"""Loudness gate for EVERY exported file (audit §3 "two audio paths").

server.py has two audio paths: the layered export (separate WAV pass +
two-pass loudnorm) and the legacy filtergraph (one-pass loudnorm, and an
`alimiter` whose default auto-level can push the gain). Instead of trusting
either, every finished file is measured once (EBU R128 via loudnorm
print_format=json). Only when it is off target (|I - (-14)| > 1 LU or true
peak > -0.5 dBTP) the audio is re-rendered with a LINEAR second pass using
the measured values (= real two-pass) + a sample-peak limiter, video copied.
Silence / no audio stream -> untouched.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
from typing import Any, Dict, Optional

TARGET_I = -14.0
TARGET_TP = -1.0
TARGET_LRA = 11.0
TOL_I = 1.0
TOL_TP = 0.5


def _ln(extra: str = "") -> str:
    return f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={TARGET_LRA}{extra}"


def _json_tail(text: str) -> Optional[Dict[str, Any]]:
    end = text.rfind("}")
    start = text.rfind("{", 0, end) if end >= 0 else -1
    if start < 0:
        return None
    try:
        return json.loads(text[start:end + 1])
    except ValueError:
        return None


def _num(v) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _finite(v: Optional[float]) -> Optional[float]:
    return round(v, 2) if v is not None and math.isfinite(v) else None


def has_audio(path: str, timeout: int = 60) -> bool:
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a",
                            "-show_entries", "stream=index", "-of", "csv=p=0", path],
                           capture_output=True, text=True, timeout=timeout)
    except Exception:
        return False
    return r.returncode == 0 and bool((r.stdout or "").strip())


def measure(path: str, timeout: int = 600) -> Optional[Dict[str, Optional[float]]]:
    """EBU R128 of the first audio stream, or None (no file / no audio / error)."""
    if not os.path.isfile(path) or not has_audio(path):
        return None
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-map", "0:a:0",
                            "-af", _ln(":print_format=json"), "-f", "null", "-"],
                           capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    j = _json_tail(r.stderr or "")
    if not j:
        return None
    m = {k: _num(j.get(k)) for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")}
    return m if m["input_i"] is not None else None


def needs_fix(m: Dict[str, Optional[float]]) -> bool:
    i, tp = m.get("input_i"), m.get("input_tp")
    if i is None or not math.isfinite(i) or i < -70.0:      # silence: nothing to normalize
        return False
    return abs(i - TARGET_I) > TOL_I or (tp is not None and math.isfinite(tp) and tp > TARGET_TP + TOL_TP)


def _fix_cmd(path: str, tmp: str, m: Dict[str, Optional[float]], limiter: str):
    def v(k, d=0.0):
        x = m.get(k)
        return x if x is not None and math.isfinite(x) else d
    af = _ln(f":measured_I={v('input_i')}:measured_TP={v('input_tp')}:measured_LRA={v('input_lra')}"
             f":measured_thresh={v('input_thresh', -70.0)}:offset={v('target_offset')}:linear=true") + "," + limiter
    return ["ffmpeg", "-y", "-loglevel", "error", "-i", path,
            "-map", "0:v?", "-map", "0:a:0", "-c:v", "copy",
            "-af", af, "-ar", "48000", "-c:a", "aac", "-b:a", "256k",
            "-map_metadata", "0", "-movflags", "+faststart", tmp]


def apply_fix(path: str, m: Dict[str, Optional[float]], timeout: int = 900) -> bool:
    root, ext = os.path.splitext(path)
    tmp = f"{root}.loudtmp{ext or '.mp4'}"
    # level=0: no auto-level (ffmpeg >= 4.4 enables it by default and it re-gains the signal)
    for limiter in ("alimiter=limit=0.891:attack=5:release=50:level=0",
                    "alimiter=limit=0.891:attack=5:release=50"):
        try:
            r = subprocess.run(_fix_cmd(path, tmp, m, limiter), stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE, text=True, timeout=timeout)
            if r.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 1024:
                os.replace(tmp, path)
                return True
        except Exception:
            pass
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
    return False


def ensure(path: str) -> Dict[str, Any]:
    """Measure; fix when off target. JSON-safe result (no inf/nan)."""
    m = measure(path)
    if m is None:
        return {"checked": False}
    info: Dict[str, Any] = {"checked": True, "input_i": _finite(m["input_i"]),
                            "input_tp": _finite(m["input_tp"]), "fixed": False,
                            "target_i": TARGET_I, "target_tp": TARGET_TP}
    if needs_fix(m):
        info["fixed"] = apply_fix(path, m)
        if info["fixed"]:
            m2 = measure(path)
            if m2:
                info["output_i"] = _finite(m2["input_i"])
                info["output_tp"] = _finite(m2["input_tp"])
        else:
            info["error"] = "loudness fix failed; file left as rendered"
    return info
