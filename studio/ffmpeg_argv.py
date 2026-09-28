"""Rewrite ffmpeg argv of the legacy export paths without touching server.py.

server.py builds its export commands inline (libx264 medium/slow, CRF 15/16,
single-pass loudnorm on the legacy path). Instead of anchoring patches in a
217 KB file, the studio layer wraps ``subprocess`` inside the loaded server
module and rewrites only final EXPORT encodes (libx264, output inside
downloads/exported_packs):

* video codec block -> ``ffmpeg_caps.h264_args(fps)`` (NVENC when usable,
  platform bitrates 8/12 Mb/s, High, yuv420p, BT.709 tags);
* optional output fps override (templates "История"/"Чистый" = 30 fps);
* legacy one-pass ``loudnorm=I=-14:TP=-1.5`` -> same targets as the layered
  path (-14 LUFS, TP -1.0, LRA 11) + the same true-peak limiter;
* "intermediate" mode (a canvas text overlay pass follows): near-lossless
  CRF 12 so the final encode happens exactly once at platform settings.

Everything here is pure (argv in -> argv out) and unit-tested.
"""
from fractions import Fraction
import os
import re

X264_OUT_OPTS_WITH_VALUE = {
    "-c:v", "-vcodec", "-codec:v", "-preset", "-crf", "-tune", "-profile:v", "-profile",
    "-level", "-level:v", "-x264-params", "-x264opts", "-g", "-keyint_min", "-bf",
    "-b:v", "-maxrate", "-minrate", "-bufsize", "-pix_fmt", "-colorspace",
    "-color_primaries", "-color_trc", "-color_range", "-qp", "-cq", "-rc",
}
LEGACY_LOUDNORM = re.compile(r"loudnorm=I=-14:TP=-1\.5(?::LRA=\d+(?:\.\d+)?)?(?![:\w])")
LOUDNORM_FIXED = "loudnorm=I=-14:TP=-1.0:LRA=11,alimiter=limit=0.891:attack=5:release=50"


def is_ffmpeg(argv):
    if not argv:
        return False
    exe = os.path.basename(str(argv[0])).lower()
    return exe in ("ffmpeg", "ffmpeg.exe") or exe.startswith("ffmpeg")


def last_input_index(argv):
    idx = -1
    for i, a in enumerate(argv[:-1]):
        if a == "-i":
            idx = i
    return idx


def output_path(argv):
    return str(argv[-1]) if argv else ""


def video_codec(argv):
    li = last_input_index(argv)
    for i in range(max(li, 0), len(argv) - 1):
        if argv[i] in ("-c:v", "-vcodec", "-codec:v"):
            return str(argv[i + 1])
    return ""


def output_fps(argv):
    li = last_input_index(argv)
    for i in range(max(li + 2, 0), len(argv) - 1):
        if argv[i] == "-r":
            return str(argv[i + 1])
    return ""


def parse_rate(value, default=60.0):
    try:
        s = str(value).strip()
        f = float(Fraction(s)) if "/" in s else float(s)
        return f if f > 0 else default
    except (ValueError, ZeroDivisionError):
        return default


def rate_string(fps):
    """30 -> '30', 29.97 -> '30000/1001' (exact NTSC rates)."""
    f = parse_rate(fps)
    for num in (24000, 30000, 60000):
        if abs(f - num / 1001.0) < 0.002:
            return f"{num}/1001"
    return str(int(round(f))) if abs(f - round(f)) < 1e-6 else f"{f:.6f}"


def is_export_encode(argv, export_dir):
    """Final export encode: ffmpeg + libx264 + output inside export_dir."""
    if not is_ffmpeg(argv) or len(argv) < 4:
        return False
    if video_codec(argv) not in ("libx264", "h264"):
        return False
    out = output_path(argv)
    if not out or out.startswith("-") or out in ("pipe:1", "-"):
        return False
    try:
        base = os.path.realpath(export_dir)
        cand = os.path.realpath(out)
        return os.path.commonpath([base, cand]) == base
    except ValueError:
        return False


def strip_video_codec_opts(argv):
    """Remove the video-encoder option block after the last input."""
    li = last_input_index(argv)
    head, tail = list(argv[:li + 2]), list(argv[li + 2:-1])
    out = []
    i = 0
    while i < len(tail):
        a = tail[i]
        if a in X264_OUT_OPTS_WITH_VALUE and i + 1 < len(tail):
            i += 2
            continue
        out.append(a)
        i += 1
    return head, out, argv[-1]


def intermediate_args():
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "12", "-pix_fmt", "yuv420p",
            "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]


def fix_loudnorm(argv):
    changed = False
    out = []
    for a in argv:
        if isinstance(a, str) and "loudnorm=I=-14:TP=-1.5" in a:
            a2 = LEGACY_LOUDNORM.sub(LOUDNORM_FIXED, a)
            changed = changed or a2 != a
            a = a2
        out.append(a)
    return out, changed


def rewrite_export(argv, *, h264_args, fps_override=None, intermediate=False):
    """Return (new_argv, info). h264_args: callable(fps) -> list."""
    argv = [str(a) for a in argv]
    info = {"codec": None, "fps": None, "loudnorm": False}
    argv, info["loudnorm"] = fix_loudnorm(argv)
    head, tail, out = strip_video_codec_opts(argv)
    src_rate = output_fps(argv)
    rate = rate_string(fps_override) if fps_override else (src_rate or "")
    fps_val = parse_rate(rate or 60)
    t2 = []
    i = 0
    while i < len(tail):
        if tail[i] == "-r" and i + 1 < len(tail):
            i += 2
            continue
        t2.append(tail[i])
        i += 1
    codec = intermediate_args() if intermediate else list(h264_args(fps_val))
    info["codec"] = codec[1]
    info["fps"] = rate or None
    extra = ["-r", rate] if rate else []
    if "-ar" not in t2 and "-an" not in t2 and any(x in t2 for x in ("-c:a", "-acodec")):
        extra += ["-ar", "48000"]
    return head + t2 + codec + extra + [out], info


def seek_audit(argv):
    """Which inputs are fast-seeked (-ss before -i)? Returns a dict."""
    res = []
    pending_ss = None
    for i, a in enumerate(argv[:-1]):
        if a == "-ss":
            pending_ss = argv[i + 1]
        elif a == "-i":
            res.append({"input": os.path.basename(str(argv[i + 1])), "ss": pending_ss})
            pending_ss = None
    graph = ""
    for i, a in enumerate(argv[:-1]):
        if a in ("-filter_complex", "-vf", "-af", "-lavfi"):
            graph += str(argv[i + 1])
    late = [float(m) for m in re.findall(r"trim=(?:start=)?([0-9.]+)", graph) if _num(m)]
    slow = [r for r in res if r["ss"] is None and not r["input"].startswith(("color", "anullsrc"))
            and late and max(late) > 30]
    return {"inputs": res, "slow_seek": bool(slow), "max_trim_start": max(late) if late else 0.0}


def _num(s):
    try:
        float(s)
        return True
    except ValueError:
        return False
