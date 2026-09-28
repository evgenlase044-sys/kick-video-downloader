"""PR #10 (REMAINING_FIXES §3 "Скачивание"): fMP4 / BYTERANGE / AES-128 HLS
actually download (real ffmpeg + local HTTP server with Range), Kick JSON API
with fallbacks, stratified size estimate, live chat -> JSONL recorder
(local WebSocket/Pusher server)."""
import base64
import hashlib
import http.server
import json
import os
import shutil
import socket
import socketserver
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)

HAVE_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


# ── helpers ──────────────────────────────────────────────────────────────
class _RangeHandler(http.server.SimpleHTTPRequestHandler):
    """Static files with single-range support (like a CDN)."""
    hits = []

    def log_message(self, *a):
        pass

    def do_HEAD(self):
        self._serve(head=True)

    def do_GET(self):
        self._serve(head=False)

    def _serve(self, head):
        path = self.translate_path(self.path.split("?", 1)[0])
        _RangeHandler.hits.append((self.command, self.path, self.headers.get("Range")))
        if not os.path.isfile(path):
            self.send_error(404)
            return
        size = os.path.getsize(path)
        rng = self.headers.get("Range")
        start, end, code = 0, size - 1, 200
        if rng and rng.startswith("bytes="):
            a, b = rng[6:].split("-", 1)
            start = int(a) if a else 0
            end = min(size - 1, int(b)) if b else size - 1
            code = 206
        self.send_response(code)
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if head:
            return
        with open(path, "rb") as fh:
            fh.seek(start)
            self.wfile.write(fh.read(end - start + 1))


class _Server:
    def __init__(self, root):
        handler = lambda *a, **k: _RangeHandler(*a, directory=root, **k)  # noqa: E731
        self.httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self.t = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.t.start()

    def url(self, name):
        return f"http://127.0.0.1:{self.port}/{name}"

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def _ffmpeg(*args, cwd=None):
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", *args], capture_output=True, text=True, cwd=cwd)
    assert r.returncode == 0, r.stderr


def _src_args(sec=4):
    return ["-f", "lavfi", "-i", f"testsrc2=size=320x180:rate=30:duration={sec}",
            "-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=48000:duration={sec}",
            "-c:v", "libx264", "-preset", "ultrafast", "-g", "30", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "64k", "-f", "hls", "-hls_time", "1", "-hls_playlist_type", "vod"]


def _probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
                        "-of", "json", path], capture_output=True, text=True)
    j = json.loads(r.stdout or "{}")
    return float(j.get("format", {}).get("duration", 0) or 0), sorted(s["codec_type"] for s in j.get("streams", []))


def _decodes_clean(path):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "null", "-"], capture_output=True, text=True)
    return r.returncode == 0 and not r.stderr.strip(), r.stderr[-400:]


