import os
import sys
import time
import json
import asyncio
import threading
import subprocess
import shutil
from typing import Dict, Any, Optional, List

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from pydantic import BaseModel

from kick_extractor import KickExtractor
from size_calculator import SizeCalculator
from disk_manager import DiskManager, format_bytes
from downloader import KickDownloader, sanitize_filename

# Ensure clean UTF-8 console output
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure Windows Fontconfig for FFmpeg libass subtitles support.
# Project fonts (viral display faces with Cyrillic) ship in ./fonts via a
# local fonts.conf so no admin install into C:\Windows\Fonts is needed.
FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
os.environ["FONTCONFIG_PATH"] = FONTS_DIR
try:
    import tempfile
    _fc_cache = os.path.join(tempfile.gettempdir(), "fontconfig-cache")
    os.makedirs(_fc_cache, exist_ok=True)
    _conf_xml = f"""<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <dir>{FONTS_DIR}</dir>
  <dir>C:\\Windows\\Fonts</dir>
  <cachedir>{_fc_cache}</cachedir>
</fontconfig>
"""
    with open(os.path.join(FONTS_DIR, "fonts.conf"), "w", encoding="utf-8") as _fconf:
        _fconf.write(_conf_xml)
except Exception:
    pass

import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load environment variables from .env if present
_env_file = os.path.join(BASE_DIR, ".env")
if os.path.exists(_env_file):
    try:
        with open(_env_file, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    os.environ.setdefault(_k.strip(), _v.strip().strip("'\""))
    except Exception:
        pass

DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
THUMBS_DIR = os.path.join(DOWNLOADS_DIR, ".thumbs")
EXPORTED_PACKS_DIR = os.path.join(DOWNLOADS_DIR, "exported_packs")
SFX_DIR = os.path.join(BASE_DIR, "sfx")
WEB_DIR = os.path.join(BASE_DIR, "web")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
os.makedirs(THUMBS_DIR, exist_ok=True)
os.makedirs(EXPORTED_PACKS_DIR, exist_ok=True)
os.makedirs(SFX_DIR, exist_ok=True)
os.makedirs(WEB_DIR, exist_ok=True)

app = FastAPI(title="Kick Video Studio", version="2.0.0")

extractor = KickExtractor(BASE_DIR)
calculator = SizeCalculator()
disk_manager = DiskManager(DOWNLOADS_DIR)

# Global download state
state_lock = threading.Lock()
download_state = {
    "status": "idle", # idle, probing, downloading, merging, completed, error, cancelled
    "message": "",
    "url": "",
    "title": "",
    "quality_label": "",
    "completed_segments": 0,
    "total_segments": 0,
    "downloaded_bytes": 0,
    "downloaded_formatted": "0 B",
    "total_bytes": 0,
    "total_formatted": "0 B",
    "percent": 0.0,
    "speed_formatted": "0 B/s",
    "eta_formatted": "--:--",
    "elapsed_seconds": 0,
    "output_file": "",
}

current_downloader: Optional[KickDownloader] = None
download_thread: Optional[threading.Thread] = None

class ProbeRequest(BaseModel):
    url: str

class CheckDiskRequest(BaseModel):
    required_bytes: int

class DownloadRequest(BaseModel):
    url: str
    playlist_url: str
    quality_label: str
    title: str
    streamer: str
    required_bytes: int
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    trim_offset: Optional[float] = None
    trim_duration: Optional[float] = None

def format_range_suffix(start: float, end: float) -> str:
    def mmss(sec: float) -> str:
        s = max(0, int(sec))
        return f"{s // 60:02d}{s % 60:02d}"
    return f"_part_{mmss(start)}-{mmss(end)}"

@app.get("/api/disk-info")
def get_disk_info():
    """Get current free/total disk space information."""
    return disk_manager.get_disk_info()

@app.post("/api/check-disk")
def check_disk(req: CheckDiskRequest):
    """
    Check if disk has enough free space for the requested size.
    Returns status, shortage, and clear messages if space is insufficient.
    """
    return disk_manager.check_space(req.required_bytes)

@app.post("/api/probe")
def probe_video(req: ProbeRequest):
    """
    Extract video info, available streams, and calculate real sizes for each stream.
    Also provides pre-calculated disk space checks for each option.
    """
    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="Укажите корректную ссылку на видео Kick.com")

    try:
        video_info = extractor.extract(req.url.strip())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка извлечения видео: {str(e)}")

    # Calculate sizes for each quality tier
    qualities_with_size = []
    disk_info = disk_manager.get_disk_info()
    # Size sampling must send the same UA + cookies as the page fetch,
    # otherwise the CDN rejects HEAD requests and sizes fall back to rough bitrate estimates.
    try:
        calc = SizeCalculator(headers=extractor.get_size_headers())
    except Exception:
        calc = calculator

    for q in video_info["qualities"]:
        size_res = calc.calculate_stream_size(
            q["playlist_url"],
            q["bandwidth"],
            video_info["duration"]
        )
        space_check = disk_manager.check_space(size_res["estimated_bytes"])

        qualities_with_size.append({
            "label": q["label"],
            "resolution": q["resolution"],
            "fps": q["fps"],
            "bandwidth": q["bandwidth"],
            "playlist_url": q["playlist_url"],
            "size": size_res,
            "space_check": space_check,
            "is_source": False
        })

    # Identify if a stream (like 720p60) is the uncompressed source stream (highest bitrate)
    if qualities_with_size:
        max_bitrate = max(item["size"]["bitrate_kbps"] for item in qualities_with_size)
        for item in qualities_with_size:
            if item["size"]["bitrate_kbps"] == max_bitrate and len(qualities_with_size) > 1 and item != qualities_with_size[0]:
                item["is_source"] = True

    return {
        "url": video_info["url"],
        "title": video_info["title"],
        "streamer": video_info["streamer"],
        "duration": video_info["duration"],
        "duration_str": video_info["duration_str"],
        "thumbnail": video_info["thumbnail"],
        "master_m3u8": video_info["master_m3u8"],
        "qualities": qualities_with_size,
        "disk_info": disk_info
    }

def _run_download_task(req: DownloadRequest, segments: list):
    global current_downloader, download_state

    suffix = ""
    if req.start_time is not None and req.end_time is not None:
        suffix = format_range_suffix(req.start_time, req.end_time)
    clean_title = sanitize_filename(f"{req.streamer}_{req.title}_{req.quality_label}{suffix}")
    output_filename = f"{clean_title}.mp4"

    def on_progress(p_data: Dict[str, Any]):
        with state_lock:
            download_state.update(p_data)
            download_state["title"] = req.title
            download_state["quality_label"] = req.quality_label

    downloader = KickDownloader(output_dir=DOWNLOADS_DIR)
    with state_lock:
        current_downloader = downloader
        download_state["status"] = "downloading"
        download_state["output_file"] = os.path.join(DOWNLOADS_DIR, output_filename)

    try:
        final_path = downloader.download_stream(
            segment_urls=segments,
            output_filename=output_filename,
            estimated_total_bytes=req.required_bytes,
            progress_callback=on_progress
        )
        # Precise fragment trim (stream copy, no re-encode): cut head slack
        # so the file matches the requested [start, end) range closely.
        if req.trim_offset is not None and req.trim_duration:
            trimmed_path = final_path + ".trim.mp4"
            trim_cmd = [
                "ffmpeg", "-y",
                "-ss", str(round(req.trim_offset, 3)),
                "-t", str(round(req.trim_duration, 3)),
                "-i", final_path,
                "-c", "copy",
                "-movflags", "+faststart",
                trimmed_path
            ]
            try:
                trim_res = subprocess.run(
                    trim_cmd, stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE, text=True, timeout=120
                )
                if trim_res.returncode == 0 and os.path.exists(trimmed_path) \
                        and os.path.getsize(trimmed_path) > 0:
                    os.replace(trimmed_path, final_path)
                else:
                    if os.path.exists(trimmed_path):
                        os.remove(trimmed_path)
            except Exception:
                pass
        with state_lock:
            download_state["status"] = "completed"
            download_state["output_file"] = final_path
            download_state["percent"] = 100.0
            download_state["message"] = f"Видео успешно загружено: {os.path.basename(final_path)}"
        # Generate thumbnail immediately
        try:
            get_or_generate_thumbnail(final_path)
        except Exception:
            pass
    except KeyboardInterrupt:
        with state_lock:
            download_state["status"] = "cancelled"
            download_state["message"] = "Загрузка отменена пользователем."
    except PermissionError as pe:
        with state_lock:
            download_state["status"] = "error"
            download_state["message"] = str(pe)
    except Exception as e:
        with state_lock:
            download_state["status"] = "error"
            download_state["message"] = f"Ошибка скачивания: {str(e)}"
    finally:
        with state_lock:
            current_downloader = None

@app.post("/api/start-download")
def start_download(req: DownloadRequest):
    """
    Start downloading the video in the requested quality.
    STRICTLY checks disk space first. If space is not enough, rejects with 400!
    """
    global download_state, download_thread, current_downloader

    with state_lock:
        if download_state["status"] in ("downloading", "merging"):
            raise HTTPException(status_code=409, detail="Уже выполняется загрузка другого видео.")

    # 1. Resolve segment list: whole VOD or [start_time, end_time) slice
    want_range = req.start_time is not None and req.end_time is not None
    try:
        if want_range:
            detailed, _ = calculator.fetch_playlist_segments_detailed(req.playlist_url)
            segments, range_dur, total_dur, range_start = SizeCalculator.slice_range(
                detailed, req.start_time, req.end_time
            )
            # Precise post-trim: skip the slack before the requested start
            offset = req.start_time - range_start
            if offset > 0.3:
                req.trim_offset = offset
                req.trim_duration = req.end_time - req.start_time
            # Scale size estimate down to the fragment
            if total_dur > 0:
                req.required_bytes = max(
                    1024, int(req.required_bytes * (range_dur / total_dur))
                )
        else:
            segments, _ = calculator.fetch_playlist_segments(req.playlist_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Не удалось получить список сегментов потока: {e}")

    if not segments:
        raise HTTPException(status_code=400, detail="Суб-плейлист не содержит сегментов для скачивания.")

    # 2. STRICT DISK SPACE VALIDATION (fragment-aware)
    space_check = disk_manager.check_space(req.required_bytes)
    if not space_check["is_enough"]:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INSUFFICIENT_SPACE",
                "message": space_check["message"],
                "shortage": space_check["shortage_formatted"],
                "free": space_check["free_formatted"],
                "required": space_check["required_formatted"],
                "drive": space_check["drive"]
            }
        )

    # Reset state
    with state_lock:
        download_state = {
            "status": "starting",
            "message": "Подготовка к загрузке...",
            "url": req.url,
            "title": req.title,
            "quality_label": req.quality_label,
            "completed_segments": 0,
            "total_segments": len(segments),
            "downloaded_bytes": 0,
            "downloaded_formatted": "0 B",
            "total_bytes": req.required_bytes,
            "total_formatted": format_bytes(req.required_bytes),
            "percent": 0.0,
            "speed_formatted": "0 B/s",
            "eta_formatted": "--:--",
            "elapsed_seconds": 0,
            "output_file": "",
        }

    # Launch background thread
    download_thread = threading.Thread(
        target=_run_download_task,
        args=(req, segments),
        daemon=True
    )
    download_thread.start()

    return {"status": "started", "segments_count": len(segments)}

@app.post("/api/cancel-download")
def cancel_download():
    """Cancel active download."""
    global current_downloader
    with state_lock:
        if current_downloader:
            current_downloader.cancel()
            download_state["status"] = "cancelled"
            download_state["message"] = "Отмена запрошена..."
            return {"status": "cancelling"}
    return {"status": "idle"}

@app.get("/api/progress")
async def progress_stream():
    """SSE endpoint for live real-time download progress."""
    async def event_generator():
        while True:
            with state_lock:
                data = dict(download_state)
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

def format_duration_str(seconds: float) -> str:
    s = int(seconds)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"

def get_or_generate_thumbnail(video_path: str) -> Optional[str]:
    if not os.path.exists(video_path):
        return None
    base_name = os.path.basename(video_path)
    thumb_name = f"{base_name}.jpg"
    thumb_path = os.path.join(THUMBS_DIR, thumb_name)
    if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
        return thumb_path
    try:
        cmd = [
            "ffmpeg", "-y", "-ss", "00:00:01", "-i", video_path,
            "-vframes", "1", "-vf", "scale=360:-1", "-q:v", "3", thumb_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=12)
        if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
            return thumb_path
    except Exception as e:
        print(f"Error generating thumbnail for {base_name}: {e}")
    return None

def probe_media_file(video_path: str) -> Dict[str, Any]:
    duration = 0.0
    width = 1920
    height = 1080
    fps = 60
    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", video_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if res.returncode == 0 and res.stdout:
            data = json.loads(res.stdout)
            format_info = data.get("format", {})
            duration = float(format_info.get("duration", 0) or 0)
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    width = int(stream.get("width") or 1920)
                    height = int(stream.get("height") or 1080)
                    r_frame_rate = stream.get("r_frame_rate", "60/1")
                    if "/" in r_frame_rate:
                        num, den = r_frame_rate.split("/")
                        if int(den) > 0:
                            fps = round(int(num) / int(den))
                    break
    except Exception as e:
        print(f"Error probing {video_path}: {e}")
    return {
        "duration": duration,
        "duration_str": format_duration_str(duration),
        "width": width,
        "height": height,
        "fps": fps
    }

class ImportMediaRequest(BaseModel):
    path: str

class DeleteMediaRequest(BaseModel):
    filename: str

class PrepareImageRequest(BaseModel):
    filename: str
    duration: float = 5.0


@app.post("/api/prepare-image")
def prepare_image(req: PrepareImageRequest):
    """Convert a library image into a timeline-ready video clip (looped still)."""
    base = os.path.basename(req.filename)
    src = os.path.join(DOWNLOADS_DIR, base)
    if not os.path.exists(src):
        raise HTTPException(status_code=404, detail="Image not found")
    dur = max(1.0, min(60.0, float(req.duration or 5.0)))
    stem = os.path.splitext(base)[0]
    out_name = f"{sanitize_filename(stem)}_still_{int(dur)}s.mp4"
    out_path = os.path.join(DOWNLOADS_DIR, out_name)
    if not os.path.exists(out_path):
        r = subprocess.run(
            ["ffmpeg", "-y", "-loop", "1", "-framerate", "30", "-i", src,
             "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={dur:.2f}",
             "-t", f"{dur:.2f}",
             "-vf", "scale='min(1920,iw)':-2:flags=lanczos+accurate_rnd,scale=trunc(iw/2)*2:trunc(ih/2)*2",
             "-c:v", "libx264", "-preset", "medium", "-crf", "12", "-pix_fmt", "yuv420p",
             "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
             "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", "-shortest",
             out_path],
            capture_output=True, text=True, timeout=120,
        )
        if r.returncode != 0 or not os.path.exists(out_path):
            raise HTTPException(status_code=500, detail="Image conversion failed")
    meta = probe_media_file(out_path)
    return {
        "filename": out_name,
        "kind": "video",
        "title": os.path.splitext(out_name)[0],
        "size_bytes": os.path.getsize(out_path),
        "duration": meta["duration"],
        "duration_str": meta["duration_str"],
        "width": meta["width"],
        "height": meta["height"],
        "fps": meta["fps"],
        "stream_url": f"/api/media/stream?file={out_name}",
        "thumb_url": f"/api/media/thumb?file={base}",
    }


@app.get("/api/media/library")
def get_media_library():
    """Returns list of all video/audio/image files available in the project media library."""
    supported_exts = {".mp4", ".ts", ".mkv", ".mov", ".webm"}
    audio_exts = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"}
    image_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    items = []
    if not os.path.exists(DOWNLOADS_DIR):
        return items

    for fname in sorted(os.listdir(DOWNLOADS_DIR)):
        if fname.startswith("."):
            continue
        fpath = os.path.join(DOWNLOADS_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        ext = os.path.splitext(fname)[1].lower()
        if ext not in supported_exts and ext not in audio_exts and ext not in image_exts:
            continue

        size_bytes = os.path.getsize(fpath)
        mtime = os.path.getmtime(fpath)
        kind = "audio" if ext in audio_exts else ("image" if ext in image_exts else "video")
        if kind == "image":
            meta = {"duration": 5.0, "duration_str": "0:05", "width": None, "height": None, "fps": None}
            has_thumb = True
            thumb_url = f"/api/media/thumb?file={fname}"
        else:
            meta = probe_media_file(fpath)
            thumb_file = get_or_generate_thumbnail(fpath) if kind == "video" else None
            has_thumb = bool(thumb_file and os.path.exists(thumb_file))
            thumb_url = f"/api/media/thumb?file={fname}" if has_thumb else None

        items.append({
            "filename": fname,
            "kind": kind,
            "title": os.path.splitext(fname)[0],
            "size_bytes": size_bytes,
            "size_formatted": format_bytes(size_bytes),
            "mtime": mtime,
            "duration": meta["duration"],
            "duration_str": meta["duration_str"],
            "width": meta["width"],
            "height": meta["height"],
            "fps": meta["fps"],
            "stream_url": f"/api/media/stream?file={fname}",
            "thumb_url": thumb_url
        })

    return sorted(items, key=lambda x: x["mtime"], reverse=True)

# Real recorded SFX library (files in ./sfx)
SFX_FILES = {
    "click": "camera_click.mp3",
    "camera_click": "camera_click.mp3",
    "camera": "camera_click.mp3",
    "shutter": "camera_click.mp3",
    "click_hard": "camera_click_hard.mp3",
    "approve": "ding_positive.mp3",
    "ding": "ding_positive.mp3",
    "cancel": "fail_buzz.mp3",
    "fail": "fail_buzz.mp3",
    "buzz": "fail_buzz.mp3",
    "pop": "pop_game.mp3",
    "pop_light": "pop_light.mp3",
    "whoosh": "whoosh_fast.mp3",
    "whoosh_fast": "whoosh_fast.mp3",
    "whoosh_cinematic": "whoosh_cinematic.mp3",
    "magic": "whoosh_magic.mp3",
    "boom": "impact_epic.mp3",
    "impact": "impact_epic.mp3",
    "hit": "hit_small.mp3",
    "cheer": "cheer_crowd.mp3",
    "cheer_big": "cheer_victory.mp3",
    "applause": "applause.mp3",
    "laugh": "laugh_crowd.mp3",
    "laugh_big": "laugh_big.mp3",
    "levelup": "level_complete.mp3",
    "coin": "coin_win.mp3",
}
SFX_LABELS = {
    "click": "Щелчок камеры", "camera_click": "Щелчок камеры", "click_hard": "Жёсткий щелчок",
    "approve": "Динг (аппрув)", "ding": "Динг (аппрув)",
    "cancel": "Баззер (фейл)", "fail": "Баззер (фейл)", "buzz": "Баззер (фейл)",
    "pop": "Поп", "pop_light": "Лёгкий поп",
    "whoosh": "Вуш быстрый", "whoosh_fast": "Вуш быстрый", "whoosh_cinematic": "Вуш кинематик",
    "magic": "Магия-спаркл", "boom": "Эпик-импакт", "impact": "Эпик-импакт", "hit": "Удар",
    "cheer": "Улюлюкания толпы", "cheer_big": "Рёв толпы (победа)",
    "applause": "Овации", "laugh": "Смех толпы", "laugh_big": "Громкий смех",
    "levelup": "Левел-ап", "coin": "Монетка",
}

@app.get("/api/sfx/list")
def list_sfx():
    """Available real SFX for flash/FX elements and the library."""
    out = []
    for kind, fn in SFX_FILES.items():
        if os.path.exists(os.path.join(SFX_DIR, fn)):
            out.append({"id": kind, "name": SFX_LABELS.get(kind, kind), "file": fn})
    return out

@app.get("/api/sfx/{sfxfile}")
def get_sfx_file(sfxfile: str):
    safe = os.path.basename(sfxfile)
    path = os.path.join(SFX_DIR, safe)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="SFX not found")
    return FileResponse(path, media_type="audio/mpeg",
                        headers={"Cache-Control": "public, max-age=86400"})

