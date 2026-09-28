"""Speed-ramp / freeze curve shared by export and preview (web/core/timeRemap.js).

Ramp over an output window d (duration preserving): first half at 0.35x,
second half at b = (d - k)/(d/2), k = 0.35*d/2 -> back in sync at the end.
"""
from __future__ import annotations

RAMP_IN_SPEED = 0.35


def ramp_breakpoints(d: float):
    d = max(1e-3, float(d))
    h = d / 2.0
    k = RAMP_IN_SPEED * h
    return h, k, (d - k) / h


def ramp_src_offset(local: float, d: float) -> float:
    h, k, b = ramp_breakpoints(d)
    if local <= 0:
        return 0.0
    if local <= h:
        return RAMP_IN_SPEED * local
    if local <= d:
        return k + b * (local - h)
    return local