# ── HLS parser ───────────────────────────────────────────────────────────
class HlsParserV2Test(unittest.TestCase):
    def test_byterange_map_key_resolution(self):
        from size_calculator import parse_media_playlist, ensure_downloadable, Segment
        pl = "\n".join([
            "#EXTM3U", "#EXT-X-VERSION:7", "#EXT-X-TARGETDURATION:2", "#EXT-X-MEDIA-SEQUENCE:40",
            '#EXT-X-MAP:URI="init.mp4",BYTERANGE="700@0"',
            '#EXT-X-KEY:METHOD=AES-128,URI="k.bin"',
            "#EXTINF:2.0,", "#EXT-X-BYTERANGE:1000@700", "media.mp4",
            "#EXTINF:2.0,", "#EXT-X-BYTERANGE:900", "media.mp4",          # implicit offset 1700
            '#EXT-X-KEY:METHOD=AES-128,URI="k2.bin",IV=0x0000000000000000000000000000ABCD',
            "#EXTINF:1.5,", "#EXT-X-BYTERANGE:500", "media.mp4",          # implicit offset 2600
            "#EXT-X-KEY:METHOD=NONE",
            "#EXTINF:1.0,", "plain.m4s", "#EXT-X-ENDLIST"])
        info = parse_media_playlist(pl, "https://cdn.kick.com/v/index.m3u8")
        ensure_downloadable(info)
        segs = [s["ref"] for s in info["segments"]]
        self.assertTrue(all(isinstance(s, Segment) and isinstance(s, str) for s in segs))
        self.assertEqual([s.byterange for s in segs], [(1000, 700), (900, 1700), (500, 2600), None])
        self.assertEqual([s.seq for s in segs], [40, 41, 42, 43])
        self.assertEqual(segs[0].key["iv"], (40).to_bytes(16, "big"))      # IV = media sequence
        self.assertEqual(segs[1].key["iv"], (41).to_bytes(16, "big"))
        self.assertEqual(segs[2].key["iv"][-2:], b"\xab\xcd")               # explicit IV
        self.assertEqual(segs[2].key["uri"], "https://cdn.kick.com/v/k2.bin")
        self.assertIsNone(segs[3].key)
        self.assertEqual(segs[0].init, {"uri": "https://cdn.kick.com/v/init.mp4", "byterange": (700, 0)})
        self.assertTrue(all(s.advanced for s in segs))
        self.assertTrue(info["encrypted"] and info["byterange"])
        self.assertEqual(info["map"], "https://cdn.kick.com/v/init.mp4")
        self.assertEqual(segs[0], "https://cdn.kick.com/v/media.mp4")      # still a URL string

    def test_drm_is_rejected_clearly(self):
        from size_calculator import parse_media_playlist, ensure_downloadable, HLSUnsupportedError
        for line in ('#EXT-X-KEY:METHOD=SAMPLE-AES,URI="skd://x"',
                     '#EXT-X-KEY:METHOD=AES-128,URI="k",KEYFORMAT="com.apple.streamingkeydelivery"',
                     "#EXT-X-KEY:METHOD=AES-128"):
            info = parse_media_playlist(f"#EXTM3U\n{line}\n#EXTINF:2,\na.ts\n", "https://h/")
            with self.assertRaises(HLSUnsupportedError):
                ensure_downloadable(info)

    def test_slice_keeps_segment_attributes(self):
        from size_calculator import SizeCalculator, Segment
        det = [(Segment(f"u{i}", 2.0, i, (10, i * 10)), 2.0) for i in range(5)]
        urls, dur, total, start = SizeCalculator.slice_range(det, 3.0, 6.5)
        self.assertEqual([u.byterange for u in urls], [(10, 10), (10, 20), (10, 30)])
        self.assertEqual(start, 2.0)

    def test_resume_key_tells_ranges_apart(self):
        from downloader import resume_key
        from size_calculator import Segment
        a = resume_key("x.mp4", [Segment("https://c/f.mp4?s=1", 1, 0, (10, 0)), Segment("https://c/f.mp4?s=1", 1, 1, (10, 10))])
        b = resume_key("x.mp4", [Segment("https://c/f.mp4?s=2", 1, 0, (10, 0)), Segment("https://c/f.mp4?s=2", 1, 1, (10, 20))])
        self.assertNotEqual(a, b)

    def test_local_playlist_has_explicit_iv_and_map(self):
        from downloader import build_local_playlist
        pl = build_local_playlist([
            {"file": "seg_000000.m4s", "duration": 2, "init": "init_000.mp4", "key": "key_000.key", "iv": b"\x00" * 15 + b"\x07"},
            {"file": "seg_000001.m4s", "duration": 2, "init": "init_000.mp4", "key": None, "iv": None, "discontinuity": True},
        ])
        self.assertIn('#EXT-X-MAP:URI="init_000.mp4"', pl)
        self.assertIn("IV=0x00000000000000000000000000000007", pl)
        self.assertIn("#EXT-X-KEY:METHOD=NONE", pl)
        self.assertEqual(pl.count("#EXT-X-MAP"), 2)                         # re-announced after discontinuity
        self.assertTrue(pl.rstrip().endswith("#EXT-X-ENDLIST"))