@app.get("/api/fonts/{fontfile}")
def get_font_file(fontfile: str):
    """Serve bundled display fonts for the web preview (@font-face)."""
    safe = os.path.basename(fontfile)
    path = os.path.join(FONTS_DIR, safe)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Font not found")
    return FileResponse(path, media_type="font/ttf",
                        headers={"Cache-Control": "public, max-age=86400"})

@app.get("/api/media/thumb")
def get_media_thumbnail(file: str):
    base_name = os.path.basename(file)
    if os.path.splitext(base_name)[1].lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
        img_path = os.path.join(DOWNLOADS_DIR, base_name)
        if os.path.exists(img_path):
            return FileResponse(img_path)
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    thumb_path = os.path.join(THUMBS_DIR, f"{base_name}.jpg")
    if not os.path.exists(thumb_path):
        video_path = os.path.join(DOWNLOADS_DIR, base_name)
        thumb_path = get_or_generate_thumbnail(video_path)
    if thumb_path and os.path.exists(thumb_path):
        return FileResponse(thumb_path, media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="Thumbnail not found")

@app.get("/api/media/stream")
def stream_media_file(file: str, request: Request):
    """
    Stream media files with HTTP 206 Partial Content (Range requests)
    for instant seeking and low-latency playback in HTML5 video and timelines.
    """
    base_name = os.path.basename(file)
    file_path = os.path.join(DOWNLOADS_DIR, base_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Медиафайл {base_name} не найден")

    file_size = os.path.getsize(file_path)
    range_header = request.headers.get("range")

    content_type = "video/mp4"
    if base_name.endswith(".webm"):
        content_type = "video/webm"
    elif base_name.endswith(".ts"):
        content_type = "video/mp2t"

    if range_header:
        # e.g. "bytes=1048576-" or "bytes=0-1048576"
        range_val = range_header.replace("bytes=", "").strip()
        parts = range_val.split("-")
        start = int(parts[0]) if parts[0] else 0
        chunk_max = 4 * 1024 * 1024 # 4MB chunk size
        if len(parts) > 1 and parts[1]:
            end = int(parts[1])
        else:
            end = min(start + chunk_max - 1, file_size - 1)
        end = min(end, file_size - 1)
        content_length = (end - start) + 1

        def iter_file():
            with open(file_path, "rb") as f:
                f.seek(start)
                bytes_left = content_length
                buf_size = 64 * 1024
                while bytes_left > 0:
                    chunk = f.read(min(buf_size, bytes_left))
                    if not chunk:
                        break
                    bytes_left -= len(chunk)
                    yield chunk

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Type": content_type,
        }
        return StreamingResponse(iter_file(), status_code=206, headers=headers)
    else:
        return FileResponse(file_path, media_type=content_type, headers={"Accept-Ranges": "bytes"})

@app.post("/api/media/import")
def import_media(req: ImportMediaRequest):
    """Import an existing video from local path into the library."""
    src = req.path.strip().strip('"').strip("'")
    if not os.path.exists(src) or not os.path.isfile(src):
        raise HTTPException(status_code=400, detail="Указанный файл не существует")

    dest_name = os.path.basename(src)
    dest_path = os.path.join(DOWNLOADS_DIR, dest_name)

    if os.path.abspath(src) != os.path.abspath(dest_path):
        try:
            shutil.copy2(src, dest_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка копирования: {e}")

    get_or_generate_thumbnail(dest_path)
    meta = probe_media_file(dest_path)
    return {"status": "imported", "filename": dest_name, "meta": meta}

@app.post("/api/media/upload")
async def upload_media(request: Request):
    """Browser file upload (multipart FormData) into the library. Works without Electron file.path."""
    try:
        form = await request.form()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Не удалось прочитать форму: {e}")
    up = form.get("file")
    if up is None:
        raise HTTPException(status_code=400, detail="Файл не передан")
    filename = sanitize_filename(getattr(up, "filename", "upload.mp4") or "upload.mp4")
    if not os.path.splitext(filename)[1]:
        filename += ".mp4"
    dest_path = os.path.join(DOWNLOADS_DIR, filename)
    try:
        content = await up.read()
        if not content:
            raise HTTPException(status_code=400, detail="Пустой файл")
        with open(dest_path, "wb") as f:
            f.write(content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения: {e}")
    get_or_generate_thumbnail(dest_path)
    meta = probe_media_file(dest_path)
    return {"status": "imported", "filename": filename, "meta": meta}

@app.delete("/api/media/delete")
def delete_media(req: DeleteMediaRequest):
    base_name = os.path.basename(req.filename)
    fpath = os.path.join(DOWNLOADS_DIR, base_name)
    if os.path.exists(fpath):
        try:
            os.remove(fpath)
            tpath = os.path.join(THUMBS_DIR, f"{base_name}.jpg")
            if os.path.exists(tpath):
                os.remove(tpath)
            return {"status": "deleted", "filename": base_name}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Не удалось удалить файл: {e}")
    raise HTTPException(status_code=404, detail="Файл не найден")

# ── Groq Whisper Cloud Auto-Transcription ───────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
DEFAULT_SPEECH_PROMPT = "Разговорная речь, видеоблог, нарезка, мемы, стрим, сленг, TikTok, YouTube Shorts, Reels, субтитры. Четкая пунктуация, заглавные буквы, эмоциональная интонация."

class TranscribeRequest(BaseModel):
    filename: str
    start_time: float = 0.0
    duration: Optional[float] = None
    language: Optional[str] = None
    prompt: Optional[str] = None
    model: str = "whisper-large-v3-turbo"

def build_segments_from_words(words: List[Dict[str, Any]], base_offset: float = 0.0) -> List[Dict[str, Any]]:
    segments = []
    if not words:
        return segments

    current_words = []
    segment_id = 0

    for w in words:
        should_split = False
        if current_words:
            pause = w["start"] - current_words[-1]["end"]
            count = len(current_words)
            dur = w["end"] - current_words[0]["start"]
            last_word = current_words[-1]["word"].strip()
            if (
                pause > 0.35
                or count >= 3
                or dur >= 1.5
                or last_word.endswith(('.', '?', '!', '...'))
            ):
                should_split = True

        if should_split and current_words:
            start = current_words[0]["start"]
            end = current_words[-1]["end"]
            seg_text = " ".join(item["word"].strip() for item in current_words)
            segments.append({
                "id": segment_id,
                "start": round(start, 3),
                "end": round(end, 3),
                "abs_start": round(start + base_offset, 3),
                "abs_end": round(end + base_offset, 3),
                "text": seg_text,
                "words": list(current_words)
            })
            segment_id += 1
            current_words = []

        current_words.append(w)

    if current_words:
        start = current_words[0]["start"]
        end = current_words[-1]["end"]
        seg_text = " ".join(item["word"].strip() for item in current_words)
        segments.append({
            "id": segment_id,
            "start": round(start, 3),
            "end": round(end, 3),
            "abs_start": round(start + base_offset, 3),
            "abs_end": round(end + base_offset, 3),
            "text": seg_text,
            "words": list(current_words)
        })

    return segments

@app.post("/api/transcribe")
def transcribe_media(req: TranscribeRequest):
    """
    Server-side speech recognition using Groq Whisper API (whisper-large-v3-turbo).
    Returns word-level timestamps and smart subtitle segments.
    NO local heavy neural networks used.
    """
    base_name = os.path.basename(req.filename)
    file_path = os.path.join(DOWNLOADS_DIR, base_name)
    if not os.path.exists(file_path):
        if os.path.exists(req.filename):
            file_path = req.filename
        else:
            raise HTTPException(status_code=404, detail=f"Медиафайл {base_name} не найден")

    # Extract lightweight mono 16kHz audio slice via FFmpeg
    temp_id = int(time.time() * 1000)
    temp_audio = os.path.join(DOWNLOADS_DIR, f"temp_transcribe_{temp_id}.mp3")

    cmd = ["ffmpeg", "-y", "-ss", str(max(0.0, req.start_time))]
    if req.duration and req.duration > 0:
        cmd.extend(["-t", str(req.duration)])
    cmd.extend([
        "-i", file_path,
        "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k",
        "-f", "mp3", temp_audio
    ])

    try:
        sub_res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=60)
        if sub_res.returncode != 0 or not os.path.exists(temp_audio) or os.path.getsize(temp_audio) == 0:
            err_msg = sub_res.stderr[-200:] if sub_res.stderr else "Empty audio"
            raise HTTPException(status_code=500, detail=f"Ошибка извлечения аудиодорожки: {err_msg}")
    except Exception as e:
        if os.path.exists(temp_audio):
            os.remove(temp_audio)
        raise HTTPException(status_code=500, detail=f"FFmpeg ошибка: {str(e)}")

    # Send to Groq Whisper API
    if not GROQ_API_KEY:
        if os.path.exists(temp_audio):
            os.remove(temp_audio)
        raise HTTPException(status_code=400, detail="GROQ_API_KEY не задан в .env или переменных окружения")

    try:
        with open(temp_audio, "rb") as f:
            files = {"file": (os.path.basename(temp_audio), f, "audio/mpeg")}
            data = {
                "model": req.model or "whisper-large-v3-turbo",
                "response_format": "verbose_json",
                "timestamp_granularities[]": "word",
                "temperature": "0.0",
                "prompt": req.prompt or DEFAULT_SPEECH_PROMPT
            }
            if req.language:
                data["language"] = req.language

            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "User-Agent": "Corsica-General-Server/1.0"
            }

            resp = requests.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                files=files,
                data=data,
                headers=headers,
                timeout=90
            )

        if resp.status_code != 200:
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"Ошибка Groq API ({resp.status_code}): {resp.text}"
            )

        result_data = resp.json()
        raw_words = result_data.get("words", [])
        clean_words = []
        for w in raw_words:
            word_str = w.get("word", "").strip()
            if word_str:
                start_sec = float(w.get("start", 0.0))
                end_sec = float(w.get("end", 0.0))
                clean_words.append({
                    "word": word_str,
                    "start": round(start_sec, 3),
                    "end": round(end_sec, 3),
                    "abs_start": round(start_sec + req.start_time, 3),
                    "abs_end": round(end_sec + req.start_time, 3),
                })

        segments = build_segments_from_words(clean_words, base_offset=req.start_time)

        return {
            "status": "ok",
            "text": result_data.get("text", "").strip(),
            "language": result_data.get("language", "auto"),
            "duration": result_data.get("duration", 0.0),
            "words": clean_words,
            "segments": segments,
            "start_offset": req.start_time
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка транскрибации: {str(e)}")
    finally:
        if os.path.exists(temp_audio):
            try:
                os.remove(temp_audio)
            except Exception:
                pass

# ── Object Tracking (template-matching tracker over ffmpeg-extracted frames) ──
class TrackObjectRequest(BaseModel):
    filename: str
    start_time: float = 0.0
    duration: Optional[float] = None
    x: float  # normalized 0..1, search box top-left
    y: float
    w: float
    h: float
    sample_fps: float = 12.0

def _extract_tracking_frames(video_path: str, start_time: float, duration: Optional[float],
                             fps: float, out_dir: str, max_w: int = 640) -> int:
    os.makedirs(out_dir, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-ss", str(max(0.0, start_time))]
    if duration and duration > 0:
        cmd.extend(["-t", str(duration)])
    cmd.extend([
        "-i", video_path,
        "-vf", f"fps={fps},scale='min({max_w},iw)':-2",
        "-q:v", "2",
        os.path.join(out_dir, "%05d.jpg")
    ])
    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=180)
    frames = sorted(f for f in os.listdir(out_dir) if f.endswith(".jpg"))
    if res.returncode != 0 or not frames:
        raise HTTPException(status_code=500, detail=f"Не удалось извлечь кадры для трекинга: {(res.stderr or '')[-200:]}")
    return len(frames)

def _run_template_tracker(frames_dir: str, fps: float, box_norm: Dict[str, float]) -> List[Dict[str, Any]]:
    import cv2
    import numpy as np

    frames = sorted(f for f in os.listdir(frames_dir) if f.endswith(".jpg"))
    if not frames:
        raise HTTPException(status_code=500, detail="Нет кадров для трекинга")

    first = cv2.imread(os.path.join(frames_dir, frames[0]))
    fh, fw = first.shape[:2]
    bx = max(0.0, min(0.95, box_norm["x"]))
    by = max(0.0, min(0.95, box_norm["y"]))
    bw = max(0.01, min(1.0 - bx, box_norm["w"]))
    bh = max(0.01, min(1.0 - by, box_norm["h"]))
    px, py, pw, ph = int(bx * fw), int(by * fh), max(8, int(bw * fw)), max(8, int(bh * fh))

    template = first[py:py + ph, px:px + pw].copy()
    tw, th = pw, ph
    cx, cy = px + pw / 2.0, py + ph / 2.0  # tracked center
    path: List[Dict[str, Any]] = []
    low_conf_streak = 0

    # Strict boundary: tracking is constrained strictly inside the selection area
    pad_x = int(pw * 0.20)
    pad_y = int(ph * 0.20)
    bound_x0 = max(0, px - pad_x)
    bound_y0 = max(0, py - pad_y)
    bound_x1 = min(fw, px + pw + pad_x)
    bound_y1 = min(fh, py + ph + pad_y)

    for idx, fname in enumerate(frames):
        frame = cv2.imread(os.path.join(frames_dir, fname))
        if frame is None:
            continue
        if idx > 0:
            margin = 0.5  # search window bounded inside region
            sx0 = int(max(bound_x0, cx - tw / 2 - tw * margin))
            sy0 = int(max(bound_y0, cy - th / 2 - th * margin))
            sx1 = int(min(bound_x1, cx + tw / 2 + tw * margin))
            sy1 = int(min(bound_y1, cy + th / 2 + th * margin))
            search = frame[sy0:sy1, sx0:sx1]
            found = False
            if search.shape[0] >= th and search.shape[1] >= tw and template.size > 0:
                res = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                if max_val > 0.35:
                    found = True
                    cx = sx0 + max_loc[0] + tw / 2.0
                    cy = sy0 + max_loc[1] + th / 2.0
                    low_conf_streak = 0
                    # Adapt template to appearance changes when confident
                    if max_val > 0.65 and idx % 12 == 0:
                        nx0 = int(max(0, cx - tw / 2)); ny0 = int(max(0, cy - th / 2))
                        nx1 = int(min(fw, cx + tw / 2)); ny1 = int(min(fh, cy + th / 2))
                        if nx1 - nx0 > 7 and ny1 - ny0 > 7:
                            template = frame[ny0:ny1, nx0:nx1].copy()
                else:
                    low_conf_streak += 1

            # Clamp tracked center strictly inside the user selection bounds
            cx = max(bound_x0 + tw / 2.0, min(bound_x1 - tw / 2.0, cx))
            cy = max(bound_y0 + th / 2.0, min(bound_y1 - th / 2.0, cy))

        norm_x = round(max(0.0, min(1.0, (cx - tw / 2.0) / fw)), 4)
        norm_y = round(max(0.0, min(1.0, (cy - th / 2.0) / fh)), 4)
        path.append({
            "t": round(idx / fps, 3),
            "x": norm_x,
            "y": norm_y,
            "w": round(tw / fw, 4),
            "h": round(th / fh, 4),
        })
    return path

@app.post("/api/track-object")
def track_object(req: TrackObjectRequest):
    """
    Track an object selected by a normalized box [x,y,w,h] across the media clip.
    Extracts frames with ffmpeg, runs a template-matching tracker, returns
    normalized keyframes [{t, x, y, w, h}] relative to clip start.
    """
    base_name = os.path.basename(req.filename)
    file_path = os.path.join(DOWNLOADS_DIR, base_name)
    if not os.path.exists(file_path):
        if os.path.exists(req.filename):
            file_path = req.filename
        else:
            raise HTTPException(status_code=404, detail=f"Медиафайл {base_name} не найден")

    if not (0 <= req.x <= 1 and 0 <= req.y <= 1 and req.w > 0 and req.h > 0):
        raise HTTPException(status_code=400, detail="Некорректная рамка объекта")

    temp_id = int(time.time() * 1000)
    frames_dir = os.path.join(DOWNLOADS_DIR, f"temp_track_{temp_id}")
    try:
        fps = max(4.0, min(24.0, req.sample_fps or 12.0))
        _extract_tracking_frames(file_path, req.start_time, req.duration, fps, frames_dir)
        path = _run_template_tracker(frames_dir, fps, {"x": req.x, "y": req.y, "w": req.w, "h": req.h})
        # Hard clamp: the tracked object may NEVER leave the selection area.
        # Every keyframe is intersected with (pinned into) the user's box.
        bx0, by0, bx1, by1 = req.x, req.y, req.x + req.w, req.y + req.h
        for k in path:
            k["w"] = min(k["w"], req.w)
            k["h"] = min(k["h"], req.h)
            cx = min(max(k["x"] + k["w"] / 2.0, bx0), bx1)
            cy = min(max(k["y"] + k["h"] / 2.0, by0), by1)
            k["x"] = min(max(cx - k["w"] / 2.0, bx0), max(bx0, bx1 - k["w"]))
            k["y"] = min(max(cy - k["h"] / 2.0, by0), max(by0, by1 - k["h"]))
        return {"status": "ok", "fps": fps, "keyframes": path}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка трекинга: {str(e)}")
    finally:
        shutil.rmtree(frames_dir, ignore_errors=True)

# ── Viral Shorts Template & Batch Exporter ───────────────────────────
class ExportSegment(BaseModel):
    start_time: float
    end_time: float

class CropBox(BaseModel):
    """Normalized webcam/face region to crop from the source (0..1)."""
    x: float
    y: float
    w: float
    h: float

class PipBox(BaseModel):
    """Normalized PiP window on the output frame (0..1)."""
    x: float = 0.688
    y: float = 0.018
    w: float = 0.30

class FxOverlay(BaseModel):
    start: float = 0.0           # output-time seconds
    end: float = 0.5
    kind: str = "flash"          # flash | bars | shake
    color: str = "white"         # white | green | red | bw
    peak: float = 0.75           # max opacity 0..1 (never fully covers)
    bar_h: int = 120             # cinebars height px (kind=bars)
    amp: int = 10                # shake amplitude px (kind=shake)
    z: int = 0                   # video-track index (0 = topmost track): the FX
                                 # affects only the composite built BELOW its track
    freq: float = 7.0            # shake frequency Hz (kind=shake)

class ExportLayer(BaseModel):
    """One video/image element from the timeline for layered compositing."""
    source_file: str
    src_offset: float = 0.0      # source in-point (seconds in the file)
    duration: float = 0.0        # seconds used from the source (region length)
    out_start: float = 0.0       # seconds into the output where this layer appears
    opacity: float = 1.0
    volume: float = 1.0          # its own audio gain in the mix
    muted: bool = False
    pip: Optional[PipBox] = None             # None = fullscreen base behavior
    track_path: Optional[List[Dict[str, Any]]] = None  # [{t,x,y,w,h}] normalized
    z: int = 0                   # track index (0 = topmost), higher = deeper


class FxSound(BaseModel):
    at: float = 0.0              # output-time seconds
    kind: str = "click"          # click | approve | cancel | pop | whoosh | none
    gain: float = 1.0


class TimelineAudioClip(BaseModel):
    filename: str
    src_offset: float = 0.0
    out_start: float = 0.0       # output-time placement
    duration: float = 5.0
    gain: float = 1.0
    loop: bool = False           # loop short music over duration
    duck: bool = False           # duck under the main voice track


class ExportClipItem(BaseModel):
    id: str
    title: Optional[str] = None
    source_file: str
    background_file: Optional[str] = None
    start_time: float
    end_time: float
    format: str = "split_adhd" # split_adhd, talking_head_9_16, cinematic_16_9
    crop_preset: str = "center" # top_right, top_left, face, center
    platform: str = "TWITCH"    # TWITCH, KICK, YOUTUBE
    streamer_handle: str = ""   # e.g. @jesusavgn
    subtitle_template: str = "meme" # meme, karaoke, news, accent, clean, acid, lime, cyan, yellow
    subtitles: List[Dict[str, Any]] = []
    # Viral subtitle render options
    sub_font: str = "Anton"   # Anton | Bebas Neue | Russo One | Oswald | Montserrat | Lobster | Arial Black | Impact
    sub_size: float = 1.0           # 0.7 .. 1.4
    sub_glow: float = 45.0          # 0 .. 100
    sub_anim: str = "pop"           # pop | wave | none
    # Tracked overlay: media (image/video) that follows the object path
    overlay_file: Optional[str] = None
    overlay_scale: float = 0.35          # overlay width as fraction of output width
    track_path: Optional[List[Dict[str, Any]]] = None  # [{t,x,y,w,h}] normalized, t relative to clip start
    # TV-graded templates: multi-moment cuts with white flash transitions
    color_grade: str = "none"            # none | tv
    flash_cuts: bool = False             # soft white flash between segments
    skip_flash_at: List[int] = []        # junction indices (0-based, between seg k and k+1) with hard cut
    segments: Optional[List[ExportSegment]] = None  # None -> single [start_time, end_time]
    crop_box: Optional[CropBox] = None   # webcam/face region (page-recording streams)
    bg_box: Optional[CropBox] = None     # background/gameplay region for split bottom band
    # Timeline FX (layer elements): overlays burned UNDER subtitles,
    # synth/file sounds, timeline audio (music ducking, SFX)
    overlays: List[FxOverlay] = []
    sounds: List[FxSound] = []
    extra_audio: List[TimelineAudioClip] = []
    # Layered compositing: every video/image element from the timeline.
    # When non-empty, takes priority over the single source_file pipeline.
    layers: List[ExportLayer] = []
    # Free text elements (AE-style): {text,start,end,font,size,color,glow,
    # anim_in,anim_out,x,y,align,shake} — output-local seconds
    text_items: List[Dict[str, Any]] = []
    # subtitles already in output time (region pipeline) — skip re-mapping
    subs_in_output_time: bool = False
    # source is already a finished short (burned subs + grade): passthrough —
    # do NOT re-grade and do NOT burn subtitles/text over it
    src_processed: bool = False
    # track index of the TOPMOST text layer: FX on tracks ABOVE it burn over text
    text_z: Optional[int] = None
    # highlight long "hot" keywords in an accent color (viral style)
    hot_words: bool = True
    # Static cinematic frames (рамки) burned above FX, below subtitles (px)
    bar_top: int = 0
    bar_bottom: int = 0

def _probe_duration(path: str) -> Optional[float]:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=20,
        )
        return float(r.stdout.strip()) if r.stdout.strip() else None
    except Exception:
        return None


