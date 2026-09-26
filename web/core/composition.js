/* Kick Clip Studio — web/core/composition.js
 * PLAN §8: Composition JSON model + the ONE time function.
 *   §8.2 evalAnim — value | keyframes | spring, eases: linear/hold/snap/bezier
 *   §8.3 mapTime — timeline -> local -> source (with speed-ramp integration)
 * Pure JS, Node-testable. Deterministic: no Math.random, no wall clock. */
(function (root, factory) {
    const mod = factory();
    if (typeof module !== "undefined" && module.exports) module.exports = mod;
    root.CoreComposition = mod;
})(typeof self !== "undefined" ? self : this, function () {
    "use strict";
    const TM = (typeof CoreTimeMap !== "undefined") ? CoreTimeMap : require("./timeMap.js");

    // ── §8.3 one time function ───────────────────────────────────────────
    /** Integral of a piecewise-linear speed curve {k:[[t,v],...]} up to `local`. */
    function integrateSpeed(speed, local) {
        const k = speed && speed.k;
        if (!k || !k.length) return local;
        const pts = k;
        let acc = 0;
        for (let i = 0; i < pts.length - 1; i++) {
            const t0 = pts[i][0], v0 = pts[i][1];
            const t1 = pts[i + 1][0], v1 = pts[i + 1][1];
            if (local <= t0) break;
            const b = Math.min(local, t1);
            const mid = v0 + (v1 - v0) * ((b - t0) / Math.max(1e-9, t1 - t0));
            acc += (v0 + mid) / 2 * (b - t0);
            if (local <= t1) return acc;
        }
        const last = pts[pts.length - 1];
        if (local > last[0]) acc += last[1] * (local - last[0]);
        return acc;
    }

    /** timeline time -> {local, src} for a layer (§8.3). */
    function mapTime(layer, t) {
        const time = layer.time || { in: 0, srcIn: 0 };
        const local = t - (time.in || 0);
        const src = (time.srcIn || 0) + (time.speed ? integrateSpeed(time.speed, local) : local);
        return { local: local, src: src };
    }

    // ── §8.2 easing ──────────────────────────────────────────────────────
    /** Chromium UnitBezier (Newton 4-6 iters + bisection) for css-style curves. */
    function UnitBezier(p1x, p1y, p2x, p2y) {
        const cx = 3 * p1x, bx = 3 * (p2x - p1x) - cx, ax = 1 - cx - bx;
        const cy = 3 * p1y, by = 3 * (p2y - p1y) - cy, ay = 1 - cy - by;
        function sampleX(t) { return ((ax * t + bx) * t + cx) * t; }
        function sampleY(t) { return ((ay * t + by) * t + cy) * t; }
        function sampleDX(t) { return (3 * ax * t + 2 * bx) * t + cx; }
        return function (x) {
            if (x <= 0) return 0;
            if (x >= 1) return 1;
            let t = x;
            for (let i = 0; i < 6; i++) {           // Newton
                const r = sampleX(t) - x;
                if (Math.abs(r) < 1e-6) return sampleY(t);
                const d = sampleDX(t);
                if (Math.abs(d) < 1e-6) break;
                t -= r / d;
            }
            let lo = 0, hi = 1;                      // bisection fallback
            t = x;
            while (lo < hi) {
                const r = sampleX(t);
                if (Math.abs(r - x) < 1e-6) return sampleY(t);
                if (x > r) lo = t + 1e-6; else hi = t - 1e-6;
                t = (lo + hi) / 2;
                if (hi - lo < 1e-6) break;
            }
            return sampleY(t);
        };
    }

    const EASE_SNAP = UnitBezier(0.16, 1, 0.3, 1);
    const EASE_EASE = UnitBezier(0.33, 0, 0.67, 1);

    function applyEase(ease, u) {
        if (!ease || ease === "linear") return u;
        if (ease === "hold") return 0;
        if (ease === "snap") return EASE_SNAP(u);
        if (ease === "ease") return EASE_EASE(u);
        if (Array.isArray(ease) && ease[0] === "bezier") {
            return UnitBezier(ease[1], ease[2], ease[3], ease[4])(u);
        }
        if (Array.isArray(ease) && ease[0] === "spring") {
            const p = TM.springParams(ease[1] || 0.18, (ease[2] || 300) / 1000);
            return TM.spring(u, p);
        }
        return u;
    }

    /** §8.2 evalAnim: T | {k:[[t,v,ease?]...]} | {spring:{O,Ts}, from, to, at}. */
    function evalAnim(a, tLocal) {
        if (a == null) return a;
        if (typeof a === "number" || typeof a === "string" || typeof a === "boolean") return a;
        if (a.spring) {
            const at = a.at || 0;
            if (tLocal <= at - 1e-9) return a.from;
            const p = TM.springParams(a.spring.O != null ? a.spring.O : 0.18,
                                      (a.spring.Ts != null ? a.spring.Ts : 0.22));
            const raw = TM.spring(tLocal - at, p);   // 0..1 (+overshoot)
            return a.from + (a.to - a.from) * raw;
        }
        if (a.k && a.k.length) {
            const k = a.k;
            if (tLocal <= k[0][0]) return k[0][1];
            for (let i = 0; i < k.length - 1; i++) {
                const t0 = k[i][0], v0 = k[i][1];
                const t1 = k[i + 1][0], v1 = k[i + 1][1];
                if (tLocal >= t0 && tLocal <= t1) {
                    const u = (tLocal - t0) / Math.max(1e-9, t1 - t0);
                    return v0 + (v1 - v0) * applyEase(k[i][2], u);
                }
            }
            return k[k.length - 1][1];
        }
        return a;
    }

    // ── §10.5 follow-cam (virtual camera on a track) ─────────────────────
    /**
     * Deterministic follow-cam crop center over track keys.
     * keys: [{t, x, y, w, h}] (source-normalized, sorted); returns a function
     * center(srcT) -> {x, y} integrated with deadZone + maxSpeed + spring Ts.
     */
    function followCam(keys, opts) {
        const o = opts || {};
        const deadZone = o.deadZone != null ? o.deadZone : 0.04;
        const maxSpeed = o.maxSpeed != null ? o.maxSpeed : 0.6;   // units/sec
        const Ts = o.Ts != null ? o.Ts : 0.35;
        if (!keys || !keys.length) return function () { return { x: 0.5, y: 0.5 }; };
        const t0 = keys[0].t, t1 = keys[keys.length - 1].t;
        const step = 1 / Math.max(24, o.sampleFps || 60);
        // pre-integrate on a fixed grid (deterministic)
        const grid = [];
        let cx = keys[0].x, cy = keys[0].y, vx = 0, vy = 0;
        let cmdPX = keys[0].x, cmdPY = keys[0].y;      // integrated commanded position
        const w0 = 4 / Ts;
        function targetAt(t) {
            let a = keys[0], b = keys[keys.length - 1];
            for (let i = 0; i < keys.length - 1; i++) {
                if (t >= keys[i].t && t <= keys[i + 1].t) { a = keys[i]; b = keys[i + 1]; break; }
            }
            const f = (t - a.t) / Math.max(1e-9, b.t - a.t);
            return { x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f };
        }
        for (let t = t0; t <= t1 + 1e-9; t += step) {
            const tgt = targetAt(t);
            const dx = tgt.x - cmdPX, dy = tgt.y - cmdPY;
            const dzx = Math.abs(dx) <= deadZone ? 0 : dx - Math.sign(dx) * deadZone;
            const dzy = Math.abs(dy) <= deadZone ? 0 : dy - Math.sign(dy) * deadZone;
            // §10.5: position command limited by maxSpeed, then critically
            // damped spring pulls the actual crop toward the command
            cmdPX += Math.max(-maxSpeed * step, Math.min(maxSpeed * step, dzx));
            cmdPY += Math.max(-maxSpeed * step, Math.min(maxSpeed * step, dzy));
            vx += ((cmdPX - cx) * w0 * w0 - 2 * w0 * vx) * step;
            vy += ((cmdPY - cy) * w0 * w0 - 2 * w0 * vy) * step;
            cx += vx * step;
            cy += vy * step;
            grid.push({ t: t, x: cx, y: cy });
        }
        return function (srcT) {
            if (srcT <= grid[0].t) return { x: grid[0].x, y: grid[0].y };
            if (srcT >= grid[grid.length - 1].t) return { x: grid[grid.length - 1].x, y: grid[grid.length - 1].y };
            let lo = 0, hi = grid.length - 1;
            while (hi - lo > 1) { const m = (lo + hi) >> 1; if (grid[m].t <= srcT) lo = m; else hi = m; }
            const a = grid[lo], b = grid[hi];
            const f = (srcT - a.t) / Math.max(1e-9, b.t - a.t);
            return { x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f };
        };
    }

    /** Validate the minimal §8.1 shape. */
    function validate(comp) {
        if (!comp || comp.version !== 3) throw new Error("composition.version must be 3");
        if (!comp.canvas || !comp.canvas.w || !comp.canvas.h || !comp.canvas.fps) {
            throw new Error("composition.canvas {w,h,fps} required");
        }
        if (!Array.isArray(comp.layers)) throw new Error("composition.layers must be an array");
        return true;
    }

    return {
        integrateSpeed: integrateSpeed,
        mapTime: mapTime,
        UnitBezier: UnitBezier,
        applyEase: applyEase,
        evalAnim: evalAnim,
        followCam: followCam,
        validate: validate
    };
});
