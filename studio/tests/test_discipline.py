"""Discipline-edit planner tests (no ffmpeg; pure math + grid logic)."""
import unittest

from studio import discipline as D


def _mats():
    return [
        {"filename": "a.mp4", "duration": 15.0},
        {"filename": "b.mp4", "duration": 56.0},
        {"filename": "c.mp4", "duration": 15.0},
    ]


def _analysis():
    per = 0.5
    beats = [round(k * per, 2) for k in range(int(163.0 / per) + 1)]
    return {"duration": 163.0, "drop": 9.0, "beat_period": per,
            "beat_phase": 0.0, "beats": beats,
            "accents": [round(1.0 + k * 2.0, 2) for k in range(int(163.0 / 2.0))],
            "onsets": beats[::2]}


def _plan(**kw):
    args = dict(materials=_mats(), music_file="m.m4a", target_dur=21.0,
                n_pics=4, pic_loops=["p1.mp4", "p2.mp4"],
                analysis=_analysis())
    args.update(kw)
    return D.plan_discipline(**args)


class BeatGridTest(unittest.TestCase):
    def test_grid_from_synthetic_pulses(self):
        # pulses every 0.45s -> period 0.45 +-0.01, phase near 0
        ts = [round(k * 0.45, 2) for k in range(80)]
        ss = [5.0] * len(ts)
        per, phase, beats = D._beat_grid(ts, ss, 36.0)
        self.assertAlmostEqual(per, 0.45, delta=0.012)
        self.assertLess(min(phase, abs(phase - per)), 0.06)
        self.assertTrue(beats)
        self.assertAlmostEqual(beats[0], phase, places=2)

    def test_accent_cadence_anchored_on_drop(self):
        per, drop, dur = 0.5, 9.0, 21.0
        beats = [round(k * per, 2) for k in range(int(dur / per) + 1)]
        acc = D._accent_cadence(beats, drop, per, dur)
        self.assertIn(round(drop, 2), acc)
        gaps = [round(b - a, 2) for a, b in zip(acc, acc[1:])]
        self.assertTrue(all(abs(g - step) < 0.01 for g, step in
                            zip(gaps, gaps[:1])), gaps)
        self.assertGreaterEqual(acc[0], 0.0)
        self.assertLessEqual(acc[-1], dur)


class DisciplinePlanTest(unittest.TestCase):
    def test_duration_snaps_to_beats_and_music_fits(self):
        p = _plan(target_dur=21.0)   # per=0.5 -> 42 beats = 21.0
        self.assertAlmostEqual(p["duration"], 21.0)
        self.assertAlmostEqual(p["music"]["offset"], 0.0)
        self.assertAlmostEqual(p["music"]["duration"], 21.0)

    def test_intro_tiles_and_takeover_overlap(self):
        p = _plan()
        t = 0.0
        for c in p["clips"]:
            self.assertAlmostEqual(c["out_start"], t, places=1)
            t += c["duration"]
        self.assertGreaterEqual(t, p["drop"] + D.TAKEOVER_S - 0.05)
        first = p["cards"][0]
        self.assertAlmostEqual(first["out_start"], p["drop"], places=2)
        self.assertLess(first["scale_from"], 0.3)
        self.assertAlmostEqual(first["scale_in"], D.TAKEOVER_S, places=2)

    def test_cards_tile_drop_to_end_no_outro(self):
        p = _plan()
        t = p["drop"]
        for c in p["cards"]:
            self.assertAlmostEqual(c["out_start"], t, places=1)
            t += c["duration"]
        self.assertAlmostEqual(t, p["duration"], places=1)
        # no text outro, no slides — user removed them
        self.assertEqual(p.get("text", []), [])
        self.assertNotIn("slides", p)

    def test_no_white_flash_transitions(self):
        p = _plan()
        self.assertNotIn("flash", [f["kind"] for f in p["fx"]])

    def test_cut_points_on_beat_grid(self):
        p = _plan()
        beats = set(_analysis()["beats"][:int(21.0 / 0.5) + 1])
        on_grid = [c["out_start"] for c in p["clips"]]
        for c in p["cards"][1:]:   # part B slots
            on_grid.append(c["out_start"])
        for t in on_grid:
            self.assertIn(round(t, 2), {round(b, 2) for b in beats} | {p["duration"]},
                          f"{t} off the beat grid")

    def test_accent_has_sound_and_visual(self):
        p = _plan()
        boom_times = [round(s["at"], 2) for s in p["sounds"]
                      if s["kind"] in ("boom", "hit_small")]
        visual_windows = [(f["start"], f["end"]) for f in p["fx"]
                          if f["kind"] in ("zoom", "shake")]
        covered = 0
        accents = [a for a in (1.0 + k * 2.0 for k in range(9)) if 0.5 <= a <= 20.8]
        for a in accents:
            if abs(a - p["drop"]) < 0.1:
                continue
            has_sound = any(abs(a - b) < 0.15 for b in boom_times)
            has_visual = any(s0 - 0.1 <= a <= e0 + 0.1 for s0, e0 in visual_windows)
            if has_sound and has_visual:
                covered += 1
        self.assertGreaterEqual(covered, 4)   # every accent gets SFX + a visual
        self.assertLessEqual(len([f for f in p["fx"] if f["kind"] in ("zoom", "shake")]),
                             8)   # FX budget kept low or the graph stalls

    def test_final_hit_at_end(self):
        p = _plan()
        final_zoom = [f for f in p["fx"] if f["kind"] == "zoom"
                      and f["end"] >= p["duration"] - 0.1]
        self.assertTrue(final_zoom)
        self.assertTrue(any(s["kind"] == "boom"
                            and s["at"] >= p["duration"] - 0.15
                            for s in p["sounds"]))

    def test_fx_variety_and_tracks(self):
        p = _plan()
        kinds = {f["kind"] for f in p["fx"]}
        self.assertIn("zoom", kinds)
        self.assertIn("shake", kinds)
        self.assertIn("push", kinds)
        tracks = {f.get("track") for f in p["fx"]}
        self.assertEqual(tracks, {"video", "cards"})
        modes = {f.get("mode") for f in p["fx"] if f["kind"] == "push"}
        self.assertIn("out", modes)
        for f in p["fx"]:
            if f.get("track") == "cards":
                self.assertGreaterEqual(f["start"], p["drop"] - 0.01)

    def test_src_windows_inside_files(self):
        p = _plan(n_pics=2, pic_loops=["p1.mp4"])
        by_name = {m["filename"]: m["duration"] for m in _mats()}
        for c in list(p["clips"]) + [x for x in p["cards"] if x["kind"] == "video"]:
            dur = by_name[c["filename"]]
            self.assertGreaterEqual(c["src_in"], 0.0)
            self.assertLessEqual(c["src_in"] + c["duration"], dur + 0.05)

    def test_no_pics_still_tiles(self):
        p = _plan(target_dur=15.0, n_pics=0, pic_loops=[])
        total = sum(c["duration"] for c in p["clips"]) + \
            sum(c["duration"] for c in p["cards"])
        self.assertGreaterEqual(total, p["duration"] - 0.2)

    def test_bounds_helpers(self):
        self.assertEqual(D._merge_close([0, 0.4, 1.5, 3.0], min_gap=0.9), [0, 1.5, 3.0])
        split = D._split_long_slots([0, 10.0], max_slot=4.0)
        self.assertEqual(len(split), 4)
        self.assertTrue(all(b - a <= 4.0 for a, b in zip(split, split[1:])))


if __name__ == "__main__":
    unittest.main()
