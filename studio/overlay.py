"""Canvas text layer -> export (audit §2 "один рендер для текста").

The browser renders the text/emoji layer with the SAME canvasText.drawCue()
the preview uses, frame by frame, into a transparent canvas and streams only
CHANGED frames as PNG over /ws/overlay/{clip_id}:

    1. JSON header {w, h, fps, frames}
    2. binary messages: uint32 LE frame index + PNG bytes (strictly increasing)
    3. JSON {"end": true}

The server stores the PNGs and an ffconcat list with exact hold durations.
After the regular export (with ASS text disabled) a single overlay pass
burns the layer on top and does the one and only platform encode.
Needs ffmpeg >= 5.0 (concat "option" directive); otherwise the export falls
back to ASS text automatically.
"""
import os
import re
import shutil
import struct
import subprocess
import tempfile
import threading
import time
from fractions import Fraction

PNG_SIG = b"\x89PNG\r\n\x1a\n"
MAX_SIDE = 3840
MAX_FRAMES = 60 * 60 * 10
MAX_FRAME_BYTES = 24 * 1024 * 1024
MAX_TOTAL_BYTES = 3 * 1024 * 1024 * 1024
TTL_S = 3 * 3600
ACK_EVERY = 8
_ID = re.compile(r"^[A-Za-z0-9_.\-]{1,96}$")

_lock = threading.Lock()
_jobs = {}


class OverlayError(ValueError):
    pass


def parse_fps(v):
    try:
        s = str(v).strip()
        fr = Fraction(s) if "/" in s else Fraction(s).limit_denominator(1001)
    except (ValueError, ZeroDivisionError):
        raise OverlayError(f"bad fps {v!r}")
    for num in (24000, 30000, 60000):
        if abs(float(fr) - num / 1001) < 0.002:
            return Fraction(num, 1001)
    if not (Fraction(1) <= fr <= Fraction(240)):
        raise OverlayError(f"fps out of range {v!r}")
    return fr


def parse_header(h):
    cid = str(h.get("clip_id") or "")
    if not _ID.match(cid):
        raise OverlayError("clip_id must match [A-Za-z0-9_.-]{1,96}")
    try:
        w, hh, frames = int(h["w"]), int(h["h"]), int(h["frames"])
    except (KeyError, TypeError, ValueError):
        raise OverlayError("header needs integer w, h, frames")
    if not (16 <= w <= MAX_SIDE and 16 <= hh <= MAX_SIDE) or w % 2 or hh % 2:
        raise OverlayError(f"bad overlay size {w}x{hh}")
    if not (1 <= frames <= MAX_FRAMES):
        raise OverlayError(f"bad frame count {frames}")
    return {"clip_id": cid, "w": w, "h": hh, "frames": frames, "fps": parse_fps(h.get("fps", 60))}


def write_concat(job_dir, indices, frames, fps):
    """ffconcat list: every stored frame held until the next stored one."""
    fps = Fraction(fps)
    rate = f"{fps.numerator}/{fps.denominator}"
    lines = ["ffconcat version 1.0"]
    idx = sorted(indices)
    if not idx or idx[0] != 0:
        raise OverlayError("frame 0 missing")
    for k, i in enumerate(idx):
        nxt = idx[k + 1] if k + 1 < len(idx) else frames
        dur = Fraction(nxt - i) / fps
        # "option framerate": image2 time base = 1/fps, so holds land on exact frames
        lines.append(f"file '{i:06d}.png'")
        lines.append(f"option framerate {rate}")
        lines.append(f"duration {float(dur):.6f}")
    lines.append(f"file '{idx[-1]:06d}.png'")
    lines.append(f"option framerate {rate}")
    path = os.path.join(job_dir, "list.ffconcat")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


def register(job):
    with _lock:
        _gc_locked()
        old = _jobs.pop(job["clip_id"], None)
        _jobs[job["clip_id"]] = job
    if old and old.get("dir") and old["dir"] != job.get("dir"):
        shutil.rmtree(old["dir"], ignore_errors=True)


def take(clip_id):
    with _lock:
        return _jobs.pop(str(clip_id), None)


def peek(clip_id):
    with _lock:
        return _jobs.get(str(clip_id))


def _gc_locked():
    now = time.time()
    for k in [k for k, j in _jobs.items() if now - j.get("created", now) > TTL_S]:
        j = _jobs.pop(k)
        shutil.rmtree(j.get("dir") or "", ignore_errors=True)


def discard(job):
    if job and job.get("dir"):
        shutil.rmtree(job["dir"], ignore_errors=True)