# ── real downloads (ffmpeg-generated HLS served over local HTTP) ─────────
@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg required")
class HlsDownloadE2ETest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.out = tempfile.mkdtemp()
        self.srv = _Server(self.root)

    def tearDown(self):
        self.srv.close()
        shutil.rmtree(self.root, ignore_errors=True)
        shutil.rmtree(self.out, ignore_errors=True)

    def _download(self, playlist_name, start=None, end=None):
        from size_calculator import SizeCalculator
        from downloader import KickDownloader
        calc = SizeCalculator(headers={"User-Agent": "test"})
        url = self.srv.url(playlist_name)
        if start is None:
            segs, total = calc.fetch_playlist_segments(url)
        else:
            det, total = calc.fetch_playlist_segments_detailed(url)
            segs, _, total, _ = SizeCalculator.slice_range(det, start, end)
        size = calc.calculate_stream_size(url, 0, 0)
        path = KickDownloader(output_dir=self.out, max_workers=4, headers={"User-Agent": "test"}).download_stream(
            segs, os.path.splitext(playlist_name)[0] + ".mp4", force_skip_space_check=True)
        return path, segs, size

    def _assert_good(self, path, min_dur):
        dur, kinds = _probe(path)
        self.assertGreaterEqual(dur, min_dur - 0.3)
        self.assertEqual(kinds, ["audio", "video"])
        ok, err = _decodes_clean(path)
        self.assertTrue(ok, err)

    def test_aes128_ts(self):
        with open(os.path.join(self.root, "enc.key"), "wb") as fh:
            fh.write(bytes(range(16)))
        with open(os.path.join(self.root, "keyinfo.txt"), "w") as fh:
            fh.write(f"{self.srv.url('enc.key')}\n{os.path.join(self.root, 'enc.key')}\n")
        _ffmpeg(*_src_args(4), "-hls_key_info_file", os.path.join(self.root, "keyinfo.txt"),
                "-hls_segment_filename", os.path.join(self.root, "aes_%03d.ts"), os.path.join(self.root, "aes.m3u8"))
        self.assertIn("METHOD=AES-128", open(os.path.join(self.root, "aes.m3u8")).read())
        path, segs, size = self._download("aes.m3u8")
        self.assertTrue(segs[0].key)
        self.assertTrue(size["encrypted"])
        self._assert_good(path, 4.0)

    def test_aes128_slice_keeps_sequence_iv(self):
        """Sliced list starting at segment 2: IV must stay = original media sequence."""
        with open(os.path.join(self.root, "enc.key"), "wb") as fh:
            fh.write(os.urandom(16))
        with open(os.path.join(self.root, "keyinfo.txt"), "w") as fh:
            fh.write(f"{self.srv.url('enc.key')}\n{os.path.join(self.root, 'enc.key')}\n")
        _ffmpeg(*_src_args(5), "-hls_key_info_file", os.path.join(self.root, "keyinfo.txt"),
                "-hls_segment_filename", os.path.join(self.root, "s_%03d.ts"), os.path.join(self.root, "s.m3u8"))
        path, segs, _ = self._download("s.m3u8", start=2.2, end=4.5)
        self.assertEqual(segs[0].seq, 2)
        self._assert_good(path, 2.5)

    def test_fmp4(self):
        _ffmpeg(*_src_args(4), "-hls_segment_type", "fmp4", "-hls_fmp4_init_filename", "init.mp4",
                "-hls_segment_filename", os.path.join(self.root, "f_%03d.m4s"), os.path.join(self.root, "f.m3u8"),
                cwd=self.root)
        self.assertIn("#EXT-X-MAP", open(os.path.join(self.root, "f.m3u8")).read())
        path, segs, size = self._download("f.m3u8")
        self.assertTrue(segs[0].init)
        self.assertTrue(size["fmp4"])
        self._assert_good(path, 4.0)

    def test_byterange_single_file(self):
        _ffmpeg(*_src_args(4), "-hls_flags", "single_file", os.path.join(self.root, "b.m3u8"))
        text = open(os.path.join(self.root, "b.m3u8")).read()
        self.assertIn("#EXT-X-BYTERANGE", text)
        _RangeHandler.hits.clear()
        path, segs, size = self._download("b.m3u8")
        self.assertTrue(all(s.byterange for s in segs))
        # exact size from the ranges, no network sizing needed
        self.assertEqual(size["method"], "byterange_exact")
        self.assertFalse(size["is_estimate"])
        self.assertEqual(size["estimated_bytes"], sum(s.byterange[0] for s in segs))
        self.assertTrue(any(h[2] for h in _RangeHandler.hits if h[0] == "GET"))  # ranged GETs happened
        self._assert_good(path, 4.0)

    def test_plain_ts_still_concat(self):
        _ffmpeg(*_src_args(3), "-hls_segment_filename", os.path.join(self.root, "p_%03d.ts"),
                os.path.join(self.root, "p.m3u8"))
        path, segs, size = self._download("p.m3u8")
        self.assertFalse(any(s.advanced for s in segs))
        self.assertEqual(size["method"], "head_all")
        self._assert_good(path, 3.0)


