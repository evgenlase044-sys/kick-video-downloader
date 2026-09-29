"""Platform reuse / music / farm policies (§6 P2).
No enforcement here — just warnings that the UI surfaces before export."""
from __future__ import annotations

from typing import Any, Dict

RULES: Dict[str, Dict[str, Any]] = {
    "youtube": {
        "min_duration": 22.0,
        "max_duration": 60.0,
        "warn_reused": "Reused content: original commentary/edit required or demonetization risk.",
        "warn_music": "Commercial music without license may trigger Content ID.",
    },
    "tiktok": {
        "min_duration": 5.0,
        "max_duration": 180.0,
        "warn_reused": "Reused content without added value may be suppressed.",
        "warn_music": "Use Sounds library; unlicensed tracks may be muted.",
    },
    "kick": {
        "min_duration": 5.0,
        "max_duration": 300.0,
        "warn_reused": "",
        "warn_music": "",
    },
}


def check(platform: str, duration: float | None = None, has_music: bool = False, reused: bool = False) -> Dict[str, Any]:
    r = RULES.get((platform or "youtube").lower(), RULES["youtube"])
    warns: list[str] = []
    if duration is not None:
        if duration < r["min_duration"]:
            warns.append(f"Too short for {platform} (<{r['min_duration']}s).")
        if duration > r["max_duration"]:
            warns.append(f"Too long for {platform} (>{r['max_duration']}s).")
    if reused and r["warn_reused"]:
        warns.append(r["warn_reused"])
    if has_music and r["warn_music"]:
        warns.append(r["warn_music"])
    return {"platform": platform, "ok": not warns, "warnings": warns, "rules": r}
