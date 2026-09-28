import math
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple, Any

from kick_extractor import HEADERS


class HLSUnsupportedError(RuntimeError):
    """The media playlist uses a feature the segment downloader cannot
    reproduce faithfully (DRM / SAMPLE-AES, key without URI, empty list...)."""


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

# Methods the downloader can decrypt (via ffmpeg's crypto protocol on a local playlist).
SUPPORTED_KEY_METHODS = {"NONE", "AES-128"}
_IDENTITY_KEYFORMATS = {"", "identity"}


def _attrs(line: str) -> Dict[str, str]:
    body = line.split(":", 1)[1] if ":" in line else ""
    return {k: v.strip('"') for k, v in _ATTR_RE.findall(body)}


def _parse_byterange(value: str) -> Tuple[int, Optional[int]]:
    """'<n>[@<o>]' -> (length, offset or None)."""
    v = (value or "").strip()
    if "@" in v:
        n, o = v.split("@", 1)
        return int(n), int(o)
    return int(v), None


def _is_http(url: str) -> bool:
    return urllib.parse.urlsplit(url).scheme in ("http", "https")


class Segment(str):
    """One HLS media segment.

    Subclass of ``str`` (the absolute URL) so every legacy caller that treats
    segments as plain URLs keeps working (slicing, resume keys, logging), while
    the downloader reads the extra attributes:

    * ``byterange`` - (length, offset) for EXT-X-BYTERANGE, else None;
    * ``key``       - {"method", "uri", "iv"} for EXT-X-KEY AES-128, else None
                      (``iv`` is explicit or derived from the media sequence);
    * ``init``      - {"uri", "byterange"} of the EXT-X-MAP init section (fMP4);
    * ``seq``       - media sequence number, ``duration``, ``discontinuity``.
    """

    def __new__(cls, url: str, duration: float = 0.0, seq: int = 0,
                byterange: Optional[Tuple[int, int]] = None, key: Optional[Dict[str, Any]] = None,
                init: Optional[Dict[str, Any]] = None, discontinuity: bool = False):
        obj = str.__new__(cls, url)
        obj.duration = float(duration or 0.0)
        obj.seq = int(seq)
        obj.byterange = tuple(byterange) if byterange else None
        obj.key = dict(key) if key else None
        obj.init = dict(init) if init else None
        obj.discontinuity = bool(discontinuity)
        return obj

    def __reduce__(self):
        return (Segment, (str(self), self.duration, self.seq, self.byterange, self.key,
                          self.init, self.discontinuity))

    @property
    def url(self) -> str:
        return str(self)

    @property
    def advanced(self) -> bool:
        """Needs the local-playlist merge (byte ranges, AES-128 or fMP4)."""
        return bool(self.byterange or self.key or self.init)


