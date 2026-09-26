import os
import re
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Any

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

def get_cookies_header(base_dir: Optional[str] = None) -> str:
    """Load cookies from cookies.json or cookies.txt in project directory."""
    if base_dir is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    json_path = os.path.join(base_dir, "cookies.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return "; ".join(f"{c['name']}={c['value']}" for c in data if "name" in c and "value" in c)
        except Exception:
            pass

    txt_path = os.path.join(base_dir, "cookies.txt")
    if os.path.exists(txt_path):
        try:
            cookies = []
            with open(txt_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split("\t")
                    if len(parts) >= 7:
                        cookies.append(f"{parts[5]}={parts[6]}")
            if cookies:
                return "; ".join(cookies)
        except Exception:
            pass

    return ""

def format_duration(seconds: int) -> str:
    """Format seconds into HH:MM:SS or MM:SS."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

class KickExtractor:
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))
        self.cookie_header = get_cookies_header(self.base_dir)

    def get_size_headers(self) -> Dict[str, str]:
        """Headers for CDN requests (HEAD/GET on stream segments): UA + cookies."""
        headers = dict(HEADERS)
        if self.cookie_header:
            headers["Cookie"] = self.cookie_header
        return headers

    def _fetch_url(self, url: str, attempts: int = 3) -> str:
        last_err: Optional[Exception] = None
        for attempt in range(attempts):
            try:
                headers = dict(HEADERS)
                if self.cookie_header:
                    headers["Cookie"] = self.cookie_header

                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=20) as resp:
                    charset = resp.headers.get_content_charset() or "utf-8"
                    return resp.read().decode(charset, errors="replace")
            except urllib.error.HTTPError as e:
                last_err = e
                if e.code in (403, 429, 503):
                    # Cloudflare / rate-limit: retry with backoff, then fail with clear message
                    if attempt < attempts - 1:
                        time.sleep(1.2 * (attempt + 1))
                        continue
                    raise ValueError(
                        f"Kick отклонил запрос (HTTP {e.code}). Похоже на блокировку Cloudflare "
                        f"или устаревшие cookies. Обновите cookies.json (экспорт из браузера) "
                        f"и попробуйте снова через минуту."
                    ) from e
                raise ValueError(f"Kick вернул HTTP {e.code} для {url}") from e
            except ValueError:
                raise
            except Exception as e:
                last_err = e
                if attempt < attempts - 1:
                    time.sleep(0.8 * (attempt + 1))
                    continue
        raise ValueError(f"Не удалось загрузить страницу Kick: {last_err}")

    def extract(self, url: str) -> Dict[str, Any]:
        """
        Extract video details, master playlist, and available stream qualities
        from a Kick.com video URL.
        """
        url = url.strip()
        if not re.match(r"^https?://", url):
            url = f"https://kick.com/{url.lstrip('/')}"

        # 1. Fetch web page HTML
        html = self._fetch_url(url)

        # 2. Extract Master M3U8 URL
        master_m3u8 = None
        m_rec = re.search(r'recording_url\\?["\']?\s*:\s*\\?["\'](https://[^"\'\\]+master\.m3u8)', html)
        if m_rec:
            master_m3u8 = m_rec.group(1).replace("\\/", "/")
        else:
            m_direct = re.search(r'(https://stream\.kick\.com/[^"\'\s\\]+\.m3u8)', html)
            if m_direct:
                master_m3u8 = m_direct.group(1).replace("\\/", "/")

        if not master_m3u8:
            raise ValueError("Не удалось обнаружить M3U8 поток видео на странице. Проверьте ссылку и доступность записи.")

        # 3. Extract title, streamer, duration, thumbnail
        title = "Kick Stream Video"
        # Find title specifically near recording_url or video data
        idx_rec = html.find("recording_url")
        search_region = html[max(0, idx_rec - 1000):min(len(html), idx_rec + 1500)] if idx_rec != -1 else html

        m_title = re.search(r'\\?"title\\?":\\?"([^"\\]+)\\?"', search_region)
        if m_title and m_title.group(1) not in ("null", ""):
            title = m_title.group(1)
        else:
            m_og = re.search(r'property="og:title"\s+content="([^"]+)"', html)
            if m_og:
                title = m_og.group(1).replace(" - Watch the VOD on Kick", "")

        streamer = "Kick Streamer"
        m_user = re.search(r'\\?"username\\?":\\?"([^"\\]+)\\?"', search_region)
        if not m_user:
            m_url_user = re.search(r'kick\.com/([^/]+)/videos', url)
            if m_url_user:
                streamer = m_url_user.group(1)
        else:
            streamer = m_user.group(1)

        duration = 0
        m_dur = re.search(r'\\?"duration\\?":(\d+)', search_region)
        if m_dur:
            duration = int(m_dur.group(1))

        thumbnail = ""
        m_thumb = re.search(r'\\?"src\\?":\\?"(https://images\.kick\.com/[^"\\\s]+)\\?"', search_region)
        if not m_thumb:
            m_thumb = re.search(r'property="og:image"\s+content="([^"]+)"', html)
        if m_thumb:
            thumbnail = m_thumb.group(1).replace("\\/", "/")

        # 4. Fetch and parse master M3U8 playlist for available qualities
        qualities = self._parse_master_m3u8(master_m3u8)

        return {
            "url": url,
            "title": title,
            "streamer": streamer,
            "duration": duration,
            "duration_str": format_duration(duration),
            "thumbnail": thumbnail,
            "master_m3u8": master_m3u8,
            "qualities": qualities,
        }

    def _parse_master_m3u8(self, master_url: str) -> List[Dict[str, Any]]:
        """Download master.m3u8 and parse all EXT-X-STREAM-INF variants."""
        content = self._fetch_url(master_url)
        lines = content.splitlines()

        qualities = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("#EXT-X-STREAM-INF:"):
                inf_line = line[len("#EXT-X-STREAM-INF:"):]
                # Next non-empty, non-comment line is the sub-playlist URL
                i += 1
                while i < len(lines) and (not lines[i].strip() or lines[i].strip().startswith("#")):
                    i += 1
                if i < len(lines):
                    sub_url = urllib.parse.urljoin(master_url, lines[i].strip())
                    
                    # Parse attributes
                    bandwidth = 0
                    m_bw = re.search(r'BANDWIDTH=(\d+)', inf_line)
                    if m_bw:
                        bandwidth = int(m_bw.group(1))

                    res = ""
                    m_res = re.search(r'RESOLUTION=([0-9x]+)', inf_line)
                    if m_res:
                        res = m_res.group(1)

                    fps = 30
                    m_fps = re.search(r'FRAME-RATE=([0-9.]+)', inf_line)
                    if m_fps:
                        fps = int(float(m_fps.group(1)))

                    # Human-friendly label (e.g., 1080p60, 720p60, 480p)
                    label = res
                    if res:
                        h = res.split("x")[-1]
                        label = f"{h}p{fps}" if fps > 30 else f"{h}p"

                    qualities.append({
                        "label": label,
                        "resolution": res,
                        "fps": fps,
                        "bandwidth": bandwidth,
                        "playlist_url": sub_url
                    })
            i += 1

        def get_quality_rank(q):
            h = 0
            res = q.get("resolution", "")
            if "x" in res:
                try:
                    h = int(res.split("x")[-1])
                except Exception:
                    pass
            return (h, q.get("fps", 0), q.get("bandwidth", 0))

        # Sort qualities descending by resolution (1080p -> 720p -> 480p -> 360p -> 160p)
        qualities.sort(key=get_quality_rank, reverse=True)
        return qualities

if __name__ == "__main__":
    import sys
    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://kick.com/jesusavgn/videos/01a0c558-1fd0-7b89-bc86-e5e39b939572"
    ext = KickExtractor()
    info = ext.extract(test_url)
    print("Found video:", info["title"], "by", info["streamer"])
    print("Duration:", info["duration_str"])
    print("Qualities available:")
    for q in info["qualities"]:
        print(f" - {q['label']} ({q['resolution']} @ {q['fps']}fps, bandwidth={q['bandwidth']} bps)")
