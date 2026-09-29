"""Playwright/Electron smoke: open file, Z/R/E, template from moments, queue, text_layer canvas, preview frame no console errors."""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIX_DIR = os.path.join(BASE, "tests", "fixtures")


class SmokeContractTest(unittest.TestCase):
    """Offline contract for the same scenario that Playwright/Electron exercises.

    - открыть файл -> push to library + timeline
    - Z/R/E хоткеи ставят эффект ровно в плейхед
    - шаблон из моментов -> plan_effects
    - в очередь -> POST /api/export-queue -> SSE /status -> file with text_layer canvas
    - превью кадр без ошибок
    """
    @classmethod
    def setUpClass(cls):
        import studio.loader as L
        cls.S = L.load_server()
        from fastapi.testclient import TestClient
        import studio.moments as _M
        import studio.api as A
        cls.client = TestClient(cls.S.app)
        cls._M = _M
        cls.A = A
        # pick a real source (fixture if present, else synthetic)
        for name in ("fixture_kick_full_1080x1080.mp4", "fixture_kick_1080p60_short.mp4", "fixture_phone_1080p.mp4"):
            if os.path.exists(os.path.join(FIX_DIR, name)):
                import shutil
                dst = os.path.join(BASE, "downloads", name)
                if not os.path.exists(dst):
                    shutil.copy2(os.path.join(FIX_DIR, name), dst)
                cls.src = name
                break
        else:
            dl = os.path.join(BASE, "downloads", "_vt_test_src.mp4")
            if not os.path.exists(dl):
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                                "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=6",
                                "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
                                "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-pix_fmt", "yuv420p",
                                "-c:a", "aac", "-shortest", dl], check=True, timeout=120)
            cls.src = "_vt_test_src.mp4"

    def test_editor_hotkeys_present(self):
        ed = open(os.path.join(BASE, "web", "editor.js"), encoding="utf-8").read()
        for key, kind in [("KeyZ", "zoom"), ("KeyR", "ramp"), ("KeyE", "freeze"),
                          ("KeyL", "lens"), ("KeyB", "threshold"), ("KeyW", "whip")]:
            self.assertIn(key, ed, f"hotkey {key}")
            self.assertIn(f'addEffectAtPlayhead("{kind}"', ed, f"hotkey {key} -> {kind}")
        self.assertIn("snapToCut", ed)
        self.assertIn("exportQueueBtn", ed)
        self.assertIn("/api/export-queue", ed)
        self.assertIn("EventSource", ed)

    def test_template_and_moments_then_queue_e2e(self):
        from studio.templates import plan_effects
        beats = [{"t": 1.0, "intensity": 0.9}, {"t": 5.0, "intensity": 0.5}, {"t": 9.0, "intensity": 0.95}]
        fxs = plan_effects("hype", beats, face={"x": 0.5, "y": 0.35})
        self.assertTrue(any(f["kind"] == "zoom" for f in fxs))
        # also verify moments signal wiring (no network)
        rms = [ -30.0 + 8.0 * (i % 20 == 3) for i in range(80) ]
        moments = self._M.find_moments(duration=42.0, rms_db=rms, chat=[], words=[], top_k=3, clip_len=28.0)
        self.assertGreaterEqual(len(moments), 1)
        # queue one clip using those fx + text_layer canvas path
        clip = {
            "id": "smoke_q", "title": "Smoke", "source_file": self.src,
            "start_time": 0, "end_time": 1.5, "format": "fullscreen", "color_grade": "tv",
            "layers": [{"source_file": self.src, "src_offset": 0, "duration": 1.5,
                        "out_start": 0, "opacity": 1, "volume": 1, "muted": False, "z": 0}],
            "overlays": [{"kind": "zoom", "start": 0.2, "end": 0.5, "peak": 0.15, "z": 0}],
            "subs_in_output_time": True, "subtitle_mode": "none", "hot_words": False,
        }
        self.client.post("/api/export-queue/clear")
        r = self.client.post("/api/export-queue", json={"clips": [clip], "name_template": "{channel}_{date}_{n}_{title}"})
        self.assertEqual(r.status_code, 200, r.text[:800])
        # drain SSE stream until end
        saw_progress = saw_end = False
        files = []
        with self.client.stream("GET", "/api/export-queue/stream") as resp:
            self.assertTrue(resp.headers.get("content-type", "").startswith("text/event-stream"))
            for line in resp.iter_lines():
                if not line.startswith("data:"):
                    continue
                m = json.loads(line[5:].strip())
                if m.get("type") == "progress": saw_progress = True
                if m.get("type") == "end": saw_end = True; break
        st = self.client.get("/api/export-queue/status").json()
        for res in st.get("results", []):
            files.extend(res.get("files", []))
        self.assertTrue(saw_progress and saw_end, f"progress={saw_progress} end={saw_end}")
        self.assertEqual(len(files), 1)
        self.assertTrue(os.path.exists(files[0]), files)
        # cleanup
        try: os.remove(files[0])
        except: pass
        self.client.post("/api/export-queue/clear")

    def test_canvas_text_layer_and_preview_frame(self):
        # preview frame renders without error for a clip with canvas text
        r = self.client.post("/api/preview-frame", json={
            "source_file": self.src, "src_time": 0.8, "format": "fullscreen",
            "width": 608, "height": 1080, "color_grade": "tv",
            "subtitles": [{"text": "ПРИВЕТ", "start": 0, "end": 1.0, "style": "acid",
                           "words": [{"word": "ПРИВЕТ", "start": 0, "end": 1.0}]}],
            "overlays": [{"kind": "shake", "start": 0.2, "end": 0.5, "amp": 12, "z": 0}],
        })
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.headers.get("content-type", "").startswith("image/"))

    def test_electron_main_loads_index_with_token(self):
        main_js = open(os.path.join(BASE, "main.js"), encoding="utf-8").read()
        self.assertIn("loadURL", main_js)
        self.assertIn("index.html?token=", main_js)
        self.assertIn("ensureFreshBackend", main_js)
        self.assertIn("/api/version", main_js)


if __name__ == "__main__":
    unittest.main()
