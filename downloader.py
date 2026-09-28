import hashlib
import json
import os
import sys
import time
import shutil
import urllib.request
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Event
from typing import List, Callable, Optional, Dict, Any

from disk_manager import DiskManager, format_bytes, DOWNLOAD_PEAK_FACTOR

# Ensure clean UTF-8 output
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def format_eta(seconds: float) -> str:
    """Format seconds into HH:MM:SS or MM:SS."""
    if seconds < 0 or seconds > 86400 * 7:
        return "--:--"
    sec = int(seconds)
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def sanitize_filename(name: str) -> str:
    """Sanitize string for safe Windows filename."""
    name = "".join(c for c in name if c not in '<>:"/\\|?*' and ord(c) >= 32)
    name = name.strip().strip(".")
    return name if name else "kick_video"


def resume_key(clean_name: str, segment_urls: List[str]) -> str:
    """Stable id of a download job: same file name + same segment list ->
    same temp folder, so an interrupted download resumes across runs."""
    h = hashlib.sha1()
    h.update(clean_name.encode("utf-8"))
    for u in segment_urls:
        h.update(b"\n")
        h.update(u.split("?", 1)[0].encode("utf-8"))   # signed query strings change per run
    return h.hexdigest()[:16]


class KickDownloader:
    def __init__(
        self,
        output_dir: Optional[str] = None,
        max_workers: int = 12,
        headers: Optional[Dict[str, str]] = None
    ):
        self.output_dir = output_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
        os.makedirs(self.output_dir, exist_ok=True)
        self.max_workers = max_workers
        self.headers = headers or {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        self.stop_event = Event()
        self.disk_manager = DiskManager(self.output_dir)

    def cancel(self):
        """Cancel the ongoing download (segments already on disk are kept for resume)."""
        self.stop_event.set()

    def _download_segment(self, url: str, target_path: str, max_retries: int = 4) -> int:
        """Download single .ts segment with retries."""
        if self.stop_event.is_set():
            return 0

        # already complete from a previous run -> resume
        if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
            return os.path.getsize(target_path)

        tmp_path = target_path + ".part"
        last_err: Optional[Exception] = None
        for attempt in range(max_retries):
            if self.stop_event.is_set():
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                return 0
            try:
                req = urllib.request.Request(url, headers=self.headers)
                with urllib.request.urlopen(req, timeout=12) as resp:
                    expected = resp.headers.get("Content-Length")
                    with open(tmp_path, "wb") as f:
                        shutil.copyfileobj(resp, f)
                size = os.path.getsize(tmp_path)
                if expected and expected.isdigit() and int(expected) != size:
                    raise IOError(f"обрыв: {size} из {expected} байт")
                if size > 0:
                    os.replace(tmp_path, target_path)
                    return size
            except Exception as e:
                last_err = e
                time.sleep(0.5 * (attempt + 1))

        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        raise IOError(f"Не удалось скачать сегмент: {url} после {max_retries} попыток ({last_err})")

    @staticmethod
    def _dir_bytes(path: str) -> int:
        total = 0
        if os.path.isdir(path):
            for name in os.listdir(path):
                if name.endswith(".ts"):
                    try:
                        total += os.path.getsize(os.path.join(path, name))
                    except OSError:
                        pass
        return total

    def download_stream(
        self,
        segment_urls: List[str],
        output_filename: str,
        estimated_total_bytes: int = 0,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        force_skip_space_check: bool = False
    ) -> str:
        """
        Download all segments and merge into output_filename MP4.
        Resumable across runs: segments live in downloads/_resume_<key>/ until
        the merge succeeds. Disk check covers the peak (segments + MP4) + 5%.
        """
        self.stop_event.clear()

        clean_name = sanitize_filename(output_filename)
        if not clean_name.lower().endswith(".mp4"):
            clean_name += ".mp4"
        final_mp4_path = os.path.join(self.output_dir, clean_name)

        temp_dir = os.path.join(self.output_dir, f"_resume_{resume_key(clean_name, segment_urls)}")
        already = self._dir_bytes(temp_dir)

        # 1. STRICT DISK SPACE CHECK (peak = segments + merged MP4, minus resumed bytes)
        if not force_skip_space_check and estimated_total_bytes > 0:
            space_check = self.disk_manager.check_space(
                estimated_total_bytes, self.output_dir,
                peak_factor=DOWNLOAD_PEAK_FACTOR, already_present_bytes=already)
            if not space_check["is_enough"]:
                raise PermissionError(space_check["message"])

        os.makedirs(temp_dir, exist_ok=True)
        with open(os.path.join(temp_dir, "job.json"), "w", encoding="utf-8") as fh:
            json.dump({"output": clean_name, "segments": len(segment_urls), "created": time.time()}, fh)

        total_segments = len(segment_urls)
        completed_segments = 0
        downloaded_bytes = 0
        start_time = time.time()
        last_speed_update = start_time
        bytes_at_last_update = 0
        current_speed = 0.0

        def send_progress(status: str, message: str = ""):
            if not progress_callback:
                return
            now = time.time()
            elapsed = now - start_time
            nonlocal last_speed_update, bytes_at_last_update, current_speed
            time_delta = now - last_speed_update
            if time_delta >= 0.8:
                speed_sample = (downloaded_bytes - bytes_at_last_update) / time_delta
                current_speed = 0.7 * current_speed + 0.3 * speed_sample if current_speed > 0 else speed_sample
                last_speed_update = now
                bytes_at_last_update = downloaded_bytes
            pct = round((completed_segments / total_segments) * 100, 1) if total_segments > 0 else 0.0
            eta_sec = 0.0
            if current_speed > 0:
                if estimated_total_bytes > downloaded_bytes:
                    eta_sec = (estimated_total_bytes - downloaded_bytes) / current_speed
                elif total_segments > completed_segments:
                    avg_seg_bytes = downloaded_bytes / max(1, completed_segments)
                    rem_bytes = (total_segments - completed_segments) * avg_seg_bytes
                    eta_sec = rem_bytes / current_speed
            progress_callback({
                "status": status,
                "message": message,
                "completed_segments": completed_segments,
                "total_segments": total_segments,
                "downloaded_bytes": downloaded_bytes,
                "downloaded_formatted": format_bytes(downloaded_bytes),
                "total_bytes": estimated_total_bytes,
                "total_formatted": format_bytes(estimated_total_bytes),
                "percent": pct,
                "speed_bps": current_speed,
                "speed_formatted": f"{format_bytes(int(current_speed))}/s",
                "eta_seconds": int(eta_sec),
                "eta_formatted": format_eta(eta_sec),
                "elapsed_seconds": int(elapsed),
                "resumed_bytes": already,
            })

        send_progress("downloading", "Продолжение загрузки..." if already else "Запуск загрузки сегментов...")

        segment_files = []
        success = False
        try:
            with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                futures = {}
                for idx, seg_url in enumerate(segment_urls):
                    seg_filename = f"seg_{idx:06d}.ts"
                    seg_path = os.path.join(temp_dir, seg_filename)
                    segment_files.append((idx, seg_filename, seg_path))
                    fut = pool.submit(self._download_segment, seg_url, seg_path)
                    futures[fut] = (idx, seg_url)

                for fut in as_completed(futures):
                    if self.stop_event.is_set():
                        pool.shutdown(wait=False, cancel_futures=True)
                        send_progress("cancelled", "Загрузка отменена. Скачанные сегменты сохранены для продолжения.")
                        raise KeyboardInterrupt("Загрузка отменена.")
                    try:
                        seg_size = fut.result()
                        downloaded_bytes += seg_size
                        completed_segments += 1
                        send_progress("downloading")
                    except Exception as e:
                        pool.shutdown(wait=False, cancel_futures=True)
                        send_progress("error", f"Ошибка сегмента: {e}. Повторный запуск продолжит с места обрыва.")
                        raise

            # 3. MERGE (ffmpeg concat, stream copy). genpts + make_zero keep
            # A/V monotonic across HLS discontinuities (ad breaks, reconnects).
            send_progress("merging", "Сборка цельного MP4 через FFmpeg без потери качества...")
            segment_files.sort(key=lambda x: x[0])
            concat_list_path = os.path.join(temp_dir, "concat_list.txt")
            with open(concat_list_path, "w", encoding="utf-8") as f:
                for _, fname, _ in segment_files:
                    f.write(f"file '{fname}'\n")
            part_mp4 = final_mp4_path + ".part.mp4"
            cmd = [
                "ffmpeg", "-y", "-nostdin", "-loglevel", "error",
                "-fflags", "+genpts+discardcorrupt",
                "-f", "concat", "-safe", "0",
                "-i", concat_list_path,
                "-map", "0:v:0?", "-map", "0:a:0?",
                "-c", "copy",
                "-bsf:v", "h264_metadata=colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1:video_full_range_flag=0",
                "-avoid_negative_ts", "make_zero",
                "-movflags", "+faststart",
                part_mp4
            ]
            process = subprocess.run(cmd, cwd=temp_dir, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.PIPE, text=True)
            if process.returncode != 0:
                raise RuntimeError(f"FFmpeg вернул ошибку при сборке: {process.stderr[-500:]}")
            if not os.path.exists(part_mp4) or os.path.getsize(part_mp4) == 0:
                raise RuntimeError("Выходной MP4 файл не создан или пустой после FFmpeg.")
            os.replace(part_mp4, final_mp4_path)

            final_size = os.path.getsize(final_mp4_path)
            success = True
            send_progress("completed", f"Видео успешно сохранено: {clean_name} ({format_bytes(final_size)})")
            return final_mp4_path
        finally:
            # keep segments on failure/cancel (resume); remove after success
            if success and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    dl = KickDownloader()
    print("Downloader initialized, output directory:", dl.output_dir)
