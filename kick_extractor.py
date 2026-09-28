import os
import re
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Any

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

# XHR-style headers for Kick's internal JSON API (what the SPA itself sends)
API_HEADERS = {
    "User-Agent": HEADERS["User-Agent"],
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": HEADERS["Accept-Language"],
    "Referer": "https://kick.com/",
    "Origin": "https://kick.com",
    "Sec-Ch-Ua": HEADERS["Sec-Ch-Ua"],
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

KICK_API = "https://kick.com/api"
UUID_RE = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
SLUG_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_-]{0,63}$")
# first path segments that are Kick site routes, never channel slugs
RESERVED_PATHS = {"", "api", "browse", "categories", "category", "following", "search", "settings",
                  "dashboard", "about", "terms", "privacy", "community-guidelines", "video", "videos",
                  "clips", "clip", "login", "signup", "subscriptions", "messages", "stream"}


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
    seconds = int(seconds or 0)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def parse_kick_url(url: str) -> Dict[str, Optional[str]]:
    """kick.com/{slug}/videos/{uuid} | kick.com/video/{uuid} | kick.com/{slug}
    -> {"kind": "vod"|"live"|"unknown", "slug", "uuid"}."""
    u = (url or "").strip()
    if not re.match(r"^https?://", u):
        u = f"https://kick.com/{u.lstrip('/')}"
    parts = urllib.parse.urlsplit(u)
    segs = [s for s in parts.path.split("/") if s]
    q = urllib.parse.parse_qs(parts.query)
    m = re.search(rf"/videos?/({UUID_RE})", parts.path)
    if m:
        slug = segs[0] if segs and segs[0].lower() not in RESERVED_PATHS else None
        return {"kind": "vod", "slug": slug, "uuid": m.group(1).lower()}
    if q.get("video") and re.fullmatch(UUID_RE, q["video"][0]):
        slug = segs[0] if segs and segs[0].lower() not in RESERVED_PATHS else None
        return {"kind": "vod", "slug": slug, "uuid": q["video"][0].lower()}
    if len(segs) == 1 and segs[0].lower() not in RESERVED_PATHS and SLUG_RE.match(segs[0]):
        return {"kind": "live", "slug": segs[0].lower(), "uuid": None}
    return {"kind": "unknown", "slug": None, "uuid": None}


def _ms_or_s(value: Any, assume_ms: bool) -> int:
    """Kick reports livestream durations in ms, some objects in seconds."""
    try:
        v = float(value or 0)
    except (TypeError, ValueError):
        return 0
    if v <= 0:
        return 0
    if assume_ms or v > 7 * 86400:
        return int(round(v / 1000.0))
    return int(round(v))