def _sfx_maybe_file(inputs: List[str], filter_parts: List[str], n_inputs: int,
                    kind: str, gain: float, at_ms: int, tag: str) -> Optional[int]:
    """Real recorded SFX (./sfx) when available; returns the new input count,
    or None so the caller falls back to the synthesized chain."""
    fn = SFX_FILES.get(kind)
    if not fn:
        return None
    path = os.path.join(SFX_DIR, fn)
    if not os.path.exists(path):
        return None
    g = max(0.0, min(3.0, gain))
    inputs.extend(["-i", path])
    filter_parts.append(
        f"[{n_inputs}:a]aresample=48000,aformat=channel_layouts=stereo,"
        f"volume={g:.2f},adelay={at_ms}|{at_ms}[{tag}]"
    )
    return n_inputs + 1


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
            return f"({v1:.2f})"
        k = (v1 - v0) / (t1 - t0)
        return f"({v0:.2f}+{k:.4f}*(t-{t0:.3f}))"

    expr = f"{v_last:.2f}"
    for i in range(len(vals) - 2, -1, -1):
        t0, v0 = vals[i]
        t1, v1 = vals[i + 1]
        expr = f"if(lt(t,{t1:.3f}),{lerp_expr(t0, v0, t1, v1)},{expr})"
    return expr

class ExportPackRequest(BaseModel):
    pack_name: Optional[str] = "Pack"
    clips: List[ExportClipItem]

def generate_ass_subtitle_content(subtitles: List[Dict[str, Any]], template_id: str = "meme") -> str:
    """Generates ASS subtitles formatted for viral vertical shorts in full 1080x1920."""
    font = "Montserrat ExtraBold"
    style_def = f"Style: Default,{font},58,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,3,2,30,30,220,1"
    if template_id == "meme":
        style_def = f"Style: Default,{font},64,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,7,4,2,30,30,220,1"
    elif template_id == "karaoke":
        style_def = f"Style: Default,{font},64,&H0038D7C1,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,7,4,2,30,30,220,1"
    elif template_id == "highlight":
        style_def = f"Style: Default,{font},60,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,3,2,30,30,220,1"
    elif template_id == "news":
        style_def = f"Style: Default,{font},52,&H00FFFFFF,&H000000FF,&H00171D22,&HB0171D22,-1,0,0,0,100,100,0,0,3,3,0,2,30,30,220,1"
    elif template_id == "accent":
        style_def = f"Style: Default,{font},64,&H0008B9FF,&H000000FF,&H00171D22,&H80000000,-1,0,0,0,100,100,0,0,1,7,3,2,30,30,220,1"

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        style_def,
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
    ]

    def fmt_ass_time(sec: float, fps: int = 60) -> str:
        s = max(0.0, sec)
        frame = round(s * fps)
        s = frame / fps
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        sc = int(s % 60)
        cs = int(round((s - int(s)) * 100))
        if cs >= 100:
            sc += 1
            cs = 0
            if sc >= 60:
                m += 1
                sc = 0
                if m >= 60:
                    h += 1
                    m = 0
        return f"{h}:{m:02d}:{sc:02d}.{cs:02d}"

    for sub in subtitles:
        w_list = sub.get("words", [])
        if template_id == "karaoke" and w_list:
            for w in w_list:
                w_start = fmt_ass_time(w.get("start", 0))
                w_end = fmt_ass_time(w.get("end", 0))
                w_text = w.get("word", "").strip().upper()
                pop_text = f"{{\\fscx75\\fscy75\\t(0,90,\\fscx110\\fscy110)\\t(90,160,\\fscx100\\fscy100)}}{w_text}"
                lines.append(f"Dialogue: 0,{w_start},{w_end},Default,,0,0,0,,{pop_text}")
        else:
            s_start = fmt_ass_time(sub.get("start", 0))
            s_end = fmt_ass_time(sub.get("end", 0))
            text = sub.get("text", "").strip()
            if template_id in ("meme", "karaoke"):
                text = text.upper()
            pop_text = f"{{\\fscx80\\fscy80\\t(0,90,\\fscx108\\fscy108)\\t(90,160,\\fscx100\\fscy100)}}{text}"
            lines.append(f"Dialogue: 0,{s_start},{s_end},Default,,0,0,0,,{pop_text}")

    return "\n".join(lines)

# ── TV templates: viral subtitle styles + AE-grade color + white flash cuts ──
TV_TEMPLATES_CONFIG = {
    "mrbeast": {
        "name": "MrBeast 3D",
        "font": "Montserrat ExtraBold",
        "primary": "&H0000E6FF",
        "alt_colors": ["&H0000E6FF", "&H00FFF200", "&H00FFFFFF"],
        "outline_color": "&H00000000",
        "border_style": 1,
        "outline": 8,
        "is_3d": True,
        "tilt": -4,
        "anim": "pop",
        "hot_color": "&H0000E6FF",
    },
    "hormozi": {
        "name": "Hormozi Badge",
        "font": "Montserrat ExtraBold",
        "primary": "&H0000E6FF",
        "outline_color": "&H00000000",
        "back_color": "&HDC0C0A08",
        "border_style": 3,
        "outline": 14,
        "is_box": True,
        "tilt": 0,
        "anim": "pop",
        "hot_color": "&H0014FF39",
    },
    "cyber_glitch": {
        "name": "Cyber Glitch",
        "font": "Unbounded ExtraBold",
        "primary": "&H00FFFFFF",
        "outline_color": "&H00000000",
        "border_style": 1,
        "outline": 6,
        "is_glitch": True,
        "cyan_color": "&H00FFF200",
        "mag_color": "&H00FF007F",
        "tilt": 0,
        "anim": "tremble",
        "hot_color": "&H00FFF200",
    },
    "comic_pop": {
        "name": "Comic Pop-Art",
        "font": "Montserrat Black",
        "primary": "&H0000E6FF",
        "outline_color": "&H00000000",
        "border_style": 1,
        "outline": 12,
        "tilt": -6,
        "anim": "pop",
        "hot_color": "&H002222FF",
    },
    "golden_luxury": {
        "name": "Golden Luxury",
        "font": "Montserrat ExtraBold",
        "primary": "&H0082E0FF",
        "outline_color": "&H00183048",
        "border_style": 1,
        "outline": 3,
        "shadow": 4,
        "spacing": 4,
        "glow_color": "&H0050B8FF",
        "glow": 45,
        "tilt": 0,
        "anim": "rise",
        "hot_color": "&H00FFFFFF",
    },
    "rage_red": {
        "name": "Rage Red Slam",
        "font": "Montserrat Black",
        "primary": "&H00221CFF",
        "outline_color": "&H00000000",
        "glow_color": "&H000022FF",
        "border_style": 1,
        "outline": 8,
        "glow": 80,
        "tilt": 0,
        "anim": "tremble",
        "hot_color": "&H0000E6FF",
    },
    "clean_editorial": {
        "name": "Clean Editorial",
        "font": "Montserrat ExtraBold",
        "primary": "&H00FFFFFF",
        "outline_color": "&H00000000",
        "back_color": "&HE614100D",
        "border_style": 3,
        "outline": 12,
        "is_box": True,
        "spacing": 1,
        "tilt": 0,
        "anim": "pop",
        "hot_color": "&H0000E6FF",
    },
    "karaoke_spotlight": {
        "name": "Karaoke Spotlight",
        "font": "Montserrat ExtraBold",
        "primary": "&H00999999",
        "active_color": "&H00FFF200",
        "outline_color": "&H00000000",
        "border_style": 1,
        "outline": 6,
        "is_spotlight": True,
        "anim": "pop",
        "hot_color": "&H0000E6FF",
    },
    "acid": {
        "name": "Acid Neon",
        "font": "Montserrat ExtraBold",
        "primary": "&H0014FF39",
        "outline_color": "&H00000000",
        "glow_color": "&H0014FF39",
        "border_style": 1,
        "outline": 7,
        "glow": 75,
        "anim": "pop",
        "hot_color": "&H0000E6FF",
    },
    "purple_phonk": {
        "name": "Purple Phonk",
        "font": "Montserrat ExtraBold",
        "primary": "&H00FF26B0",
        "outline_color": "&H00000000",
        "glow_color": "&H00FF00B0",
        "border_style": 1,
        "outline": 7,
        "glow": 75,
        "anim": "pop",
        "hot_color": "&H0000E6FF",
    },
    "sunset_drift": {
        "name": "Sunset Fire",
        "font": "Montserrat ExtraBold",
        "primary": "&H0000A2FF",
        "outline_color": "&H00000000",
        "glow_color": "&H000055FF",
        "border_style": 1,
        "outline": 7,
        "glow": 70,
        "anim": "wave",
        "hot_color": "&H00FFFFFF",
    },
    "typewriter_terminal": {
        "name": "Terminal Arcade",
        "font": "Montserrat ExtraBold",
        "primary": "&H0066FF00",
        "outline_color": "&H00000000",
        "back_color": "&HF0000000",
        "border_style": 3,
        "outline": 10,
        "is_box": True,
        "spacing": 2,
        "anim": "type",
        "hot_color": "&H0000E6FF",
    },
    # Backwards-compatible aliases
    "lime": {"name": "TV Lime", "primary": "&H0014FF39", "font": "Montserrat ExtraBold", "outline": 7, "glow": 60, "anim": "pop", "hot_color": "&H0000E6FF"},
    "cyan": {"name": "TV Cyan", "primary": "&H00FFF200", "font": "Montserrat ExtraBold", "outline": 7, "glow": 60, "anim": "pop", "hot_color": "&H0000E6FF"},
    "yellow": {"name": "TV Yellow", "primary": "&H0000E6FF", "font": "Montserrat ExtraBold", "outline": 7, "glow": 60, "anim": "pop", "hot_color": "&H0014FF39"},
    "white": {"name": "Pure White", "primary": "&H00FFFFFF", "font": "Montserrat ExtraBold", "outline": 7, "glow": 45, "anim": "pop", "hot_color": "&H0000E6FF"},
    "red": {"name": "TV Red", "primary": "&H003322FF", "font": "Montserrat ExtraBold", "outline": 7, "glow": 60, "anim": "pop", "hot_color": "&H0000E6FF"},
    "violet": {"name": "TV Violet", "primary": "&H00FF33B4", "font": "Montserrat ExtraBold", "outline": 7, "glow": 60, "anim": "pop", "hot_color": "&H0000E6FF"},
}

TV_SUB_COLORS = {k: v.get("primary", "&H00FFFFFF") for k, v in TV_TEMPLATES_CONFIG.items()}
TV_HOT_COLORS = {k: v.get("hot_color", "&H0000E6FF") for k, v in TV_TEMPLATES_CONFIG.items()}

TV_SUB_FONTS = {
    "Anton", "Bebas Neue", "Russo One", "Oswald", "Oswald SemiBold", "Oswald Bold",
    "Montserrat", "Montserrat ExtraBold", "Montserrat Black", "Unbounded", "Unbounded ExtraBold",
    "Lobster", "Rubik Mono One", "Play", "Press Start 2P", "Arial Black", "Impact",
    "Dela Gothic One", "Prosto One", "Pacifico", "Marck Script", "Amatic SC",
    "Yeseva One", "M PLUS Rounded 1c", "Fira Sans Extra Bold", "Caveat Bold",
    "Tektur Bold", "Exo 2 Black", "Sofia Sans Extra Condensed Black", "Rubik Black",
    "Nunito Black", "Golos Text Black", "Yanone Kaffeesatz Bold", "Alumni Sans Black",
    "Onest Black", "Wix Madefor Display ExtraBold",
}
# Fonts without Cyrillic glyphs: substitute a close display face for RU text
FONT_NO_CYR = {"Anton", "Bebas Neue", "Impact", "Arial Black", "Bangers"}
CYR_FALLBACK = {
    "Anton": "Montserrat ExtraBold",
    "Bebas Neue": "Montserrat ExtraBold",
    "Impact": "Montserrat ExtraBold",
    "Arial Black": "Montserrat ExtraBold",
    "Bangers": "Montserrat ExtraBold",
    "Montserrat Black": "Montserrat ExtraBold",
}

def _text_has_cyrillic(subtitles: List[Dict[str, Any]]) -> bool:
    for sub in subtitles or []:
        s = str(sub.get("text", "")) + "".join(str(w.get("word", "")) for w in (sub.get("words") or []))
        for ch in s:
            if "\u0400" <= ch <= "\u04FF":
                return True
    return False

def _resolve_font(font: str, has_cyr: bool) -> str:
    font = font if font in TV_SUB_FONTS else "Montserrat ExtraBold"
    if has_cyr and font in FONT_NO_CYR:
        return CYR_FALLBACK.get(font, "Montserrat ExtraBold")
    return font


# ── Exact per-letter advance widths (fontTools metrics) for per-letter anims ──
_FONT_FILE_FOR = {
    "Bangers": "Bangers-Regular.ttf",
    "Anton": "anton-Anton-Regular.ttf",
    "Bebas Neue": "bebasneue-BebasNeue-Regular.ttf",
    "Russo One": "russoone-RussoOne-Regular.ttf",
    "Oswald": "oswald-oswald-semibold.ttf",
    "Oswald SemiBold": "oswald-oswald-semibold.ttf",
    "Oswald Bold": "oswald-oswald-bold.ttf",
    "Montserrat": "montserrat-montserrat-extrabold.ttf",
    "Montserrat ExtraBold": "montserrat-montserrat-extrabold.ttf",
    "Montserrat Black": "montserrat-montserrat-extrabold.ttf",
    "Unbounded": "unbounded-unbounded-extrabold.ttf",
    "Unbounded ExtraBold": "unbounded-unbounded-extrabold.ttf",
    "Lobster": "lobster-Lobster-Regular.ttf",
    "Rubik Mono One": "rubikmono-RubikMonoOne-Regular.ttf",
    "Play": "play-Play-Bold.ttf",
    "Press Start 2P": "pressstart-PressStart2P-Regular.ttf",
    "Dela Gothic One": "delagothone-DelaGothicOne-Regular.ttf",
    "Prosto One": "prostoone-ProstoOne-Regular.ttf",
    "Pacifico": "pacifico-Pacifico-Regular.ttf",
    "Marck Script": "marckscript-MarckScript-Regular.ttf",
    "Amatic SC": "amaticsc-AmaticSC-Bold.ttf",
    "Yeseva One": "yesevaone-YesevaOne-Regular.ttf",
    "M PLUS Rounded 1c": "mplusrounded1c-ExtraBold.ttf",
    "Fira Sans Extra Bold": "firasans-FiraSans-ExtraBold.ttf",
    "Caveat Bold": "caveat-caveat-bold.ttf",
    "Exo 2 Black": "exo2-exo2-black.ttf",
    "Sofia Sans Extra Condensed Black": "sofiasansxc-sofiasansxc-black.ttf",
    "Rubik Black": "rubik-rubik-black.ttf",
    "Nunito Black": "nunito-nunito-black.ttf",
    "Golos Text Black": "golostext-golostext-black.ttf",
    "Yanone Kaffeesatz Bold": "yanone-yanone-bold.ttf",
    "Alumni Sans Black": "alumnisans-alumnisans-black.ttf",
    "Onest Black": "onest-onest-black.ttf",
    "Wix Madefor Display ExtraBold": "wixmadefor-wixmadefor-extrabold.ttf",
}
_adv_cache: Dict[str, Any] = {}

def _letter_widths(font: str, size_px: float, text: str) -> List[float]:
    """Real advance width of every char in px (falls back to 0.62*size)."""
    key = f"{font}|{size_px:.1f}"
    entry = _adv_cache.get(key)
    if entry is None:
        cmap = upem = None
        fname = _FONT_FILE_FOR.get(font)
        if fname:
            try:
                from fontTools.ttLib import TTFont
                f = TTFont(os.path.join(FONTS_DIR, fname), fontNumber=0, lazy=True)
                cmap = f.getBestCmap()
                hmtx = f["hmtx"]
                upem = f["head"].unitsPerEm or 1000
                widths = {}
                for code, gname in cmap.items():
                    try:
                        widths[chr(code)] = hmtx[gname][0]
                    except Exception:
                        continue
                entry = (widths, upem)
            except Exception:
                entry = (None, None)
        else:
            entry = (None, None)
        _adv_cache[key] = entry
    widths, upem = entry
    out = []
    for ch in text:
        w = None
        if widths and ch in widths and upem:
            w = widths[ch] / float(upem) * size_px
        if not w:
            w = 0.62 * size_px
        out.append(w)
    return out

def _letter_positions(font: str, size_px: float, text: str, out_w: int, spacing: float = 0.0) -> List[float]:
    """Centered x position (px) of each letter's middle in a single line."""
    ws = _letter_widths(font, size_px, text)
    total = sum(ws) + spacing * max(0, len(text) - 1)
    x = (out_w - total) / 2.0
    pos = []
    for w in ws:
        pos.append(x + w / 2.0)
        x += w + spacing
    return pos

