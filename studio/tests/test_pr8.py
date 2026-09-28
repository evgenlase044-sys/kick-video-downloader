"""PR #8 regression tests: preview-frame ReferenceError (collectors hoisted),
undefined `token` guard, face anchor units, export zoom that really zooms
(anchored), animated lens punch. Real ffmpeg for the filtergraph checks."""
import os
import re
import shutil
import subprocess
import unittest

import studio.pr8_patches  # noqa: F401  (appends the PR #8 patches)
from studio.patching import apply_patches, read_source

HAVE_FFMPEG = shutil.which("ffmpeg") is not None
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _body_range(src, head):
    """[start, end) of the function whose header line contains `head` (brace scan)."""
    i = src.index(head)
    j = src.index("{", i)
    depth = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            depth += 1
        elif src[k] == "}":
            depth -= 1
            if depth == 0:
                return i, k + 1
    raise AssertionError("unbalanced " + head)


class Pr8EditorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from studio.web_patches import EDITOR_PATCHES
        path = os.path.join(BASE, "web", "editor.js")
        text, _ = read_source(path)
        cls.src, res = apply_patches(text, EDITOR_PATCHES, "web/editor.js")
        cls.res = {r.id: r for r in res}

    def test_patches_applied(self):
        for pid in ("hoist-collectors-subs", "hoist-collectors-text", "hoist-collectors-fx",
                    "hoist-collectors-define", "preview-frame-v2", "face-anchor-norm"):
            self.assertIn(self.res[pid].status, ("applied", "already"), self.res[pid])

    def test_collectors_live_outside_initClipperPanel(self):
        a, b = _body_range(self.src, "function initClipperPanel()")
        for name in ("collectRegionSubtitles", "collectRegionTextItems", "collectRegionFx"):
            defs = [m.start() for m in re.finditer(r"function " + name + r"\(", self.src)]
            self.assertEqual(len(defs), 1, name)
            self.assertFalse(a <= defs[0] < b, name + " is still local to initClipperPanel")
        pa, pb = _body_range(self.src, "function requestServerPreviewFrame()")
        self.assertFalse(a <= pa < b)

    def test_preview_frame_has_no_undefined_token(self):
        pa, pb = _body_range(self.src, "function requestServerPreviewFrame()")
        body = self.src[pa:pb]
        self.assertNotIn("=== token", body)
        self.assertIn("seq !== pvSeq", body)
        self.assertIn("URL.revokeObjectURL", body)

    def test_face_anchor_is_normalized_object(self):
        self.assertNotIn("return [box.x + box.w / 2, box.y + box.h / 2];", self.src)
        self.assertIn("studio:face-anchor-norm", self.src)

    def test_fx_anchor_exported(self):
        self.assertIn("ov.anchor_x", self.src)

    @unittest.skipUnless(shutil.which("node"), "node required")
    def test_patched_editor_parses(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
            fh.write(self.src)
        try:
            r = subprocess.run(["node", "--check", fh.name], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
        finally:
            os.unlink(fh.name)


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg required")
class Pr8ExportFxTest(unittest.TestCase):
    W, H = 320, 568

    @classmethod
    def setUpClass(cls):
        import studio.loader as L
        cls.s = L.load_server()

    def _hashes(self, fxs):
        parts = []
        out = self.s._apply_fx_chain(parts, "[0:v]", fxs, self.W, self.H, 1.0, "t_")
        if not parts:
            parts, out = ["[0:v]null[t_none]"], "[t_none]"
        r = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                            f"testsrc2=size={self.W}x{self.H}:rate=30:duration=1",
                            "-filter_complex", ";".join(parts), "-map", out,
                            "-pix_fmt", "yuv420p", "-f", "framemd5", "-"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return [ln.split(",")[-1].strip() for ln in r.stdout.splitlines() if not ln.startswith("#")]

    def _zoom(self, **kw):
        return self.s.FxOverlay(kind="zoom", start=0.2, end=0.8, peak=0.15, **kw)

    def test_zoom_really_zooms_only_inside_its_window(self):
        raw = self._hashes([])
        z = self._hashes([self._zoom()])
        self.assertEqual(len(z), 30)
        self.assertEqual(raw[:6], z[:6])            # before the window: untouched
        self.assertEqual(raw[25:], z[25:])          # after the window: untouched
        self.assertGreaterEqual(sum(a != b for a, b in zip(raw[6:24], z[6:24])), 15)

    def test_zoom_anchor_moves_the_punch(self):
        c = self._hashes([self._zoom()])
        tr = self._hashes([self._zoom(anchor_x=1.0, anchor_y=0.0)])
        tl = self._hashes([self._zoom(anchor_x=0.0, anchor_y=0.0)])
        self.assertGreater(sum(a != b for a, b in zip(c[6:24], tr[6:24])), 10)
        self.assertGreater(sum(a != b for a, b in zip(tl[6:24], tr[6:24])), 10)

    def test_lens_punch_is_animated(self):
        parts = []
        self.s._apply_fx_chain(parts, "[0:v]", [self.s.FxOverlay(kind="lens", start=0.2, end=0.8, peak=0.18)],
                               self.W, self.H, 1.0, "t_")
        k1s = sorted({float(m) for m in re.findall(r"lenscorrection=k1=([-0-9.]+)", ";".join(parts))})
        self.assertGreaterEqual(len(k1s), 4)        # stepped, not one static barrel
        self.assertAlmostEqual(max(k1s), 0.18, delta=0.02)
        self.assertEqual(len(self._hashes([self.s.FxOverlay(kind="lens", start=0.2, end=0.8, peak=0.18)])), 30)

    def test_mixed_chain_renders(self):
        F = self.s.FxOverlay
        h = self._hashes([F(kind="shake", start=0.1, end=0.5, amp=12),
                          F(kind="zoom", start=0.3, end=0.7, peak=0.2, anchor_x=0.3, anchor_y=0.7),
                          F(kind="lens", start=0.5, end=0.9, peak=0.12),
                          F(kind="threshold", start=0.9, end=0.97)])
        self.assertEqual(len(h), 30)


if __name__ == "__main__":
    unittest.main()