# ── size estimate ────────────────────────────────────────────────────────
class SizeEstimateTest(unittest.TestCase):
    def _calc(self, sizes, durations, fail_every=0):
        from size_calculator import SizeCalculator, Segment
        segs = [{"ref": Segment(f"https://c/{i}.ts", d, i), "duration": d} for i, d in enumerate(durations)]

        class Fake(SizeCalculator):
            probes = []

            def _load(self, url):
                return {"segments": segs, "total": sum(durations), "discontinuities": 0}

            def _get_segment_size(self, url):
                i = int(str(url).rsplit("/", 1)[1].split(".")[0])
                Fake.probes.append(i)
                if fail_every and i % fail_every == 0:
                    return None
                return sizes[i]
        return Fake()

    def test_stratified_sampling_is_accurate_and_bounded(self):
        import random
        random.seed(7)
        durs = [6.0] * 1199 + [1.3]                     # 2 h VOD, short last segment
        sizes = []
        for i, d in enumerate(durs):
            rate = 600_000 if i < 600 else 1_200_000      # bitrate jumps halfway (menu -> gameplay)
            sizes.append(int(d * rate * random.uniform(0.85, 1.15)))
        c = self._calc(sizes, durs)
        res = c.calculate_stream_size("x", bandwidth=0, fallback_duration=0)
        true = sum(sizes)
        self.assertEqual(res["method"], "head_sampling")
        self.assertLess(abs(res["estimated_bytes"] - true) / true, 0.06, res)
        self.assertIsNotNone(res["error_pct"])
        self.assertLessEqual(res["estimated_bytes_low"], true * 1.02)
        self.assertGreaterEqual(res["estimated_bytes_high"], true * 0.98)
        self.assertIn(0, type(c).probes)
        self.assertIn(1199, type(c).probes)              # first and last are always sized
        self.assertLessEqual(len(set(type(c).probes)), 60)

    def test_short_playlist_is_exact(self):
        durs = [2.0] * 20
        sizes = [1000 + i for i in range(20)]
        res = self._calc(sizes, durs).calculate_stream_size("x")
        self.assertEqual((res["method"], res["is_estimate"], res["estimated_bytes"]), ("head_all", False, sum(sizes)))

    def test_head_refused_falls_back_to_ranged_get(self):
        from size_calculator import SizeCalculator
        import urllib.request
        calls = []

        class R:
            def __init__(self, headers, status=206):
                self.headers, self.status = headers, status
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        class H(dict):
            def get(self, k, d=None):
                return dict.get(self, k, d)

        def fake_open(req, timeout=0):
            calls.append((req.get_method(), req.headers.get("Range")))
            if req.get_method() == "HEAD":
                raise urllib.error.HTTPError(req.full_url, 405, "no", {}, None)
            return R(H({"Content-Range": "bytes 0-0/123456", "Content-Length": "1"}))
        orig = urllib.request.urlopen
        urllib.request.urlopen = fake_open
        try:
            self.assertEqual(SizeCalculator(headers={})._get_segment_size("https://c/a.ts"), 123456)
        finally:
            urllib.request.urlopen = orig
        self.assertEqual(calls[1], ("GET", "bytes=0-0"))


# ── Kick extractor ───────────────────────────────────────────────────────
UUID = "01a0c558-1fd0-7b89-bc86-e5e39b939572"
MASTER = ("#EXTM3U\n#EXT-X-STREAM-INF:AVERAGE-BANDWIDTH=10,BANDWIDTH=8000000,RESOLUTION=1920x1080,FRAME-RATE=60.000\n"
          "1080p60/playlist.m3u8\n#EXT-X-STREAM-INF:BANDWIDTH=2500000,RESOLUTION=1280x720,FRAME-RATE=30.000\n"
          "720p30/playlist.m3u8\n")
SRC = "https://stream.kick.com/ivs/v1/1/abc/master.m3u8"


