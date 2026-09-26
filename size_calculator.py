import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple, Any

from kick_extractor import HEADERS

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

class SizeCalculator:
    def __init__(self, headers: Optional[Dict[str, str]] = None):
        self.headers = headers or dict(HEADERS)

    def fetch_playlist_segments(self, playlist_url: str) -> Tuple[List[str], float]:
        """
        Download sub-playlist M3U8 and extract list of segment URLs and total duration.
        """
        req = urllib.request.Request(playlist_url, headers=self.headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8", errors="replace")

        segments = []
        total_duration = 0.0
        current_dur = 0.0

        for line in content.splitlines():
            line = line.strip()
            if line.startswith("#EXTINF:"):
                m = re.search(r'#EXTINF:([0-9.]+)', line)
                if m:
                    current_dur = float(m.group(1))
                    total_duration += current_dur
            elif line and not line.startswith("#"):
                seg_url = urllib.parse.urljoin(playlist_url, line)
                segments.append(seg_url)

        return segments, total_duration

    def fetch_playlist_segments_detailed(self, playlist_url: str) -> Tuple[List[Tuple[str, float]], float]:
        """
        Same as fetch_playlist_segments but keeps per-segment durations.
        Returns ([(url, duration_sec)], total_duration_sec).
        """
        req = urllib.request.Request(playlist_url, headers=self.headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8", errors="replace")

        detailed: List[Tuple[str, float]] = []
        total_duration = 0.0
        current_dur = 0.0

        for line in content.splitlines():
            line = line.strip()
            if line.startswith("#EXTINF:"):
                m = re.search(r'#EXTINF:([0-9.]+)', line)
                if m:
                    current_dur = float(m.group(1))
            elif line and not line.startswith("#"):
                seg_url = urllib.parse.urljoin(playlist_url, line)
                detailed.append((seg_url, current_dur))
                total_duration += current_dur
                current_dur = 0.0

        return detailed, total_duration

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
        start = max(0.0, start_time)
        end = min(total, end_time)
        if end <= start:
            raise ValueError("Пустой диапазон: конец должен быть позже начала")
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
        Calculate required disk space for a stream.
        Combines segment sampling (HEAD requests) with bitrate calculation.
        """
        segments = []
        exact_duration = 0.0
        try:
            segments, exact_duration = self.fetch_playlist_segments(playlist_url)
        except Exception as e:
            # Fallback if sub-playlist cannot be downloaded
            pass

        dur = exact_duration if exact_duration > 0 else fallback_duration
        bitrate_size_bytes = int((bandwidth * dur) / 8) if (bandwidth and dur) else 0

        # Sample segments if available
        sampled_sizes = []
        if segments:
            total_segs = len(segments)
            indices = []
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
            "sample_count_used": len(sampled_sizes)
        }

if __name__ == "__main__":
    from kick_extractor import KickExtractor
    ext = KickExtractor()
    info = ext.extract("https://kick.com/jesusavgn/videos/01a0c558-1fd0-7b89-bc86-e5e39b939572")
    calc = SizeCalculator()
    print("Video:", info["title"], "Duration:", info["duration_str"])
    print("\nCalculating sizes for all available qualities:")
    for q in info["qualities"]:
        res = calc.calculate_stream_size(q["playlist_url"], q["bandwidth"], info["duration"])
        print(f"[{q['label']}] {q['resolution']} @ {q['fps']}fps: {res['formatted_size']} ({res['segments_count']} segments, method={res['method']})")