def parse_media_playlist(content: str, base_url: str) -> Dict[str, Any]:
    """Parse an HLS *media* playlist.

    Returns {"segments": [{"url", "duration", "discontinuity", "ref", ...}], "total",
    "discontinuities", "map", "encrypted", "byterange", "endlist", "media_sequence",
    "key_methods", "unsupported"}.
    Only URI lines that follow #EXTINF are segments. EXT-X-BYTERANGE (with the
    implicit "continue after the previous range" offset), EXT-X-MAP (fMP4 init,
    optionally ranged), EXT-X-KEY (AES-128 with explicit or sequence-derived IV)
    and EXT-X-MEDIA-SEQUENCE are fully resolved per segment, so the downloader
    can fetch exactly the right bytes. ``unsupported`` lists what cannot be
    reproduced (SAMPLE-AES / DRM key formats, keys without URI).
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
    pending_range: Optional[Tuple[int, Optional[int]]] = None
    disc_count = 0
    init_map: Optional[Dict[str, Any]] = None
    first_map_uri: Optional[str] = None
    key: Optional[Dict[str, Any]] = None
    key_methods = set()
    unsupported: List[str] = []
    encrypted = False
    byterange = False
    endlist = False
    media_seq = 0
    seq = 0
    last_range_end: Dict[str, int] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            m = re.match(r"#EXTINF:\s*([0-9.]+)", line)
            pending_dur = float(m.group(1)) if m else 0.0
        elif line.startswith("#EXT-X-MEDIA-SEQUENCE:"):
            try:
                media_seq = int(line.split(":", 1)[1].strip())
            except ValueError:
                media_seq = 0
            seq = media_seq
        elif line.startswith("#EXT-X-DISCONTINUITY") and not line.startswith("#EXT-X-DISCONTINUITY-SEQUENCE"):
            pending_disc = True
            disc_count += 1
        elif line.startswith("#EXT-X-KEY"):
            a = _attrs(line)
            method = a.get("METHOD", "NONE").upper()
            key_methods.add(method)
            if method == "NONE":
                key = None
                continue
            encrypted = True
            fmt = a.get("KEYFORMAT", "").strip().lower()
            uri = a.get("URI")
            if method not in SUPPORTED_KEY_METHODS:
                unsupported.append(f"шифрование {method} (DRM / SAMPLE-AES)")
                key = None
                continue
            if fmt not in _IDENTITY_KEYFORMATS:
                unsupported.append(f"ключ формата {fmt} (DRM)")
                key = None
                continue
            if not uri:
                unsupported.append("EXT-X-KEY без URI")
                key = None
                continue
            key_url = urllib.parse.urljoin(base_url, uri)
            if not _is_http(key_url):
                unsupported.append("ключ не по http(s)")
                key = None
                continue
            iv = None
            if a.get("IV"):
                iv_hex = a["IV"].lower().replace("0x", "")
                try:
                    iv = bytes.fromhex(iv_hex.rjust(32, "0"))[-16:]
                except ValueError:
                    unsupported.append("некорректный IV")
            key = {"method": method, "uri": key_url, "iv": iv}
        elif line.startswith("#EXT-X-MAP"):
            a = _attrs(line)
            uri = a.get("URI")
            if uri:
                map_url = urllib.parse.urljoin(base_url, uri)
                br = None
                if a.get("BYTERANGE"):
                    n, o = _parse_byterange(a["BYTERANGE"])
                    br = (n, o or 0)
                init_map = {"uri": map_url, "byterange": br}
                if first_map_uri is None:
                    first_map_uri = map_url
        elif line.startswith("#EXT-X-BYTERANGE"):
            byterange = True
            try:
                pending_range = _parse_byterange(line.split(":", 1)[1])
            except (ValueError, IndexError):
                unsupported.append("некорректный EXT-X-BYTERANGE")
        elif line.startswith("#EXT-X-ENDLIST"):
            endlist = True
        elif line.startswith("#"):
            continue
        else:
            if pending_dur is None:
                # URI without #EXTINF is not a media segment (old bug: it was)
                continue
            url = urllib.parse.urljoin(base_url, line)
            rng = None
            if pending_range is not None:
                n, o = pending_range
                if o is None:
                    o = last_range_end.get(url, 0)
                rng = (n, o)
                last_range_end[url] = o + n
            seg_key = None
            if key:
                iv = key["iv"] if key["iv"] is not None else seq.to_bytes(16, "big")
                seg_key = {"method": key["method"], "uri": key["uri"], "iv": iv}
            ref = Segment(url, pending_dur, seq, rng, seg_key, init_map, pending_disc)
            segs.append({"url": url, "duration": pending_dur, "discontinuity": pending_disc,
                         "byterange": rng, "seq": seq, "ref": ref})
            total += pending_dur
            seq += 1
            pending_dur, pending_disc, pending_range = None, False, None
    return {"segments": segs, "total": total, "discontinuities": disc_count, "map": first_map_uri,
            "encrypted": encrypted, "byterange": byterange, "endlist": endlist,
            "media_sequence": media_seq, "key_methods": sorted(key_methods),
            "unsupported": sorted(set(unsupported))}


def ensure_downloadable(info: Dict[str, Any]) -> None:
    """AES-128, fMP4 (EXT-X-MAP) and byte ranges are supported since PR #10.
    Only DRM-like schemes (SAMPLE-AES, non-identity KEYFORMAT) and broken keys
    are rejected - with a clear message instead of a corrupt file."""
    bad = info.get("unsupported") or []
    if bad:
        raise HLSUnsupportedError("Плейлист не может быть скачан: " + "; ".join(bad))
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
        """Segments (``Segment`` = URL str + HLS attributes) + total duration."""
        info = self._load(playlist_url)
        return [s["ref"] for s in info["segments"]], info["total"]

    def fetch_playlist_segments_detailed(self, playlist_url: str) -> Tuple[List[Tuple[str, float]], float]:
        """Same as fetch_playlist_segments but keeps per-segment durations."""
        info = self._load(playlist_url)
        return [(s["ref"], s["duration"]) for s in info["segments"]], info["total"]

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
        """Content-Length via HEAD; CDNs that refuse HEAD (403/405) or omit
        the length get a 1-byte ranged GET and we read the total from
        Content-Range ("bytes 0-0/12345")."""
        try:
            req = urllib.request.Request(url, headers=self.headers, method="HEAD")
            with urllib.request.urlopen(req, timeout=6) as resp:
                cl = resp.headers.get("Content-Length")
                if cl and cl.isdigit() and int(cl) > 0:
                    return int(cl)
        except Exception:
            pass
        try:
            h = dict(self.headers)
            h["Range"] = "bytes=0-0"
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=6) as resp:
                cr = resp.headers.get("Content-Range") or ""
                m = re.search(r"/(\d+)\s*$", cr)
                if m:
                    return int(m.group(1))
                cl = resp.headers.get("Content-Length")
                if resp.status == 200 and cl and cl.isdigit():
                    return int(cl)
        except Exception:
            pass
        return None

    @staticmethod
    def stratified_indices(durations: List[float], k: int, phase: float = 0.5) -> List[int]:
        """k indices spread by *cumulative duration* (not by index), always
        including the first and the last segment; ``phase`` shifts the probe
        inside each stratum so a second pass samples new segments."""
        n = len(durations)
        if n == 0:
            return []
        if n <= k:
            return list(range(n))
        weights = [max(0.0, float(d or 0.0)) for d in durations]
        if sum(weights) <= 0:
            weights = [1.0] * n
        cum, acc = [], 0.0
        for w in weights:
            acc += w
            cum.append(acc)
        picks = {0, n - 1}
        j = 0
        for s in range(k):
            target = (s + phase) / k * cum[-1]
            while j < n - 1 and cum[j] < target:
                j += 1
            picks.add(j)
        return sorted(picks)

    def calculate_stream_size(
        self,
        playlist_url: str,
        bandwidth: int = 0,
        fallback_duration: float = 0.0,
        sample_count: int = 15
    ) -> Dict[str, Any]:
        """
        Required disk space for a stream.

        * byte-range playlists: EXACT (sum of the ranges, no network);
        * short playlists (<= 3 x sample_count segments): every segment is
          sized -> exact;
        * otherwise a duration-stratified sample (first + last + strata) with a
          ratio estimator bytes/second x duration and a 95 % error bound; when
          the bound is wider than 8 % a second, shifted pass is sampled.
        Falls back to BANDWIDTH x duration when nothing can be sized.
        """
        segments: List[Segment] = []
        exact_duration = 0.0
        info: Dict[str, Any] = {}
        try:
            info = self._load(playlist_url)
            segments = [s["ref"] for s in info["segments"]]
            exact_duration = info["total"]
        except Exception:
            info = {}

        dur = exact_duration if exact_duration > 0 else fallback_duration
        bitrate_size_bytes = int((bandwidth * dur) / 8) if (bandwidth and dur) else 0

        estimated_bytes = 0
        method = "unknown"
        is_estimate = True
        error_pct = None
        sampled: Dict[int, int] = {}
        init_bytes = 0

        # fMP4 init sections (once per distinct map)
        inits = {}
        for s in segments:
            if s.init:
                inits[(s.init["uri"], s.init.get("byterange"))] = s.init
        for (uri, br), _ in inits.items():
            if br:
                init_bytes += int(br[0])
            else:
                sz = self._get_segment_size(uri)
                init_bytes += int(sz or 0)

        if segments and all(s.byterange for s in segments):
            estimated_bytes = sum(int(s.byterange[0]) for s in segments) + init_bytes
            method = "byterange_exact"
            is_estimate = False
            error_pct = 0.0
        elif segments:
            n = len(segments)
            durations = [s.duration for s in segments]

            def probe(indices):
                todo = [i for i in indices if i not in sampled]
                if not todo:
                    return
                with ThreadPoolExecutor(max_workers=min(10, len(todo))) as pool:
                    futs = {pool.submit(self._get_segment_size, segments[i]): i for i in todo}
                    for fut in as_completed(futs):
                        size = fut.result()
                        if size and size > 0:
                            sampled[futs[fut]] = int(size)

            if n <= max(3, sample_count) * 3:
                probe(range(n))
                if len(sampled) == n:
                    estimated_bytes = sum(sampled.values()) + init_bytes
                    method = "head_all"
                    is_estimate = False
                    error_pct = 0.0
            else:
                probe(self.stratified_indices(durations, sample_count, 0.5))
                est, err = self._ratio_estimate(sampled, durations, n)
                if err is not None and err > 0.08:
                    probe(self.stratified_indices(durations, sample_count, 0.15))
                    probe(self.stratified_indices(durations, sample_count, 0.85))
                    est, err = self._ratio_estimate(sampled, durations, n)
                if est:
                    estimated_bytes = int(est) + init_bytes
                    method = "head_sampling"
                    error_pct = round(err * 100, 1) if err is not None else None
            if method == "unknown" and sampled and len(sampled) >= 3:
                est, err = self._ratio_estimate(sampled, durations, n)
                if est:
                    estimated_bytes = int(est) + init_bytes
                    method = "head_sampling"
                    error_pct = round(err * 100, 1) if err is not None else None
        if method == "unknown" and bitrate_size_bytes > 0:
            estimated_bytes = bitrate_size_bytes
            method = "bitrate_estimate"
            error_pct = None

        bitrate_kbps = int((estimated_bytes * 8) / (dur * 1000)) if (dur > 0 and estimated_bytes > 0) else (bandwidth // 1000)
        bitrate_mbps = round(bitrate_kbps / 1000, 2)
        bitrate_formatted = f"{bitrate_mbps:.2f} Mbps" if bitrate_mbps >= 1 else f"{bitrate_kbps} kbps"
        err_frac = (error_pct or 0.0) / 100.0
        high = int(estimated_bytes * (1 + err_frac)) if error_pct is not None else int(estimated_bytes * 1.25)
        low = int(estimated_bytes * max(0.0, 1 - err_frac)) if error_pct is not None else int(estimated_bytes * 0.75)

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
            "is_estimate": is_estimate,
            "error_pct": error_pct,
            "estimated_bytes_low": low,
            "estimated_bytes_high": high,
            "sample_count_used": len(sampled),
            "discontinuities": (info or self.last_playlist or {}).get("discontinuities", 0),
            "encrypted": bool((info or {}).get("encrypted")),
            "fmp4": bool((info or {}).get("map")),
            "byterange": bool((info or {}).get("byterange")),
        }

    @staticmethod
    def _ratio_estimate(sampled: Dict[int, int], durations: List[float], n: int):
        """Ratio estimator: total = (sum sizes / sum durations) x total duration.
        Returns (estimate, relative 95 % half-width) or (None, None)."""
        pts = [(sampled[i], durations[i]) for i in sampled if durations[i] > 0]
        if len(pts) < 3:
            if pts:
                total_d = sum(durations)
                r = sum(s for s, _ in pts) / max(1e-9, sum(d for _, d in pts))
                return r * total_d, None
            return None, None
        total_d = sum(durations)
        sy = sum(s for s, _ in pts)
        sx = sum(d for _, d in pts)
        r = sy / sx
        m = len(pts)
        xbar = sx / m
        resid = [(s - r * d) for s, d in pts]
        var = sum(e * e for e in resid) / (m - 1)
        fpc = max(0.0, 1.0 - m / max(1, n))
        se_r = math.sqrt(fpc * var / m) / max(1e-9, xbar)
        return r * total_d, (1.96 * se_r / r) if r > 0 else None


if __name__ == "__main__":
    from kick_extractor import KickExtractor
    ext = KickExtractor()
    info = ext.extract("https://kick.com/jesusavgn/videos/01a0c558-1fd0-7b89-bc86-e5e39b939572")
    calc = SizeCalculator(headers=ext.get_size_headers() if hasattr(ext, "get_size_headers") else None)
    print("Video:", info["title"], "Duration:", info["duration_str"])
    for q in info["qualities"]:
        res = calc.calculate_stream_size(q["playlist_url"], q["bandwidth"], info["duration"])
        print(f"[{q['label']}] {q['resolution']} @ {q['fps']}fps: ~{res['formatted_size']} "
              f"(±{res['error_pct']}%, {res['segments_count']} segments, method={res['method']})")