def _tv_sub_opts(subtitle_template: str, clip, subtitles=None) -> dict:
    """Resolve per-clip subtitle render options with safe defaults."""
    has_cyr = _text_has_cyrillic(subtitles if subtitles is not None else getattr(clip, "subtitles", None))
    cfg = TV_TEMPLATES_CONFIG.get(subtitle_template) or TV_TEMPLATES_CONFIG.get("mrbeast") or TV_TEMPLATES_CONFIG.get("acid")
    font = getattr(clip, "sub_font", None)
    if not font or font not in TV_SUB_FONTS:
        font = cfg.get("font", "Montserrat ExtraBold")
    font = _resolve_font(font, has_cyr)
    try:
        size_mul = float(getattr(clip, "sub_size", None) or 1.0)
    except (TypeError, ValueError):
        size_mul = 1.0
    size_mul = max(0.6, min(1.6, size_mul))
    try:
        glow = float(getattr(clip, "sub_glow", None) if getattr(clip, "sub_glow", None) is not None else cfg.get("glow", 55.0))
    except (TypeError, ValueError):
        glow = cfg.get("glow", 55.0)
    glow = max(0.0, min(100.0, glow))
    anim = getattr(clip, "sub_anim", None) or cfg.get("anim", "pop")
    if anim not in ("pop", "wave", "shimmer", "type", "rise", "spin", "tremble", "none"):
        anim = cfg.get("anim", "pop")
    default_style = subtitle_template if (subtitle_template in TV_TEMPLATES_CONFIG or subtitle_template in TV_SUB_COLORS) else "mrbeast"
    return {"font": font, "size_mul": size_mul, "glow": glow, "anim": anim, "default_style": default_style}

def _is_hot_word(word: str) -> bool:
    clean = "".join(ch for ch in str(word) if ch.isalnum())
    return len(clean) >= 5

