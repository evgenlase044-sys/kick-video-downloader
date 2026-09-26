/* Kick Clip Studio — web/core/render/effects.js
 * PLAN §12.4/§12.8/§15: render-effect math shared by preview and export.
 * Everything is a pure, deterministic function of time/inputs (no wall clock).
 *   - §12.8 hash/noise (pcg + value noise), identical formula to the GLSL side
 *   - SDF stroke: jump-flood distance field + smoothstep edge (§12.4)
 *   - glow: dual-Kawase blur passes + glowAlpha = opacity^1.5 · amount (§12.4)
 *   - §15/§12.6 effect states: zoom punch (scale + radial force), shake
 *     (noise + envelope + overscan), flash, threshold hit, RGB split, whip
 * Node-compatible (UMD) — golden-numeric gates run without a browser. */
(function (root, factory) {
    const mod = factory();
    if (typeof module !== "undefined" && module.exports) module.exports = mod;
    root.CoreEffects = mod;
})(typeof self !== "undefined" ? self : this, function () {
    "use strict";
    const TM = (typeof CoreTimeMap !== "undefined") ? CoreTimeMap : require("../timeMap.js");

    // ── §12.8 deterministic noise ────────────────────────────────────────
    function pcg(n) {
        n = (n * 747796405 + 2891336453) >>> 0;
        let w = ((n >>> ((n >>> 28) + 4)) ^ n) * 277803737 >>> 0;
        return ((w >>> 22) ^ w) >>> 0;
    }
    function rand(seed, i) {
        return pcg(seed ^ Math.imul(i, 0x9E3779B1)) / 4294967296;
    }
    function noise1(seed, x) {
        const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f);
        return (rand(seed, i) * (1 - u) + rand(seed, i + 1) * u) * 2 - 1;
    }

    // ── §12.4 SDF stroke: jump flood ─────────────────────────────────────
    /**
     * Jump-flood distance field over a binary mask (Uint8, 0/255).
     * Returns Float32Array of Euclidean distances (px) to the nearest set
     * pixel; unset pixels keep +1e6 sentinel until reached.
     */
    function jumpFlood(mask, W, H) {
        const INF = 1e6;
        let gx = new Int32Array(W * H).fill(-1);
        let gy = new Int32Array(W * H).fill(-1);
        let gd = new Float32Array(W * H).fill(INF);
        for (let y = 0; y < H; y++) {
            for (let x = 0; x < W; x++) {
                if (mask[y * W + x]) {
                    const i = y * W + x;
                    gx[i] = x; gy[i] = y; gd[i] = 0;
                }
            }
        }
        let steps = 1;
        while (steps < Math.max(W, H)) steps <<= 1;
        let sx = gx, sy = gy, sd = gd;
        for (; steps >= 1; steps >>= 1) {
            const nx = new Int32Array(W * H);
            const ny = new Int32Array(W * H);
            const nd = new Float32Array(W * H);
            for (let y = 0; y < H; y++) {
                for (let x = 0; x < W; x++) {
                    const i = y * W + x;
                    let bx = sx[i], by = sy[i], bd = sd[i];
                    for (let oy = -1; oy <= 1; oy++) {
                        for (let ox = -1; ox <= 1; ox++) {
                            if (!ox && !oy) continue;
                            const px = x + ox * steps, py = y + oy * steps;
                            if (px < 0 || py < 0 || px >= W || py >= H) continue;
                            const pi = py * W + px;
                            if (sx[pi] < 0) continue;
                            const d = Math.hypot(sx[pi] - x, sy[pi] - y);
                            if (d < bd) { bd = d; bx = sx[pi]; by = sy[pi]; }
                        }
                    }
                    nx[i] = bx; ny[i] = by; nd[i] = bd;
                }
            }
            sx = nx; sy = ny; sd = nd;
        }
        return sd;
    }

    /** Stroke coverage from a distance field: smoothstep(r+0.5, r-0.5, d). */
    function strokeAlpha(dist, r) {
        const t = Math.max(0, Math.min(1, (r + 0.5 - dist) / 1.0));
        return t * t * (3 - 2 * t);
    }

    // ── §12.4 dual-Kawase glow ───────────────────────────────────────────
    function _kawaseDown(src, W, H) {
        const w2 = W >> 1, h2 = H >> 1;
        const out = new Float32Array(w2 * h2);
        for (let y = 0; y < h2; y++) {
            for (let x = 0; x < w2; x++) {
                const sx = Math.min(W - 1, x * 2), sy = Math.min(H - 1, y * 2);
                const x1 = Math.min(W - 1, sx + 1), y1 = Math.min(H - 1, sy + 1);
                out[y * w2 + x] = (src[sy * W + sx] + src[sy * W + x1] +
                                   src[y1 * W + sx] + src[y1 * W + x1]) * 0.25;
            }
        }
        return { data: out, W: w2, H: h2 };
    }
    function _kawaseUp(src, W, H, dstW, dstH) {
        const out = new Float32Array(dstW * dstH);
        for (let y = 0; y < dstH; y++) {
            const fy = Math.min(H - 1, Math.max(0, (y - 0.5) * 0.5));
            const y0 = Math.floor(fy), wy = fy - y0;
            const y1 = Math.min(H - 1, y0 + 1);
            for (let x = 0; x < dstW; x++) {
                const fx = Math.min(W - 1, Math.max(0, (x - 0.5) * 0.5));
                const x0 = Math.floor(fx), wx = fx - x0;
                const x1 = Math.min(W - 1, x0 + 1);
                const a = src[y0 * W + x0] * (1 - wx) + src[y0 * W + x1] * wx;
                const b = src[y1 * W + x0] * (1 - wx) + src[y1 * W + x1] * wx;
                out[y * dstW + x] = a * (1 - wy) + b * wy;
            }
        }
        return { data: out, W: dstW, H: dstH };
    }
    /** Dual-Kawase blur: `passes` downsample+upsample rounds. */
    function kawaseBlur(src, W, H, passes) {
        let cur = { data: Float32Array.from(src), W: W, H: H };
        const chain = [cur];
        for (let i = 0; i < passes; i++) {
            if (cur.W < 2 || cur.H < 2) break;
            cur = _kawaseDown(cur.data, cur.W, cur.H);
            chain.push(cur);
        }
        for (let i = chain.length - 2; i >= 0; i--) {
            const up = _kawaseUp(cur.data, cur.W, cur.H, chain[i].W, chain[i].H);
            cur = { data: up.data, W: chain[i].W, H: chain[i].H };
        }
        return cur.data;
    }

    /** §12.4: glow physically cannot appear before the glyph. */
    function glowAlpha(opacity, amount, boost) {
        return Math.pow(Math.max(0, opacity), 1.5) * amount * (boost != null ? boost : 1);
    }

    // ── §15 / §12.6 effect states (pure functions of time) ───────────────
    /** Zoom punch: scale = 1 + A·spring(τ); radial blur force = |ds/dt|·shutter. */
    function zoomPunch(t, opts) {
        const o = opts || {};
        const A = o.A != null ? o.A : 0.15;
        const at = o.at || 0;
        const p = TM.springParams(o.overshoot != null ? o.overshoot : 0.12,
                                  (o.settleMs || 220) / 1000);
        const e = 1e-3;
        const s0 = 1 + A * TM.spring(t - at, p);
        const s1 = 1 + A * TM.spring(t + e - at, p);
        const v = (s1 - s0) / e;                                  // ds/dt
        return {
            scale: s0,
            radialForce: Math.abs(v) * (o.shutter != null ? o.shutter : 0.5),
            samples: o.samples || 12
        };
    }

    /** Camera shake §15: noise-driven offset/rot with attack/exp-decay envelope
     *  and CONSTANT overscan 1 + 2·amp/W (N11). */
    function shake(t, opts) {
        const o = opts || {};
        const amp = o.amp != null ? o.amp : 14;
        const f = o.freq != null ? o.freq : 9;
        const tau = (o.tauMs != null ? o.tauMs : 120) / 1000;
        const at = o.at || 0;
        const seed = o.seed != null ? o.seed : 7;
        const dur = o.dur != null ? o.dur : 0.35;
        const local = t - at;
        const env = (local < 0 || local > dur) ? 0
            : (local < 1 / 60 ? local / (1 / 60) : Math.exp(-local / tau));
        const dx = amp * env * (0.7 * noise1(seed, t * f) + 0.3 * noise1(seed + 1, 2.3 * f * t));
        const dy = amp * env * (0.7 * noise1(seed + 2, t * f * 1.13) + 0.3 * noise1(seed + 3, 1.7 * f * t));
        const rot = 0.4 * env * noise1(seed + 4, t * f);
        return { dx: dx, dy: dy, rot: rot, env: env, overscan: 1 + 2 * amp / (o.W || 1080) };
    }

    /** Threshold hit §15: luma gate with deterministic noise dither. */
    function thresholdHit(luma, t, opts) {
        const o = opts || {};
        const th = o.threshold != null ? o.threshold : 0.45;
        const n = rand(o.seed != null ? o.seed : 3, Math.floor(t * 60)) * 0.08;
        return (luma > th + n) ? 1 : 0;
    }

    /** RGB split §15: radial k (×1.6–2 on hits). */
    function rgbSplit(t, hitBoost) {
        const k = 0.004 * (hitBoost ? 1.8 : 1.0);
        return k;
    }

    /** Whip §15: easeInOutCubic displacement over 6–8 frames. */
    function whip(t, opts) {
        const o = opts || {};
        const dur = (o.durMs || 120) / 1000;
        const p = Math.max(0, Math.min(1, (t - (o.at || 0)) / dur));
        const e = p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;
        return { p: p, dx: (o.dir || 1) * 0.35 * e, blurSamples: 16 };
    }

    return {
        pcg: pcg, rand: rand, noise1: noise1,
        jumpFlood: jumpFlood, strokeAlpha: strokeAlpha,
        kawaseBlur: kawaseBlur, glowAlpha: glowAlpha,
        zoomPunch: zoomPunch, shake: shake, thresholdHit: thresholdHit,
        rgbSplit: rgbSplit, whip: whip
    };
});
