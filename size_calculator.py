import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple, Any

from kick_extractor import HEADERS


class HLSUnsupportedError(RuntimeError):
    """The media playlist uses a feature the segment downloader cannot
    reproduce faithfully (encryption, byte ranges, fMP4 init map...)."""


def format_size(bytes_val: int) -> str:
    """Format bytes into readable string (B, KB, MB, GB)."""
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.2f} KB"
    elif bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.2f} MB"
    else:
        return f"{bytes_val / (1024 * 1024 * 1024):.2f} GB"


_ATTR_RE = re.compile(r'([A-Z0-9-]+)=("[^"]*"|[^,]*)')


def _attrs(line: str) -> Dict[str, str]:
    body = line.split(":", 1)[1] if ":" in line else ""
    return {k: v.strip('"') for k, v in _ATTR_RE.findall(body)}


def parse_media_playlist(content: str, base_url: str) -> Dict[str, Any]:
    """Parse an HLS *media* playlist.

    Returns {"segments": [{"url", "duration", "discontinuity"}], "total",
    "discontinuities", "map", "encrypted", "byterange", "endlist"}.
    Unlike the old parser, only URI lines that follow #EXTINF are segments;
    EXT-X-MAP / EXT-X-KEY / EXT-X-BYTERANGE / EXT-X-DISCONTINUITY are
    recognised instead of being silently mis-read.
    """
    text = (content or "").lstrip("\ufeff")
    if "#EXTM3U" not in text[:64]:
        raise HLSUnsupportedError("Ответ не похож на HLS-плейлист (#EXTM3U отсутствует)")
    if "#EXT-X-STREAM-INF" in text:
        raise HLSUnsupportedError("Передан master-плейлист, нужен плейлист конкретного качества")
    segs: List[Dict[str, Any]] = []
    total = 0.0
    pending_dur: Optional[float] = None
    pending_disc = False
    disc_count = 0
    init_map = None
    encrypted = False
    byterange = False
    endlist = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            m = re.match(r"#EXTINF:\s*([0-9.]+)", line)
            pending_dur = float(m.group(1)) if m else 0.0
        elif line.startswith("#EXT-X-DISCONTINUITY") and not line.startswith("#EXT-X-DISCONTINUITY-SEQUENCE"):
            pending_disc = True
            disc_count += 1
        elif line.startswith("#EXT-X-KEY"):
            method = _attrs(line).get("METHOD", "NONE").upper()
            if method != "NONE":
                encrypted = True
        elif line.startswith("#EXT-X-MAP"):
            uri = _attrs(line).get("URI")
            if uri:
                init_map = urllib.parse.urljoin(base_url, uri)
        elif line.startswith("#EXT-X-BYTERANGE"):
            byterange = True
        elif line.startswith("#EXT-X-ENDLIST"):
            endlist = True
        elif line.startswith("#"):
            continue
        else:
            if pending_dur is None:
                # URI without #EXTINF is not a media segment (old bug: it was)
                continue
            segs.append({"url": urllib.parse.urljoin(base_url, line),
                         "duration": pending_dur, "discontinuity": pending_disc})
            total += pending_dur
            pending_dur, pending_disc = None, False
    return {"segments": segs, "total": total, "discontinuities": disc_count, "map": init_map,
            "encrypted": encrypted, "byterange": byterange, "endlist": endlist}


def ensure_downloadable(info: Dict[str, Any]) -> None:
    if info.get("encrypted"):
        raise HLSUnsupportedError("Плейлист зашифрован (EXT-X-KEY): посегментная загрузка не поддерживается")
    if info.get("byterange"):
        raise HLSUnsupportedError("Плейлист с EXT-X-BYTERANGE пока не поддерживается загрузчиком")
    if info.get("map"):
        raise HLSUnsupportedError("fMP4-плейлист (EXT-X-MAP) пока не поддерживается загрузчиком")
    if not info.get("segments"):
        raise HLSUnsupportedError("В плейлисте нет сегментов")


