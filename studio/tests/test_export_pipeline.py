"""Export pipeline tests (PR #6). Real ffmpeg where available, no server.py needed."""
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import types
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)

from studio import ffmpeg_argv as FA  # noqa: E402
from studio import grade as G  # noqa: E402
from studio import overlay as OV  # noqa: E402

HAVE_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def fake_h264(fps):
    return ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-g", str(int(round(fps * 2)))]


def ff(*args):
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args], capture_output=True, text=True)
    if r.returncode:
        raise AssertionError(r.stderr[-800:])


def write_png(path, w, h, box=None, rgba=(255, 0, 0, 255)):
    import zlib
    x0, y0, x1, y1 = box or (0, 0, 0, 0)
    rows = []
    for y in range(h):
        row = bytearray(b"\x00")
        for x in range(w):
            row += bytes(rgba) if (x0 <= x < x1 and y0 <= y < y1) else b"\x00\x00\x00\x00"
        rows.append(bytes(row))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(png)


def rgb_frame(path, idx, w, h):
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-vf", f"select=eq(n\\,{idx}),scale={w}:{h}",
                        "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    return r.stdout


class ArgvRewriteTest(unittest.TestCase):
    EXP = os.path.join(tempfile.gettempdir(), "exported_packs_test")

    def cmd(self, out=None, codec="libx264"):
        return ["ffmpeg", "-y", "-colorspace", "bt709", "-ss", "12.5", "-i", "src.mp4", "-i", "music.wav",
                "-filter_complex", "[0:v]scale=1080:1920[v];[1:a]loudnorm=I=-14:TP=-1.5[a]",
                "-map", "[v]", "-map", "[a]", "-c:v", codec, "-preset", "medium", "-crf", "15",
                "-tune", "film", "-x264-params", "aq-mode=3", "-pix_fmt", "yuv420p", "-r", "60",
                "-colorspace", "bt709", "-c:a", "aac", "-b:a", "320k", "-movflags", "+faststart",
                out or os.path.join(self.EXP, "Short_1.mp4")]

    def test_export_encode_detected_only_in_export_dir(self):
        self.assertTrue(FA.is_export_encode(self.cmd(), self.EXP))
        self.assertFalse(FA.is_export_encode(self.cmd(out="/tmp/other/proxy.mp4"), self.EXP))
        self.assertFalse(FA.is_export_encode(self.cmd(codec="copy"), self.EXP))
        self.assertFalse(FA.is_export_encode(["ffprobe", "-i", "x"], self.EXP))

    def test_codec_block_replaced_and_input_tags_kept(self):
        new, info = FA.rewrite_export(self.cmd(), h264_args=fake_h264)
        tail = new[new.index("[a]") + 1:]
        self.assertNotIn("medium", tail)
        self.assertNotIn("-tune", tail)
        self.assertEqual(new.count("-c:v"), 1)
        self.assertEqual(new[1:4], ["-y", "-colorspace", "bt709"])
        self.assertEqual(new[new.index("-r") + 1], "60")
        self.assertEqual(new[-1], self.cmd()[-1])
        self.assertTrue(info["loudnorm"])
        self.assertIn("loudnorm=I=-14:TP=-1.0:LRA=11,alimiter=limit=0.891", new[new.index("-filter_complex") + 1])
        self.assertIn("-ar", new)

    def test_fps_override_and_ntsc(self):
        new, _ = FA.rewrite_export(self.cmd(), h264_args=fake_h264, fps_override=30)
        self.assertEqual(new[new.index("-r") + 1], "30")
        self.assertEqual(new.count("-r"), 1)
        self.assertEqual(FA.rate_string(29.97), "30000/1001")

    def test_intermediate_is_near_lossless(self):
        new, _ = FA.rewrite_export(self.cmd(), h264_args=fake_h264, intermediate=True)
        self.assertEqual(new[new.index("-crf") + 1], "12")

    def test_seek_audit(self):
        self.assertEqual(FA.seek_audit(self.cmd())["inputs"][0], {"input": "src.mp4", "ss": "12.5"})
        slow = ["ffmpeg", "-i", "vod.mp4", "-filter_complex", "[0:v]trim=start=3600:end=3620[v]", "-map", "[v]", "o.mp4"]
        self.assertTrue(FA.seek_audit(slow)["slow_seek"])


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg not installed")
class GradeAndOverlayTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_grade_chain_runs(self):
        cube = os.path.join(self.tmp, "id.cube")
        with open(cube, "w") as fh:
            fh.write("LUT_3D_SIZE 2\n" + "".join(f"{r} {g} {b}\n" for b in (0, 1) for g in (0, 1) for r in (0, 1)))
        for s in (0.0, 0.55, 1.0):
            g = G.grade_chain("[s]", "[g]", cube, s)[0]
            ff("-f", "lavfi", "-i", "testsrc2=s=320x240:d=0.2:r=10", "-filter_complex",
               "[0:v]format=yuv420p[s];" + g + ";[g]format=yuv420p[out]", "-map", "[out]", "-f", "null", "-")
        self.assertEqual(G.escape_filter_path(r"C:\a\tv_grade.cube"), r"C\:/a/tv_grade.cube")

    def test_overlay_lands_on_exact_frame(self):
        video = os.path.join(self.tmp, "clip.mp4")
        ff("-f", "lavfi", "-i", "color=c=0x202020:s=320x568:r=30:d=1", "-f", "lavfi", "-i",
           "sine=f=440:d=1:sample_rate=48000", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", video)
        d = os.path.join(self.tmp, "job")
        os.makedirs(d)
        write_png(os.path.join(d, "000000.png"), 160, 284)
        write_png(os.path.join(d, "000015.png"), 160, 284, box=(40, 40, 120, 100))
        lst = OV.write_concat(d, [0, 15], 30, OV.parse_fps(30))
        ok, msg = OV.burn_overlay(video, {"list": lst, "dir": d}, fake_h264)
        self.assertTrue(ok, msg)
        px = lambda buf, x, y: buf[(y * 32 + x) * 3]
        self.assertLess(px(rgb_frame(video, 14, 32, 57), 16, 10), 80)
        self.assertGreater(px(rgb_frame(video, 15, 32, 57), 16, 10), 180)

    def test_header_validation(self):
        with self.assertRaises(OV.OverlayError):
            OV.parse_header({"clip_id": "../x", "w": 1080, "h": 1920, "frames": 10})
        with self.assertRaises(OV.OverlayError):
            OV.parse_header({"clip_id": "a", "w": 1081, "h": 1920, "frames": 10})


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg not installed")
class ExportWrapperTest(unittest.TestCase):
    def setUp(self):
        from studio import export_pipeline as EP
        self.EP = EP
        self.tmp = tempfile.mkdtemp()
        self.exp = os.path.join(self.tmp, "exported_packs")
        os.makedirs(self.exp)
        self.calls = []

        class Clip:
            def __init__(s, cid):
                s.id, s.title = cid, "t"
                s.subtitles = [{"text": "hi"}]
                s.text_items = [{"text": "HELLO"}]
                s.subtitle_mode = None

        class Req:
            def __init__(s, pack_name="Pack", clips=(), name_template=None):
                s.pack_name, s.clips, s.name_template = pack_name, list(clips), name_template
        self.Clip, self.Req = Clip, Req
        srv = types.SimpleNamespace(EXPORTED_PACKS_DIR=self.exp, DOWNLOADS_DIR=self.tmp, ExportPackRequest=Req)
        shim = EP.make_subprocess_shim(subprocess, self.exp)
        test = self

        def original(req):
            clip = req.clips[0]
            test.calls.append((list(clip.text_items), clip.subtitle_mode))
            out = os.path.join(test.exp, f"Short_{clip.id}.mp4")
            shim.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=gray:s=160x284:r=30:d=0.5",
                      "-c:v", "libx264", "-preset", "medium", "-crf", "15", out], check=True)
            return {"exported_count": 1, "clips": [{"filename": os.path.basename(out)}], "failed": []}
        self.wrapped = EP.make_export_wrapper(srv, original)
        self._h264 = EP.ffmpeg_caps.h264_args
        EP.ffmpeg_caps.h264_args = fake_h264

    def tearDown(self):
        self.EP.ffmpeg_caps.h264_args = self._h264
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _job(self, broken=False):
        d = os.path.join(self.tmp, "ovjob")
        os.makedirs(d, exist_ok=True)
        write_png(os.path.join(d, "000000.png"), 160, 284, box=(10, 10, 60, 60), rgba=(255, 255, 255, 255))
        lst = OV.write_concat(d, [0], 15, 30)
        if broken:
            os.remove(os.path.join(d, "000000.png"))
        return {"clip_id": "c1", "list": lst, "dir": d, "created": 1e18}

    def test_passthrough_without_options(self):
        self.wrapped(self.Req(clips=[self.Clip("zz")]))
        self.assertEqual(self.calls[0][0], [{"text": "HELLO"}])

    def test_canvas_layer_replaces_ass_text(self):
        OV.register(self._job())
        self.EP.set_clip_options("c1", {"template": "story", "overlay": True})
        res = self.wrapped(self.Req(clips=[self.Clip("c1")]))
        self.assertEqual(self.calls[0], ([], "none"))
        self.assertEqual(res["clips"][0].get("text_layer"), "canvas")
        self.assertAlmostEqual(float(OV.probe_video(os.path.join(self.exp, "Short_c1.mp4"))["fps"]), 30.0, places=2)

    def test_fallback_to_ass_when_overlay_fails(self):
        OV.register(self._job(broken=True))
        res = self.wrapped(self.Req(clips=[self.Clip("c1")]))
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.calls[1][0], [{"text": "HELLO"}])
        self.assertEqual(res["clips"][0].get("text_layer"), "ass_fallback")

    def test_multi_clip_split(self):
        self.EP.set_clip_options("a", {"template": "hype"})
        res = self.wrapped(self.Req(clips=[self.Clip("a"), self.Clip("b")]))
        self.assertEqual(res["exported_count"], 2)


if __name__ == "__main__":
    unittest.main()
