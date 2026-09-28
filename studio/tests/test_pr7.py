"""PR #7 regression tests (real ffmpeg): loudness gate, export wrapper gate,
new anchored patches present after folding."""
import os
import shutil
import subprocess
import tempfile
import types
import unittest

from studio import loudness as LN

HAVE_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_clip(path, gain_db=-28.0, seconds=8, audio=True):
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "lavfi", "-i", f"testsrc2=size=160x284:rate=30:duration={seconds}"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=48000:duration={seconds}",
                "-af", f"volume={gain_db}dB", "-c:a", "aac", "-b:a", "128k"]
    cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", path]
    subprocess.run(cmd, check=True)


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg required")
class LoudnessGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_quiet_clip_is_normalized_and_video_kept(self):
        p = os.path.join(self.tmp, "quiet.mp4")
        make_clip(p, -28.0)
        before = LN.measure(p)
        self.assertIsNotNone(before)
        self.assertLess(before["input_i"], -20.0)
        info = LN.ensure(p)
        self.assertTrue(info["checked"])
        self.assertTrue(info["fixed"], info)
        after = LN.measure(p)
        self.assertAlmostEqual(after["input_i"], LN.TARGET_I, delta=1.5)
        self.assertLessEqual(after["input_tp"], LN.TARGET_TP + LN.TOL_TP)
        v = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-count_packets",
                            "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", p],
                           capture_output=True, text=True).stdout.strip()
        self.assertEqual(int(v), 240)          # 8 s @ 30 fps, video stream copied untouched

    def test_on_target_clip_untouched(self):
        p = os.path.join(self.tmp, "ok.mp4")
        make_clip(p, -28.0)
        LN.ensure(p)
        mtime = os.path.getmtime(p)
        info = LN.ensure(p)
        self.assertTrue(info["checked"])
        self.assertFalse(info["fixed"], info)
        self.assertEqual(os.path.getmtime(p), mtime)

    def test_no_audio_is_skipped(self):
        p = os.path.join(self.tmp, "mute.mp4")
        make_clip(p, audio=False)
        self.assertEqual(LN.ensure(p), {"checked": False})

    def test_loud_clip_true_peak_limited(self):
        p = os.path.join(self.tmp, "loud.mp4")
        make_clip(p, 0.0)
        info = LN.ensure(p)
        self.assertTrue(info["fixed"], info)
        after = LN.measure(p)
        self.assertAlmostEqual(after["input_i"], LN.TARGET_I, delta=1.5)

    def test_export_wrapper_applies_gate_on_plain_exports(self):
        from studio import export_pipeline as EP
        p = os.path.join(self.tmp, "clip1.mp4")
        make_clip(p, -30.0)

        class Req:
            def __init__(self, pack_name="p", clips=None, name_template="{n}"):
                self.pack_name, self.clips, self.name_template = pack_name, clips or [], name_template

        fake_server = types.SimpleNamespace(EXPORTED_PACKS_DIR=self.tmp, ExportPackRequest=Req)
        wrapped = EP.make_export_wrapper(fake_server, lambda req: {"clips": [{"path": p}]})
        res = wrapped(Req(clips=[types.SimpleNamespace(id="")]))
        self.assertTrue(res["clips"][0]["loudness"]["fixed"], res)
        self.assertAlmostEqual(LN.measure(p)["input_i"], LN.TARGET_I, delta=1.5)


class Pr7PatchesTest(unittest.TestCase):
    def _apply(self, rel, patches):
        from studio.patching import apply_patches, read_source
        path = os.path.join(BASE, rel)
        if not os.path.exists(path):
            self.skipTest(rel + " missing")
        text, _ = read_source(path)
        new, res = apply_patches(text, patches, rel)
        return new, {r.id: r for r in res}

    def test_server_patches(self):
        from studio.server_patches import SERVER_PATCHES
        new, res = self._apply("server.py", SERVER_PATCHES)
        for pid in ("check-disk-peak", "main-secure"):
            self.assertIn(res[pid].status, ("applied", "already"), res[pid])
        self.assertIn("peak_factor=_studio.DOWNLOAD_PEAK_FACTOR)  # studio:check-disk-peak", new)
        self.assertIn("studio_server.main()", new)

    def test_editor_patches(self):
        from studio.web_patches import EDITOR_PATCHES
        new, res = self._apply(os.path.join("web", "editor.js"), EDITOR_PATCHES)
        for pid in ("addfx-v2", "addfx-source"):
            self.assertIn(res[pid].status, ("applied", "already"), res[pid])
        self.assertNotIn("Math.round(f.amp * 100)", new)       # shake amp 16 -> 1600 bug gone
        self.assertIn("addEffectAtPlayhead(kind", new)
        self.assertIn('{ timeBase: "source" }', new)

    def test_gl_lens_shader_has_no_debug_output(self):
        with open(os.path.join(BASE, "web", "core", "render", "glPasses.js"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn("DEBUG", src)
        self.assertIn("texture(uSrc, uvR).r", src)


if __name__ == "__main__":
    unittest.main()