class SizeCalculator:
    def __init__(self, headers: Optional[Dict[str, str]] = None):
        self.headers = headers or dict(HEADERS)
        self.last_playlist: Dict[str, Any] = {}

    def _load(self, playlist_url: str) -> Dict[str, Any]:
        req = urllib.request.Request(playlist_url, headers=self.headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8", errors="replace")
        info = parse_media_playlist(content, playlist_url)
        ensure_downloadable(info)
        self.last_playlist = info
        return info

    def fetch_playlist_segments(self, playlist_url: str) -> Tuple[List[str], float]:
        """Segment URLs + total duration of a media playlist."""
        info = self._load(playlist_url)
        return [s["url"] for s in info["segments"]], info["total"]

    def fetch_playlist_segments_detailed(self, playlist_url: str) -> Tuple[List[Tuple[str, float]], float]:
        """Same as fetch_playlist_segments but keeps per-segment durations."""
        info = self._load(playlist_url)
        return [(s["url"], s["duration"]) for s in info["segments"]], info["total"]

    @staticmethod
    def slice_range(
        detailed: List[Tuple[str, float]],
        start_time: float,
        end_time: float
    ) -> Tuple[List[str], float, float, float]:
        """
        Cut segment list to [start_time, end_time) seconds.
        Returns (urls, range_duration, total_duration, range_start_actual).
        Segments overlapping the range are included whole; the caller can
        precisely post-trim with ``start_time - range_start_actual`` offset.
        """
        total = sum(d for _, d in detailed)
        if start_time is None or end_time is None:
            raise ValueError("Нужны и начало, и конец фрагмента")
        if start_time < 0 or end_time <= start_time:
            raise ValueError("Некорректный диапазон: 0 ≤ начало < конец")
        if start_time >= total:
            raise ValueError("Начало фрагмента за пределами видео")
        start = max(0.0, start_time)
        end = min(total, end_time)
        urls: List[str] = []
        range_dur = 0.0
        range_start = 0.0
        cursor = 0.0
        for url, dur in detailed:
            seg_start, seg_end = cursor, cursor + dur
            cursor = seg_end
            if seg_end > start and seg_start < end:
                if not urls:
                    range_start = seg_start
                urls.append(url)
                range_dur += dur
        if not urls:
            raise ValueError("Диапазон не покрывает ни одного сегмента")
        return urls, range_dur, total, range_start

    def _get_segment_size(self, url: str) -> Optional[int]:
        """Fast HTTP HEAD request to determine Content-Length of a segment."""
        try:
            req = urllib.request.Request(url, headers=self.headers, method="HEAD")
            with urllib.request.urlopen(req, timeout=6) as resp:
                cl = resp.headers.get("Content-Length")
                if cl:
                    return int(cl)
        except Exception:
            pass
        return None

    def calculate_stream_size(
        self,
        playlist_url: str,
        bandwidth: int = 0,
        fallback_duration: float = 0.0,
        sample_count: int = 15
    ) -> Dict[str, Any]:
        """
        ESTIMATE the required disk space for a stream: HEAD-samples up to
        `sample_count` segments and extrapolates (it is not an exact size).
        """
        segments: List[str] = []
        exact_duration = 0.0
        try:
            segments, exact_duration = self.fetch_playlist_segments(playlist_url)
        except Exception:
            pass

        dur = exact_duration if exact_duration > 0 else fallback_duration
        bitrate_size_bytes = int((bandwidth * dur) / 8) if (bandwidth and dur) else 0

        sampled_sizes = []
        if segments:
            total_segs = len(segments)
            if total_segs <= sample_count:
                indices = list(range(total_segs))
            else:
                step = total_segs / sample_count
                indices = [int(i * step) for i in range(sample_count)]
            sample_urls = [segments[idx] for idx in indices]
            with ThreadPoolExecutor(max_workers=min(10, len(sample_urls))) as pool:
                futures = {pool.submit(self._get_segment_size, u): u for u in sample_urls}
                for fut in as_completed(futures):
                    size = fut.result()
                    if size and size > 0:
                        sampled_sizes.append(size)

        if sampled_sizes and len(sampled_sizes) >= 3 and segments:
            avg_seg_size = sum(sampled_sizes) / len(sampled_sizes)
            estimated_bytes = int(avg_seg_size * len(segments))
            method = "head_sampling"
        elif bitrate_size_bytes > 0:
            estimated_bytes = bitrate_size_bytes
            method = "bitrate_estimate"
        else:
            estimated_bytes = 0
            method = "unknown"

        bitrate_kbps = int((estimated_bytes * 8) / (dur * 1000)) if (dur > 0 and estimated_bytes > 0) else (bandwidth // 1000)
        bitrate_mbps = round(bitrate_kbps / 1000, 2)
        bitrate_formatted = f"{bitrate_mbps:.2f} Mbps" if bitrate_mbps >= 1 else f"{bitrate_kbps} kbps"

        return {
            "estimated_bytes": estimated_bytes,
            "estimated_mb": round(estimated_bytes / (1024 * 1024), 2),
            "estimated_gb": round(estimated_bytes / (1024 * 1024 * 1024), 2),
            "formatted_size": format_size(estimated_bytes),
            "segments_count": len(segments),
            "duration_seconds": round(dur, 2),
            "bitrate_kbps": bitrate_kbps,
            "bitrate_mbps": bitrate_mbps,
            "bitrate_formatted": bitrate_formatted,
            "method": method,
            "is_estimate": True,
            "sample_count_used": len(sampled_sizes),
            "discontinuities": (self.last_playlist or {}).get("discontinuities", 0),
        }


if __name__ == "__main__":
    from kick_extractor import KickExtractor
    ext = KickExtractor()
    info = ext.extract("https://kick.com/jesusavgn/videos/01a0c558-1fd0-7b89-bc86-e5e39b939572")
    calc = SizeCalculator(headers=ext.get_size_headers() if hasattr(ext, "get_size_headers") else None)
    print("Video:", info["title"], "Duration:", info["duration_str"])
    for q in info["qualities"]:
        res = calc.calculate_stream_size(q["playlist_url"], q["bandwidth"], info["duration"])
        print(f"[{q['label']}] {q['resolution']} @ {q['fps']}fps: ~{res['formatted_size']} ({res['segments_count']} segments, method={res['method']})")
