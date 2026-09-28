"""PR #9: lens v2 (overscan, no rgbashift), motion blur only in its window,
per-band grade. Real ffmpeg."""
import shutil
import subprocess
import unittest

from studio import fx_extra as X

HAVE_FFMPEG = shutil.which("ffmpeg") is not None


def _md5s(parts, out, w=320, h=568):
    r = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"testsrc2=size={w}x{h}:rate=30:duration=1",
                        "-filter_complex", ";".join(parts), "-map", out, "-pix_fmt", "yuv420p", "-f", "framemd5", "-"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return [ln.split(",")[-1].strip() for ln in r.stdout.splitlines() if not ln.startswith("#")]


class Pr9FxTest(unittest.TestCase):
    def test_lens_params_match_lens_js(self):
        k_ff, norm = X.lens_step_params(0.18, 9 / 16)
        self.assertAlmostEqual(k_ff, 0.18 * ((0.5 * 9 / 16) ** 2 + 0.25), places=6)
        self.assertGreater(norm, 1.0)

    def test_lens_parts_have_overscan_and_no_rgbashift(self):
        parts, _ = X.lens_punch_parts("[0:v]", "t_", 0.2, 0.8, 0.18, 320, 568)
        g = ";".join(parts)
        self.assertNotIn("rgbashift", g)
        self.assertIn("perspective=", g)
        self.assertIn("chromashift=", g)

    @unittest.skipUnless(HAVE_FFMPEG, "ffmpeg required")
    def test_lens_and_blur_only_touch_their_window(self):
        raw = _md5s(["[0:v]null[o]"], "[o]")
        lp, lo = X.lens_punch_parts("[0:v]", "t_", 0.2, 0.8, 0.18, 320, 568)
        lens = _md5s(lp, lo)
        mp, mo = X.motion_blur_parts("[0:v]", "m_", 0.4, 0.6)
        mb = _md5s(mp, mo)
        for h in (lens, mb):
            self.assertEqual(len(h), 30)
            self.assertEqual(h[:6], raw[:6])
            self.assertEqual(h[25:], raw[25:])
        self.assertGreater(sum(a != b for a, b in zip(raw[12:18], mb[12:18])), 3)

    def test_split_top_h(self):
        self.assertEqual(X.split_top_h({"fmt": "split_adhd", "top_h": 432}), 432)
        self.assertEqual(X.split_top_h({"fmt": "talking_head_9_16", "top_h": 432}), 0)

    @unittest.skipUnless(HAVE_FFMPEG, "ffmpeg required")
    def test_grade_bands_renders(self):
        fake = lambda s, d, is_vertical=True: [f"{s}hue=h=90,format=gbrp{d}"]
        parts = X.grade_bands(fake, "[0:v]", "[graded]", 320, 568, 256)
        self.assertEqual(len(_md5s(parts, "[graded]")), 30)


if __name__ == "__main__":
    unittest.main()
