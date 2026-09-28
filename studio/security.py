"""Local-server hardening: loopback Host, per-launch token (header / HttpOnly
SameSite=Strict cookie / ?token=), Origin check for unsafe requests and
WebSockets, path guards, playlist host allowlist (SSRF)."""
from __future__ import annotations

import hmac
import ipaddress
import os
import threading
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlsplit

COOKIE_NAME = "studio_token"
HEADER_NAME = "x-studio-token"
MEDIA_EXTS = {".mp4", ".mkv", ".mov", ".webm", ".ts", ".m4v", ".mp3", ".wav", ".m4a", ".ogg",
              ".flac", ".aac", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
MEDIA_HOST_SUFFIXES = ("kick.com", "live-video.net", "cloudfront.net", "akamaized.net", "kickcdn.com")

_lock = threading.Lock()
_urls = set()
_hosts = set()


def remember_playlist_urls(urls):
    with _lock:
        for u in urls:
            if not u:
                continue
            _urls.add(u)
            h = (urlsplit(u).hostname or "").lower()
            if h:
                _hosts.add(h)


def is_allowed_media_host(url: str) -> bool:
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    if parts.scheme not in ("https", "http"):
        return False
    host = (parts.hostname or "").lower()
    if not host:
        return False
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False
    except ValueError:
        pass
    with _lock:
        if url in _urls or host in _hosts:
            return True
    extra = tuple(h.strip().lower().lstrip(".") for h in os.environ.get("STUDIO_EXTRA_MEDIA_HOSTS", "").split(",") if h.strip())
    for suf in MEDIA_HOST_SUFFIXES + extra:
        if host == suf or host.endswith("." + suf):
            return True
    return False


def safe_join(base_dir: str, name: str) -> str:
    base = os.path.realpath(base_dir)
    cand = os.path.realpath(os.path.join(base, os.path.basename(str(name or ""))))
    if os.path.commonpath([base, cand]) != base:
        raise ValueError("path escapes the allowed directory")
    return cand


def check_import_path(path: str) -> str:
    src = str(path or "").strip().strip('"').strip("'")
    if not src:
        raise ValueError("Путь не указан")
    if os.path.splitext(src)[1].lower() not in MEDIA_EXTS:
        raise ValueError("Импорт разрешён только для медиафайлов")
    if os.path.islink(src):
        raise ValueError("Символические ссылки не импортируются")
    if not os.path.isfile(src):
        raise ValueError("Указанный файл не существует")
    return src


def _hostname(h: str) -> str:
    h = (h or "").strip().lower()
    if h.startswith("["):
        return h[1:h.find("]")] if "]" in h else h
    return h.rsplit(":", 1)[0] if ":" in h else h


class StudioSecurityMiddleware:
    def __init__(self, app, token: str, port: int = 8765,
                 allowed_hosts=("127.0.0.1", "localhost", "::1"), public_paths=("/api/version",)):
        self.app = app
        self.token = token or ""
        self.allowed_hosts = {h.lower() for h in allowed_hosts}
        self.public_paths = set(public_paths)
        self.allowed_origins = {f"http://127.0.0.1:{port}", f"http://localhost:{port}", f"http://[::1]:{port}"}

    def _ok(self, c):
        return bool(self.token) and bool(c) and hmac.compare_digest(c, self.token)

    def authorized(self, headers, query):
        if self._ok(headers.get(HEADER_NAME)):
            return True
        if headers.get("cookie"):
            try:
                jar = SimpleCookie()
                jar.load(headers["cookie"])
                if COOKIE_NAME in jar and self._ok(jar[COOKIE_NAME].value):
                    return True
            except Exception:
                pass
        q = parse_qs(query or "").get("token")
        return bool(q) and self._ok(q[0])

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        if _hostname(headers.get("host", "")) not in self.allowed_hosts:
            return await self._deny(scope, send, 403, "host not allowed")
        path = scope.get("path", "")
        if (path.startswith("/api/") or path.startswith("/ws/")) and path not in self.public_paths:
            if not self.authorized(headers, scope.get("query_string", b"").decode("latin-1")):
                return await self._deny(scope, send, 401, "studio token required")
            origin = headers.get("origin")
            unsafe = scope["type"] == "websocket" or scope.get("method", "GET") not in ("GET", "HEAD", "OPTIONS")
            if unsafe and origin and origin not in self.allowed_origins:
                return await self._deny(scope, send, 403, "cross-origin request blocked")
        return await self.app(scope, receive, send)

    async def _deny(self, scope, send, status, msg):
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 4000 + status})
            return
        body = ('{"detail":"%s"}' % msg).encode()
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})