def _fake(routes):
    seen = []

    def fetch(url, api):
        seen.append(url)
        for k, v in routes.items():
            if url == k:
                if isinstance(v, Exception):
                    raise v
                return v if isinstance(v, str) else json.dumps(v)
        raise ValueError(f"Kick вернул HTTP 404 для {url}")
    return fetch, seen


class KickExtractorApiTest(unittest.TestCase):
    def test_url_parsing(self):
        from kick_extractor import parse_kick_url
        self.assertEqual(parse_kick_url(f"https://kick.com/Jesusavgn/videos/{UUID}"),
                         {"kind": "vod", "slug": "Jesusavgn", "uuid": UUID})
        self.assertEqual(parse_kick_url(f"kick.com/video/{UUID}")["uuid"], UUID)
        self.assertEqual(parse_kick_url("https://kick.com/xqc"), {"kind": "live", "slug": "xqc", "uuid": None})
        self.assertEqual(parse_kick_url("https://kick.com/browse")["kind"], "unknown")

    def test_v2_video_api_first(self):
        from kick_extractor import KickExtractor
        fetch, seen = _fake({
            f"https://kick.com/api/v2/video/{UUID}": {
                "source": SRC, "livestream": {"session_title": "Мой стрим", "duration": 5_400_000,
                                              "start_time": "2025-02-16 01:27:34",
                                              "thumbnail": {"src": "https://images.kick.com/t.webp"},
                                              "channel": {"slug": "jesusavgn", "user": {"username": "JesusAVGN"}}}},
            SRC: MASTER})
        info = KickExtractor(tempfile.mkdtemp(), fetch=fetch).extract(f"https://kick.com/jesusavgn/videos/{UUID}")
        self.assertEqual(info["extract_method"], "api_v2_video")
        self.assertEqual((info["title"], info["streamer"], info["duration"]), ("Мой стрим", "JesusAVGN", 5400))
        self.assertEqual(info["duration_str"], "01:30:00")
        self.assertEqual(info["thumbnail"], "https://images.kick.com/t.webp")
        self.assertEqual([q["label"] for q in info["qualities"]], ["1080p60", "720p"])
        self.assertEqual(info["qualities"][0]["bandwidth"], 8000000)       # not AVERAGE-BANDWIDTH
        self.assertEqual(info["qualities"][0]["playlist_url"], "https://stream.kick.com/ivs/v1/1/abc/1080p60/playlist.m3u8")
        self.assertAlmostEqual(info["start_time"], 1739669254.0)
        self.assertNotIn("kick.com/jesusavgn/videos", " ".join(seen))    # no HTML scrape needed

    def test_v1_then_channel_videos_then_html(self):
        from kick_extractor import KickExtractor
        fetch, _ = _fake({f"https://kick.com/api/v1/video/{UUID}": {"source": SRC, "livestream": {
            "session_title": "v1", "duration": 60_000, "channel": {"slug": "abc"}}}, SRC: MASTER})
        info = KickExtractor(tempfile.mkdtemp(), fetch=fetch).extract(f"https://kick.com/abc/videos/{UUID}")
        self.assertEqual((info["extract_method"], info["duration"]), ("api_v1_video", 60))
        self.assertTrue(info["api_errors"])                                 # v2 failure recorded

        fetch, _ = _fake({"https://kick.com/api/v2/channels/abc/videos": [
            {"session_title": "other", "source": "https://x/other.m3u8", "video": {"uuid": "zzz"}},
            {"session_title": "from list", "duration": 120_000, "source": SRC, "video": {"uuid": UUID}}], SRC: MASTER})
        info = KickExtractor(tempfile.mkdtemp(), fetch=fetch).extract(f"https://kick.com/abc/videos/{UUID}")
        self.assertEqual((info["extract_method"], info["title"], info["duration"]), ("api_v2_channel_videos", "from list", 120))

        html = ('<script>{\\"recording_url\\":\\"' + SRC.replace("/", "\\/") + '\\",\\"title\\":\\"html title\\",'
                '\\"username\\":\\"abc\\",\\"duration\\":77}</script>')
        fetch, _ = _fake({f"https://kick.com/abc/videos/{UUID}": html, SRC: MASTER,
                          f"https://kick.com/api/v2/video/{UUID}": "<html>Just a moment...</html>"})
        info = KickExtractor(tempfile.mkdtemp(), fetch=fetch).extract(f"https://kick.com/abc/videos/{UUID}")
        self.assertEqual((info["extract_method"], info["title"], info["master_m3u8"]), ("html", "html title", SRC))
        self.assertTrue(any("не JSON" in e for e in info["api_errors"]))

    def test_live_channel_and_media_playlist_as_source(self):
        from kick_extractor import KickExtractor
        media = "#EXTM3U\n#EXT-X-TARGETDURATION:2\n#EXTINF:2,\na.ts\n"
        fetch, _ = _fake({"https://kick.com/api/v2/channels/xqc": {
            "slug": "xqc", "id": 668, "user": {"username": "xQc"}, "chatroom": {"id": 668},
            "playback_url": "https://live.kick.com/xqc/index.m3u8",
            "livestream": {"is_live": True, "session_title": "live!", "start_time": "2025-01-01 00:00:00"}},
            "https://live.kick.com/xqc/index.m3u8": media})
        info = KickExtractor(tempfile.mkdtemp(), fetch=fetch).extract("https://kick.com/xqc")
        self.assertEqual((info["is_live"], info["chatroom_id"], info["streamer"]), (True, 668, "xQc"))
        self.assertEqual(info["qualities"][0]["label"], "source")

    def test_offline_channel_message(self):
        from kick_extractor import KickExtractor
        fetch, _ = _fake({"https://kick.com/api/v2/channels/abc": {"slug": "abc", "livestream": None,
                                                                   "chatroom": {"id": 1}},
                          "https://kick.com/abc": "<html>no stream</html>"})
        with self.assertRaises(ValueError) as cm:
            KickExtractor(tempfile.mkdtemp(), fetch=fetch).extract("https://kick.com/abc")
        self.assertIn("не в эфире", str(cm.exception))


