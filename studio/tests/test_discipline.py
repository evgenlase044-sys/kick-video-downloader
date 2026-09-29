"""Discipline-edit planner tests (no ffmpeg; slides need PIL only)."""
import os
import tempfile
import unittest

from studio import discipline as D


def _mats():
    return [
        {"filename": "a.mp4", "duration": 15.0},
        {"filename": "b.mp4", "duration": 56.0},
        {"filename": "c.mp4", "duration": 15.0},
    ]


def _analysis():
    return {"duration": 162.0, "drop": 9.2,
            "onsets": [round(0.5 + i * 0.9, 2) for i in range(120)]}


def _plan(**kw):
    args = dict(materials=_mats(), music_file="m.m4a", target_dur=21.0,
                n_pics=4, hook_text="X", pic_loops=["p1.mp4", "p2.mp4"],
                analysis=_analysis())
    args.update(kw)
    return D.plan_discipline(**args)


class DisciplinePlanTest(unittest.TestCase):
    def test_intro_tiles_and_takeover_overlap(self):
        p = _plan()
        self.assertAlmostEqual(p["duration"], 21.0)
        # clips tile [0, drop] without gaps; the last one runs UNDER the card
        t = 0.0
        for c in p["clips"]:
            self.assertAlmostEqual(c["out_start"], t, places=1)
            t += c["duration"]
        self.assertGreaterEqual(t, p["drop"] + D.TAKEOVER_S - 0.05)
        # takeover card starts exactly at the drop, small, growing
        first = p["cards"][0]
        self.assertAlmostEqual(first["out_start"], p["drop"], places=2)
        self.assertLess(first["scale_from"], 0.3)
        self.assertAlmostEqual(first["scale_in"], D.TAKEOVER_S, places=2)

    def test_cards_tile_drop_to_end(self):
        p = _plan()
        t = p["drop"]
        for c in p["cards"]:
            self.assertAlmostEqual(c["out_start"], t, places=1)
            t += c["duration"]
        self.assertAlmostEqual(t, p["duration"], places=1)

    def test_src_windows_inside_files(self):
        p = _plan(n_pics=2, pic_loops=["p1.mp4"])
        by_name = {m["filename"]: m["duration"] for m in _mats()}
        for c in list(p["clips"]) + [x for x in p["cards"] if x["kind"] == "video"]:
            dur = by_name[c["filename"]]
            self.assertGreaterEqual(c["src_in"], 0.0)
            self.assertLessEqual(c["src_in"] + c["duration"], dur + 0.05)

    def test_fx_variety_and_tracks(self):
        p = _plan()
        kinds = {f["kind"] for f in p["fx"]}
        self.assertIn("zoom", kinds)     # pre-drop punch
        self.assertIn("shake", kinds)    # drop impact
        self.assertIn("flash", kinds)    # beat-cut flashes
        self.assertIn("push", kinds)
        tracks = {f.get("track") for f in p["fx"]}
        self.assertEqual(tracks, {"video", "cards"})
        modes = {f.get("mode") for f in p["fx"] if f["kind"] == "push"}
        self.assertIn("out", modes)      # alternating movement
        # card FX never start before the drop
        for f in p["fx"]:
            if f.get("track") == "cards":
                self.assertGreaterEqual(f["start"], p["drop"] - 0.01)

    def test_sounds_riser_boom(self):
        p = _plan()
        kinds = [s["kind"] for s in p["sounds"]]
        self.assertIn("riser", kinds)
        self.assertIn("boom", kinds)
        boom = next(s for s in p["sounds"] if s["kind"] == "boom")
        self.assertAlmostEqual(boom["at"], p["drop"], places=2)

    def test_no_pics_still_tiles(self):
        p = _plan(target_dur=15.0, n_pics=0, pic_loops=[])
        total = sum(c["duration"] for c in p["clips"]) + \
            sum(c["duration"] for c in p["cards"])
        self.assertGreaterEqual(total, p["duration"] - 0.2)

    def test_slides_generated_and_placed(self):
        with tempfile.TemporaryDirectory() as td:
            p = _plan(work_dir=td, hook_text="ДИСЦИПЛИНА")
            self.assertEqual(len(p["slides"]), 3)
            for s in p["slides"]:
                self.assertTrue(os.path.isfile(os.path.join(td, s)))
            slide_cards = [c for c in p["cards"] if c.get("file") in p["slides"]]
            self.assertEqual(len(slide_cards), 3)
            # outro cards tile [outro_start, duration] exactly
            sl = sum(c["duration"] for c in slide_cards)
            self.assertAlmostEqual(slide_cards[0]["out_start"], p["duration"] - sl, places=1)
            self.assertAlmostEqual(slide_cards[-1]["out_start"]
                                   + slide_cards[-1]["duration"], p["duration"], places=1)

    def test_bounds_helpers(self):
        self.assertEqual(D._merge_close([0, 0.4, 1.5, 3.0], min_gap=0.9), [0, 1.5, 3.0])
        split = D._split_long_slots([0, 10.0], max_slot=4.0)
        self.assertEqual(len(split), 4)
        self.assertTrue(all(b - a <= 4.0 for a, b in zip(split, split[1:])))
        self.assertEqual(D._snap_to_onset(5.1, [4.8, 5.3], tol=0.6), 5.3)


if __name__ == "__main__":
    unittest.main()
