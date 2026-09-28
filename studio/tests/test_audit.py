"""Regression tests for the audit fixes (run: python -m unittest discover -s studio/tests -t .)."""
import os
import sys
import tempfile
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)


class DiskManagerTest(unittest.TestCase):
    def test_peak_and_safety(self):
        from disk_manager import DiskManager
        with tempfile.TemporaryDirectory() as d:
            r = DiskManager(d).check_space(1000, peak_factor=2.0)
            self.assertEqual(r["required_safety_bytes"], 2100)
            self.assertIn("required_safety_formatted", r)      # cli.py used to KeyError here
            self.assertEqual(DiskManager.required_with_margin(1000, 2.0, 0.05, 600), 1500)

    def test_server_patch_signature(self):
        # studio:disk-peak calls check_space(bytes, peak_factor=...) -> must not TypeError
        from disk_manager import DiskManager
        with tempfile.TemporaryDirectory() as d:
            DiskManager(d).check_space(10, peak_factor=2.0)


class HlsParserTest(unittest.TestCase):
    def test_parse(self):
        from size_calculator import parse_media_playlist, ensure_downloadable, HLSUnsupportedError
        pl = "\n".join(["#EXTM3U", "#EXT-X-TARGETDURATION:6", "#EXTINF:6.0,", "a.ts", "#EXT-X-DISCONTINUITY",
                        "#EXTINF:4.5,", "b.ts", "stray-uri-without-extinf.ts", "#EXT-X-ENDLIST"])
        info = parse_media_playlist(pl, "https://cdn.kick.com/x/index.m3u8")
        self.assertEqual([s["url"] for s in info["segments"]],
                         ["https://cdn.kick.com/x/a.ts", "https://cdn.kick.com/x/b.ts"])
        self.assertAlmostEqual(info["total"], 10.5)
        self.assertEqual(info["discontinuities"], 1)
        self.assertTrue(info["segments"][1]["discontinuity"])
        ensure_downloadable(info)
        # PR #10: AES-128 is downloadable now (studio/tests/test_pr10.py downloads it for real);
        # DRM-like schemes (SAMPLE-AES) are still rejected with a clear message
        aes = parse_media_playlist("#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI=\"k\"\n#EXTINF:2,\na.ts\n", "https://h/")
        ensure_downloadable(aes)
        self.assertTrue(aes["encrypted"])
        enc = parse_media_playlist("#EXTM3U\n#EXT-X-KEY:METHOD=SAMPLE-AES,URI=\"k\"\n#EXTINF:2,\na.ts\n", "https://h/")
        with self.assertRaises(HLSUnsupportedError):
            ensure_downloadable(enc)
        with self.assertRaises(HLSUnsupportedError):
            parse_media_playlist("#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1\nlow.m3u8\n", "https://h/")

    def test_slice_validation(self):
        from size_calculator import SizeCalculator
        det = [("a", 6.0), ("b", 6.0), ("c", 6.0)]
        urls, dur, total, start = SizeCalculator.slice_range(det, 7, 13)
        self.assertEqual(urls, ["b", "c"])
        self.assertEqual(start, 6.0)
        for bad in ((5, 5), (-1, 3), (30, 40)):
            with self.assertRaises(ValueError):
                SizeCalculator.slice_range(det, *bad)


class DownloaderTest(unittest.TestCase):
    def test_resume_key_stable_across_signed_urls(self):
        from downloader import resume_key
        a = resume_key("x.mp4", ["https://c/1.ts?sig=aaa", "https://c/2.ts?sig=bbb"])
        b = resume_key("x.mp4", ["https://c/1.ts?sig=zzz", "https://c/2.ts?sig=yyy"])
        self.assertEqual(a, b)
        self.assertNotEqual(a, resume_key("y.mp4", ["https://c/1.ts"]))


class HooksTest(unittest.TestCase):
    def test_short_words_kept(self):
        from studio.server_hooks import enforce_min_word_duration
        words = [{"word": "а", "start": 1.0, "end": 1.0}, {"word": "б", "start": 1.01, "end": 1.2}]
        out = enforce_min_word_duration(words, 2 / 60)
        self.assertEqual(len(out), 2)
        self.assertTrue(all(w["end"] > w["start"] for w in out))

    def test_fps_exact(self):
        from studio.server_hooks import stream_fps
        self.assertEqual(stream_fps({"avg_frame_rate": "60000/1001", "r_frame_rate": "60/1"}), (59.9401, "60000/1001"))

    def test_time_remap_filters(self):
        from studio.server_hooks import fx_time_remap
        parts, label = fx_time_remap("freeze", "[v0]", "t0", 1.0, 1.5)
        self.assertIn("select=", parts[0])
        parts, label = fx_time_remap("ramp", "[v0]", "t0", 1.0, 1.6)
        self.assertIn("setpts=", parts[0])

    def test_ramp_duration_preserving(self):
        from studio.timeremap import ramp_src_offset
        self.assertAlmostEqual(ramp_src_offset(0.6, 0.6), 0.6)   # back in sync at the window end
        self.assertAlmostEqual(ramp_src_offset(0.3, 0.6), 0.105)


