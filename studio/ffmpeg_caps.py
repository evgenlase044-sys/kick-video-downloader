"""Cached ffmpeg capability probes + H.264 presets for Shorts."""
from __future__ import annotations

import functools
import os
import subprocess

FFMPEG = os.environ.get("STUDIO_FFMPEG", "ffmpeg")


def _run(args, timeout=20):
    return subprocess.run([FFMPEG, "-hide_banner"] + args, capture_output=True, text=True, timeout=timeout)


@functools.lru_cache(maxsize=None)
def fps_supports_source_fps() -> bool:
    try:
        r = _run(["-h", "filter=fps"])
        return "source_fps" in (r.stdout + r.stderr)
    except Exception:
        return False


@functools.lru_cache(maxsize=None)
def nvenc_available() -> bool:
    """Listed AND usable (1-frame test encode)."""
    if os.environ.get("STUDIO_ENCODER", "").lower() in ("x264", "libx264", "cpu"):
        return False
    try:
        if "h264_nvenc" not in _run(["-encoders"]).stdout:
            return False
        t = _run(["-loglevel", "error", "-f", "lavfi", "-i", "color=black:s=256x256:d=0.1",
                  "-frames:v", "1", "-c:v", "h264_nvenc", "-f", "null", "-"], timeout=30)
        return t.returncode == 0
    except Exception:
        return False


def platform_bitrate(fps: float) -> str:
    """YouTube 1080p SDR: 8 Mb/s @30, 12 Mb/s @60."""
    return "12M" if fps > 40 else "8M"


def h264_args(fps: float, gop_seconds: float = 2.0):
    br = platform_bitrate(fps)
    maxrate = "16M" if br == "12M" else "12M"
    gop = str(max(1, int(round(fps * gop_seconds))))
    if nvenc_available():
        enc = ["-c:v", "h264_nvenc", "-preset", "p5", "-tune", "hq", "-rc", "vbr",
               "-cq", "19", "-b:v", br, "-maxrate", maxrate, "-bufsize", "32M"]
    else:
        enc = ["-c:v", "libx264", "-preset", os.environ.get("STUDIO_X264_PRESET", "medium"),
               "-crf", "18", "-maxrate", maxrate, "-bufsize", "32M"]
    return enc + ["-profile:v", "high", "-pix_fmt", "yuv420p", "-g", gop,
                  "-colorspace", "bt709", "-color_primaries", "bt709",
                  "-color_trc", "bt709", "-color_range", "tv"]
