/* Kick Clip Studio — web/core/timeRemap.js
 * Freeze / speed-ramp remap shared by preview and composer; the ffmpeg
 * export renders the same curve (studio/timeremap.py). Ramp over window d
 * (duration preserving): first half 0.35x, second half b=(d-k)/(d/2),
 * k=0.35*d/2 -> back in sync at the window end. Freeze holds the start. */
(function (root, factory) {
    const mod = factory();
    if (typeof module !== "undefined" && module.exports) module.exports = mod;
    root.CoreTimeRemap = mod;
})(typeof self !== "undefined" ? self : this, function () {
    "use strict";
    const RAMP_IN_SPEED = 0.35;
    function rampBreakpoints(d) {
        d = Math.max(1e-3, d);
        const h = d / 2, k = RAMP_IN_SPEED * h;
        return { h: h, k: k, b: (d - k) / h };
    }
    function rampSrcOffset(local, d) {
        const bp = rampBreakpoints(d);
        if (local <= 0) return 0;
        if (local <= bp.h) return RAMP_IN_SPEED * local;
        if (local <= d) return bp.k + bp.b * (local - bp.h);
        return local;
    }
    function remapTime(t, fxList) {
        for (const f of fxList || []) {
            if (f.kind !== "freeze" && f.kind !== "ramp") continue;
            const s0 = f.in != null ? f.in : f.start, e0 = f.out != null ? f.out : f.end;
            if (s0 == null || e0 == null || !(t >= s0 && t <= e0)) continue;
            return f.kind === "freeze" ? s0 : s0 + rampSrcOffset(t - s0, e0 - s0);
        }
        return t;
    }
    return { RAMP_IN_SPEED: RAMP_IN_SPEED, rampBreakpoints: rampBreakpoints,
             rampSrcOffset: rampSrcOffset, remapTime: remapTime };
});