class SecurityTest(unittest.TestCase):
    def test_paths_and_hosts(self):
        from studio.security import safe_join, is_allowed_media_host
        with tempfile.TemporaryDirectory() as d:
            p = safe_join(d, "../../etc/passwd")
            self.assertEqual(os.path.dirname(p), os.path.realpath(d))
        self.assertTrue(is_allowed_media_host("https://stream.kick.com/a.m3u8"))
        self.assertFalse(is_allowed_media_host("http://127.0.0.1:8765/api/shutdown"))
        self.assertFalse(is_allowed_media_host("http://169.254.169.254/latest"))
        self.assertFalse(is_allowed_media_host("file:///etc/passwd"))


class RenderWsTest(unittest.TestCase):
    def test_header_limits_and_command(self):
        from studio.render_ws import parse_header, build_command, HeaderError
        with tempfile.TemporaryDirectory() as d:
            p = parse_header({"w": 1080, "h": 1920, "frames": 60, "fps": 59.94}, d, d)
            self.assertEqual(str(p["fps"]), "60000/1001")
            cmd = build_command(p, os.path.join(d, "o.mp4"))
            self.assertLess(cmd.index("-colorspace"), cmd.index("pipe:0"))
            self.assertIn("-t", cmd)
            for bad in ({"w": 99999, "h": 2, "frames": 1}, {"w": 1081, "h": 1920, "frames": 1},
                        {"w": 1080, "h": 1920, "frames": 0}):
                with self.assertRaises(HeaderError):
                    parse_header(bad, d, d)
            with self.assertRaises(HeaderError):
                parse_header({"w": 2, "h": 2, "frames": 1, "audio_wav": "/etc/passwd"}, d, d)


class MomentsTest(unittest.TestCase):
    def test_finds_injected_peak(self):
        from studio import moments as M
        import random
        random.seed(3)
        rms = [-40 + random.random() * 3 for _ in range(2400)]      # 20 min @ 0.5 s
        for i in range(1600, 1616):
            rms[i] = -6.0                                           # explosion at 800 s
        chat = [{"t": 815 + random.random() * 8, "user": f"u{i}", "text": "KEKW CLIP IT"} for i in range(60)]
        chat += [{"t": random.random() * 1200, "user": "x", "text": "hi"} for _ in range(150)]
        res = M.find_moments(duration=1200, rms_db=rms, chat=chat, top_k=3)
        self.assertTrue(res[0]["start"] <= 800 <= res[0]["end"], res[0])
        starts = [m["peak"] for m in res]
        self.assertTrue(all(abs(a - b) >= 30 for i, a in enumerate(starts) for b in starts[i + 1:]))

    def test_llm_fallback(self):
        from studio import moments as M
        def boom(_):
            raise OSError("no network")
        res = M.find_moments(duration=200, rms_db=[-30.0] * 400, words=[{"start": 5, "word": "что"}],
                             top_k=2, use_llm=True, llm=boom)
        self.assertEqual(len(res), 2)


class TemplatesTest(unittest.TestCase):
    def test_policy(self):
        from studio.templates import plan_effects
        fx = plan_effects("hype", [{"t": 1, "intensity": 0.5}, {"t": 1.5, "intensity": 0.9},
                                   {"t": 4, "intensity": 0.95}])
        zooms = [f for f in fx if f["kind"] == "zoom"]
        self.assertEqual(len(zooms), 2)                    # 1.5 s beat dropped by the cooldown
        self.assertTrue(0.15 <= zooms[1]["amp"] <= 0.30)   # peak punch 115-130 %
        self.assertEqual(plan_effects("clean", [{"t": 1, "intensity": 1}]), [])


class PatchAnchorsTest(unittest.TestCase):
    """Every required anchored fix must still apply (or be folded in)."""
    def test_all_required_patches_apply(self):
        from studio.patching import apply_patches, read_source, targets
        bad = []
        for rel, patches in targets():
            path = os.path.join(BASE, rel)
            if not os.path.exists(path):
                continue
            _, res = apply_patches(read_source(path)[0], patches, rel)
            bad += [f"{rel}:{r.id} ({r.detail})" for r in res if r.status == "failed" and r.required]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
