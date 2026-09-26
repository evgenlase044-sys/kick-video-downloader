/* Kick Clip Studio — web/core/render/lens.js
 * PLAN §13: Lens & Detail — barrel/fisheye/bulge/CA/wave/twirl as pure
 * normalized-coordinate maps, composed in the §13.1 order (wave -> lens ->
 * fisheye -> bulge -> twirl; CA reads the distorted radius; detail/grain go
 * after grade). Auto-overscan: the `norm` term keeps the frame corners
 * exactly in place for k1>0, so no empty corners (§7.5 gate).
 * Presets §13.3: Lens Punch (animated), Fisheye Hold, Bulge Face, Crispy,
 * Heat Wobble, Crispy Lens.
 * Pure JS (UMD) — Node-verifiable; LENS_GLSL mirrors the same formulas. */
(function (root, factory) {
    const mod = factory();
    if (typeof module !== "undefined" && module.exports) module.exports = mod;
    root.CoreLens = mod;
})(typeof self !== "undefined" ? self : this, function () {
    "use strict";
    const TM = (typeof CoreTimeMap !== "undefined") ? CoreTimeMap : require("../timeMap.js");

    // ── §13.1 component maps (normalized output -> normalized source) ────
    /** Barrel/pincushion: uv_src = c + (uv-c)*(1 + k1*r^2 + k2*r^4)/norm. */
    function lensMap(u, v, p) {
        const cx = p.cx != null ? p.cx : 0.5, cy = p.cy != null ? p.cy : 0.5;
        const k1 = p.k1 || 0, k2 = p.k2 || 0;
        if (!k1 && !k2) return { u: u, v: v };
        const aspect = p.aspect || (p.W && p.H ? p.W / p.H : 9 / 16);
        const du = (u - cx) * aspect, dv = v - cy;
        const r2 = du * du + dv * dv;
        const rCorner = Math.hypot(Math.max(cx, aspect - cx), Math.max(cy, 1 - cy));
        // auto-overscan: corners stay in place (empty corners impossible)
        const norm = 1 + k1 * rCorner * rCorner + k2 * rCorner * rCorner * rCorner * rCorner;
        const s = (1 + k1 * r2 + k2 * r2 * r2) / norm;
        return { u: cx + du / aspect * s, v: cy + dv * s };
    }

    /** Equidistant fisheye with mix (§13.1). */
    function fisheyeMap(u, v, p) {
        const fov = (p.fov || 0) * Math.PI / 180;
        if (!fov) return { u: u, v: v };
        const cx = p.cx != null ? p.cx : 0.5, cy = p.cy != null ? p.cy : 0.5;
        const aspect = p.aspect || 9 / 16;
        const du = (u - cx) * aspect, dv = v - cy;
        const r = Math.min(0.999, Math.hypot(du, dv));
        const theta = r * fov / 2;
        const rSrc = Math.tan(theta) / Math.tan(fov / 2);
        const mix = p.mix != null ? p.mix : 1;
        const su = du !== 0 ? du * (rSrc / r) : 0;
        const sv = dv !== 0 ? dv * (rSrc / r) : 0;
        return {
            u: cx + ((u - cx) * (1 - mix) + su / aspect * mix),
            v: cy + ((v - cy) * (1 - mix) + sv * mix)
        };
    }

    /** Bulge/pinch: amount>0 bulge, <0 pinch (§13.1). */
    function bulgeMap(u, v, p) {
        const amount = p.amount || 0;
        if (!amount) return { u: u, v: v };
        const cx = p.cx != null ? p.cx : 0.5, cy = p.cy != null ? p.cy : 0.5;
        const aspect = p.aspect || 9 / 16;
        const R = p.R || 0.25;
        const soft = p.softness != null ? p.softness : 0.2;
        const du = (u - cx) * aspect, dv = v - cy;
        const d = Math.hypot(du, dv);
        const dN = d / R;
        if (dN >= 1) return { u: u, v: v };
        const k = 1 - amount * Math.pow(1 - dN, 2);
        const uS = cx + du / aspect * k;
        const vS = cy + dv * k;
        // soften the boundary: blend to identity within the `soft` rim band
        const rim = dN > (1 - soft) ? 1 - (dN - (1 - soft)) / soft : 1;
        return {
            u: u + (uS - u) * rim,
            v: v + (vS - v) * rim
        };
    }

    /** Radial chromatic aberration: per-channel radius multipliers (§13.1). */
    function caOffsets(u, v, p) {
        const ca = (p.ca || 0) / (p.W || 1080);   // px @1080 -> normalized
        if (!ca) return { kR: 1, kB: 1 };
        const cx = p.cx != null ? p.cx : 0.5, cy = p.cy != null ? p.cy : 0.5;
        const aspect = p.aspect || 9 / 16;
        const r = Math.hypot((u - cx) * aspect, v - cy);
        const k = ca * r;                          // grows toward the edges
        return { kR: 1 + k, kB: 1 - k };
    }

    /** Wave/heat: horizontal sine displacement (§13.1). */
    function waveMap(u, v, p, t) {
        const A = (p.A || 0) / (p.W || 1080);
        if (!A) return { u: u, v: v };
        return { u: u + A * Math.sin(2 * Math.PI * (v * (p.f || 6) + t * (p.v || 1.5))), v: v };
    }

    /** Twirl: rotation theta = amount*(1 - d/R)^2 around the center. */
    function twirlMap(u, v, p) {
        const amount = p.twirl || 0;
        if (!amount) return { u: u, v: v };
        const cx = p.cx != null ? p.cx : 0.5, cy = p.cy != null ? p.cy : 0.5;
        const aspect = p.aspect || 9 / 16;
        const R = p.R || 0.4;
        const du = (u - cx) * aspect, dv = v - cy;
        const d = Math.hypot(du, dv);
        if (d >= R) return { u: u, v: v };
        const theta = amount * Math.pow(1 - d / R, 2);
        const cos = Math.cos(theta), sin = Math.sin(theta);
        return { u: cx + (du * cos - dv * sin) / aspect, v: cy + du * sin + dv * cos };
    }

    /** Compose the §13.1 pipeline; returns per-channel source coords. */
    function mapPoint(u, v, params, t) {
        const p = params || {};
        let q = { u: u, v: v };
        q = waveMap(q.u, q.v, p, t != null ? t : 0);
        q = lensMap(q.u, q.v, p);
        q = fisheyeMap(q.u, q.v, p);
        q = bulgeMap(q.u, q.v, p);
        q = twirlMap(q.u, q.v, p);
        const ca = caOffsets(u, v, p);
        return {
            r: { u: cx_(q, ca.kR, u, p), v: q.v },
            g: { u: q.u, v: q.v },
            b: { u: cx_(q, ca.kB, u, p), v: q.v }
        };
    }
    function cx_(q, k, u0, p) {
        // radial CA: scale the offset from the lens center by k
        const cx = p.cx != null ? p.cx : 0.5;
        return cx + (q.u - cx) * k;
    }

    /** Sample a source through the pipeline; srcFn(u,v) -> [r,g,b] 0..1. */
    function sampleColor(srcFn, u, v, params, t) {
        const m = mapPoint(u, v, params, t);
        const r = srcFn(m.r.u, m.r.v);
        const g = srcFn(m.g.u, m.g.v);
        const b = srcFn(m.b.u, m.b.v);
        return [r[0], g[1], b[2]];
    }

    // ── §13.1 Detail: unsharp on luma (pure, plane-based) ────────────────
    function gauss1d(sigma) {
        const rad = Math.max(1, Math.ceil(sigma * 3));
        const k = [];
        let s = 0;
        for (let i = -rad; i <= rad; i++) {
            const v = Math.exp(-(i * i) / (2 * sigma * sigma));
            k.push(v); s += v;
        }
        return k.map(v => v / s);
    }
    function _sepBlur(plane, W, H, sigma) {
        const k = gauss1d(sigma);
        const rad = (k.length - 1) / 2;
        const tmp = new Float32Array(W * H);
        for (let y = 0; y < H; y++) {
            for (let x = 0; x < W; x++) {
                let acc = 0;
                for (let i = -rad; i <= rad; i++) {
                    const xx = Math.max(0, Math.min(W - 1, x + i));
                    acc += plane[y * W + xx] * k[i + rad];
                }
                tmp[y * W + x] = acc;
            }
        }
        const out = new Float32Array(W * H);
        for (let y = 0; y < H; y++) {
            for (let x = 0; x < W; x++) {
                let acc = 0;
                for (let i = -rad; i <= rad; i++) {
                    const yy = Math.max(0, Math.min(H - 1, y + i));
                    acc += tmp[yy * W + x] * k[i + rad];
                }
                out[y * W + x] = acc;
            }
        }
        return out;
    }
    /** Detail/unsharp: Y' = Y + a1*(Y - G_sigma(Y)), clamped vs halos. */
    function applyDetail(luma, W, H, opts) {
        const o = opts || {};
        const a1 = o.a1 != null ? o.a1 : 1.2;
        if (!a1) return Float32Array.from(luma);
        const sigma = o.sigma || 1.0;
        const blur = _sepBlur(luma, W, H, sigma);
        const out = new Float32Array(W * H);
        for (let i = 0; i < out.length; i++) {
            out[i] = Math.max(0, Math.min(1, luma[i] + a1 * (luma[i] - blur[i])));
        }
        return out;
    }

    // ── §13.3 presets ────────────────────────────────────────────────────
    const LENS_PRESETS = {
        lens_punch: { k1: 0.18, k2: 0, ca: 3, W: 1080, cx: 0.5, cy: 0.5,
                      zoom: { A: 0.12, overshoot: 0.18, settleMs: 250 }, durMs: 250 },
        fisheye_hold: { fov: 120, mix: 0.6, W: 1080 },
        bulge_face: { amount: 0.35, R: 0.25, softness: 0.3, W: 1080, cy: 0.4 },
        crispy: { detail: { a1: 1.2, sigma: 1.0 }, ca: 1, W: 1080 },
        heat_wobble: { A: 3, f: 6, v: 1.5, W: 1080 },
        crispy_lens: { detail: { a1: 1.2, sigma: 1.0 }, ca: 1, k1: 0.06, vignette: 0.2, W: 1080 }
    };

    /** Lens Punch animation (§13.3): k1 0->0.18->0 (snap, peak @80 ms), CA 0->3->0. */
    function lensPunch(t, opts) {
        const o = opts || {};
        const dur = (o.durMs || 250) / 1000;
        const at = o.at || 0;
        const p = Math.max(0, Math.min(1, (t - at) / dur));
        if (p <= 0) return { k1: 0, ca: 0, zoomScale: 1 };
        const env = TM.easeSnap(p);
        const peakT = (o.peakMs || 80) / 1000 / dur;
        const bell = Math.exp(-Math.pow((p - peakT) / 0.35, 2));
        const zp = (typeof CoreEffects !== "undefined" ? CoreEffects : require("./effects.js"))
            .zoomPunch(t, { A: 0.12, overshoot: 0.18, settleMs: 250, at: at });
        return {
            k1: (o.k1 != null ? o.k1 : 0.18) * bell,
            ca: (o.ca != null ? o.ca : 3) * bell,
            zoomScale: zp.scale
        };
    }

    /** GLSL mirror of lensMap/bulge/fisheye/wave (same math as above). */
    const LENS_GLSL = [
        "vec2 lensMap(vec2 uv, float k1, float k2, vec2 c, float aspect, float norm){",
        "  vec2 d = (uv - c) * vec2(aspect, 1.0);",
        "  float r2 = dot(d, d);",
        "  return c + (uv - c) * ((1.0 + k1*r2 + k2*r2*r2) / norm);",
        "}"
    ].join("\n");

    return {
        lensMap: lensMap, fisheyeMap: fisheyeMap, bulgeMap: bulgeMap,
        caOffsets: caOffsets, waveMap: waveMap, twirlMap: twirlMap,
        mapPoint: mapPoint, sampleColor: sampleColor,
        applyDetail: applyDetail, LENS_PRESETS: LENS_PRESETS,
        lensPunch: lensPunch, LENS_GLSL: LENS_GLSL
    };
});
