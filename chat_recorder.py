"""Kick live-chat recorder -> JSONL ``{t, user, text}`` (+ ``id``, ``ts``).

The file is exactly what ``/api/studio/moments`` accepts as ``chat_file``
(studio/moments.py: chat lag, rate vs baseline, unique chatters, CAPS...).

* Chat comes from Kick's public Pusher feed ``chatrooms.{id}.v2`` (anonymous,
  no token), event ``App\\Events\\ChatMessageEvent`` (double-encoded JSON).
* ``t`` = seconds since the livestream started (``livestream.start_time`` from
  ``api/v2/channels/{slug}``), so the log lines up with the VOD timeline. When
  the channel is offline the origin is the recorder start (see ``.meta.json``).
* Reconnects with exponential backoff + jitter, answers Pusher pings, dedups
  messages by id across reconnects, flushes every line (crash-safe).
* Stdlib only: a small RFC 6455 client (TLS, masking, fragmentation, ping/pong).

CLI:  python chat_recorder.py <channel | kick.com/<channel>> [-o chat.jsonl]
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import random
import re
import socket
import ssl
import struct
import sys
import threading
import time
import urllib.parse
import uuid as _uuid
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Tuple

PUSHER_KEY = os.environ.get("KICK_PUSHER_KEY", "32cbd69e4b950bf97679")
PUSHER_CLUSTER = os.environ.get("KICK_PUSHER_CLUSTER", "us2")
CHAT_EVENT = "App\\Events\\ChatMessageEvent"
_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
SLUG_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_-]{0,63}$")


def pusher_url(key: str = PUSHER_KEY, cluster: str = PUSHER_CLUSTER) -> str:
    return (f"wss://ws-{cluster}.pusher.com/app/{key}"
            "?protocol=7&client=js&version=8.4.0&flash=false")


# ── RFC 6455 framing ─────────────────────────────────────────────────────
OP_CONT, OP_TEXT, OP_BIN, OP_CLOSE, OP_PING, OP_PONG = 0x0, 0x1, 0x2, 0x8, 0x9, 0xA


def encode_frame(opcode: int, payload: bytes, mask: bool = True, mask_key: Optional[bytes] = None,
                 fin: bool = True) -> bytes:
    head = bytearray([(0x80 if fin else 0) | (opcode & 0x0F)])
    n = len(payload)
    mbit = 0x80 if mask else 0
    if n < 126:
        head.append(mbit | n)
    elif n < 1 << 16:
        head.append(mbit | 126)
        head += struct.pack("!H", n)
    else:
        head.append(mbit | 127)
        head += struct.pack("!Q", n)
    if not mask:
        return bytes(head) + payload
    mk = mask_key or os.urandom(4)
    return bytes(head) + mk + bytes(b ^ mk[i % 4] for i, b in enumerate(payload))


class WSClosed(ConnectionError):
    pass


class WebSocketClient:
    """Minimal blocking WebSocket client (ws:// and wss://)."""

    def __init__(self, url: str, timeout: float = 15.0, headers: Optional[Dict[str, str]] = None):
        self.url = url
        self.timeout = timeout
        self.headers = headers or {}
        self.sock: Optional[socket.socket] = None
        self._buf = b""

    def connect(self) -> None:
        p = urllib.parse.urlsplit(self.url)
        if p.scheme not in ("ws", "wss"):
            raise ValueError("ws:// или wss:// URL")
        port = p.port or (443 if p.scheme == "wss" else 80)
        raw = socket.create_connection((p.hostname, port), timeout=self.timeout)
        if p.scheme == "wss":
            ctx = ssl.create_default_context()
            raw = ctx.wrap_socket(raw, server_hostname=p.hostname)
        self.sock = raw
        key = base64.b64encode(os.urandom(16)).decode()
        path = (p.path or "/") + (f"?{p.query}" if p.query else "")
        host = p.hostname if p.port is None else f"{p.hostname}:{p.port}"
        lines = [f"GET {path} HTTP/1.1", f"Host: {host}", "Upgrade: websocket", "Connection: Upgrade",
                 f"Sec-WebSocket-Key: {key}", "Sec-WebSocket-Version: 13",
                 "Origin: https://kick.com",
                 "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) KickClipStudio/3.0"]
        lines += [f"{k}: {v}" for k, v in self.headers.items()]
        self.sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise WSClosed("рукопожатие оборвано")
            resp += chunk
            if len(resp) > 65536:
                raise WSClosed("слишком длинный ответ рукопожатия")
        head, self._buf = resp.split(b"\r\n\r\n", 1)
        status = head.split(b"\r\n", 1)[0].decode("latin-1")
        if " 101 " not in status + " ":
            raise WSClosed(f"рукопожатие отклонено: {status}")
        want = base64.b64encode(hashlib.sha1((key + _WS_GUID).encode()).digest()).decode()
        hdrs = {ln.split(b":", 1)[0].strip().lower(): ln.split(b":", 1)[1].strip()
                for ln in head.split(b"\r\n")[1:] if b":" in ln}
        if hdrs.get(b"sec-websocket-accept", b"").decode() != want:
            raise WSClosed("неверный Sec-WebSocket-Accept")

    def _read_exact(self, n: int) -> bytes:
        while len(self._buf) < n:
            chunk = self.sock.recv(max(4096, n - len(self._buf)))
            if not chunk:
                raise WSClosed("соединение закрыто")
            self._buf += chunk
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    def _read_frame(self) -> Tuple[bool, int, bytes]:
        b1, b2 = self._read_exact(2)
        fin, op = bool(b1 & 0x80), b1 & 0x0F
        n = b2 & 0x7F
        if n == 126:
            n = struct.unpack("!H", self._read_exact(2))[0]
        elif n == 127:
            n = struct.unpack("!Q", self._read_exact(8))[0]
        if n > 16 * 1024 * 1024:
            raise WSClosed("кадр больше 16 МБ")
        mk = self._read_exact(4) if b2 & 0x80 else None
        data = self._read_exact(n)
        if mk:
            data = bytes(b ^ mk[i % 4] for i, b in enumerate(data))
        return fin, op, data

    def send_text(self, text: str) -> None:
        self.sock.sendall(encode_frame(OP_TEXT, text.encode("utf-8")))

    def recv_text(self) -> str:
        """Next complete text message; answers pings, raises WSClosed on close."""
        parts, first_op = [], None
        while True:
            fin, op, data = self._read_frame()
            if op == OP_PING:
                self.sock.sendall(encode_frame(OP_PONG, data))
                continue
            if op == OP_PONG:
                continue
            if op == OP_CLOSE:
                try:
                    self.sock.sendall(encode_frame(OP_CLOSE, data[:2]))
                except OSError:
                    pass
                raise WSClosed("сервер закрыл соединение")
            if op in (OP_TEXT, OP_BIN):
                first_op, parts = op, [data]
            elif op == OP_CONT and first_op is not None:
                parts.append(data)
            if fin and first_op is not None:
                payload = b"".join(parts)
                if first_op == OP_TEXT:
                    return payload.decode("utf-8", errors="replace")
                parts, first_op = [], None

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.sendall(encode_frame(OP_CLOSE, struct.pack("!H", 1000)))
            except OSError:
                pass
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None


# ── Pusher / Kick payloads ───────────────────────────────────────────────
def parse_pusher(raw: str) -> Tuple[str, Any, Optional[str]]:
    """Pusher envelope -> (event, data (decoded when double-encoded), channel)."""
    env = json.loads(raw)
    data = env.get("data")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except ValueError:
            pass
    return str(env.get("event", "")), data, env.get("channel")


def _epoch(value: Any) -> Optional[float]:
    if not value:
        return None
    s = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        try:
            dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def chat_line(msg: Dict[str, Any], t0: float, now: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """ChatMessageEvent data -> {t, user, text, id, ts} (None for non-messages)."""
    if not isinstance(msg, dict):
        return None
    text = msg.get("content")
    if text is None:
        text = msg.get("message")
    sender = msg.get("sender") or {}
    user = sender.get("username") or sender.get("slug") or ""
    if text is None or not user:
        return None
    ts = _epoch(msg.get("created_at"))
    if ts is None:
        ts = now if now is not None else time.time()
    return {"t": round(max(0.0, ts - t0), 3), "user": str(user), "text": str(text),
            "id": str(msg.get("id") or ""), "ts": round(ts, 3)}


def _default_channel_info(slug: str) -> Dict[str, Any]:
    from kick_extractor import KickExtractor
    info = KickExtractor().channel_api(slug)
    if not info:
        raise ValueError(f"Канал {slug} не найден через API Kick")
    return info


class KickChatRecorder:
    def __init__(self, slug: str, out_path: str, chatroom_id: Optional[int] = None,
                 stream_start: Optional[float] = None, ws_url: Optional[str] = None,
                 channel_info: Optional[Callable[[str], Dict[str, Any]]] = None,
                 max_backoff: float = 16.0):
        slug = (slug or "").strip().lower()
        if not SLUG_RE.match(slug):
            raise ValueError("Некорректное имя канала Kick")
        self.slug = slug
        self.out_path = out_path
        self.chatroom_id = chatroom_id
        self.stream_start = stream_start
        self.ws_url = ws_url or pusher_url()
        self._channel_info = channel_info or _default_channel_info
        self.max_backoff = max_backoff
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self._ws: Optional[WebSocketClient] = None
        self._seen: "OrderedDict[str, None]" = OrderedDict()
        self.stats: Dict[str, Any] = {"messages": 0, "reconnects": 0, "connected": False,
                                      "last_error": "", "started_at": None, "t_origin": None,
                                      "file": os.path.basename(out_path)}

    def resolve(self) -> None:
        if self.chatroom_id is None or self.stream_start is None:
            info = self._channel_info(self.slug)
            if self.chatroom_id is None:
                self.chatroom_id = info.get("chatroom_id")
            if self.stream_start is None and info.get("start_time"):
                self.stream_start = float(info["start_time"])
                self.stats["t_origin"] = "stream_start"
        if not self.chatroom_id:
            raise ValueError("Не удалось определить chatroom id канала")
        if self.stream_start is None:
            self.stream_start = time.time()
            self.stats["t_origin"] = "recorder_start"
        elif self.stats["t_origin"] is None:
            self.stats["t_origin"] = "stream_start"

    def _write_meta(self) -> None:
        meta = {"channel": self.slug, "chatroom_id": self.chatroom_id, "t0_epoch": self.stream_start,
                "t_origin": self.stats["t_origin"], "format": "jsonl {t,user,text,id,ts}",
                "started_at": self.stats["started_at"]}
        with open(self.out_path + ".meta.json", "w", encoding="utf-8") as fh:
            json.dump(meta, fh, ensure_ascii=False, indent=2)

    def _session(self, fh) -> None:
        ws = WebSocketClient(self.ws_url, timeout=15.0)
        self._ws = ws
        ws.connect()
        try:
            ev, data, _ = parse_pusher(ws.recv_text())
            if ev != "pusher:connection_established":
                raise WSClosed(f"ожидался pusher:connection_established, пришло {ev}")
            # Pusher asks for activity every `activity_timeout` s (default 120)
            act = 120.0
            if isinstance(data, dict):
                act = float(data.get("activity_timeout") or 120)
            ws.sock.settimeout(max(5.0, act))
            ws.send_text(json.dumps({"event": "pusher:subscribe",
                                     "data": {"auth": "", "channel": f"chatrooms.{self.chatroom_id}.v2"}}))
            self.stats["connected"] = True
            while not self.stop_event.is_set():
                try:
                    raw = ws.recv_text()
                except socket.timeout:
                    ws.send_text(json.dumps({"event": "pusher:ping", "data": {}}))
                    continue
                try:
                    ev, data, _ = parse_pusher(raw)
                except ValueError:
                    continue
                if ev == "pusher:ping":
                    ws.send_text(json.dumps({"event": "pusher:pong", "data": {}}))
                    continue
                if ev == "pusher:error":
                    raise WSClosed(f"pusher:error {data}")
                if ev != CHAT_EVENT:
                    continue
                line = chat_line(data, self.stream_start)
                if not line:
                    continue
                mid = line["id"]
                if mid:
                    if mid in self._seen:
                        continue
                    self._seen[mid] = None
                    if len(self._seen) > 5000:
                        self._seen.popitem(last=False)
                fh.write(json.dumps(line, ensure_ascii=False) + "\n")
                fh.flush()
                self.stats["messages"] += 1
        finally:
            self.stats["connected"] = False
            ws.close()
            self._ws = None

    def run(self) -> None:
        self.stats["started_at"] = time.time()
        try:
            self.resolve()
        except Exception as exc:
            self.stats["last_error"] = str(exc)
            raise
        os.makedirs(os.path.dirname(os.path.abspath(self.out_path)), exist_ok=True)
        self._write_meta()
        delay = 1.0
        with open(self.out_path, "a", encoding="utf-8") as fh:
            while not self.stop_event.is_set():
                t_conn = time.time()
                try:
                    self._session(fh)
                except Exception as exc:
                    if self.stop_event.is_set():
                        break
                    self.stats["last_error"] = str(exc)[:300]
                    self.stats["reconnects"] += 1
                    if time.time() - t_conn > 30:
                        delay = 1.0          # the connection was healthy: reset backoff
                    self.stop_event.wait(delay + random.random())
                    delay = min(self.max_backoff, delay * 2)

    def start(self) -> "KickChatRecorder":
        self.thread = threading.Thread(target=self._safe_run, daemon=True, name=f"chat-{self.slug}")
        self.thread.start()
        return self

    def _safe_run(self) -> None:
        try:
            self.run()
        except Exception as exc:
            self.stats["last_error"] = str(exc)[:300]

    def stop(self, timeout: float = 5.0) -> None:
        self.stop_event.set()
        ws = self._ws
        if ws is not None and ws.sock is not None:
            try:
                ws.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        if self.thread is not None:
            self.thread.join(timeout)

    def status(self) -> Dict[str, Any]:
        return dict(self.stats, channel=self.slug, chatroom_id=self.chatroom_id,
                    running=bool(self.thread and self.thread.is_alive()))


# ── process-wide registry (studio API) ───────────────────────────────────
_REG_LOCK = threading.Lock()
RECORDERS: Dict[str, KickChatRecorder] = {}


def default_filename(slug: str) -> str:
    return f"chat_{slug}_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"


def start_recording(slug: str, out_dir: str, **kw) -> Tuple[str, KickChatRecorder]:
    slug = (slug or "").strip().lower()
    with _REG_LOCK:
        for rid, rec in RECORDERS.items():
            if rec.slug == slug and rec.thread and rec.thread.is_alive():
                return rid, rec
        rec = KickChatRecorder(slug, os.path.join(out_dir, default_filename(slug)), **kw)
        rid = _uuid.uuid4().hex[:12]
        RECORDERS[rid] = rec
    rec.start()
    return rid, rec


def stop_recording(rid: str) -> Optional[Dict[str, Any]]:
    with _REG_LOCK:
        rec = RECORDERS.get(rid)
    if rec is None:
        return None
    rec.stop()
    return rec.status()


def recordings_status() -> Dict[str, Dict[str, Any]]:
    with _REG_LOCK:
        items = list(RECORDERS.items())
    return {rid: rec.status() for rid, rec in items}


def slug_from(value: str) -> str:
    v = (value or "").strip()
    if "kick.com" in v or v.startswith("http"):
        from kick_extractor import parse_kick_url
        t = parse_kick_url(v)
        if t.get("slug"):
            return t["slug"]
    v = v.strip("/").lstrip("@").lower()
    if not SLUG_RE.match(v):
        raise ValueError("Некорректное имя канала Kick")
    return v


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Record Kick live chat to JSONL {t,user,text}")
    ap.add_argument("channel", help="имя канала или ссылка kick.com/<канал>")
    ap.add_argument("-o", "--output", help="файл .jsonl (по умолчанию downloads/chat_<канал>_<время>.jsonl)")
    args = ap.parse_args(argv)
    slug = slug_from(args.channel)
    out = args.output or os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads", default_filename(slug))
    rec = KickChatRecorder(slug, out)
    print(f"[chat] {slug} -> {out}  (Ctrl+C = стоп)")
    rec.start()
    try:
        last = -1
        while rec.thread.is_alive():
            time.sleep(2)
            st = rec.status()
            if st["messages"] != last:
                last = st["messages"]
                print(f"\r[chat] сообщений: {last}  переподключений: {st['reconnects']}  "
                      f"{'online' if st['connected'] else 'offline'}   ", end="", flush=True)
    except KeyboardInterrupt:
        pass
    rec.stop()
    st = rec.status()
    print(f"\n[chat] готово: {st['messages']} сообщений в {out}")
    if st["last_error"] and not st["messages"]:
        print(f"[chat] последняя ошибка: {st['last_error']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
