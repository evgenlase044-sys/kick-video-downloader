/* Kick Clip Studio — web/core/timeMap.js
 * PLAN §8.2/§8.3/§12.5/§16: pure time math shared by preview (canvas monitor)
 * and the future export renderer. Node-compatible (UMD) for verification. */
(function (root, factory) {
    const mod = factory();
    if (typeof module !== "undefined" && module.exports) module.exports = mod;
    root.CoreTimeMap = mod;
})(typeof self !== "undefined" ? self : this, function () {
    "use strict";

    /** Snap timeline time to the composition frame grid: round(t·fps)/fps (§16.5). */
    function frameSnap(t, fps) {
        if (!isFinite(t) || fps <= 0) return t;
        return Math.round(t * fps) / fps;
    }

    /** Step n frames from t on the frame grid (±1/fps preview stepping). */
    function stepFrames(t, fps, n) {
        const cur = Math.round(t * fps);
        return Math.max(0, cur + n) / fps;
    }

    /**
     * Master-clock follower (§16.3): video chases the audio master clock.
     * Returns {action:"rate", rate} for small drift, {action:"seek"} beyond
     * 150 ms, or {action:"none"} when close enough.
     */
    function clockCorrection(videoTime, masterTime, opts) {
        const o = opts || {};
        const tol = o.toleranceMs != null ? o.toleranceMs : 12;
        const seekMs = o.seekMs != null ? o.seekMs : 150;
        const fast = o.fastRate != null ? o.fastRate : 1.03;
        const slow = o.slowRate != null ? o.slowRate : 0.97;
        const errMs = (videoTime - masterTime) * 1000;
        if (Math.abs(errMs) > seekMs) return { action: "seek", errMs };
        if (errMs > tol) return { action: "rate", rate: slow, errMs };   // video ahead
        if (errMs < -tol) return { action: "rate", rate: fast, errMs };  // video behind
        return { action: "none", errMs };
    }

    /** Free-running audio master clock (§16.3): audioCtx.currentTime − outputLatency. */
    function makeAudioClock(audioCtx) {
        const t0 = audioCtx.currentTime - (audioCtx.outputLatency || 0);
        return function masterNow() {
            return audioCtx.currentTime - (audioCtx.outputLatency || 0) - t0;
        };
    }

    /** Critically damped spring parameters from overshoot O and settle Ts (§12.5). */
    function springParams(O, Ts) {
        const L = Math.log(O);
        const z = -L / Math.sqrt(Math.PI * Math.PI + L * L);
        return { z: z, w0: 4 / (z * Ts) };
    }

    /** Underdamped spring position/velocity, 0 → 1 at time t (§12.5). */
    function spring(t, params, v0) {
        const z = params.z, w0 = params.w0;
        const v = v0 || 0;
        if (t <= 0) return 0;
        const x0 = -1;
        if (z < 1) {
            const wd = w0 * Math.sqrt(1 - z * z);
            const e = Math.exp(-z * w0 * t);
            const A = x0, B = (v + z * w0 * x0) / wd;
            const c = Math.cos(wd * t), s = Math.sin(wd * t);
            return 1 + e * (A * c + B * s);
        }
        const e = Math.exp(-w0 * t), B = v + w0 * x0;
        return 1 + e * (x0 + B * t);
    }

    /** easeOutCubic for exits/zoom holds. */
    function easeOutCubic(x) { return 1 - Math.pow(1 - x, 3); }
    /** "snap" ease (§8.2): cubic-bezier(0.16,1,0.3,1) approximation. */
    function easeSnap(x) { return 1 - Math.pow(1 - x, 4); }
    function clamp01(x) { return x < 0 ? 0 : (x > 1 ? 1 : x); }

    /**
     * Word visibility gate shared with the ASS export (§7.4 gate):
     * the word becomes visible at time s; on the frame grid its first visible
     * frame is ceil(s·fps) which is within round(s·fps) ± 1.
     */
    function wordVisibleFrame(s, fps) { return Math.ceil(s * fps - 1e-6); }
    function wordAssStartFrame(s, fps) { return Math.round(s * fps); }

    return {
        frameSnap: frameSnap,
        stepFrames: stepFrames,
        clockCorrection: clockCorrection,
        makeAudioClock: makeAudioClock,
        springParams: springParams,
        spring: spring,
        easeOutCubic: easeOutCubic,
        easeSnap: easeSnap,
        clamp01: clamp01,
        wordVisibleFrame: wordVisibleFrame,
        wordAssStartFrame: wordAssStartFrame
    };
});