def _parse_time(value: Any) -> Optional[float]:
    """'2024-01-01 12:00:00' (UTC) or ISO-8601 -> epoch seconds."""
    if not value:
        return None
    s = str(value).strip().replace("Z", "+00:00")
    for fmt in (None, "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.fromisoformat(s) if fmt is None else datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except ValueError:
            continue
    return None


def _thumb(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("src") or value.get("url") or value.get("srcset") or ""
    s = str(value or "")
    return s.split(" ")[0].replace("\\/", "/") if s.startswith("http") else ""


class KickExtractor:
    def __init__(self, base_dir: Optional[str] = None,
                 fetch: Optional[Callable[[str, bool], str]] = None):
        """``fetch(url, is_api) -> text`` can be injected (tests / proxies)."""
        self.base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))
        self.cookie_header = get_cookies_header(self.base_dir)
        self._fetch_override = fetch

    def get_size_headers(self) -> Dict[str, str]:
        """Headers for CDN requests (HEAD/GET on stream segments): UA + cookies."""
        headers = dict(HEADERS)
        if self.cookie_header:
            headers["Cookie"] = self.cookie_header
        return headers

    def _fetch_url(self, url: str, attempts: int = 3, api: bool = False) -> str:
        if self._fetch_override is not None:
            return self._fetch_override(url, api)
        last_err: Optional[Exception] = None
        for attempt in range(attempts):
            try:
                headers = dict(API_HEADERS if api else HEADERS)
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

    def _fetch_json(self, url: str) -> Any:
        text = self._fetch_url(url, attempts=2, api=True)
        t = (text or "").lstrip()
        if not t or t[0] not in "{[":
            raise ValueError(f"не JSON (Cloudflare-челлендж?) от {url}")
        return json.loads(t)

    # ── API sources (primary) ────────────────────────────────────────────
    def video_api(self, uuid: str, errors: List[str]) -> Optional[Dict[str, Any]]:
        """/api/v2/video/{uuid}, then /api/v1/video/{uuid}."""
        for ver in ("v2", "v1"):
            url = f"{KICK_API}/{ver}/video/{uuid}"
            try:
                data = self._fetch_json(url)
            except Exception as exc:
                errors.append(f"{ver}/video: {exc}")
                continue
            if not isinstance(data, dict):
                errors.append(f"{ver}/video: неожиданный ответ")
                continue
            ls = data.get("livestream") or {}
            ch = ls.get("channel") or data.get("channel") or {}
            user = ch.get("user") or {}
            source = data.get("source") or ls.get("source") or ""
            if not source:
                errors.append(f"{ver}/video: нет поля source")
                continue
            dur = _ms_or_s(ls.get("duration"), True) if ls.get("duration") else _ms_or_s(data.get("duration"), False)
            return {
                "master_m3u8": source.replace("\\/", "/"),
                "title": ls.get("session_title") or data.get("title") or "",
                "streamer": user.get("username") or ch.get("slug") or "",
                "slug": ch.get("slug") or "",
                "duration": dur,
                "thumbnail": _thumb(ls.get("thumbnail") or data.get("thumbnail")),
                "start_time": _parse_time(ls.get("start_time") or ls.get("created_at") or data.get("created_at")),
                "channel_id": ch.get("id") or ls.get("channel_id"),
                "extract_method": f"api_{ver}_video",
            }
        return None

    def channel_videos_api(self, slug: str, uuid: str, errors: List[str]) -> Optional[Dict[str, Any]]:
        """/api/v2/channels/{slug}/videos: find the VOD by uuid (fallback)."""
        try:
            data = self._fetch_json(f"{KICK_API}/v2/channels/{slug}/videos")
        except Exception as exc:
            errors.append(f"v2/channels/videos: {exc}")
            return None
        items = data if isinstance(data, list) else (data or {}).get("data") or []
        for it in items:
            vid = (it or {}).get("video") or {}
            if str(vid.get("uuid", "")).lower() != uuid:
                continue
            source = it.get("source") or vid.get("source") or ""
            if not source:
                errors.append("v2/channels/videos: у VOD нет source")
                return None
            ch = it.get("channel") or {}
            return {
                "master_m3u8": source.replace("\\/", "/"),
                "title": it.get("session_title") or vid.get("title") or "",
                "streamer": (ch.get("user") or {}).get("username") or ch.get("slug") or slug,
                "slug": ch.get("slug") or slug,
                "duration": _ms_or_s(it.get("duration"), True),
                "thumbnail": _thumb(it.get("thumbnail")),
                "start_time": _parse_time(it.get("start_time") or it.get("created_at")),
                "channel_id": it.get("channel_id") or ch.get("id"),
                "extract_method": "api_v2_channel_videos",
            }
        errors.append("v2/channels/videos: VOD не найден в списке канала")
        return None

    def channel_api(self, slug: str, errors: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """/api/v2/channels/{slug}, then /api/v1/channels/{slug}: live
        playback URL, chatroom id, stream start (also used by chat_recorder)."""
        errors = errors if errors is not None else []
        for ver in ("v2", "v1"):
            try:
                data = self._fetch_json(f"{KICK_API}/{ver}/channels/{slug}")
            except Exception as exc:
                errors.append(f"{ver}/channels: {exc}")
                continue
            if not isinstance(data, dict):
                errors.append(f"{ver}/channels: неожиданный ответ")
                continue
            ls = data.get("livestream") or {}
            user = data.get("user") or {}
            return {
                "slug": data.get("slug") or slug,
                "streamer": user.get("username") or data.get("slug") or slug,
                "channel_id": data.get("id"),
                "chatroom_id": (data.get("chatroom") or {}).get("id"),
                "is_live": bool(ls) and bool(ls.get("is_live", True)),
                "playback_url": (data.get("playback_url") or ls.get("playback_url") or "").replace("\\/", "/"),
                "title": ls.get("session_title") or "",
                "thumbnail": _thumb(ls.get("thumbnail")),
                "start_time": _parse_time(ls.get("start_time") or ls.get("created_at")),
                "duration": _ms_or_s(ls.get("duration"), True),
                "extract_method": f"api_{ver}_channel",
            }
        return None

    # ── HTML scraping (last resort) ──────────────────────────────────────
    def from_html(self, url: str, html: Optional[str] = None) -> Dict[str, Any]:
        html = html if html is not None else self._fetch_url(url)
        html = html.replace("\\/", "/")          # JSON-escaped URLs inside Next.js payloads
        master_m3u8 = None
        m_rec = re.search(r'recording_url\\?["\']?\s*:\s*\\?["\'](https://[^"\'\\]+master\.m3u8)', html)
        if m_rec:
            master_m3u8 = m_rec.group(1).replace("\\/", "/")
        else:
            m_direct = re.search(r'(https://stream\.kick\.com/[^"\'\s\\]+\.m3u8)', html)
            if m_direct:
                master_m3u8 = m_direct.group(1).replace("\\/", "/")
        if not master_m3u8:
            m_any = re.search(r'(https://[^"\'\s\\]+\.m3u8[^"\'\s\\]*)', html)
            if m_any:
                master_m3u8 = m_any.group(1).replace("\\/", "/")

        if not master_m3u8:
            raise ValueError("Не удалось обнаружить M3U8 поток видео на странице. Проверьте ссылку и доступность записи.")

        title = "Kick Stream Video"
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
            duration = _ms_or_s(m_dur.group(1), False)

        thumbnail = ""
        m_thumb = re.search(r'\\?"src\\?":\\?"(https://images\.kick\.com/[^"\\\s]+)\\?"', search_region)
        if not m_thumb:
            m_thumb = re.search(r'property="og:image"\s+content="([^"]+)"', html)
        if m_thumb:
            thumbnail = m_thumb.group(1).replace("\\/", "/")
        return {"master_m3u8": master_m3u8, "title": title, "streamer": streamer, "slug": "",
                "duration": duration, "thumbnail": thumbnail, "start_time": None,
                "channel_id": None, "extract_method": "html"}

    def extract(self, url: str) -> Dict[str, Any]:
        """
        Video details, master playlist and stream qualities for a Kick URL.

        Order: official-ish JSON API (``api/v2|v1/video/{uuid}``, then
        ``api/v2/channels/{slug}/videos``; live: ``api/v2|v1/channels/{slug}``)
        -> HTML regex scraping as the last resort. ``extract_method`` and
        ``api_errors`` say which source answered (diagnostics).
        """
        url = url.strip()
        if not re.match(r"^https?://", url):
            url = f"https://kick.com/{url.lstrip('/')}"
        target = parse_kick_url(url)
        errors: List[str] = []
        meta: Optional[Dict[str, Any]] = None
        chan: Optional[Dict[str, Any]] = None

        if target["kind"] == "vod":
            meta = self.video_api(target["uuid"], errors)
            if meta is None and target["slug"]:
                meta = self.channel_videos_api(target["slug"], target["uuid"], errors)
        elif target["kind"] == "live":
            chan = self.channel_api(target["slug"], errors)
            if chan and chan.get("playback_url"):
                meta = dict(chan, master_m3u8=chan["playback_url"])
            elif chan and not chan.get("is_live"):
                errors.append("канал сейчас не в эфире")
        if meta is None:
            try:
                meta = self.from_html(url)
            except ValueError as exc:
                detail = f" (API: {'; '.join(errors)})" if errors else ""
                if target["kind"] == "live" and chan and not chan.get("is_live"):
                    raise ValueError(f"Канал {chan.get('streamer') or target['slug']} сейчас не в эфире; "
                                     f"для записи укажите ссылку на VOD (kick.com/<канал>/videos/<id>).") from exc
                raise ValueError(f"{exc}{detail}") from exc

        slug = meta.get("slug") or target.get("slug") or ""
        streamer = meta.get("streamer") or slug or "Kick Streamer"
        if meta.get("chatroom_id") is None and chan:
            meta["chatroom_id"] = chan.get("chatroom_id")

        qualities = self._parse_master_m3u8(meta["master_m3u8"])
        duration = int(meta.get("duration") or 0)

        return {
            "url": url,
            "title": meta.get("title") or "Kick Stream Video",
            "streamer": streamer,
            "duration": duration,
            "duration_str": format_duration(duration),
            "thumbnail": meta.get("thumbnail") or "",
            "master_m3u8": meta["master_m3u8"],
            "qualities": qualities,
            # PR #10 extras (additive)
            "uuid": target.get("uuid"),
            "slug": slug,
            "is_live": target["kind"] == "live",
            "chatroom_id": meta.get("chatroom_id"),
            "channel_id": meta.get("channel_id"),
            "start_time": meta.get("start_time"),
            "extract_method": meta.get("extract_method", "html"),
            "api_errors": errors,
        }

    def _parse_master_m3u8(self, master_url: str) -> List[Dict[str, Any]]:
        """Download master.m3u8 and parse all EXT-X-STREAM-INF variants.
        A media playlist given as "master" becomes one "source" quality."""
        content = self._fetch_url(master_url)
        lines = content.splitlines()

        if "#EXT-X-STREAM-INF" not in content and "#EXTINF" in content:
            return [{"label": "source", "resolution": "", "fps": 30, "bandwidth": 0,
                     "playlist_url": master_url, "is_source": True}]

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

                    bandwidth = 0
                    m_bw = re.search(r'(?<![A-Z-])BANDWIDTH=(\d+)', inf_line)
                    if m_bw:
                        bandwidth = int(m_bw.group(1))

                    res = ""
                    m_res = re.search(r'RESOLUTION=([0-9x]+)', inf_line)
                    if m_res:
                        res = m_res.group(1)

                    fps = 30
                    m_fps = re.search(r'FRAME-RATE=([0-9.]+)', inf_line)
                    if m_fps:
                        # N17: keep fractional fps (59.94 stays 59.94, not 59)
                        fps = float(m_fps.group(1))

                    label = res
                    if res:
                        h = res.split("x")[-1]
                        fps_label = int(round(fps))
                        label = f"{h}p{fps_label}" if fps_label > 30 else f"{h}p"

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

        qualities.sort(key=get_quality_rank, reverse=True)
        # N17: mark the source quality = highest bitrate (usually first after sort)
        if qualities:
            best = max(qualities, key=lambda q: q.get("bandwidth", 0))
            for q in qualities:
                q["is_source"] = (q is best)
        return qualities


if __name__ == "__main__":
    import sys
    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://kick.com/jesusavgn/videos/01a0c558-1fd0-7b89-bc86-e5e39b939572"
    ext = KickExtractor()
    info = ext.extract(test_url)
    print("Found video:", info["title"], "by", info["streamer"], f"[{info['extract_method']}]")
    print("Duration:", info["duration_str"])
    print("Qualities available:")
    for q in info["qualities"]:
        print(f" - {q['label']} ({q['resolution']} @ {q['fps']}fps, bandwidth={q['bandwidth']} bps)")
