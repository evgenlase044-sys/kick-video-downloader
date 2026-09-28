"""Three one-click templates instead of a hundred knobs (audit §5/§7 step 3).

Template = layout + text style + per-region grade + fps/encoder + an EFFECT
POLICY: one effect per beat, cooldowns, intensity tiers
    speech  (<0.45)  -> nothing or a 105% push
    build   (<0.75)  -> smooth push 105-115%
    peak    (>=0.75) -> punch 115-130% (+1 SFX), optionally ramp/freeze
Zoom anchors on the tracked face when a track box is available.
"""
from __future__ import annotations

from typing import Dict, List, Optional

TEMPLATES: Dict[str, dict] = {
    "hype": {
        "id": "hype", "title": "Хайп",
        "fps": 60, "length": {"default": 25, "min": 10, "max": 35},
        "layout": {"format": "split_adhd", "facecam_ratio": 0.38, "facecam_ratio_peak": 0.5},
        "text": {"style": "viral_italic", "max_lines": 2, "words_per_screen": [2, 4], "karaoke": True,
                 "hot_words": True},
        "grade": {"gameplay": {"preset": "viral_punch", "strength": 0.55},
                  "facecam": {"preset": "clean_natural", "strength": 0.35, "skin_protect": True}},
        "audio": {"loudness_lufs": -14, "true_peak": -1.0},
        "policy": {"allowed": ["zoom", "shake", "flash", "whip", "ramp", "freeze"], "cooldown_s": 1.6,
                   "max_per_10s": 4, "sfx_on_peak": True, "peak_extras": ["ramp", "freeze"]},
    },
    "story": {
        "id": "story", "title": "История",
        "fps": 30, "length": {"default": 40, "min": 20, "max": 60},
        "layout": {"format": "split_adhd", "facecam_ratio": 0.42, "facecam_ratio_peak": 0.5},
        "text": {"style": "story_clean", "max_lines": 2, "words_per_screen": [3, 5], "karaoke": True,
                 "hot_words": True},
        "grade": {"gameplay": {"preset": "clean_natural", "strength": 0.4},
                  "facecam": {"preset": "clean_natural", "strength": 0.3, "skin_protect": True}},
        "audio": {"loudness_lufs": -14, "true_peak": -1.0},
        "policy": {"allowed": ["zoom"], "cooldown_s": 4.0, "max_per_10s": 1, "sfx_on_peak": False,
                   "peak_extras": []},
    },
    "clean": {
        "id": "clean", "title": "Чистый",
        "fps": 30, "length": {"default": 25, "min": 10, "max": 45},
        "layout": {"format": "split_adhd", "facecam_ratio": 0.35, "facecam_ratio_peak": 0.35},
        "text": {"style": "viral_italic", "max_lines": 2, "words_per_screen": [2, 5], "karaoke": True,
                 "hot_words": False},
        "grade": {"gameplay": {"preset": "clean_natural", "strength": 0.3},
                  "facecam": {"preset": "clean_natural", "strength": 0.25, "skin_protect": True}},
        "audio": {"loudness_lufs": -14, "true_peak": -1.0},
        "policy": {"allowed": [], "cooldown_s": 999, "max_per_10s": 0, "sfx_on_peak": False, "peak_extras": []},
    },
}


def list_templates() -> List[dict]:
    return [dict(t) for t in TEMPLATES.values()]


def get_template(tid: str) -> dict:
    if tid not in TEMPLATES:
        raise KeyError(f"unknown template {tid!r}; known: {', '.join(TEMPLATES)}")
    return TEMPLATES[tid]


def tier(intensity: float) -> str:
    if intensity >= 0.75:
        return "peak"
    if intensity >= 0.45:
        return "build"
    return "speech"


def plan_effects(template_id: str, beats: List[dict], face: Optional[dict] = None) -> List[dict]:
    """beats: [{t, intensity 0..1, kind?}] -> fx list honouring the policy.
    One effect per beat, cooldown, max density; returns sorted fx dicts
    {kind, start, end, amp, anchor?, sfx?} in the editor's fx format."""
    tpl = get_template(template_id)
    pol = tpl["policy"]
    allowed = set(pol["allowed"])
    out: List[dict] = []
    last_t = -1e9
    for b in sorted(beats or [], key=lambda x: float(x.get("t", 0))):
        t = float(b.get("t", 0))
        inten = max(0.0, min(1.0, float(b.get("intensity", 0.5))))
        tr = tier(inten)
        if tr == "speech" and inten < 0.3:
            continue
        if t - last_t < pol["cooldown_s"]:
            continue
        if sum(1 for f in out if t - 10.0 < f["start"] <= t) >= pol["max_per_10s"]:
            continue
        kind = b.get("kind")
        if kind and kind not in allowed:
            kind = None
        if not kind:
            if "zoom" not in allowed:
                continue
            kind = "zoom"
        fx = {"kind": kind, "start": round(t, 3)}
        if kind == "zoom":
            amp = {"speech": 0.05, "build": 0.05 + 0.10 * (inten - 0.45) / 0.30, "peak": 0.15 + 0.15 * (inten - 0.75) / 0.25}[tr]
            fx.update(amp=round(min(0.30, max(0.05, amp)), 3), end=round(t + (0.6 if tr != "peak" else 0.45), 3))
            if face:
                fx["anchor"] = {"x": float(face.get("x", 0.5)), "y": float(face.get("y", 0.4))}
        elif kind == "shake":
            fx.update(amp=10 if tr != "peak" else 16, freq=8, end=round(t + 0.35, 3))
        elif kind == "flash":
            fx.update(color="white", peak=0.6 if tr != "peak" else 0.85, end=round(t + 0.18, 3))
        elif kind == "whip":
            fx.update(end=round(t + 0.25, 3))
        elif kind == "ramp":
            fx.update(end=round(t + 0.1, 3))            # 2-6 frames of slow-mo feel
        elif kind == "freeze":
            fx.update(end=round(t + 0.6, 3))
        if tr == "peak" and pol.get("sfx_on_peak"):
            fx["sfx"] = "hit_small" if kind == "zoom" else "whoosh"
        out.append(fx)
        last_t = t
        if tr == "peak" and pol.get("peak_extras") and inten >= 0.92:
            extra = pol["peak_extras"][0]
            if extra in allowed:
                out.append({"kind": extra, "start": round(t + 0.05, 3),
                            "end": round(t + (0.15 if extra == "ramp" else 0.6), 3)})
    return out