# ── chat recorder ────────────────────────────────────────────────────────
def _ws_server_frame(opcode, payload):
    from chat_recorder import encode_frame
    return encode_frame(opcode, payload, mask=False)


class _FakePusher(threading.Thread):
    """Plain ws:// server speaking just enough Pusher: established -> expects
    subscribe -> ping + messages (one duplicated, one fragmented) -> close.
    The second connection sends one more message, proving reconnect + dedup."""

    def __init__(self, messages):
        super().__init__(daemon=True)
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(4)
        self.port = self.sock.getsockname()[1]
        self.messages = messages
        self.subscribed = []
        self.pongs = 0
        self.conns = 0

    def _recv_frame(self, c):
        from chat_recorder import WebSocketClient
        w = WebSocketClient("ws://x")
        w.sock = c
        return w._read_frame()

    def run(self):
        from chat_recorder import OP_TEXT, OP_PING, OP_CONT, OP_CLOSE
        while self.conns < 2:
            c, _ = self.sock.accept()
            self.conns += 1
            req = b""
            while b"\r\n\r\n" not in req:
                req += c.recv(4096)
            key = [ln.split(b":", 1)[1].strip() for ln in req.split(b"\r\n") if ln.lower().startswith(b"sec-websocket-key")][0]
            acc = base64.b64encode(hashlib.sha1(key + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest())
            c.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                      b"Sec-WebSocket-Accept: " + acc + b"\r\n\r\n")
            c.sendall(_ws_server_frame(OP_TEXT, json.dumps({"event": "pusher:connection_established",
                      "data": json.dumps({"socket_id": "1.2", "activity_timeout": 120})}).encode()))
            fin, op, data = self._recv_frame(c)
            self.subscribed.append(json.loads(data))
            c.sendall(_ws_server_frame(OP_PING, b"hb"))
            fin, op, data = self._recv_frame(c)
            if op == 0xA:
                self.pongs += 1
            c.sendall(_ws_server_frame(OP_TEXT, json.dumps({"event": "pusher:ping", "data": {}}).encode()))
            self._recv_frame(c)                                             # pusher:pong
            batch = self.messages if self.conns == 1 else self.messages[-1:] + [
                dict(self.messages[0], id="m-new", content="после реконнекта")]
            for i, m in enumerate(batch):
                env = json.dumps({"event": "App\\Events\\ChatMessageEvent", "channel": "chatrooms.42.v2",
                                  "data": json.dumps(m)}).encode()
                if i == 1:                                                  # fragmented message
                    c.sendall(encode_head(env[:10], OP_TEXT, fin=False) + encode_head(env[10:], OP_CONT, fin=True))
                else:
                    c.sendall(_ws_server_frame(OP_TEXT, env))
            c.sendall(_ws_server_frame(OP_TEXT, json.dumps({"event": "App\\Events\\PinnedMessageCreatedEvent",
                                                            "data": "{}"}).encode()))
            time.sleep(0.2)
            c.sendall(_ws_server_frame(OP_CLOSE, struct.pack("!H", 1001)))
            time.sleep(0.2)
            c.close()