async def ws_overlay(ws, clip_id, *, root_dir):
    await ws.accept()
    job_dir = None
    try:
        hdr = parse_header(dict(await ws.receive_json(), clip_id=clip_id))
        os.makedirs(root_dir, exist_ok=True)
        job_dir = tempfile.mkdtemp(prefix=f"ov_{hdr['clip_id'][:24]}_", dir=root_dir)
        got, total, last = [], 0, -1
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                raise OverlayError("client disconnected")
            data = msg.get("bytes")
            if data is None:
                txt = msg.get("text") or ""
                if '"end"' in txt:
                    break
                continue
            if len(data) < 12 or data[4:12] != PNG_SIG:
                raise OverlayError("frame must be uint32 index + PNG")
            (i,) = struct.unpack("<I", data[:4])
            if i <= last or i >= hdr["frames"]:
                raise OverlayError(f"bad frame index {i}")
            if len(data) - 4 > MAX_FRAME_BYTES:
                raise OverlayError("frame too large")
            total += len(data) - 4
            if total > MAX_TOTAL_BYTES:
                raise OverlayError("overlay too large")
            with open(os.path.join(job_dir, f"{i:06d}.png"), "wb") as fh:
                fh.write(data[4:])
            got.append(i)
            last = i
            if len(got) % ACK_EVERY == 0:
                await ws.send_json({"ack": len(got)})
        if not got:
            shutil.rmtree(job_dir, ignore_errors=True)
            await ws.send_json({"ok": True, "empty": True, "frames": 0})
            return
        lst = write_concat(job_dir, got, hdr["frames"], hdr["fps"])
        register(dict(hdr, dir=job_dir, list=lst, stored=len(got), created=time.time()))
        await ws.send_json({"ok": True, "frames": hdr["frames"], "stored": len(got)})
    except Exception as exc:
        if job_dir:
            shutil.rmtree(job_dir, ignore_errors=True)
        try:
            await ws.send_json({"ok": False, "error": str(exc)})
        except Exception:
            pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass


def probe_video(path):
    import json
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,avg_frame_rate,r_frame_rate:format=duration", "-of", "json", path],
                       capture_output=True, text=True, timeout=60)
    j = json.loads(r.stdout or "{}")
    st = (j.get("streams") or [{}])[0]
    rate = st.get("avg_frame_rate") or st.get("r_frame_rate") or "60/1"
    try:
        fps = Fraction(rate) if Fraction(rate) > 0 else Fraction(60)
    except (ValueError, ZeroDivisionError):
        fps = Fraction(60)
    return {"w": int(st.get("width") or 1080), "h": int(st.get("height") or 1920), "fps": fps,
            "duration": float((j.get("format") or {}).get("duration") or 0)}


def overlay_command(video, job, out_path, codec_args, fps=None):
    v = probe_video(video)
    rate = Fraction(fps) if fps else v["fps"]
    rs = f"{rate.numerator}/{rate.denominator}"
    graph = (f"[1:v]fps={rs},format=rgba,scale={v['w']}:{v['h']}:flags=lanczos[ov];"
             f"[0:v][ov]overlay=0:0:format=auto:eof_action=pass:repeatlast=0,format=yuv420p[vout]")
    return (["ffmpeg", "-y", "-loglevel", "error", "-nostdin", "-i", video,
             "-f", "concat", "-safe", "0", "-i", job["list"],
             "-filter_complex", graph, "-map", "[vout]", "-map", "0:a?", "-c:a", "copy"]
            + list(codec_args) + ["-r", rs, "-movflags", "+faststart", out_path])


def burn_overlay(video, job, codec_args_for_fps, run=subprocess.run, timeout=3600):
    """Overlay the text layer in place. Returns (ok, message)."""
    v = probe_video(video)
    tmp = video + ".ov.mp4"
    cmd = overlay_command(video, job, tmp, codec_args_for_fps(float(v["fps"])))
    with tempfile.TemporaryFile() as err:
        try:
            r = run(cmd, stdout=subprocess.DEVNULL, stderr=err, timeout=timeout)
        except (subprocess.TimeoutExpired, OSError) as exc:
            try:
                os.remove(tmp)
            except OSError:
                pass
            return False, f"overlay ffmpeg failed: {exc}"
        err.seek(0)
        tail = err.read()[-800:].decode("utf-8", "replace")
    if r.returncode != 0 or not os.path.exists(tmp) or os.path.getsize(tmp) < 1024:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False, f"overlay ffmpeg rc={r.returncode}: {tail}"
    os.replace(tmp, video)
    return True, "ok"