def build_tv_subtitles_ass(remapped_subs, style_id: str, out_w: int, out_h: int, margin_v: int,
                           font: str = "Montserrat ExtraBold", size_mul: float = 1.0,
                           glow: float = 55.0, anim: str = "pop",
                           hot_words: bool = True) -> str:
    """Advanced viral shorts subtitle styling engine matching top-tier creators.
    Supports MrBeast 3D extrusion with dynamic tilt, Hormozi dark pill badge,
    Cyberpunk RGB split glitch, Comic pop-art squash & stretch, Golden luxury tracking,
    Rage red earthquake slam, Clean editorial glass badge, and Karaoke spotlight.
    PlayRes matches output resolution for 100% pixel parity."""
    try:
        size_mul = max(0.6, min(1.6, float(size_mul or 1.0)))
    except (TypeError, ValueError):
        size_mul = 1.0
    try:
        glow = max(0.0, min(100.0, float(glow if glow is not None else 55.0)))
    except (TypeError, ValueError):
        glow = 55.0
    if anim not in ("pop", "wave", "shimmer", "type", "rise", "spin", "tremble", "none"):
        anim = "pop"
    if style_id not in TV_TEMPLATES_CONFIG and style_id not in TV_SUB_COLORS:
        style_id = "mrbeast"
    base_fontsize = max(36, int(out_h * 0.058 * size_mul))
    gk = 0.8 + glow / 100.0 * 0.8

    header_styles = []
    for tid, c in TV_TEMPLATES_CONFIG.items():
        t_font = font if (font and font in TV_SUB_FONTS) else c.get("font", "Montserrat ExtraBold")
        t_font = _resolve_font(t_font, _text_has_cyrillic(remapped_subs))
        t_primary = c.get("primary", "&H00FFFFFF")
        t_outcol = c.get("outline_color", "&H00000000")
        t_backcol = c.get("back_color", "&H00000000")
        t_border = c.get("border_style", 1)
        t_outline = int(max(4, c.get("outline", 7) * size_mul * 0.85))
        t_spacing = c.get("spacing", 0)
        t_shadow = int(max(2, base_fontsize * 0.04))

        main_style = (f"Style: Main_{tid},{t_font},{base_fontsize},{t_primary},&H000000FF,{t_outcol},{t_backcol},"
                      f"-1,0,0,0,100,100,{t_spacing},0,{t_border},{t_outline},{t_shadow},2,{int(out_w*0.03)},{int(out_w*0.03)},{margin_v},1")
        header_styles.append(main_style)

        if c.get("is_3d"):
            sh_style = (f"Style: Shadow3D_{tid},{t_font},{base_fontsize},&H00000000,&H00000000,&H00000000,&H00000000,"
                        f"-1,0,0,0,100,100,{t_spacing},0,1,{t_outline},0,2,{int(out_w*0.03)},{int(out_w*0.03)},{margin_v},1")
            header_styles.append(sh_style)

        if c.get("is_glitch"):
            cyan_col = c.get("cyan_color", "&H00FFF200")
            mag_col = c.get("mag_color", "&H00FF007F")
            gl_cyan = (f"Style: GlitchCyan_{tid},{t_font},{base_fontsize},{cyan_col},&H000000FF,{cyan_col},&H00000000,"
                       f"-1,0,0,0,100,100,{t_spacing},0,1,{t_outline},0,2,{int(out_w*0.03)},{int(out_w*0.03)},{margin_v},1")
            gl_mag = (f"Style: GlitchMag_{tid},{t_font},{base_fontsize},{mag_col},&H000000FF,{mag_col},&H00000000,"
                      f"-1,0,0,0,100,100,{t_spacing},0,1,{t_outline},0,2,{int(out_w*0.03)},{int(out_w*0.03)},{margin_v},1")
            header_styles.extend([gl_cyan, gl_mag])

        if c.get("glow") or tid in ("acid", "purple_phonk", "sunset_drift", "rage_red", "golden_luxury", "lime", "cyan", "yellow", "white", "red", "violet"):
            gcol = c.get("glow_color", t_primary)
            g_outline = max(3, int(base_fontsize * 0.05 * gk))
            glow_style = (f"Style: Glow_{tid},{t_font},{base_fontsize},{gcol},&H000000FF,{gcol},{gcol},"
                          f"-1,0,0,0,100,100,{t_spacing},0,1,{g_outline},0,2,{int(out_w*0.03)},{int(out_w*0.03)},{margin_v},1")
            header_styles.append(glow_style)

        if c.get("is_spotlight"):
            act_col = c.get("active_color", "&H00FFF200")
            act_style = (f"Style: SpotActive_{tid},{t_font},{int(base_fontsize*1.08)},{act_col},&H000000FF,&H00000000,&H00000000,"
                         f"-1,0,0,0,100,100,{t_spacing},0,1,{t_outline+1},0,2,{int(out_w*0.03)},{int(out_w*0.03)},{margin_v},1")
            header_styles.append(act_style)

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {out_w}",
        f"PlayResY: {out_h}",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        *header_styles,
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
    ]

    def fmt_ass_time(sec: float, fps: int = 60) -> str:
        s = max(0.0, sec)
        frame = round(s * fps)
        s = frame / fps
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        sc = int(s % 60)
        cs = int(round((s - int(s)) * 100))
        if cs >= 100:
            sc += 1
            cs = 0
            if sc >= 60:
                m += 1
                sc = 0
                if m >= 60:
                    h += 1
                    m = 0
        return f"{h}:{m:02d}:{sc:02d}.{cs:02d}"

    base_y = out_h - margin_v - int(base_fontsize * 0.35)
    cx = out_w // 2

    for sub in remapped_subs:
        sid = sub.get("style") or style_id
        if sid not in TV_TEMPLATES_CONFIG:
            sid = "acid"
        t_cfg = TV_TEMPLATES_CONFIG[sid]
        cur_font = font if (font and font in TV_SUB_FONTS) else t_cfg.get("font", "Montserrat ExtraBold")
        cur_font = _resolve_font(cur_font, _text_has_cyrillic([sub]))

        words = sub.get("words") or []
        full_text = str(sub.get("text", "")).strip().upper()

        try:
            sxv = float(sub.get("x"))
            syv = float(sub.get("y"))
            if not (0.02 <= sxv <= 0.98 and 0.02 <= syv <= 0.98):
                raise ValueError
            sub_pos = f"\\pos({sxv * out_w:.0f},{syv * out_h:.0f})"
        except (TypeError, ValueError):
            sub_pos = None

        # Pick single most impactful hot word in this cue (longest meaningful word)
        hot_idx = -1
        if hot_words and words:
            longest_len = 0
            for idx, w in enumerate(words):
                clean = "".join(ch for ch in str(w.get("word", "")).strip() if ch.isalnum())
                if len(clean) >= 5 and len(clean) > longest_len:
                    longest_len = len(clean)
                    hot_idx = idx

        if words and not t_cfg.get("is_box") and t_cfg.get("anim") != "type" and anim != "type":
            items = []
            for i, w in enumerate(words):
                ws = float(w.get("start", 0))
                we = float(w.get("end", 0))
                wt = str(w.get("word", "")).strip().upper()
                if not wt:
                    continue
                nxt = float(words[i + 1].get("start", 0)) if i + 1 < len(words) else None
                if nxt is not None and nxt > ws:
                    we = max(we, min(nxt, ws + 2.5))
                wsid = w.get("style") or sid
                items.append((ws, max(ws + 0.15, we), wt, wsid, i))
        else:
            items = [(float(sub.get("start", 0)), float(sub.get("end", 0)), full_text, sid, 0)]

        for (ws, we, wt, wsid, widx) in items:
            cur_cfg = TV_TEMPLATES_CONFIG.get(wsid, t_cfg)
            dur_ms = int(max(0.15, we - ws) * 1000)
            out_fade = min(110, dur_ms // 3)
            ts = fmt_ass_time(ws)
            te = fmt_ass_time(we)
            pos_tag = sub_pos if sub_pos else f"\\pos({cx:.0f},{base_y:.0f})"
            if sub_pos:
                try:
                    cx = int(float(sub.get("x")) * out_w)
                    base_y = int(float(sub.get("y")) * out_h)
                except (TypeError, ValueError):
                    pass

            # Universal spring pop animation tag or specific viral animation
            if anim == "pop":
                pop_tag = "\\fscx68\\fscy68\\t(0,90,\\fscx112\\fscy112)\\t(90,160,\\fscx100\\fscy100)"
            elif anim == "rise":
                pop_tag = "\\fscy60\\t(0,100,\\fscy110)\\t(100,160,\\fscy100)"
            elif anim == "wave":
                pop_tag = "\\frz-3\\fscx90\\fscy90\\t(0,80,\\frz3\\fscx110\\fscy110)\\t(80,160,\\frz0\\fscx100\\fscy100)"
            elif anim == "shimmer":
                pop_tag = "\\fscx92\\fscy92\\t(0,90,\\fscx106\\fscy106)\\t(90,160,\\fscx100\\fscy100)"
            elif anim == "tremble":
                pop_tag = "\\frz2\\t(0,40,\\frz-2)\\t(40,80,\\frz1.5)\\t(80,120,\\frz-1)\\t(120,160,\\frz0)"
            elif anim == "spin":
                pop_tag = "\\frz-15\\fscx50\\fscy50\\t(0,110,\\frz3\\fscx110\\fscy110)\\t(110,170,\\frz0\\fscx100\\fscy100)"
            elif anim == "none":
                pop_tag = ""
            else:
                pop_tag = "\\fscx68\\fscy68\\t(0,90,\\fscx112\\fscy112)\\t(90,160,\\fscx100\\fscy100)"

            # 1. MrBeast 3D
            if cur_cfg.get("is_3d"):
                tilt = cur_cfg.get("tilt", -4)
                alt = cur_cfg.get("alt_colors", ["&H0000E6FF", "&H00FFF200", "&H00FFFFFF"])
                col = alt[widx % len(alt)]
                col_tag = f"\\1c{col[2:]}&"
                for si in range(1, 5):
                    off = si * 2
                    tag_sh = f"{{\\an5\\frz{tilt}\\pos({cx+off},{base_y+off}){pop_tag}}}"
                    lines.append(f"Dialogue: {si-1},{ts},{te},Shadow3D_{wsid},,0,0,0,,{tag_sh}{wt}")
                tag_m = f"{{\\an5\\frz{tilt}\\pos({cx},{base_y})\\fad(20,{out_fade}){col_tag}{pop_tag}}}"
                lines.append(f"Dialogue: 4,{ts},{te},Main_{wsid},,0,0,0,,{tag_m}{wt}")

            # 2. Cyber Glitch
            elif cur_cfg.get("is_glitch"):
                j_tag = "\\t(0,60,\\frz1\\fscx104\\fscy104)\\t(60,120,\\frz-1\\fscx100\\fscy100)\\t(120,180,\\frz0)"
                lines.append(f"Dialogue: 0,{ts},{te},GlitchMag_{wsid},,0,0,0,,{{\\an5\\blur1.5\\pos({cx+5},{base_y}){j_tag}}}{wt}")
                lines.append(f"Dialogue: 1,{ts},{te},GlitchCyan_{wsid},,0,0,0,,{{\\an5\\blur1.5\\pos({cx-5},{base_y}){j_tag}}}{wt}")
                lines.append(f"Dialogue: 2,{ts},{te},Main_{wsid},,0,0,0,,{{\\an5\\pos({cx},{base_y}){j_tag}\\fad(15,{out_fade})}}{wt}")

            # 3. Comic Pop-Art
            elif wsid == "comic_pop":
                tilt = cur_cfg.get("tilt", -6)
                cpop_tag = f"\\frz{tilt}\\fscx112\\fscy112\\t(0,90,\\fscx95\\fscy122)\\t(90,170,\\fscx100\\fscy100)"
                lines.append(f"Dialogue: 0,{ts},{te},Main_{wsid},,0,0,0,,{{\\an5\\pos({cx},{base_y})\\fad(20,{out_fade}){cpop_tag}}}{wt}")

            # 4. Golden Luxury
            elif wsid == "golden_luxury":
                lines.append(f"Dialogue: 0,{ts},{te},Glow_{wsid},,0,0,0,,{{\\an5\\blur16\\fsp4{pos_tag}\\fad(40,{out_fade}){pop_tag}}}{wt}")
                lines.append(f"Dialogue: 1,{ts},{te},Main_{wsid},,0,0,0,,{{\\an5\\fsp4{pos_tag}\\fad(40,{out_fade}){pop_tag}}}{wt}")

            # 5. Rage Red
            elif wsid == "rage_red":
                slam = "\\fscx140\\fscy140\\t(0,80,\\fscx100\\fscy100)\\t(80,140,\\frz2.5)\\t(140,200,\\frz-2)\\t(200,260,\\frz0)"
                lines.append(f"Dialogue: 0,{ts},{te},Glow_{wsid},,0,0,0,,{{\\an5\\blur20\\pos({cx},{base_y}){slam}}}{wt}")
                lines.append(f"Dialogue: 1,{ts},{te},Main_{wsid},,0,0,0,,{{\\an5\\pos({cx},{base_y}){slam}\\fad(10,{out_fade})}}{wt}")

            # 6. Pill Boxes (Hormozi / Clean Editorial)
            elif cur_cfg.get("is_box"):
                hot = hot_words and (widx == hot_idx)
                if hot:
                    hot_col = cur_cfg.get("hot_color", "&H0014FF39")
                    col_tag = f"\\1c{hot_col[2:]}&"
                else:
                    col_tag = ""
                lines.append(f"Dialogue: 0,{ts},{te},Main_{wsid},,0,0,0,,{{\\an5{pos_tag}\\fad(25,{out_fade}){col_tag}{pop_tag}}}{wt}")

            # 7. Spotlight Pulse
            elif cur_cfg.get("is_spotlight"):
                lines.append(f"Dialogue: 0,{ts},{te},SpotActive_{wsid},,0,0,0,,{{\\an5{pos_tag}\\fad(20,{out_fade}){pop_tag}}}{wt}")

            # 8. Standard Glowing TV styles (Acid / Phonk / Sunset / Lime / Cyan, etc.)
            else:
                hot = hot_words and (widx == hot_idx)
                if hot:
                    hcol = cur_cfg.get("hot_color", "&H0000E6FF")
                    col_tag = f"\\1c&H{hcol[-6:]}&"
                    gcol = hcol
                    bord_tag = f"\\bord{max(3.8, base_fontsize * 0.075):.1f}\\3c&H000000&\\shad{max(2.2, base_fontsize * 0.04):.1f}\\4c&H000000&\\4a&H50&"
                else:
                    col_tag = ""
                    gcol = cur_cfg.get("glow_color", cur_cfg.get("primary", "&H0014FF39"))
                    # Always keep crisp dark border and shadow for readability - never bord0!
                    bord_tag = f"\\bord{max(3.2, base_fontsize * 0.065):.1f}\\3c&H000000&\\shad{max(2.0, base_fontsize * 0.038):.1f}\\4c&H000000&\\4a&H60&"

                core_b = max(3, int(base_fontsize * 0.05 * gk))
                wide_b = max(8, int(base_fontsize * 0.14 * gk))

                # Ambient soft glow (bottom layer)
                lines.append(
                    f"Dialogue: 0,{ts},{te},Glow_{wsid},,0,0,0,,"
                    f"{{\\an5{pos_tag}\\blur{wide_b}\\bord{core_b}\\1c&H{gcol[-6:]}&\\3c&H{gcol[-6:]}&\\1a&HA0&\\3a&HA0&{pop_tag}}}{wt}"
                )
                # Tight intense glow (middle layer)
                lines.append(
                    f"Dialogue: 1,{ts},{te},Glow_{wsid},,0,0,0,,"
                    f"{{\\an5{pos_tag}\\blur{core_b}\\bord{max(2, core_b//2)}\\1c&H{gcol[-6:]}&\\3c&H{gcol[-6:]}&\\1a&H50&\\3a&H50&{pop_tag}}}{wt}"
                )
                # Main text with crisp dark outline and shadow (top layer)
                lines.append(
                    f"Dialogue: 2,{ts},{te},Main_{wsid},,0,0,0,,"
                    f"{{\\an5{pos_tag}\\fad(15,{out_fade}){bord_tag}{col_tag}{pop_tag}}}{wt}"
                )

    return "\n".join(lines)
def build_text_elements_ass(text_items: List[Dict[str, Any]], out_w: int, out_h: int) -> str:
    """Generates an ASS subtitle file for free text overlays placed on the canvas.
    B2 = "\\"
    Renders with After Effects-grade 4-layer radiant neon glow, 3D shadow, bold stroke,
    smooth entry/exit animations, and organic shake."""
    B2 = "\\"
    if not text_items:
        return ""
    styles_seen = {}
    for ti in text_items:
        fam = ti.get("font") if ti.get("font") in TV_SUB_FONTS else "Montserrat ExtraBold"
        fam = _resolve_font(fam, _text_has_cyrillic([{"text": ti.get("text", "")}]))
        # размер здесь должен совпадать с итоговым размером в цикле событий ниже
        # (авто-ужатие по ширине кадра), иначе Dialogue ссылается на несуществующий
        # стиль и libass падает в крошечный Default
        raw_size = max(18, int(float(ti.get("size", out_h * 0.055))))
        plain = str(ti.get("text", "")).replace("\n", " ").strip()
        ev_size = raw_size
        if plain:
            try:
                total_w = sum(_letter_widths(fam, raw_size, plain))
                if total_w > out_w * 0.92:
                    ev_size = max(18, int(raw_size * (out_w * 0.92) / total_w))
            except Exception:
                pass
        key = (fam, ev_size)
        if key not in styles_seen:
            styles_seen[key] = fam
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {out_w}",
        f"PlayResY: {out_h}",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
    ]
    for (fam, size) in styles_seen:
        lines.append(f"Style: TXT_{fam.replace(' ', '_')}_{size},{fam},{size},"
                     f"&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,"
                     f"{max(3, int(size*0.05))},{max(2, int(size*0.05))},5,10,10,10,1")
    lines += ["", "[Events]",
              "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]

    def fmt_ass_time(sec: float, fps: int = 60) -> str:
        s = max(0.0, sec)
        frame = round(s * fps)
        s = frame / fps
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        sc = int(s % 60)
        cs = int(round((s - int(s)) * 100))
        if cs >= 100:
            sc += 1
            cs = 0
            if sc >= 60:
                m += 1
                sc = 0
                if m >= 60:
                    h += 1
                    m = 0
        return f"{h}:{m:02d}:{sc:02d}.{cs:02d}"

    def hex_to_ass(c: str, default: str = "&H00FFFFFF") -> str:
        if not c:
            return default
        c = c.strip().lstrip("#")
        if len(c) == 6:
            try:
                r = int(c[0:2], 16); g = int(c[2:4], 16); b = int(c[4:6], 16)
                return "&H00%02X%02X%02X" % (b, g, r)
            except ValueError:
                return default
        return default

    for ti in text_items:
        try:
            ts = float(ti.get("start", 0)); te = float(ti.get("end", ts + 2.0))
        except (TypeError, ValueError):
            continue
        if te <= ts:
            continue
        text = str(ti.get("text", "")).replace("\n", "\\N").strip()
        if not text:
            continue
        fam = ti.get("font") if ti.get("font") in TV_SUB_FONTS else "Montserrat ExtraBold"
        fam = _resolve_font(fam, _text_has_cyrillic([{"text": text}]))
        try:
            size = max(18, int(float(ti.get("size", out_h * 0.055))))
        except (TypeError, ValueError):
            size = int(out_h * 0.055)
        plain = text.replace("\\N", " ")
        if plain.strip():
            total_w = sum(_letter_widths(fam, size, plain))
            if total_w > out_w * 0.92:
                size = max(18, int(size * (out_w * 0.92) / total_w))
        try:
            stroke = max(0.0, min(24.0, float(ti.get("stroke", 0) or 0)))
        except (TypeError, ValueError):
            stroke = 0.0
        if stroke <= 0:
            stroke = max(3.5, size * 0.065)
        try:
            spacing = max(-4.0, min(30.0, float(ti.get("spacing", 0) or 0)))
        except (TypeError, ValueError):
            spacing = 0.0
        stroke_tag = "\\bord" + f"{stroke:.1f}"
        fsp_tag = ("\\fsp" + f"{spacing:.1f}") if spacing else ""
        color = hex_to_ass(ti.get("color"), "&H00FFFFFF")
        glow_color = hex_to_ass(ti.get("glow_color") or ti.get("color"), color)
        glow = max(0.0, min(100.0, float(ti.get("glow", 50) if ti.get("glow") is not None else 50)))
        anim_in = ti.get("anim_in") or "pop"
        anim_out = ti.get("anim_out") or "fade"
        shake = bool(ti.get("shake"))
        try:
            fx = max(0.02, min(0.98, float(ti.get("x", 0.5))))
            fy = max(0.02, min(0.98, float(ti.get("y", 0.5))))
        except (TypeError, ValueError):
            fx, fy = 0.5, 0.5
        dur_ms = max(150, int((te - ts) * 1000))
        in_ms = min(400, max(120, dur_ms // 4))
        out_ms = min(350, max(120, dur_ms // 4))

        style = f"TXT_{fam.replace(' ', '_')}_{size}"
        px, py = fx * out_w, fy * out_h
        nph = max(2, min(6, dur_ms // 350))
        seg = dur_ms // nph

        # Clean sway breathing
        sway = ""
        for k in range(nph):
            t0, t1 = k * seg, (k + 1) * seg
            rz = 1.0 if k % 2 == 0 else -1.0
            sway += f"\\t({t0},{t1},\\frz{rz:.1f})"

        # Clean glow breathing
        gb_osc = ""
        for k in range(nph):
            t0, t1 = k * seg, (k + 1) * seg
            gbv = size * 0.26 * (glow / 60.0) * (1.2 if k % 2 == 0 else 0.8)
            gb_osc += f"\\t({t0},{t1},\\blur{max(1.0, gbv):.1f})"

        in_map = {
            "none": f"\\fad({in_ms if anim_in != 'none' else 0},0)",
            "pop": f"\\fad({int(in_ms*0.5)},0)\\fscx35\\fscy35\\t(0,{in_ms},\\fscx114\\fscy114)\\t({in_ms},{in_ms+70},\\fscx100\\fscy100)",
            "rise": f"\\fad({in_ms},0)\\move({px:.0f},{py+size*0.75:.0f},{px:.0f},{py:.0f},0,{in_ms})",
            "spin": f"\\fad({int(in_ms*0.6)},0)\\frz-14\\fscx55\\fscy55\\t(0,{in_ms+80},\\frz0\\fscx100\\fscy100)",
            "slide": f"\\fad({int(in_ms*0.6)},0)\\move({px-out_w*0.2:.0f},{py:.0f},{px:.0f},{py:.0f},0,{in_ms})",
            "slide_r": f"\\fad({int(in_ms*0.6)},0)\\move({px+out_w*0.2:.0f},{py:.0f},{px:.0f},{py:.0f},0,{in_ms})",
            "wave": f"\\fad({in_ms},0)\\fscx60\\fscy60\\t(0,{in_ms},\\fscx112\\fscy112)\\t({in_ms},{in_ms+100},\\fscx100\\fscy100)",
            "bounce": f"\\fad({int(in_ms*0.5)},0)\\move({px:.0f},{py-size*1.8:.0f},{px:.0f},{py:.0f},0,{in_ms})\\frz6\\t({in_ms},{in_ms+180},\\frz0)",
            "zoom": f"\\fad({int(in_ms*0.4)},0)\\fscx200\\fscy200\\blur6\\t(0,{in_ms+90},\\fscx100\\fscy100\\blur0.8)",
        }
        in_tag = in_map.get(anim_in, in_map["pop"])

        o0 = dur_ms - out_ms
        out_map = {
            "none": "",
            "fade": f"\\t({o0},{dur_ms},\\alpha&HFF&)",
            "shrink": f"\\t({o0},{dur_ms},\\fscx20\\fscy20\\alpha&HFF&)",
            "slideout": f"\\t({o0},{dur_ms},\\fscx115\\fscy20\\alpha&HFF&)",
            "blurout": f"\\t({o0},{dur_ms},\\blur12\\alpha&HFF&)",
            "spinout": f"\\t({o0},{dur_ms},\\frz25\\fscx20\\fscy20\\alpha&HFF&)",
            "riseout": f"\\t({o0},{dur_ms},\\fscy140\\fscx70\\alpha&HFF&)",
        }
        out_tag = out_map.get(anim_out, out_map["fade"])

        shake_tag = ""
        if shake:
            shake_tag = ("\\t(0,%d,\\frz1.8\\fsp0.5)\\t(%d,%d,\\frz-1.6\\fsp-0.3)"
                         % (dur_ms // 3, dur_ms // 3, 2 * dur_ms // 3))

        gb1 = max(8, int(size * 0.16 * (glow / 60.0)))
        gb2 = max(4, int(size * 0.08 * (glow / 60.0)))
        sh_off = max(3, int(size * 0.055))
        sh_bord = max(2, int(size * 0.05))

        uses_move = anim_in in ("rise", "slide", "slide_r", "bounce")
        pos_tag = "" if uses_move else f"\\pos({px:.0f},{py:.0f})"

        if anim_in == "type" and 1 < len(text.replace("\\N", "")) <= 50:
            per = max(30, min(90, (dur_ms - 200) // len(text)))
            xs = _letter_positions(fam, size, text.replace("\\N", " "), out_w, spacing)
            xi = 0
            for i, ch in enumerate(text):
                if ch == "\\":
                    continue
                cur_x = xs[xi] if xi < len(xs) else out_w / 2.0
                xi += 1
                ls = ts + i * per / 1000.0
                if ls >= te - 0.04:
                    break
                cpos = f"\\pos({cur_x:.0f},{py:.0f})"
                anim_base = f"\\an5\\fad(15,{out_ms if anim_out != 'none' else 0}){cpos}{fsp_tag}\\fscx120\\fscy120\\t(0,70,\\fscx100\\fscy100){shake_tag}{out_tag}"
                t_start_s = fmt_ass_time(ls)
                t_end_s = fmt_ass_time(te)
                if glow > 5:
                    lines.append(f"Dialogue: 1,{t_start_s},{t_end_s},{style},,0,0,0,,{{{anim_base}\\bord{gb1}\\blur{gb1}\\3c{glow_color}\\1c{glow_color}\\3a&H80&\\1a&H80&}}{ch}")
                    lines.append(f"Dialogue: 2,{t_start_s},{t_end_s},{style},,0,0,0,,{{{anim_base}\\bord{gb2}\\blur{gb2}\\3c{glow_color}\\1c{glow_color}\\3a&H40&\\1a&H40&}}{ch}")
                lines.append(f"Dialogue: 3,{t_start_s},{t_end_s},{style},,0,0,0,,{{\\an5\\pos({cur_x+sh_off:.0f},{py+sh_off:.0f}){fsp_tag}\\bord{sh_bord}\\3c&H00000000&\\1c&H00000000&\\3a&H40&\\1a&H40&\\fscx120\\fscy120\\t(0,70,\\fscx100\\fscy100){shake_tag}{out_tag}}}{ch}")
                lines.append(f"Dialogue: 4,{t_start_s},{t_end_s},{style},,0,0,0,,{{{anim_base}{stroke_tag}\\3c&H00000000&\\1c{color}}}{ch}")
        else:
            anim_base = f"\\an5{pos_tag}{in_tag}{out_tag}{shake_tag}{fsp_tag}"
            t_start_s = fmt_ass_time(ts)
            t_end_s = fmt_ass_time(te)
            if glow > 5:
                lines.append(f"Dialogue: 1,{t_start_s},{t_end_s},{style},,0,0,0,,{{{anim_base}\\bord{gb1}\\blur{gb1}\\3c{glow_color}\\1c{glow_color}\\3a&H80&\\1a&H80&{gb_osc}{sway}}}{text}")
                lines.append(f"Dialogue: 2,{t_start_s},{t_end_s},{style},,0,0,0,,{{{anim_base}\\bord{gb2}\\blur{gb2}\\3c{glow_color}\\1c{glow_color}\\3a&H40&\\1a&H40&{gb_osc}{sway}}}{text}")
            lines.append(f"Dialogue: 3,{t_start_s},{t_end_s},{style},,0,0,0,,{{\\an5{pos_tag}{in_tag}{out_tag}{shake_tag}{fsp_tag}\\bord{sh_bord}\\3c&H00000000&\\1c&H00000000&\\3a&H40&\\1a&H40&}}{text}")
            lines.append(f"Dialogue: 4,{t_start_s},{t_end_s},{style},,0,0,0,,{{{anim_base}{stroke_tag}\\3c&H00000000&\\1c{color}{sway}}}{text}")
    return "\n".join(lines)


def _source_has_audio(path: str) -> bool:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a",
             "-show_entries", "stream=index", "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=20,
        )
        return bool(r.stdout.strip())
    except Exception:
        return True


def _tv_grade_parts(src: str, dst: str, is_vertical: bool = True) -> List[str]:
    """Viral grade: clean denoise + professional DaVinci tetrahedral 3D LUT + subtle CAS sharpen.
    Eliminates pulsing brightness, milky bloom, and harsh double unsharp artifacting."""
    lut_path = os.path.join(BASE_DIR, "tv_grade.cube")
    if os.path.exists(lut_path):
        esc_lut = lut_path.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        lut_filter = f"lut3d=file='{esc_lut}':interp=tetrahedral,"
    else:
        lut_filter = "curves=m='0/0 0.25/0.22 0.5/0.52 0.75/0.78 1/1',"
    chain = (
        "hqdn3d=1.2:1.2:5:5,"
        f"{lut_filter}"
        "eq=contrast=1.05:saturation=1.10:brightness=0.01,"
        "cas=0.30,"
        "format=yuv420p"
    )
    return [f"{src}{chain}{dst}"]


def _apply_fx_chain(filter_parts: List[str], curr_v: str, fx_list: List[FxOverlay],
                    out_w: int, out_h: int, total_dur: float, tag_prefix: str) -> str:
    """Burn FX overlay elements (flash / bars / shake) onto curr_v in order.
    Returns the new current video label. Shake uses lanczos to avoid blur;
    flash uses rapid attack and additive blend for authentic viral impact."""
    for fi, fx in enumerate(fx_list):
        try:
            s0 = max(0.0, float(fx.start))
            e0 = min(total_dur, float(fx.end))
        except (TypeError, ValueError):
            continue
        if not (e0 > s0 + 0.05):
            continue
        d = e0 - s0
        en = f"'between(t,{s0:.3f},{e0:.3f})'"
        if fx.kind == "shake":
            a = max(2, min(40, int(fx.amp or 10)))
            fq = max(2.0, min(15.0, float(fx.freq or 7.0)))
            filter_parts.append(
                f"{curr_v}split=2[{tag_prefix}v{fi}a][{tag_prefix}v{fi}b]"
            )
            filter_parts.append(
                f"[{tag_prefix}v{fi}b]crop=iw-{2*a}:ih-{2*a}:"
                f"x='{a}+{a}*sin(2*PI*{fq:.1f}*t)':y='{a}+{a}*cos(2*PI*{fq*9/7:.1f}*t)',"
                f"scale={out_w}:{out_h}:flags=lanczos+accurate_rnd[{tag_prefix}v{fi}s]"
            )
            filter_parts.append(f"[{tag_prefix}v{fi}a][{tag_prefix}v{fi}s]overlay=x=0:y=0:enable={en}[{tag_prefix}v{fi}]")
            curr_v = f"[{tag_prefix}v{fi}]"
        elif fx.kind == "bars":
            bh = max(20, min(out_h // 3, int(fx.bar_h or 120)))
            prog = f"min(1,min(t-{s0:.3f},{e0:.3f}-t)/0.35)"
            sh_amp, sh_f = 0, 7.0
            for sx in fx_list:
                if sx.kind != "shake":
                    continue
                try:
                    ss = max(0.0, float(sx.start)); se = min(total_dur, float(sx.end))
                except (TypeError, ValueError):
                    continue
                if ss < e0 and se > s0:
                    sh_amp = max(sh_amp, max(2, min(40, int(sx.amp or 10))))
                    sh_f = max(2.0, min(15.0, float(sx.freq or 7.0)))
            sh_y = (f"{sh_amp}*cos(2*PI*{sh_f*9/7:.1f}*t)*between(t,{s0:.3f},{e0:.3f})") if sh_amp else "0"
            filter_parts.append(f"color=c=black:s={out_w}x{bh}:d={d:.3f},format=rgba,setpts=PTS+{s0:.3f}/TB[{tag_prefix}c{fi}t]")
            filter_parts.append(f"color=c=black:s={out_w}x{bh}:d={d:.3f},format=rgba,setpts=PTS+{s0:.3f}/TB[{tag_prefix}c{fi}b]")
            filter_parts.append(
                f"{curr_v}[{tag_prefix}c{fi}t]overlay=x=0:y='-{bh}+{bh}*{prog}+{sh_y}':enable={en}[{tag_prefix}m{fi}]"
            )
            filter_parts.append(
                f"[{tag_prefix}m{fi}][{tag_prefix}c{fi}b]overlay=x=0:y='{out_h}-{bh}*{prog}+{sh_y}':enable={en}[{tag_prefix}v{fi}]"
            )
            curr_v = f"[{tag_prefix}v{fi}]"
        else:  # flash: punchy fast attack, addition/exposure mode
            peak = max(0.2, min(1.0, float(fx.peak or 0.85)))
            f_in = min(0.04, d * 0.15)
            f_out = max(0.08, d - f_in)
            if (fx.color or "white") == "bw":
                filter_parts.append(f"{curr_v}split=2[{tag_prefix}v{fi}a][{tag_prefix}v{fi}b]")
                filter_parts.append(
                    f"[{tag_prefix}v{fi}b]hue=s=0,format=rgba,"
                    f"fade=t=in:st={s0:.3f}:d={f_in:.3f}:alpha=1,"
                    f"fade=t=out:st={s0+f_in:.3f}:d={f_out:.3f}:alpha=1,"
                    f"colorchannelmixer=aa={peak:g}[{tag_prefix}v{fi}g]"
                )
                filter_parts.append(f"[{tag_prefix}v{fi}a][{tag_prefix}v{fi}g]overlay=x=0:y=0:enable={en}[{tag_prefix}v{fi}]")
            else:
                cmap = {"white": "white", "green": "0x39FF00", "red": "0xFF2222"}.get(fx.color or "white", "white")
                filter_parts.append(
                    f"color=c={cmap}:s={out_w}x{out_h}:d={total_dur:.3f},format=rgba,"
                    f"fade=t=in:st={s0:.3f}:d={f_in:.3f}:alpha=1,"
                    f"fade=t=out:st={s0+f_in:.3f}:d={f_out:.3f}:alpha=1,"
                    f"colorchannelmixer=aa={peak:g}[{tag_prefix}c{fi}]"
                )
                filter_parts.append(f"{curr_v}[{tag_prefix}c{fi}]blend=all_mode=addition:enable={en}[{tag_prefix}v{fi}]")
            curr_v = f"[{tag_prefix}v{fi}]"
    return curr_v


def _sfx_maybe_file(inputs: List[str], filter_parts: List[str], n_inputs: int,
                    kind: str, gain: float, at_ms: int, tag: str) -> Optional[int]:
    """Check if real audio file exists in sfx/ for this sound kind.
    If so, adds input and adelay/volume filter, returning new n_inputs.
    Otherwise returns None for synthetic fallback."""
    fname = SFX_FILES.get(kind.lower())
    if not fname:
        fname = f"{kind.lower()}.mp3"
    cand = os.path.join(SFX_DIR, fname)
    if not os.path.exists(cand):
        cand = os.path.join(SFX_DIR, f"{kind.lower()}.wav")
    if os.path.exists(cand):
        ain = n_inputs
        inputs.extend(["-i", cand])
        g = max(0.0, min(3.0, gain))
        dl = f"adelay={at_ms}|{at_ms}"
        filter_parts.append(
            f"[{ain}:a]aresample=48000,aformat=channel_layouts=stereo,volume={g:.2f},{dl}[{tag}]"
        )
        return ain + 1
    return None


def _remap_subtitles_for_segments(subtitles, segments, seg_out_starts, seg_lens):
    if not subtitles or not segments:
        return subtitles or []
    out = []
    first_seg_start = segments[0][0]
    for cue in subtitles:
        c_start = float(getattr(cue, "start", 0.0) if hasattr(cue, "start") else cue.get("start", 0.0))
        c_end = float(getattr(cue, "end", 0.0) if hasattr(cue, "end") else cue.get("end", 0.0))
        c_words = getattr(cue, "words", None) if hasattr(cue, "words") else cue.get("words", None)

        if len(segments) == 1 and c_start < first_seg_start and c_end <= seg_lens[0] + 0.5:
            out.append(cue)
            continue

        for k, (s_k, e_k) in enumerate(segments):
            if c_start < e_k and c_end > s_k:
                m_start = max(0.0, seg_out_starts[k] + (c_start - s_k))
                m_end = max(m_start + 0.1, seg_out_starts[k] + (c_end - s_k))
                mapped_words = []
                if c_words:
                    for w in c_words:
                        ws = getattr(w, "start", None) if hasattr(w, "start") else w.get("start")
                        we = getattr(w, "end", None) if hasattr(w, "end") else w.get("end")
                        wword = getattr(w, "word", "") if hasattr(w, "word") else w.get("word", "")
                        if ws is not None and we is not None:
                            mw_s = max(0.0, seg_out_starts[k] + (float(ws) - s_k))
                            mw_e = max(mw_s + 0.05, seg_out_starts[k] + (float(we) - s_k))
                            if hasattr(w, "__dict__") and not isinstance(w, dict):
                                import copy
                                mw = copy.copy(w)
                                mw.start = mw_s
                                mw.end = mw_e
                            else:
                                mw = dict(w)
                                mw["start"] = mw_s
                                mw["end"] = mw_e
                            mapped_words.append(mw)
                        else:
                            mapped_words.append(w)
                if hasattr(cue, "__dict__") and not isinstance(cue, dict):
                    import copy
                    nc = copy.copy(cue)
                    nc.start = m_start
                    nc.end = m_end
                    if mapped_words:
                        nc.words = mapped_words
                    out.append(nc)
                else:
                    nc = dict(cue)
                    nc["start"] = m_start
                    nc["end"] = m_end
                    if mapped_words:
                        nc["words"] = mapped_words
                    out.append(nc)
    return out


def _export_layered_clip(clip, out_path: str, out_filename: str, timestamp_str: str, idx: int) -> Optional[Dict[str, Any]]:
    """Layered compositing export: every timeline video/image element renders
    in z-order (bottom first), FX elements apply at their track level only
    (an FX under an upper layer never touches it), then grade, static frames,
    subtitles and free text on top. Mirrors the on-canvas preview."""
    layers = [L for L in (clip.layers or []) if L.source_file]
    if not layers:
        return None
    # resolve files
    for L in layers:
        p0 = os.path.join(DOWNLOADS_DIR, os.path.basename(L.source_file))
        if not os.path.exists(p0) and os.path.exists(L.source_file):
            p0 = L.source_file
        L.source_file = p0
    layers = [L for L in layers if os.path.exists(L.source_file)]
    if not layers:
        return None
    # clamp in-points against the real source length: a layer beyond EOF
    # would silently render as an empty input
    for L in layers:
        d = _probe_duration(L.source_file)
        if d and L.src_offset > d - 0.2:
            L.src_offset = max(0.0, d - max(0.2, float(L.duration or 1.0)))
    layers.sort(key=lambda L: -L.z)          # deepest (highest z) first
    base = layers[0]

    tv = clip.color_grade == "tv" and not clip.src_processed
    fmt = "talking_head_9_16" if clip.src_processed else clip.format
    if clip.format == "cinematic_16_9":
        out_w, out_h = (1920, 1080)
    else:
        out_w, out_h = (1080, 1920)
    top_h = int(round(out_h * 0.45 / 2) * 2)
    bot_h = out_h - top_h

    total_dur = max(0.5, float(base.duration or 0.0) or max((L.duration for L in layers), default=1.0))
    total_dur = max(0.5, min(total_dur, 600.0))

    inputs: List[str] = []
    filter_parts: List[str] = []
    n_inputs = 0
    layer_audio: List[str] = []

    # crop preset for the base layer template geometry
    crop_x = "(iw-ow)/2"
    crop_y = "0"
    if clip.crop_preset == "top_left":
        crop_x = "0"
    elif clip.crop_preset == "top_right":
        crop_x = "iw-ow"
    elif clip.crop_preset == "center":
        crop_x = "(iw-ow)/2"
    elif clip.crop_preset == "face":
        crop_x = "(iw-ow)/2"
        crop_y = "(ih-oh)/3"

    bg_path = None
    if clip.background_file:
        bg_candidate = os.path.join(DOWNLOADS_DIR, os.path.basename(clip.background_file))
        if os.path.exists(bg_candidate):
            bg_path = bg_candidate

    # FX on tracks ABOVE the topmost text layer burn OVER the text
    text_z = clip.text_z if clip.text_z is not None else -1
    fx_over_text = sorted([fx for fx in (clip.overlays or []) if (fx.z or 0) <= text_z],
                          key=lambda fx: -(fx.z or 0))
    fx_normal = [fx for fx in (clip.overlays or []) if (fx.z or 0) > text_z]

    z_levels = sorted({L.z for L in layers}, reverse=True)  # deepest first
    comp = None
    for li, L in enumerate(layers):
        is_base = li == 0
        inputs.extend(["-ss", f"{max(0.0, L.src_offset):.3f}", "-t", f"{max(0.2, L.duration or total_dur):.3f}", "-i", L.source_file])
        src_i = n_inputs
        n_inputs += 1
        op = max(0.05, min(1.0, float(L.opacity if L.opacity is not None else 1.0)))
        if is_base:
            # ── template geometry on the base layer (aspect-fill, never distorts) ──
            def _fill_crop(src_tag, tw_, th_, out_tag):
                """Aspect-fill into tw_ x th_ using configured crop anchor."""
                ar = tw_ / max(1, th_)
                filter_parts.append(
                    f"[{src_tag}]crop=w='min(iw\\,ih*{ar:.5f})':h='min(ih\\,iw/{ar:.5f})':"
                    f"x='{crop_x}':y='{crop_y}',"
                    f"scale={tw_}:{th_}:force_original_aspect_ratio=increase:flags=lanczos+accurate_rnd,"
                    f"crop={tw_}:{th_}[{out_tag}]"
                )
            bx = clip.crop_box
            if bx:
                bw = f"{max(0.02, min(1.0, bx.w)):g}*iw"
                bh_ = f"{max(0.02, min(1.0, bx.h)):g}*ih"
                bxx = f"{max(0.0, min(0.98, bx.x)):g}*iw"
                byy = f"{max(0.0, min(0.98, bx.y)):g}*ih"
                if fmt == "split_adhd":
                    filter_parts.append(f"[{src_i}:v]split=2[stb{li}][sbb{li}]")
                    filter_parts.append(
                        f"[stb{li}]crop={bw}:{bh_}:{bxx}:{byy},"
                        f"scale={out_w}:{top_h}:force_original_aspect_ratio=increase,"
                        f"crop={out_w}:{top_h}[topL{li}]"
                    )
                    if not bg_path:
                        # нижний бэнд: рамка «Фон» (bg_box), если задана, иначе весь кадр
                        if clip.bg_box:
                            gx = clip.bg_box
                            gbw = f"{max(0.02, min(1.0, gx.w)):g}*iw"
                            gbh = f"{max(0.02, min(1.0, gx.h)):g}*ih"
                            gbxx = f"{max(0.0, min(0.98, gx.x)):g}*iw"
                            gbyy = f"{max(0.0, min(0.98, gx.y)):g}*ih"
                            filter_parts.append(
                                f"[sbb{li}]crop={gbw}:{gbh}:{gbxx}:{gbyy},"
                                f"scale={out_w}:{bot_h}:force_original_aspect_ratio=increase:flags=lanczos+accurate_rnd,"
                                f"crop={out_w}:{bot_h}[botL{li}]"
                            )
                        else:
                            filter_parts.append(
                                f"[sbb{li}]scale={out_w}:{bot_h}:force_original_aspect_ratio=increase,"
                                f"crop={out_w}:{bot_h}[botL{li}]"
                            )
                        filter_parts.append(f"[topL{li}][botL{li}]vstack=inputs=2[comp0]")
                        comp = "[comp0]"
                elif fmt == "talking_head_9_16":
                    filter_parts.append(
                        f"[{src_i}:v]crop={bw}:{bh_}:{bxx}:{byy},"
                        f"scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
                        f"crop={out_w}:{out_h}[comp0]"
                    )
                    comp = "[comp0]"
                else:
                    filter_parts.append(
                        f"[{src_i}:v]crop={bw}:{bh_}:{bxx}:{byy},"
                        f"scale={out_w}:{out_h}:flags=lanczos[comp0]"
                    )
                    comp = "[comp0]"
            elif fmt == "split_adhd":
                if bg_path:
                    _fill_crop(src_i, out_w, top_h, f"topL{li}")
                else:
                    filter_parts.append(f"[{src_i}:v]split=2[stb{li}][sbb{li}]")
                    _fill_crop(f"stb{li}", out_w, top_h, f"topL{li}")
                    if clip.bg_box:
                        gx = clip.bg_box
                        gbw = f"{max(0.02, min(1.0, gx.w)):g}*iw"
                        gbh = f"{max(0.02, min(1.0, gx.h)):g}*ih"
                        gbxx = f"{max(0.0, min(0.98, gx.x)):g}*iw"
                        gbyy = f"{max(0.0, min(0.98, gx.y)):g}*ih"
                        filter_parts.append(
                            f"[sbb{li}]crop={gbw}:{gbh}:{gbxx}:{gbyy},"
                            f"scale={out_w}:{bot_h}:force_original_aspect_ratio=increase:flags=lanczos+accurate_rnd,"
                            f"crop={out_w}:{bot_h}[botL{li}]"
                        )
                    else:
                        filter_parts.append(
                            f"[sbb{li}]scale={out_w}:{bot_h}:force_original_aspect_ratio=increase:flags=lanczos+accurate_rnd,"
                            f"crop={out_w}:{bot_h}[botL{li}]"
                        )
                    filter_parts.append(f"[topL{li}][botL{li}]vstack=inputs=2[comp0]")
                    comp = "[comp0]"
            elif fmt == "talking_head_9_16":
                # vertical crop: right-anchored for top presets, centered otherwise
                if clip.crop_preset in ("top_left", "top_right"):
                    ax = "0" if clip.crop_preset == "top_left" else "iw-ow"
                    ay = "0"
                elif clip.crop_preset == "face":
                    ax = "(iw-ow)/2"
                    ay = "(ih-oh)/3"
                else:
                    ax = "(iw-ow)/2"
                    ay = "0"
                ar = out_w / float(out_h)
                filter_parts.append(
                    f"[{src_i}:v]crop=w='min(iw\\,ih*{ar:.5f})':h='min(ih\\,iw/{ar:.5f})':"
                    f"x='{ax}':y='{ay}',"
                    f"scale={out_w}:{out_h}:force_original_aspect_ratio=increase:flags=lanczos+accurate_rnd,"
                    f"crop={out_w}:{out_h}[comp0]"
                )
                comp = "[comp0]"
            else:
                filter_parts.append(f"[{src_i}:v]scale={out_w}:{out_h}:flags=lanczos[comp0]")
                comp = "[comp0]"
        else:
            # ── upper layer: PiP overlay (if pip/track_path explicitly set) or fullscreen cover overlay ──
            if L.pip or L.track_path:
                pip = L.pip or PipBox()
                pw = max(0.05, min(0.95, float(pip.w or 0.30)))
                ov_w = max(24, int(out_w * pw))
                chain = f"[{src_i}:v]scale={ov_w}:-2:flags=lanczos+accurate_rnd,format=rgba"
                if op < 0.99:
                    chain += f",colorchannelmixer=aa={op:g}"
                o_start = max(0.0, float(L.out_start or 0.0))
                o_end = min(total_dur, o_start + max(0.2, float(L.duration or total_dur)))
                if o_start > 0.01:
                    chain += f",setpts=PTS+{o_start:.3f}/TB"
                filter_parts.append(chain + f"[ovlL{li}]")
                if L.track_path:
                    points = _downsample_track_path(L.track_path)
                    x_expr = _build_track_expr(points, "x", out_w, out_h)
                    y_expr = _build_track_expr(points, "y", out_w, out_h)
                    x_full = f"max(0,min({x_expr}-w/2,W-w))"
                    y_full = f"max(0,min({y_expr}-h/2,H-h))"
                else:
                    x_full = f"max(4,min({max(0.0, float(pip.x)) * out_w:.1f},W-w-4))"
                    y_full = f"max(4,min({max(0.0, float(pip.y)) * out_h:.1f},H-h-4))"
                en = ""
                if o_start > 0.01 or o_end < total_dur - 0.01:
                    en = f":enable='between(t,{o_start:.3f},{o_end:.3f})'"
                filter_parts.append(f"{comp}[ovlL{li}]overlay=x='{x_full}':y='{y_full}':format=auto{en}[eoL{li}]")
                comp = f"[eoL{li}]"
            else:
                # Fullscreen / cover video overlay (B-roll or camera angle switch, not corner duplicate)
                chain = f"[{src_i}:v]scale={out_w}:{out_h}:force_original_aspect_ratio=increase:flags=lanczos+accurate_rnd,crop={out_w}:{out_h},format=rgba"
                if op < 0.99:
                    chain += f",colorchannelmixer=aa={op:g}"
                o_start = max(0.0, float(L.out_start or 0.0))
                o_end = min(total_dur, o_start + max(0.2, float(L.duration or total_dur)))
                if o_start > 0.01:
                    chain += f",setpts=PTS+{o_start:.3f}/TB"
                filter_parts.append(chain + f"[ovlL{li}]")
                en = ""
                if o_start > 0.01 or o_end < total_dur - 0.01:
                    en = f":enable='between(t,{o_start:.3f},{o_end:.3f})'"
                filter_parts.append(f"{comp}[ovlL{li}]overlay=x=0:y=0:format=auto{en}[eoL{li}]")
                comp = f"[eoL{li}]"
        # this layer's own audio into the mix
        if not L.muted and _source_has_audio(L.source_file):
            gain = max(0.0, min(3.0, float(L.volume if L.volume is not None else 1.0)))
            delay_ms = int(max(0.0, float(L.out_start or 0.0)) * 1000)
            dl = f",adelay={delay_ms}|{delay_ms}" if delay_ms > 0 else ""
            filter_parts.append(f"[{src_i}:a]aresample=48000,aformat=channel_layouts=stereo,volume={gain}{dl}[la{li}]")
            layer_audio.append(f"[la{li}]")
        # FX that live on this z level (below text) burn onto the composite
        fx_here = [fx for fx in fx_normal if (fx.z or 0) == (L.z or 0)]
        if fx_here:
            comp = _apply_fx_chain(filter_parts, comp, fx_here, out_w, out_h, total_dur, f"z{L.z}_")
    # FX on levels with no active layer still apply at their depth
    used_z = set(z_levels)
    for z in sorted({(fx.z or 0) for fx in fx_normal}, reverse=True):
        if z in used_z:
            continue
        fx_here = [fx for fx in fx_normal if (fx.z or 0) == z]
        if fx_here:
            comp = _apply_fx_chain(filter_parts, comp, fx_here, out_w, out_h, total_dur, f"z{z}_")
            used_z.add(z)

    # background input for split bottom (looped)
    if clip.format == "split_adhd" and bg_path and comp and "[comp0]" in comp and not any(
            k in "".join(filter_parts) for k in ("botL0",)):
        inputs.extend(["-stream_loop", "-1", "-t", f"{total_dur:.3f}", "-i", bg_path])
        bg_i = n_inputs
        n_inputs += 1
        filter_parts.append(
            f"[{bg_i}:v]scale={out_w}:{bot_h}:force_original_aspect_ratio=increase,"
            f"crop={out_w}:{bot_h}[bgBot]"
        )
        filter_parts.append(f"{comp}[bgBot]overlay=x=0:y={top_h}[compBG]")
        comp = "[compBG]"

    if comp is None:
        return None

    # ── TV color grade on the full composite ──
    if tv:
        filter_parts.extend(_tv_grade_parts(comp, "[graded]", is_vertical=(out_w < out_h)))
        comp = "[graded]"

    # ── static cinematic frames (рамки сверху/снизу) ──
    bt = max(0, min(out_h // 3, int(clip.bar_top or 0)))
    bb = max(0, min(out_h // 3, int(clip.bar_bottom or 0)))
    if bt > 0 or bb > 0:
        parts = []
        if bt > 0:
            parts.append(f"drawbox=x=0:y=0:w={out_w}:h={bt}:color=black:t=fill")
        if bb > 0:
            parts.append(f"drawbox=x=0:y={out_h - bb}:w={out_w}:h={bb}:color=black:t=fill")
        filter_parts.append(f"{comp}{','.join(parts)}[barred]")
        comp = "[barred]"

    # ── subtitles (output-local) — skipped for already-processed sources ──
    ass_path = None
    if clip.subtitles and not clip.src_processed:
        subs = clip.subtitles
        if clip.subs_in_output_time:
            remapped = subs
        else:
            remapped = _remap_subtitles_for_segments(subs, [(0.0, total_dur)], [0], [total_dur])
        if remapped:
            margin_v = int(out_h * 0.55) if clip.format == "split_adhd" else (int(out_h * 0.38) if clip.format == "talking_head_9_16" else int(out_h * 0.12))
            opts = _tv_sub_opts(clip.subtitle_template, clip, remapped)
            if clip.subtitle_template in TV_TEMPLATES_CONFIG or clip.subtitle_template in TV_SUB_COLORS:
                ass_content = build_tv_subtitles_ass(remapped, opts["default_style"], out_w, out_h, margin_v,
                                                     font=opts["font"], size_mul=opts["size_mul"],
                                                     glow=opts["glow"], anim=opts["anim"],
                                                     hot_words=bool(getattr(clip, "hot_words", True)))
            else:
                ass_content = generate_ass_subtitle_content(remapped, clip.subtitle_template)
            ass_path = os.path.join(DOWNLOADS_DIR, f"temp_sub_{idx}_{timestamp_str}.ass")
            with open(ass_path, "w", encoding="utf-8") as f:
                f.write(ass_content)

    # ── free text elements (skipped in passthrough too) ──
    text_ass_path = None
    if clip.text_items and not clip.src_processed:
        tass = build_text_elements_ass(clip.text_items, out_w, out_h)
        if tass.strip():
            text_ass_path = os.path.join(DOWNLOADS_DIR, f"temp_txt_{idx}_{timestamp_str}.ass")
            with open(text_ass_path, "w", encoding="utf-8") as f:
                f.write(tass)

    def burn_ass(curr, path):
        escaped = path.replace("\\", "/").replace(":", "\\:")
        fontsdir = FONTS_DIR.replace("\\", "/").replace(":", "\\:")
        filter_parts.append(f"{curr}subtitles=filename='{escaped}':fontsdir='{fontsdir}'[assout]")
        return "[assout]"

    if ass_path and os.path.exists(ass_path):
        comp = burn_ass(comp, ass_path)
    if text_ass_path and os.path.exists(text_ass_path):
        comp = burn_ass(comp, text_ass_path)

    # FX from layers ABOVE the text layer burn over the subtitles/text
    if fx_over_text:
        comp = _apply_fx_chain(filter_parts, comp, fx_over_text, out_w, out_h, total_dur, "otx_")

    # ── audio: layers' own audio + real SFX + synth fallback + timeline music ──
    def _sfx_chain(kind: str, gain: float, at_ms: int, tag: str) -> str:
        g = max(0.0, min(3.0, gain))
        dl = f"adelay={at_ms}|{at_ms}"
        if kind == "approve":
            return (f"sine=frequency=700:duration=0.12,adelay={at_ms}|{at_ms}[{tag}a];"
                    f"sine=frequency=1050:duration=0.22,adelay={at_ms + 110}|{at_ms + 110}[{tag}b];"
                    f"[{tag}a][{tag}b]amix=inputs=2:normalize=0,volume={g}[{tag}]")
        if kind == "cancel":
            return (f"sine=frequency=420:duration=0.15,adelay={at_ms}|{at_ms}[{tag}a];"
                    f"sine=frequency=250:duration=0.30,adelay={at_ms + 150}|{at_ms + 150}[{tag}b];"
                    f"[{tag}a][{tag}b]amix=inputs=2:normalize=0,volume={g}[{tag}]")
        if kind == "pop":
            return f"sine=frequency=520:duration=0.07,afade=t=out:st=0.02:d=0.05,{dl},volume={g}[{tag}]"
        if kind == "whoosh":
            return (f"anoisesrc=d=0.45:c=white:r=48000:a=0.5,lowpass=f=900,"
                    f"afade=t=in:st=0:d=0.15,afade=t=out:st=0.25:d=0.2,{dl},volume={g}[{tag}]")
        if kind == "boom":
            return (f"sine=frequency=110:duration=0.5,afade=t=in:st=0:d=0.02,afade=t=out:st=0.12:d=0.38,"
                    f"{dl},volume={g * 1.2:.2f}[{tag}]")
        if kind == "cheer":
            return (f"anoisesrc=d=1.1:c=pink:r=48000:a=0.55,bandpass=f=1600:w=900,"
                    f"tremolo=f=9:d=0.6,afade=t=in:st=0:d=0.15,afade=t=out:st=0.7:d=0.4,{dl},volume={g}[{tag}]")
        if kind == "riser":
            return (f"sine=frequency=300:duration=0.8,volume=0.6,"
                    f"afade=t=in:st=0:d=0.6,afade=t=out:st=0.65:d=0.15,{dl},volume={g}[{tag}]")
        return (f"anoisesrc=d=0.16:c=white:r=48000:a=0.9,highpass=f=1500,"
                f"afade=t=out:st=0.06:d=0.1,{dl},volume={g}[{tag}]")

    mix_labels = list(layer_audio)
    for qi, snd in enumerate(clip.sounds or []):
        try:
            kind = (snd.kind or "click").lower()
            if kind == "none":
                continue
            gain = float(snd.gain if snd.gain is not None else 1.0)
            at_ms = int(max(0.0, float(snd.at)) * 1000)
        except (TypeError, ValueError):
            continue
        new_n = _sfx_maybe_file(inputs, filter_parts, n_inputs, kind, gain, at_ms, f"sfx{qi}")
        if new_n is None:
            filter_parts.append(_sfx_chain(kind, gain, at_ms, f"sfx{qi}"))
        else:
            n_inputs = new_n
        mix_labels.append(f"[sfx{qi}]")
    _duck_split_done = set()
    for ai, au in enumerate(clip.extra_audio or []):
        try:
            apath = os.path.join(DOWNLOADS_DIR, os.path.basename(au.filename))
            if not os.path.exists(apath):
                continue
            gain = max(0.0, min(3.0, float(au.gain if au.gain is not None else 1.0)))
            off = max(0.0, float(au.src_offset or 0.0))
            dur = max(0.2, float(au.duration or 5.0))
            place = int(max(0.0, float(au.out_start or 0.0)) * 1000)
        except (TypeError, ValueError):
            continue
        ain = n_inputs
        in_args = ["-ss", str(off), "-t", str(dur)]
        if au.loop:
            in_args = ["-stream_loop", "-1", "-ss", str(off), "-t", str(dur)]
        inputs.extend(in_args + ["-i", apath])
        n_inputs += 1
        mtag = f"mx{ai}"
        filter_parts.append(
            f"[{ain}:a]aresample=48000,aformat=channel_layouts=stereo,"
            f"volume={gain},adelay={place}|{place}[{mtag}raw]"
        )
        if au.duck:
            # duck under the main voice: the voice stream must be SPLIT —
            # one copy keys the compressor, the other goes into the final mix
            if mix_labels and mix_labels[0] not in _duck_split_done:
                first = mix_labels[0]
                base_lbl = first[1:-1]
                _duck_split_done.add(first)
                filter_parts.append(f"{first}asplit=2[{base_lbl}dk]{first}")
                filter_parts.append(
                    f"[{mtag}raw][{base_lbl}dk]sidechaincompress=threshold=0.02:ratio=9:"
                    f"attack=15:release=450[{mtag}]"
                )
            else:
                filter_parts.append(f"[{mtag}raw]volume=0.55[{mtag}]")
        else:
            filter_parts.append(f"[{mtag}raw]anull[{mtag}]")
        mix_labels.append(f"[{mtag}]")

    if mix_labels:
        filter_parts.append(
            "".join(mix_labels) + f"amix=inputs={len(mix_labels)}:duration=longest:normalize=0,apad=whole_dur={total_dur:.3f},loudnorm=I=-14:TP=-1.5:LRA=11[aout]"
        )
        audio_map = "[aout]"
    else:
        filter_parts.append(f"anullsrc=r=48000:cl=stereo:d={total_dur:.3f}[aout]")
        audio_map = "[aout]"

    filter_complex_str = ";".join(filter_parts)
    # Метаданные как у профессионального экспорта (Adobe Media Encoder / Premiere):
    # -map_metadata -1 убирает служебные теги, bitexact подавляет Lavf/Lavc-подписи,
    # creation_time пишется как в AME. Итог: чистый isom без следов ffmpeg.
    ame_time = time.strftime("%Y-%m-%dT%H:%M:%S.000000Z", time.gmtime())
    ffmpeg_cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", filter_complex_str,
        "-map", comp,
        "-map", audio_map,
        "-t", f"{total_dur:.3f}",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "15",
        "-tune", "film",
        "-x264-params", "aq-mode=3:aq-strength=0.9:deblock=-1,-1",
        "-g", "60",
        "-bf", "3",
        "-pix_fmt", "yuv420p",
        "-colorspace", "bt709",
        "-color_primaries", "bt709",
        "-color_trc", "bt709",
        "-color_range", "tv",
        "-c:a", "aac",
        "-b:a", "256k",
        "-ar", "48000",
        "-movflags", "+faststart",
        "-map_metadata", "-1",
        "-fflags", "+bitexact",
        "-flags:v", "+bitexact",
        "-flags:a", "+bitexact",
        "-metadata", f"creation_time={ame_time}",
        out_path
    ]
    try:
        ffmpeg_env = os.environ.copy()
        if "FONTCONFIG_PATH" not in ffmpeg_env and sys.platform == "win32":
            ffmpeg_env["FONTCONFIG_PATH"] = FONTS_DIR
        render_res = subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=900, env=ffmpeg_env)
        if render_res.returncode == 0 and os.path.exists(out_path):
            return {
                "id": clip.id,
                "filename": out_filename,
                "path": out_path,
                "duration": total_dur,
                "segments": 1,
                "layers": len(layers),
                "size_bytes": os.path.getsize(out_path),
                "size_formatted": format_bytes(os.path.getsize(out_path)),
                "stream_url": f"/api/media/stream?file=exported_packs/{out_filename}",
                "download_url": f"/api/media/stream?file=exported_packs/{out_filename}"
            }
        print(f"[layered] FFmpeg error ({render_res.returncode}): {render_res.stderr[-1200:] if render_res.stderr else 'unknown'}")
    except Exception as e:
        print(f"[layered] Error rendering clip {clip.id}: {e}")
    finally:
        for p in (locals().get("ass_path"), locals().get("text_ass_path")):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
    return None


@app.post("/api/export-pack")
def export_clip_pack(req: ExportPackRequest):
    r"""
    Renders highlight clips into finished vertical 9:16 shorts (matching c:\new\example.mp4).
    Supports 50/50 split, facecam crop presets, platform badge, and burned-in animated subtitles.
    """
    if not req.clips:
        raise HTTPException(status_code=400, detail="Список клипов для экспорта пуст")

    results = []
    failed = []
    timestamp_str = time.strftime("%Y%m%d_%H%M%S")
    FLASH = 0.22  # мягкая белая вспышка-раствор между моментами (как в референсах)

    for idx, clip in enumerate(req.clips):
        # ── Layered compositing mode (elements from the layers panel) ──
        if clip.layers:
            timestamp_str2 = timestamp_str
            clean_handle0 = sanitize_filename(clip.streamer_handle.replace("@", "") or "clip")
            out_filename0 = f"Short_{clean_handle0}_{timestamp_str}_{idx+1}.mp4"
            out_path0 = os.path.join(EXPORTED_PACKS_DIR, out_filename0)
            res = _export_layered_clip(clip, out_path0, out_filename0, timestamp_str2, idx)
            if res:
                results.append(res)
            else:
                failed.append({
                    "id": clip.id,
                    "title": (getattr(clip, "title", "") or clip.id),
                    "error": "FFmpeg не смог отрендерить клип — подробности в логе сервера",
                })
            continue

        source_path = os.path.join(DOWNLOADS_DIR, os.path.basename(clip.source_file))
        if not os.path.exists(source_path):
            if os.path.exists(clip.source_file):
                source_path = clip.source_file
            else:
                print(f"[export] skip clip {clip.id}: source not found: {source_path!r} (raw: {clip.source_file!r})")
                failed.append({
                    "id": clip.id,
                    "title": (getattr(clip, "title", "") or clip.id),
                    "error": f"Исходник не найден: {os.path.basename(clip.source_file)}",
                })
                continue

        # ── Segments (multi-moment cut) ──
        if clip.segments:
            segments = [(max(0.0, s.start_time), max(0.0, s.end_time)) for s in clip.segments]
            segments = [(s, e) for s, e in segments if e - s > 0.4]
        if not clip.segments or not segments:
            segments = [(clip.start_time, clip.end_time)]
        seg_lens = [max(0.4, e - s) for (s, e) in segments]
        n_seg = len(segments)
        skip_flash = set(int(x) for x in (clip.skip_flash_at or []) if 0 <= int(x) < n_seg - 1)
        n_flash = (n_seg - 1 - len(skip_flash)) if (clip.flash_cuts and n_seg > 1) else 0
        total_dur = sum(seg_lens) - FLASH * n_flash
        total_dur = max(0.5, total_dur)

        clean_handle = sanitize_filename(clip.streamer_handle.replace("@", "") or "clip")
        out_filename = f"Short_{clean_handle}_{timestamp_str}_{idx+1}.mp4"
        out_path = os.path.join(EXPORTED_PACKS_DIR, out_filename)

        # ── Output resolution: 1080x1920 for vertical, 1920x1080 for 16:9 ──
        if clip.format == "cinematic_16_9":
            out_w, out_h = (1920, 1080)
        else:
            out_w, out_h = (1080, 1920)

        # Facecam crop window for the top band of split / full-frame crop of talking head
        # (heights forced even: libx264 yuv420p rejects odd dimensions).
        # Default anchor: RIGHT-TOP (talking-head streams keep the face on the
        # right; a centered default grabs excess background from the left).
        top_h = int(round(out_h * 0.45 / 2) * 2)
        bot_h = out_h - top_h
        crop_x = "(iw-ow)/2"
        crop_y = "0"
        if clip.crop_preset == "top_left":
            crop_x = "0"
            crop_y = "0"
        elif clip.crop_preset == "top_right":
            crop_x = "iw-ow"
            crop_y = "0"
        elif clip.crop_preset == "center":
            crop_x = "(iw-ow)/2"
            crop_y = "0"
        elif clip.crop_preset == "face":
            crop_x = "(iw-ow)/2"
            crop_y = "(ih-oh)/3"

        bg_path = None
        if clip.background_file:
            bg_candidate = os.path.join(DOWNLOADS_DIR, os.path.basename(clip.background_file))
            if os.path.exists(bg_candidate):
                bg_path = bg_candidate

        inputs: List[str] = []
        filter_parts: List[str] = []
        seg_labels = []
        audio_seg_labels = []
        n_inputs = 0

        # ── Per-segment geometry ──
        for si, (seg_start, seg_end) in enumerate(segments):
            inputs.extend(["-ss", str(seg_start), "-t", str(seg_lens[si]), "-i", source_path])
            src_i = n_inputs
            n_inputs += 1
            if clip.crop_box:
                # user-drawn webcam/face region: crop the box, then aspect-fill the target
                bx = clip.crop_box
                bw = f"{max(0.02, min(1.0, bx.w)):g}*iw"
                bh = f"{max(0.02, min(1.0, bx.h)):g}*ih"
                bxx = f"{max(0.0, min(0.98, bx.x)):g}*iw"
                byy = f"{max(0.0, min(0.98, bx.y)):g}*ih"
                if clip.format == "split_adhd":
                    filter_parts.append(f"[{src_i}:v]split=2[stop{si}][sbot{si}]")
                    filter_parts.append(
                        f"[stop{si}]crop={bw}:{bh}:{bxx}:{byy},"
                        f"scale={out_w}:{top_h}:force_original_aspect_ratio=increase,"
                        f"crop={out_w}:{top_h}[top{si}]"
                    )
                    if not bg_path:
                        filter_parts.append(
                            f"[sbot{si}]scale={out_w}:{bot_h}:force_original_aspect_ratio=increase,"
                            f"crop={out_w}:{bot_h}[bot{si}]"
                        )
                        filter_parts.append(f"[top{si}][bot{si}]vstack=inputs=2[g{si}]")
                elif clip.format == "talking_head_9_16":
                    filter_parts.append(
                        f"[{src_i}:v]crop={bw}:{bh}:{bxx}:{byy},"
                        f"scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
                        f"crop={out_w}:{out_h}[g{si}]"
                    )
                else:
                    filter_parts.append(
                        f"[{src_i}:v]crop={bw}:{bh}:{bxx}:{byy},"
                        f"scale={out_w}:{out_h}:flags=lanczos[g{si}]"
                    )
            elif clip.format == "split_adhd":
                # top: facecam band, aspect-fill (never distorts, never exceeds frame)
                ar_top = out_w / float(top_h)
                safe_crop = (f"crop=w='min(iw\\,ih*{ar_top:.5f})':h='min(ih\\,iw/{ar_top:.5f})':"
                             f"x='{crop_x}':y='{crop_y}'")
                if bg_path:
                    # bottom comes from the bg input (added later, split per segment)
                    filter_parts.append(
                        f"[{src_i}:v]{safe_crop},"
                        f"scale={out_w}:{top_h}:force_original_aspect_ratio=increase:flags=lanczos+accurate_rnd,"
                        f"crop={out_w}:{top_h}[top{si}]"
                    )
                else:
                    # bottom: bg_box region if the user picked one, else full frame
                    filter_parts.append(f"[{src_i}:v]split=2[stop{si}][sbot{si}]")
                    filter_parts.append(
                        f"[stop{si}]{safe_crop},"
                        f"scale={out_w}:{top_h}:force_original_aspect_ratio=increase:flags=lanczos+accurate_rnd,"
                        f"crop={out_w}:{top_h}[top{si}]"
                    )
                    if clip.bg_box:
                        gx = clip.bg_box
                        gbw = f"{max(0.02, min(1.0, gx.w)):g}*iw"
                        gbh = f"{max(0.02, min(1.0, gx.h)):g}*ih"
                        gbxx = f"{max(0.0, min(0.98, gx.x)):g}*iw"
                        gbyy = f"{max(0.0, min(0.98, gx.y)):g}*ih"
                        filter_parts.append(
                            f"[sbot{si}]crop={gbw}:{gbh}:{gbxx}:{gbyy},"
                            f"scale={out_w}:{bot_h}:force_original_aspect_ratio=increase:flags=lanczos+accurate_rnd,"
                            f"crop={out_w}:{bot_h}[bot{si}]"
                        )
                    else:
                        filter_parts.append(
                            f"[sbot{si}]scale={out_w}:{bot_h}:force_original_aspect_ratio=increase:flags=lanczos+accurate_rnd,"
                            f"crop={out_w}:{bot_h}[bot{si}]"
                        )
                    filter_parts.append(f"[top{si}][bot{si}]vstack=inputs=2[g{si}]")
            elif clip.format == "talking_head_9_16":
                ar_v = out_w / float(out_h)
                filter_parts.append(
                    f"[{src_i}:v]crop=w='min(iw\\,ih*{ar_v:.5f})':h='min(ih\\,iw/{ar_v:.5f})':"
                    f"x='{crop_x}':y='{crop_y}',"
                    f"scale={out_w}:{out_h}:force_original_aspect_ratio=increase:flags=lanczos+accurate_rnd,"
                    f"crop={out_w}:{out_h}[g{si}]"
                )
            else:  # cinematic_16_9
                filter_parts.append(f"[{src_i}:v]scale={out_w}:{out_h}:flags=lanczos[g{si}]")
            seg_labels.append(f"[g{si}]")

            # audio trim per segment: a flash overlap eats FLASH seconds of audio
            if n_seg > 1:
                junction_flash = bool(clip.flash_cuts and si < n_seg - 1 and (si not in skip_flash))
                a_len = seg_lens[si] if (si == n_seg - 1 or not junction_flash) else (seg_lens[si] - FLASH)
                filter_parts.append(f"[{src_i}:a]atrim=0:{a_len:.3f},asetpts=PTS-STARTPTS[aseg{si}]")
                audio_seg_labels.append(f"[aseg{si}]")

        # background input (single, split across segments)
        if clip.format == "split_adhd" and bg_path:
            inputs.extend(["-stream_loop", "-1", "-t", str(total_dur), "-i", bg_path])
            bg_i = n_inputs
            n_inputs += 1
            bg_splits = "".join(f"[bgk{k}]" for k in range(n_seg))
            filter_parts.append(f"[{bg_i}:v]split={n_seg}{bg_splits}")
            for si in range(n_seg):
                filter_parts.append(
                    f"[bgk{si}]scale={out_w}:{bot_h}:force_original_aspect_ratio=increase,"
                    f"crop={out_w}:{bot_h}[bot{si}]"
                )
                filter_parts.append(f"[top{si}][bot{si}]vstack=inputs=2[g{si}]")

        # ── Join segments: soft white flash (xfade) or hard concat, per junction ──
        if n_seg == 1:
            joined = "g0"
        elif clip.flash_cuts:
            prev = "g0"
            out_dur = seg_lens[0]
            for si in range(1, n_seg):
                out_lbl = f"x{si}"
                if (si - 1) in skip_flash:
                    # hard cut: plain concat keeps both segments full-length
                    filter_parts.append(f"[{prev}][g{si}]concat=n=2:v=1:a=0[{out_lbl}]")
                    out_dur += seg_lens[si]
                else:
                    filter_parts.append(
                        f"[{prev}][g{si}]xfade=transition=fadewhite:duration={FLASH}:offset={max(0.05, out_dur - FLASH):.3f}[{out_lbl}]"
                    )
                    out_dur += seg_lens[si] - FLASH
                prev = out_lbl
            joined = prev
        else:
            joined = f"cat{idx}"
            filter_parts.append(
                "".join(seg_labels) + f"concat=n={n_seg}:v=1:a=0[{joined}]"
            )

        curr_v = f"[{joined}]"

        # ── TV color grade (after join so both halves glow uniformly) ──
        if tv:
            filter_parts.extend(_tv_grade_parts(curr_v, "[graded]", is_vertical=(out_w < out_h)))
            curr_v = "[graded]"

        # ── Facecam PIP removed: the webcam band already shows the face,
        #     a duplicated PIP only clutters the frame ──
        pip_done = False

        # ── Platform badge (только legacy; в TV-референсах бейджа нет) ──
        if not tv:
            badge_platform = clip.platform.upper()
            badge_handle = clip.streamer_handle or "@STREAMER"
            badge_text = f"{badge_platform}  {badge_handle}".replace("'", "\\'")
            fontfile_opt = "fontfile='C\\:/Windows/Fonts/arial.ttf':" if sys.platform == "win32" else ""
            s = out_w / 576.0
            filter_parts.append(
                f"{curr_v}drawbox=x={int(18*s)}:y={int(18*s)}:w={int(190*s)}:h={int(34*s)}:color=black@0.85:t=fill,"
                f"drawtext={fontfile_opt}text='{badge_text}':x={int(26*s)}:y={int(28*s)}:fontsize={int(13*s)}:fontcolor=white[with_badge]"
            )
            curr_v = "[with_badge]"

        # ── Timeline FX overlays (flash / cinebars / shake).
        #     Overlay+enable based. Burned BEFORE subtitles so text stays on top. ──
        curr_v = _apply_fx_chain(filter_parts, curr_v, clip.overlays or [], out_w, out_h, total_dur, "fx")

        # ── static cinematic frames (рамки сверху/снизу) ──
        bt = max(0, min(out_h // 3, int(clip.bar_top or 0)))
        bb = max(0, min(out_h // 3, int(clip.bar_bottom or 0)))
        if bt > 0 or bb > 0:
            parts = []
            if bt > 0:
                parts.append(f"drawbox=x=0:y=0:w={out_w}:h={bt}:color=black:t=fill")
            if bb > 0:
                parts.append(f"drawbox=x=0:y={out_h - bb}:w={out_w}:h={bb}:color=black:t=fill")
            filter_parts.append(f"{curr_v}{','.join(parts)}[barred]")
            curr_v = "[barred]"

        # ── Subtitles ──
        ass_path = None
        if clip.subtitles:
            seg_out_starts = []
            acc = 0.0
            for k in range(n_seg):
                seg_out_starts.append(acc)
                junction_flash = bool(clip.flash_cuts and n_seg > 1 and k < n_seg - 1 and k not in skip_flash)
                acc += seg_lens[k] - (FLASH if junction_flash else 0)
            if clip.subs_in_output_time:
                remapped = clip.subtitles
            else:
                remapped = _remap_subtitles_for_segments(clip.subtitles, segments, seg_out_starts, seg_lens)
            if clip.subtitle_template in TV_TEMPLATES_CONFIG or clip.subtitle_template in TV_SUB_COLORS:
                margin_v = int(out_h * 0.55) if clip.format == "split_adhd" else (int(out_h * 0.38) if clip.format == "talking_head_9_16" else int(out_h * 0.12))
                opts = _tv_sub_opts(clip.subtitle_template, clip, remapped)
                ass_content = build_tv_subtitles_ass(remapped, opts["default_style"], out_w, out_h, margin_v,
                                                     font=opts["font"], size_mul=opts["size_mul"],
                                                     glow=opts["glow"], anim=opts["anim"],
                                                     hot_words=bool(getattr(clip, "hot_words", True)))
            else:
                # legacy styles: keep 576x1024 PlayRes (libass scales)
                ass_content = generate_ass_subtitle_content(remapped, clip.subtitle_template)
            if remapped:
                ass_path = os.path.join(DOWNLOADS_DIR, f"temp_sub_{idx}_{timestamp_str}.ass")
                with open(ass_path, "w", encoding="utf-8") as f:
                    f.write(ass_content)

        # ── Free text elements (AE-style) ──
        text_ass_path = None
        if clip.text_items:
            tass = build_text_elements_ass(clip.text_items, out_w, out_h)
            if tass.strip():
                text_ass_path = os.path.join(DOWNLOADS_DIR, f"temp_txt_{idx}_{timestamp_str}.ass")
                with open(text_ass_path, "w", encoding="utf-8") as f:
                    f.write(tass)

        def _burn_ass(curr, path):
            escaped = path.replace("\\", "/").replace(":", "\\:")
            fontsdir = FONTS_DIR.replace("\\", "/").replace(":", "\\:")
            filter_parts.append(f"{curr}subtitles=filename='{escaped}':fontsdir='{fontsdir}'[ass_out]")
            return "[ass_out]"

        if ass_path and os.path.exists(ass_path):
            curr_v = _burn_ass(curr_v, ass_path)
        if text_ass_path and os.path.exists(text_ass_path):
            curr_v = _burn_ass(curr_v, text_ass_path)

        # ── Tracked overlay media (object tracking: sticker/PiP follows the path) ──
        ovl_path = None
        if clip.overlay_file:
            ovl_candidate = os.path.join(DOWNLOADS_DIR, os.path.basename(clip.overlay_file))
            if os.path.exists(ovl_candidate):
                ovl_path = ovl_candidate
        if ovl_path:
            is_image = os.path.splitext(ovl_path)[1].lower() in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
            ovl_idx = n_inputs
            if is_image:
                inputs.extend(["-loop", "1", "-framerate", "30", "-t", str(total_dur), "-i", ovl_path])
            else:
                inputs.extend(["-ss", str(clip.start_time), "-t", str(total_dur), "-i", ovl_path])
            n_inputs += 1
            ov_w = max(24, int(out_w * max(0.05, min(0.9, clip.overlay_scale or 0.35))))
            filter_parts.append(f"[{ovl_idx}:v]scale={ov_w}:-2:flags=lanczos[ovl_src]")
            points = _downsample_track_path(clip.track_path or [])
            x_expr = _build_track_expr(points, "x", out_w, out_h)
            y_expr = _build_track_expr(points, "y", out_w, out_h)
            x_full = f"max(0,min({x_expr}-w/2,W-w))"
            y_full = f"max(0,min({y_expr}-h/2,H-h))"
            filter_parts.append(f"{curr_v}[ovl_src]overlay=x='{x_full}':y='{y_full}':format=auto[ovl_out]")
            curr_v = "[ovl_out]"

        # ── Audio map: main voice + synth SFX + timeline audio (music ducking, SFX) ──
        def _sfx_chain(kind: str, gain: float, at_ms: int, tag: str) -> str:
            g = max(0.0, min(3.0, gain))
            dl = f"adelay={at_ms}|{at_ms}"
            if kind == "approve":  # bright two-tone up
                return (f"sine=frequency=700:duration=0.12,adelay={at_ms}|{at_ms}[{tag}a];"
                        f"sine=frequency=1050:duration=0.22,adelay={at_ms + 110}|{at_ms + 110}[{tag}b];"
                        f"[{tag}a][{tag}b]amix=inputs=2:normalize=0,volume={g}[{tag}]")
            if kind == "cancel":  # dark two-tone down
                return (f"sine=frequency=420:duration=0.15,adelay={at_ms}|{at_ms}[{tag}a];"
                        f"sine=frequency=250:duration=0.30,adelay={at_ms + 150}|{at_ms + 150}[{tag}b];"
                        f"[{tag}a][{tag}b]amix=inputs=2:normalize=0,volume={g}[{tag}]")
            if kind == "pop":
                return f"sine=frequency=520:duration=0.07,afade=t=out:st=0.02:d=0.05,{dl},volume={g}[{tag}]"
            if kind == "whoosh":
                return (f"anoisesrc=d=0.45:c=white:r=48000:a=0.5,lowpass=f=900,"
                        f"afade=t=in:st=0:d=0.15,afade=t=out:st=0.25:d=0.2,{dl},volume={g}[{tag}]")
            if kind == "boom":  # deep impact (vine-boom style)
                return (f"sine=frequency=110:duration=0.5,afade=t=in:st=0:d=0.02,afade=t=out:st=0.12:d=0.38,"
                        f"{dl},volume={g * 1.2:.2f}[{tag}]")
            if kind == "cheer":  # crowd cheer (улюлюкания/аплодисменты, синтез)
                return (f"anoisesrc=d=1.1:c=pink:r=48000:a=0.55,bandpass=f=1600:w=900,"
                        f"tremolo=f=9:d=0.6,afade=t=in:st=0:d=0.15,afade=t=out:st=0.7:d=0.4,{dl},volume={g}[{tag}]")
            if kind == "riser":  # rising sweep into the drop
                return (f"sine=frequency=300:duration=0.8,volume=0.6,"
                        f"afade=t=in:st=0:d=0.6,afade=t=out:st=0.65:d=0.15,{dl},volume={g}[{tag}]")
            # click: camera shutter snap
            return (f"anoisesrc=d=0.16:c=white:r=48000:a=0.9,highpass=f=1500,"
                    f"afade=t=out:st=0.06:d=0.1,{dl},volume={g}[{tag}]")

        mix_labels = []
        _duck_split_done = False
        has_extras = bool(clip.sounds or clip.extra_audio)
        if has_extras:
            # main voice as a labeled stream
            if n_seg > 1:
                filter_parts.append("".join(audio_seg_labels) + f"concat=n={n_seg}:v=0:a=1,aresample=48000,aformat=channel_layouts=stereo[amain]")
            else:
                if _source_has_audio(source_path):
                    filter_parts.append("[0:a]aresample=48000,aformat=channel_layouts=stereo[amain]")
                else:
                    filter_parts.append(f"anullsrc=r=48000:cl=stereo:d={total_dur:.3f}[amain]")
            mix_labels.append("[amain]")
            # synth SFX
            for qi, snd in enumerate(clip.sounds or []):
                try:
                    kind = (snd.kind or "click").lower()
                    if kind == "none":
                        continue
                    gain = float(snd.gain if snd.gain is not None else 1.0)
                    at_ms = int(max(0.0, float(snd.at)) * 1000)
                except (TypeError, ValueError):
                    continue
                new_n = _sfx_maybe_file(inputs, filter_parts, n_inputs, kind, gain, at_ms, f"sfx{qi}")
                if new_n is None:
                    filter_parts.append(_sfx_chain(kind, gain, at_ms, f"sfx{qi}"))
                else:
                    n_inputs = new_n
                mix_labels.append(f"[sfx{qi}]")
            # timeline audio files (music / SFX from layers)
            for ai, au in enumerate(clip.extra_audio or []):
                try:
                    apath = os.path.join(DOWNLOADS_DIR, os.path.basename(au.filename))
                    if not os.path.exists(apath):
                        continue
                    gain = max(0.0, min(3.0, float(au.gain if au.gain is not None else 1.0)))
                    off = max(0.0, float(au.src_offset or 0.0))
                    dur = max(0.2, float(au.duration or 5.0))
                    place = int(max(0.0, float(au.out_start or 0.0)) * 1000)
                except (TypeError, ValueError):
                    continue
                ain = n_inputs
                in_args = ["-ss", str(off), "-t", str(dur)]
                if au.loop:
                    in_args = ["-stream_loop", "-1", "-ss", str(off), "-t", str(dur)]
                inputs.extend(in_args + ["-i", apath])
                n_inputs += 1
                mtag = f"mx{ai}"
                filter_parts.append(
                    f"[{ain}:a]aresample=48000,aformat=channel_layouts=stereo,"
                    f"volume={gain},adelay={place}|{place}[{mtag}raw]"
                )
                if au.duck:
                    # music ducks under the voice; [amain] is split so the mix
                    # still receives a copy (a stream can only be consumed once)
                    if not _duck_split_done:
                        _duck_split_done = True
                        filter_parts.append("[amain]asplit=2[amaindk]amain")
                        filter_parts.append(
                            f"[{mtag}raw][amaindk]sidechaincompress=threshold=0.02:ratio=9:"
                            f"attack=15:release=450:makeup=1[{mtag}]"
                        )
                    else:
                        filter_parts.append(f"[{mtag}raw]volume=0.55[{mtag}]")
                else:
                    filter_parts.append(f"[{mtag}raw]anull[{mtag}]")
                mix_labels.append(f"[{mtag}]")
            filter_parts.append(
                "".join(mix_labels) + f"amix=inputs={len(mix_labels)}:duration=longest:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[aout]"
            )
            audio_map = "[aout]"
        elif n_seg > 1:
            filter_parts.append("".join(audio_seg_labels) + f"concat=n={n_seg}:v=0:a=1,loudnorm=I=-14:TP=-1.5:LRA=11[aout]")
            audio_map = "[aout]"
        else:
            filter_parts.append("0:a?loudnorm=I=-14:TP=-1.5:LRA=11[aout]")
            audio_map = "[aout]"

        # Construct full FFmpeg command
        filter_complex_str = ";".join(filter_parts)
        ffmpeg_cmd = ["ffmpeg", "-y"] + inputs + [
            "-filter_complex", filter_complex_str,
            "-map", curr_v,
            "-map", audio_map,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "15",
            "-tune", "film",
            "-x264-params", "aq-mode=3:aq-strength=0.9:deblock=-1,-1",
            "-g", "60",
            "-bf", "3",
            "-pix_fmt", "yuv420p",
            "-colorspace", "bt709",
            "-color_primaries", "bt709",
            "-color_trc", "bt709",
            "-color_range", "tv",
            "-c:a", "aac",
            "-b:a", "256k",
            "-ar", "48000",
            "-movflags", "+faststart",
            out_path
        ]

        try:
            ffmpeg_env = os.environ.copy()
            if "FONTCONFIG_PATH" not in ffmpeg_env and sys.platform == "win32":
                ffmpeg_env["FONTCONFIG_PATH"] = FONTS_DIR

            render_res = subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=600, env=ffmpeg_env)
            if render_res.returncode == 0 and os.path.exists(out_path):
                results.append({
                    "id": clip.id,
                    "filename": out_filename,
                    "path": out_path,
                    "duration": total_dur,
                    "segments": n_seg,
                    "size_bytes": os.path.getsize(out_path),
                    "size_formatted": format_bytes(os.path.getsize(out_path)),
                    "stream_url": f"/api/media/stream?file=exported_packs/{out_filename}",
                    "download_url": f"/api/media/stream?file=exported_packs/{out_filename}"
                })
            else:
                print(f"FFmpeg render error ({render_res.returncode}): {render_res.stderr[-600:] if render_res.stderr else 'unknown'}")
        except Exception as e:
            print(f"Error rendering clip {clip.id}: {e}")
        finally:
            for p in (locals().get("ass_path"), locals().get("text_ass_path")):
                if p and os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass

    return {
        "status": "ok",
        "exported_count": len(results),
        "failed": failed,
        "clips": results
    }

@app.post("/api/preview-frame")
def preview_frame(req: dict):
    """Рендерит ОДИН кадр тем же фильтр-графом, что и финальный экспорт
    (кроп/сплит, FX, TV-грейд+bloom, субтитры, свободный текст) → PNG.
    Гарантирует превью == экспорт."""
    try:
        base_src = os.path.join(DOWNLOADS_DIR, os.path.basename(req.get("source_file", "")))
        if not os.path.exists(base_src):
            base_src = req.get("source_file")
        src_time = float(req.get("src_time", 0.0))
        fmt = req.get("format", "talking_head_9_16")
        W = int(req.get("width", 1080)); H = int(req.get("height", 1920))
        top_h = int(round(H * 0.45 / 2) * 2); bot_h = H - top_h
        crop_box = req.get("crop_box"); bg_box = req.get("bg_box")
        use_tv = req.get("color_grade") == "tv"
        subs = req.get("subtitles") or []
        text_items = req.get("text_items") or []
        overlays = req.get("overlays") or []
        t_rel = float(req.get("region_time", 0.0))

        ass_path = None; text_ass_path = None
        inputs: List[str] = ["-ss", f"{max(0.0, src_time):.3f}", "-i", base_src]
        n_inputs = 1
        fp: List[str] = []
        bx = crop_box
        if fmt == "split_adhd" and bx:
            bw = f"{max(0.02, min(1.0, bx.get('w', 0.5))):g}*iw"
            bh_ = f"{max(0.02, min(1.0, bx.get('h', 0.5))):g}*ih"
            bxx = f"{max(0.0, min(0.98, bx.get('x', 0.0))):g}*iw"
            byy = f"{max(0.0, min(0.98, bx.get('y', 0.0))):g}*ih"
            fp.append(f"[0:v]split=2[stb][sbb]")
            fp.append(f"[stb]crop={bw}:{bh_}:{bxx}:{byy},scale={W}:{top_h}:force_original_aspect_ratio=increase,crop={W}:{top_h}[topL]")
            if bg_box:
                gx = bg_box
                gbw = f"{max(0.02, min(1.0, gx.get('w', 0.5))):g}*iw"
                gbh = f"{max(0.02, min(1.0, gx.get('h', 0.5))):g}*ih"
                gbxx = f"{max(0.0, min(0.98, gx.get('x', 0.0))):g}*iw"
                gbyy = f"{max(0.0, min(0.98, gx.get('y', 0.0))):g}*ih"
                fp.append(f"[sbb]crop={gbw}:{gbh}:{gbxx}:{gbyy},scale={W}:{bot_h}:force_original_aspect_ratio=increase,crop={W}:{bot_h}[botL]")
            else:
                fp.append(f"[sbb]scale={W}:{bot_h}:force_original_aspect_ratio=increase,crop={W}:{bot_h}[botL]")
            fp.append(f"[topL][botL]vstack=inputs=2[comp0]")
            comp = "[comp0]"
        else:
            bw = f"min(iw\\,ih*{W / float(H):.5f})"
            bh_ = f"min(ih\\,iw/{W / float(H):.5f})"
            fp.append(f"[0:v]crop={bw}:{bh_},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}[comp0]")
            comp = "[comp0]"

        # FX (flash/bars) — фазы относительно t_rel
        fx_list = []
        for ov in overlays:
            st = float(ov.get("start", 0)) - t_rel
            en = float(ov.get("end", 0)) - t_rel
            if en < 0 or st > 0.25:
                continue
            fx_list.append(FxOverlay(kind=ov.get("kind", "flash"), start=max(0.0, st), end=en,
                                     color=ov.get("color", "white"), peak=float(ov.get("peak", 0.75)),
                                     bar_h=int(ov.get("bar_h", 160)), amp=float(ov.get("amp", 12)),
                                     freq=float(ov.get("freq", 7)), z=int(ov.get("z", 0))))
        if fx_list:
            comp = _apply_fx_chain(fp, comp, fx_list, W, H, 0.4, "pv_")

        # TV grade + bloom
        if use_tv:
            fp.extend(_tv_grade_parts(comp, "[graded]", is_vertical=(W < H)))
            comp = "[graded]"

        # субтитры: установившееся состояние (всё допечатано)
        ass_path = None
        if subs:
            settled = []
            for s in subs:
                dur = max(0.4, float(s.get("end", 1)) - float(s.get("start", 0)))
                words = [{"word": w.get("word", ""), "start": 0.0, "end": dur} for w in (s.get("words") or [])]
                settled.append({"text": s.get("text", ""), "start": 0.0, "end": dur,
                                "style": s.get("style"), "words": words,
                                "x": s.get("x"), "y": s.get("y")})
            margin_v = int(H * 0.55) if fmt == "split_adhd" else (int(H * 0.38) if fmt == "talking_head_9_16" else int(H * 0.12))
            sid = (settled[0].get("style") or req.get("subtitle_template") or "acid") if settled else "acid"
            ass_path = os.path.join(DOWNLOADS_DIR, f"temp_prev_{int(time.time()*1000)}.ass")
            with open(ass_path, "w", encoding="utf-8") as f:
                f.write(build_tv_subtitles_ass(settled, sid, W, H, margin_v,
                                               font=req.get("sub_font") or "Montserrat ExtraBold",
                                               size_mul=(req.get("sub_size") or 1.0), glow=75,
                                               anim="pop", hot_words=bool(req.get("hot_words", True))))
            esc_ass = ass_path.replace(chr(92), "/").replace(":", chr(92) + ":")
            esc_fonts = FONTS_DIR.replace(chr(92), "/").replace(":", chr(92) + ":")
            fp.append(f"{comp}subtitles=filename='{esc_ass}':fontsdir='{esc_fonts}'[subt]")
            comp = "[subt]"

        # свободный текст: установившееся состояние
        if text_items and not req.get("src_processed"):
            ti_settled = []
            for t in text_items:
                dur = max(0.4, float(t.get("end", 1)) - float(t.get("start", 0)))
                ti_settled.append({**t, "start": 0.0, "end": dur, "anim_in": "none"})
            text_ass_path = os.path.join(DOWNLOADS_DIR, f"temp_ptxt_{int(time.time()*1000)}.ass")
            with open(text_ass_path, "w", encoding="utf-8") as f:
                f.write(build_text_elements_ass(ti_settled, W, H))
            esc_t = text_ass_path.replace(chr(92), "/").replace(":", chr(92) + ":")
            fp.append(f"{comp}subtitles=filename='{esc_t}':fontsdir='{esc_fonts}'[ptxt]")
            comp = "[ptxt]"

        out_png = os.path.join(DOWNLOADS_DIR, f"temp_pvf_{int(time.time()*1000)}.png")
        cmd = ["ffmpeg", "-y", "-v", "error"] + inputs + [
            "-filter_complex", ";".join(fp), "-map", comp, "-frames:v", "1", out_png]
        env = os.environ.copy()
        if "FONTCONFIG_PATH" not in env and sys.platform == "win32":
            env["FONTCONFIG_PATH"] = FONTS_DIR
        render_res = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)
        for p in (ass_path, text_ass_path):
            if p and os.path.exists(p):
                try: os.remove(p)
                except Exception: pass
        if render_res.returncode == 0 and os.path.exists(out_png):
            with open(out_png, "rb") as f:
                data = f.read()
            try: os.remove(out_png)
            except Exception: pass
            return Response(content=data, media_type="image/png")
        print(f"[preview-frame] error: {render_res.stderr[-400:] if render_res.stderr else 'unknown'}")
        raise HTTPException(status_code=500, detail="Не удалось отрендерить кадр")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/exported-packs")
def list_exported_packs():
    """Lists all exported short clips."""
    items = []
    if not os.path.exists(EXPORTED_PACKS_DIR):
        return items

    for fname in sorted(os.listdir(EXPORTED_PACKS_DIR), reverse=True):
        if not fname.lower().endswith(".mp4"):
            continue
        fpath = os.path.join(EXPORTED_PACKS_DIR, fname)
        size_bytes = os.path.getsize(fpath)
        items.append({
            "filename": fname,
            "size_bytes": size_bytes,
            "size_formatted": format_bytes(size_bytes),
            "mtime": os.path.getmtime(fpath),
            "stream_url": f"/api/media/stream?file=exported_packs/{fname}"
        })
    return items

@app.post("/api/open-folder")
async def open_folder(request: Request):
    """Open downloads (or downloads/exported_packs) folder in Windows Explorer."""
    sub = ""
    try:
        body = await request.json()
        if isinstance(body, dict):
            sub = str(body.get("sub") or "").strip("/\\")
    except Exception:
        sub = ""
    target = DOWNLOADS_DIR
    if sub == "exported_packs" and os.path.isdir(EXPORTED_PACKS_DIR):
        target = EXPORTED_PACKS_DIR
    try:
        os.startfile(target)
        return {"status": "ok", "path": target}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось открыть папку: {str(e)}")

# Mount static web directory
if os.path.exists(WEB_DIR):
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")

def run_server(host: str = "127.0.0.1", port: int = 8765):
    import uvicorn
    print(f"=====================================================")
    print(f"  Kick Video Downloader Web UI")
    print(f"  Откройте в браузере: http://{host}:{port}")
    print(f"  Папка сохранения: {DOWNLOADS_DIR}")
    print(f"=====================================================")
    uvicorn.run(app, host=host, port=port, log_level="warning")

if __name__ == "__main__":
    run_server()
