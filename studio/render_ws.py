"""/ws/render/{job_id}: raw yuv420p frames -> ffmpeg -> H.264 (protocol unchanged).

Fixes: stderr to a temp file (no pipe deadlock), apad + exact -t frames/fps
(no audio tail / early cut), exact rational fps, BT.709 tags before -i,
validated header, audio confined to downloads/exported_packs, blocking
writes in a thread (any event loop), partial file removed on abort.
"""
from __future__ import annotations

import asyncio
import os
import re
import subprocess
import tempfile
from fractions import Fraction

from studio import ffmpeg_caps

MAX_W = MAX_H = 3840
MAX_PIXELS = 3840 * 2160
MAX_FRAMES = 240 * 60 * 30
ACK_EVERY = 4


class HeaderError(ValueError):
    pass


def parse_fps(value) -> Fraction:
    try:
        fr = Fraction(value.strip()) if isinstance(value, str) and "/" in value else Fraction(str(float(value))).limit_denominator(1001)
    except (ValueError, ZeroDivisionError, TypeError):
        raise HeaderError(f"bad fps: {value!r}")
    if not (Fraction(1) <= fr <= Fraction(240)):
        raise HeaderError(f"fps out of range: {value!r}")
    for num in (24000, 30000, 60000, 120000):
        cand = Fraction(num, 1001)
        if abs(float(fr) - float(cand)) < 0.002:
            return cand
    return fr


def _safe_audio(path, roots):
    if not path:
        return None
    for root in roots:
        base = os.path.realpath(root)
        cand = os.path.realpath(path if os.path.isabs(path) else os.path.join(base, path))
        try:
            if os.path.commonpath([base, cand]) == base and os.path.isfile(cand):
                return cand
        except ValueError:
            continue
    raise HeaderError("audio_wav must be a file inside downloads/ or exported_packs/")


def parse_header(hdr, exported_dir, downloads_dir):
    try:
        w, h, frames = int(hdr["w"]), int(hdr["h"]), int(hdr["frames"])
    except (KeyError, TypeError, ValueError):
        raise HeaderError("header needs integer w, h, frames")
    if w <= 0 or h <= 0 or w % 2 or h % 2 or w > MAX_W or h > MAX_H or w * h > MAX_PIXELS:
        raise HeaderError(f"bad frame size {w}x{h} (even, <= {MAX_W}x{MAX_H})")
    if not (1 <= frames <= MAX_FRAMES):
        raise HeaderError(f"bad frame count {frames}")
    fps = parse_fps(hdr.get("fps", 60))
    out_name = os.path.basename(str(hdr.get("out") or "render.mp4"))
    out_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", out_name).strip(". ") or "render.mp4"
    if not out_name.lower().endswith(".mp4"):
        out_name += ".mp4"
    audio = _safe_audio(str(hdr.get("audio_wav") or ""), (downloads_dir, exported_dir))
    return {"w": w, "h": h, "frames": frames, "fps": fps, "out_name": out_name, "audio": audio}


def build_command(p, out_path):
    fps = p["fps"]
    rate = f"{fps.numerator}/{fps.denominator}"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-nostdin",
           "-f", "rawvideo", "-pix_fmt", "yuv420p", "-s", f"{p['w']}x{p['h']}", "-framerate", rate,
           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
           "-i", "pipe:0"]
    if p["audio"]:
        cmd += ["-i", p["audio"], "-map", "0:v:0", "-map", "1:a:0",
                "-af", "apad", "-c:a", "aac", "-b:a", "320k", "-ar", "48000"]
    else:
        cmd += ["-an"]
    # exact length = video length (no -frames:v: it closes the file before audio drains)
    cmd += ["-t", f"{float(Fraction(p['frames']) / fps):.6f}"]
    cmd += ffmpeg_caps.h264_args(float(fps))
    cmd += ["-r", rate, "-movflags", "+faststart", "-map_metadata", "-1", out_path]
    return cmd


async def ws_render(ws, job_id, *, exported_dir, downloads_dir):
    await ws.accept()
    try:
        p = parse_header(await ws.receive_json(), exported_dir, downloads_dir)
    except Exception as exc:
        try:
            await ws.send_json({"error": str(exc)})
            await ws.send_json({"done": False, "frames": 0, "returncode": -1, "file": None, "stderr": str(exc)})
        finally:
            await ws.close()
        return
    os.makedirs(exported_dir, exist_ok=True)
    out_path = os.path.join(exported_dir, p["out_name"])
    err_log = tempfile.TemporaryFile()
    proc = subprocess.Popen(build_command(p, out_path), stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=err_log)
    frame_bytes = p["w"] * p["h"] * 3 // 2
    n = 0
    aborted = False
    try:
        while n < p["frames"]:
            data = await ws.receive_bytes()
            if len(data) != frame_bytes:
                await ws.send_json({"error": f"frame {n}: got {len(data)} bytes, expected {frame_bytes}"})
                aborted = True
                break
            try:
                await asyncio.to_thread(proc.stdin.write, data)
            except (BrokenPipeError, OSError) as exc:
                await ws.send_json({"error": f"encoder stopped: {exc}"})
                aborted = True
                break
            n += 1
            if n % ACK_EVERY == 0 or n == p["frames"]:
                await ws.send_json({"ack": n})
    except Exception:
        aborted = True
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            rc = await asyncio.to_thread(proc.wait, 600)
        except Exception:
            proc.kill()
            rc = -9
        err_log.seek(0)
        tail = err_log.read()[-600:].decode("utf-8", "replace")
        err_log.close()
        done = rc == 0 and not aborted and n >= p["frames"] and os.path.exists(out_path)
        if not done and os.path.exists(out_path):
            try:
                os.remove(out_path)
            except OSError:
                pass
        try:
            await ws.send_json({"done": done, "frames": n, "returncode": rc,
                                "file": p["out_name"] if done else None, "stderr": tail})
            await ws.close()
        except Exception:
            pass
