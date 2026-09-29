"""Discipline-edit planner tests (no ffmpeg, pure math)."""
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


class DisciplinePlanTest(unittest.TestCase):
    def test_span_covers_target(self):
        p = D.plan_discipline(materials=_mats(), music_file="m.m4a",
                              target_dur=21.0, n_pics=4, hook_text="X",
                              pic_loops=["p1.mp4", "p2.mp4"],
                              analysis=_analysis())
        self.assertAlmostEqual(p["duration"], 21.0)
        # clips tile [0, drop] without gaps
        t = 0.0
        for c in p["clips"]:
            self.assertAlmostEqual(c["out_start"], t, places=1)
            t += c["duration"]
        self.assertAlmostEqual(t, p["drop"], places=1)
        # cards tile [drop, duration]
        t = p["drop"]
        for c in p["cards"]:
            self.assertAlmostEqual(c["out_start"], t, places=1)
            t += c["duration"]
        self.assertAlmostEqual(t, p["duration"], places=1)

    def test_src_windows_inside_files(self):
        p = D.plan_discipline(materials=_mats(), music_file="m.m4a",
                              target_dur=21.0, n_pics=2,
                              pic_loops=["p1.mp4"], analysis=_analysis())
        by_name = {m["filename"]: m["duration"] for m in _mats()}
        for c in list(p["clips"]) + [x for x in p["cards"] if x["kind"] == "video"]:
            dur = by_name[c["filename"]]
            self.assertGreaterEqual(c["src_in"], 0.0)
            self.assertLessEqual(c["src_in"] + c["duration"], dur + 0.05)

    def test_fx_cover_every_second(self):
        p = D.plan_discipline(materials=_mats(), music_file="m.m4a",
                              target_dur=21.0, n_pics=4,
                              pic_loops=["p1.mp4", "p2.mp4"],
                              analysis=_analysis())
        pushes = sorted((f["start"], f["end"]) for f in p["fx"] if f["kind"] == "push")
        self.assertTrue(pushes)
        self.assertAlmostEqual(pushes[0][0], 0.0, places=2)
        self.assertAlmostEqual(pushes[-1][1], p["duration"], places=1)
        for (s0, e0), (s1, e1) in zip(pushes, pushes[1:]):
            self.assertLessEqual(s1, e0 + 0.05)  # no uncovered gaps
        kinds = {f["kind"] for f in p["fx"]}
        self.assertIn("zoom", kinds)   # pre-drop punch
        self.assertIn("shake", kinds)  # first card hit

    def test_no_pics_still_tiles(self):
        p = D.plan_discipline(materials=_mats(), music_file="m.m4a",
                              target_dur=15.0, n_pics=0, pic_loops=[],
                              analysis=_analysis())
        total = sum(c["duration"] for c in p["clips"]) + \
            sum(c["duration"] for c in p["cards"])
        self.assertAlmostEqual(total, p["duration"], places=1)

    def test_fit_cuts_fallback_grid(self):
        cuts = D._fit_cuts([], 10.0, 20.0, 3)
        self.assertEqual(len(cuts), 3)
        self.assertTrue(all(10.0 < c < 20.0 for c in cuts))

    def test_end_card(self):
        p = D.plan_discipline(materials=_mats(), music_file="m.m4a",
                              target_dur=21.0, hook_text="ДИСЦИПЛИНА",
                              analysis=_analysis())
        self.assertEqual(len(p["text"]), 1)
        self.assertEqual(p["text"][0]["text"], "ДИСЦИПЛИНА")
        self.assertLess(p["text"][0]["end"], p["duration"])


if __name__ == "__main__":
    unittest.main()