def encode_head(payload, op, fin):
    from chat_recorder import encode_frame
    return encode_frame(op, payload, mask=False, fin=fin)


class ChatRecorderTest(unittest.TestCase):
    def test_frame_roundtrip_and_chat_line(self):
        from chat_recorder import encode_frame, parse_pusher, chat_line
        fr = encode_frame(0x1, "привет".encode(), mask=True, mask_key=b"\x01\x02\x03\x04")
        self.assertEqual(fr[0], 0x81)
        self.assertEqual(fr[1] & 0x80, 0x80)
        big = encode_frame(0x1, b"x" * 70000, mask=False)
        self.assertEqual(big[1], 127)
        ev, data, ch = parse_pusher(json.dumps({"event": "App\\Events\\ChatMessageEvent", "channel": "c",
                                                "data": json.dumps({"id": "1", "content": "KEKW",
                                                                    "created_at": "2025-01-01T00:01:05+00:00",
                                                                    "sender": {"username": "bob"}})}))
        line = chat_line(data, t0=1735689600.0)
        self.assertEqual((line["t"], line["user"], line["text"]), (65.0, "bob", "KEKW"))
        self.assertIsNone(chat_line({"type": "pin"}, 0))

    def test_records_jsonl_reconnects_and_dedups(self):
        from chat_recorder import KickChatRecorder
        msgs = [{"id": f"m{i}", "content": f"msg {i} CLIP IT", "created_at": f"2025-01-01T00:00:{10 + i:02d}Z",
                 "sender": {"username": f"u{i}"}} for i in range(4)]
        srv = _FakePusher(msgs)
        srv.start()
        d = tempfile.mkdtemp()
        out = os.path.join(d, "chat_test.jsonl")
        rec = KickChatRecorder("test_chan", out, chatroom_id=42, stream_start=1735689600.0,
                               ws_url=f"ws://127.0.0.1:{srv.port}/app/key?protocol=7", max_backoff=0.2)
        rec.start()
        deadline = time.time() + 15
        while time.time() < deadline and rec.status()["messages"] < 5:
            time.sleep(0.05)
        rec.stop()
        srv.join(3)
        self.assertEqual(srv.subscribed[0], {"event": "pusher:subscribe",
                                             "data": {"auth": "", "channel": "chatrooms.42.v2"}})
        self.assertGreaterEqual(srv.pongs, 1)
        self.assertGreaterEqual(rec.status()["reconnects"], 1)
        with open(out, encoding="utf-8") as fh:
            lines = [json.loads(x) for x in fh if x.strip()]
        self.assertEqual([x["id"] for x in lines], ["m0", "m1", "m2", "m3", "m-new"])   # m3 not duplicated
        self.assertEqual(lines[0]["t"], 10.0)
        meta = json.load(open(out + ".meta.json", encoding="utf-8"))
        self.assertEqual((meta["chatroom_id"], meta["t_origin"]), (42, "stream_start"))
        # the file is a valid moments.py chat log
        from studio import moments as M
        chat = M.load_chat_file(out)
        self.assertEqual(len(chat), 5)
        self.assertTrue(all({"t", "user", "text"} <= set(c) for c in chat))
        shutil.rmtree(d, ignore_errors=True)

    def test_slug_validation(self):
        from chat_recorder import slug_from, KickChatRecorder
        self.assertEqual(slug_from("https://kick.com/XQC"), "xqc")
        self.assertEqual(slug_from("@abc_1"), "abc_1")
        with self.assertRaises(ValueError):
            slug_from("../../etc")
        with self.assertRaises(ValueError):
            KickChatRecorder("a b", "/tmp/x.jsonl")


if __name__ == "__main__":
    unittest.main()
