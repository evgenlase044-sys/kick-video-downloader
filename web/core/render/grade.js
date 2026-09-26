/* Kick Clip Studio — web/core/render/grade.js
 * PLAN §14: primary grade as a pure JS function that mirrors the §14.2 GLSL
 * shader formula-by-formula (so JS == GPU), the §14.5 presets (Viral Punch …),
 * the §14.3 manual "Выровнять" statistics and the §14.4 spatial ops formulas.
 * Pipeline (§14.1): linearize -> WB/exposure -> log contrast -> highlight
 * knee -> CDL -> saturation/vibrance (hue-weighted, skin-protected) ->
 * split toning -> creative LUT (trilinear) -> output. */
(function (root, factory) {
    const mod = factory();
    if (typeof module !== "undefined" && module.exports) module.exports = mod;
    root.CoreGrade = mod;
})(typeof self !== "undefined" ? self : this, function () {
    "use strict";
    const LUT = (typeof CoreLut3D !== "undefined") ? CoreLut3D : require("../lut3d.js");

    // ── §14.2 primary grade (mirror of the GLSL) ─────────────────────────
    const HUE_BANDS = [           // {center, width, satGain} per §14.2 uHue[4]
        { c: 0.983, w: 0.09, g: 1.00 },   // red (default identity; presets override)
        { c: 0.833, w: 0.09, g: 1.00 },   // magenta
        { c: 0.333, w: 0.14, g: 1.00 },   // green
        { c: 0.583, w: 0.10, g: 1.00 }    // cyan
    ];

    /** Standard HSV (results match the GLSL port for all valid inputs,
     *  including the d==0 grayscale edge where the compact form explodes). */
    function rgb2hsv(c) {
        const r = c[0], g = c[1], b = c[2];
        const mx = Math.max(r, g, b), mn = Math.min(r, g, b);
        const d = mx - mn;
        let h = 0;
        if (d > 0) {
            if (mx === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
            else if (mx === g) h = ((b - r) / d + 2) / 6;
            else h = ((r - g) / d + 4) / 6;
        }
        return [h, mx === 0 ? 0 : d / mx, mx];
    }

    /** Primary grade of one display-referred RGB triple. */
    function gradeColor(c0, p, lut) {
        const PR = p || {};
        const K = [0.2126, 0.7152, 0.0722];
        const lin = c0.map(x => Math.pow(Math.max(0, x), 2.4));
        // white balance + exposure (linear), then log contrast around 0.18
        const wb = PR.wb || [1, 1, 1];
        const expo = Math.pow(2, PR.expo || 0);
        const contrast = PR.contrast != null ? PR.contrast : 1.0;
        let c = lin.map(function (x, i) {
            const v = x * wb[i] * expo;
            return 0.18 * Math.pow(Math.max(v, 1e-5) / 0.18, contrast);
        });
        // highlight soft knee §14.2
        const knee = PR.knee != null ? PR.knee : 0.8;
        c = c.map(function (x) {
            if (x <= knee) return x;
            return knee + (1 - knee) * (1 - Math.exp(-(x - knee) / (1 - knee)));
        });
        // CDL in display space
        const disp = c.map(x => Math.pow(Math.max(0, x), 1 / 2.4));
        const slope = PR.slope || [1, 1, 1], offset = PR.offset || [0, 0, 0], power = PR.power || [1, 1, 1];
        let d = disp.map((x, i) => Math.pow(Math.max(0, x * slope[i] + offset[i]), power[i]));
        // saturation / vibrance with hue-band weights + skin protection
        const hsv = rgb2hsv([Math.max(0, Math.min(1, d[0])), Math.max(0, Math.min(1, d[1])), Math.max(0, Math.min(1, d[2]))]);
        const Y = K[0] * d[0] + K[1] * d[1] + K[2] * d[2];
        const sat = PR.sat != null ? PR.sat : 1.0;
        const vib = PR.vib != null ? PR.vib : 0.0;
        let satMul = sat * (1 + vib * (1 - hsv[1]));
        const bands = PR.hueBands || HUE_BANDS;
        for (const band of bands) {
            const dh = Math.abs(Math.abs(hsv[0] - band.c + 0.5) % 1 - 0.5);
            const w = Math.max(0, Math.cos(Math.min(dh / band.w, 1) * Math.PI / 2));
            satMul *= 1 + (band.g - 1) * w;
        }
        const skinProtect = PR.skinProtect != null ? PR.skinProtect : 0;
        const skin = smooth01((0.10 - Math.abs(hsv[0] - 0.07)) / 0.08) *
                     smooth01((hsv[1] - 0.1) / 0.2) * skinProtect;
        satMul = satMul + (1 + (satMul - 1) * 0.35 - satMul) * skin;
        d = [Y + (d[0] - Y) * satMul, Y + (d[1] - Y) * satMul, Y + (d[2] - Y) * satMul];
        // split toning
        const w = smooth01((Y - 0.05) / 0.9);
        const st = PR.shadowTint || [0, 0, 0, 0];
        const ht = PR.highTint || [0, 0, 0, 0];
        d = d.map((x, i) => x + st[i] * st[3] * (1 - w) + ht[i] * ht[3] * w);
        // creative LUT (trilinear, same array as the GPU sampler3D)
        if (lut) {
            const s = d.map(x => (Math.max(0, Math.min(1, x)) * (lut.N - 1) + 0.5) / lut.N);
            d = LUT.sample(lut, s[0], s[1], s[2]);
        }
        // §7.5: hue-preserving gamut map — a hard clamp pins one channel and
        // rotates the hue of bright skin (15 -> 33 deg). Pull ALL channels
        // toward luma by the same ratio instead; 1 LSB of 10-bit headroom
        // stays free (TOP < 0.999), so nothing counts as clipped.
        const TOP = 1 - 1 / 1023, BOT = 1 / 1023;
        const Yf = K[0] * d[0] + K[1] * d[1] + K[2] * d[2];
        if (Yf > TOP || Yf < BOT) {
            d = [Math.max(BOT, Math.min(TOP, Yf)), Math.max(BOT, Math.min(TOP, Yf)),
                 Math.max(BOT, Math.min(TOP, Yf))];
        } else {
            const mx = Math.max(d[0], d[1], d[2]), mn = Math.min(d[0], d[1], d[2]);
            if (mx > TOP) {
                const k = (TOP - Yf) / Math.max(1e-6, mx - Yf);
                d = d.map(x => Yf + (x - Yf) * k);
            }
            if (mn < BOT) {
                const k = (BOT - Yf) / Math.min(-1e-6, mn - Yf);
                d = d.map(x => Yf + (x - Yf) * k);
            }
        }
        return d.map(x => Math.max(0, Math.min(1, x)));
    }
    function softClip(x) {
        if (x > 0.92) return 0.92 + 0.08 * Math.tanh((x - 0.92) / 0.08);
        if (x < 0.08) return 0.08 * Math.tanh(x / 0.08);
        return x;
    }
    function smooth01(x) {
        const t = Math.max(0, Math.min(1, x));
        return t * t * (3 - 2 * t);
    }

    // ── §14.5 presets ────────────────────────────────────────────────────
    const GRADE_PRESETS = {
        viral_punch: {
            contrast: 1.18, knee: 0.80,
            slope: [1.02, 1.00, 0.97], offset: [-0.010, -0.004, 0.012],
            sat: 1.15, vib: 0.25, skinProtect: 0.6,
            hueBands: [
                { c: 0.983, w: 0.09, g: 1.18 },   // reds +
                { c: 0.833, w: 0.09, g: 1.12 },   // magenta +
                { c: 0.333, w: 0.14, g: 0.92 },   // greens −
                { c: 0.583, w: 0.10, g: 1.00 }
            ],
            shadowTint: [0, 0.03, 0.05, 0.6], highTint: [0.05, 0.02, -0.02, 0.5],
            clarity: 0.25, bloom: 0.08, halation: 0.04,
            vignette: 0.18, rcas: 0.35, grain: 0.025
        },
        teal_orange: {
            contrast: 1.12, knee: 0.82,
            slope: [1.04, 1.00, 0.96], offset: [-0.006, 0.000, 0.014],
            sat: 1.10, vib: 0.2, skinProtect: 0.7,
            shadowTint: [0, 0.04, 0.06, 0.8], highTint: [0.06, 0.03, -0.02, 0.6],
            vignette: 0.14, grain: 0.02
        },
        night_neon: {
            contrast: 1.22, knee: 0.78, expo: 0.1,
            slope: [1.00, 0.98, 1.05], offset: [-0.012, -0.008, 0.016],
            sat: 1.25, vib: 0.3, skinProtect: 0.5,
            hueBands: [
                { c: 0.833, w: 0.12, g: 1.20 }, { c: 0.667, w: 0.10, g: 1.12 },
                { c: 0.333, w: 0.14, g: 1.00 }, { c: 0.983, w: 0.09, g: 1.05 }
            ],
            shadowTint: [0.02, 0.01, 0.06, 0.7], highTint: [0.03, 0.01, 0.05, 0.4],
            vignette: 0.22, grain: 0.03
        },
        clean_natural: { contrast: 1.04, knee: 0.85, sat: 1.03, vib: 0.08, skinProtect: 0.8, grain: 0.01 },
        moody_film: {
            contrast: 1.15, knee: 0.72, expo: -0.08,
            slope: [0.99, 1.00, 1.02], offset: [0.002, 0.000, 0.010],
            sat: 0.92, vib: 0.15, skinProtect: 0.6,
            shadowTint: [0.01, 0.02, 0.04, 0.7], highTint: [0.04, 0.03, 0.00, 0.4],
            vignette: 0.2, grain: 0.035
        },
        bw_contrast: { contrast: 1.25, knee: 0.78, sat: 0.0, vib: 0.0, vignette: 0.2, grain: 0.03 },
        tv_acid: { contrast: 1.10, knee: 0.82, sat: 1.22, vib: 0.2, skinProtect: 0.5, grain: 0.03 }
    };

    const _NEUTRAL = { contrast: 1, knee: 1, expo: 0, sat: 1, vib: 0, skinProtect: 0,
                       vignette: 0, rcas: 0, grain: 0, clarity: 0, bloom: 0, halation: 0 };
    /** Slider "Сила" 0..100% — lerp between identity and the preset params. */
    function presetStrength(name, strength) {
        const base = GRADE_PRESETS[name];
        if (!base) return null;
        const k = Math.max(0, Math.min(1, strength != null ? strength : 1));
        const out = {};
        for (const key of Object.keys(base)) {
            const v = base[key];
            if (typeof v === "number") {
                const neutral = _NEUTRAL[key] != null ? _NEUTRAL[key] : v;
                out[key] = neutral + (v - neutral) * k;
            } else if (Array.isArray(v) && typeof v[0] === "number") {
                out[key] = v.map(x => x * k);
            } else {
                out[key] = v;
            }
        }
        return out;
    }

    // ── §14.3 manual "Выровнять" (deterministic statistics, not AI) ──────
    /**
     * stats: {p1, p50, p99, chanMeans:[r,g,b], neutralMean} from 12 frames of
     * the region. Returns slider values the user can see and edit.
     */
    function autoLevels(stats) {
        const expo = Math.max(-1, Math.min(1, Math.log2(0.40 / Math.max(1e-3, stats.p50))));
        const m = stats.chanMeans || [0.5, 0.5, 0.5];
        const mean = (m[0] + m[1] + m[2]) / 3;
        const wb = m.map(x => Math.max(0.85, Math.min(1.15, mean / Math.max(1e-3, x))));
        const off = Math.max(-0.05, Math.min(0.05, (0.03 - stats.p1) * 0.5));
        return { expo: expo, wb: wb, offset: [off, off, off], contrast: 1.0 };
    }

    // ── §14.4 spatial ops ────────────────────────────────────────────────
    /** Vignette: 1 - amount * r^1.6 (r normalized so the corner ≈ 1). */
    function vignetteFactor(u, v, amount) {
        const dx = (u - 0.5) * 2, dy = (v - 0.5) * 2;
        const r = Math.min(1, Math.hypot(dx, dy) / Math.hypot(1, 1));
        return 1 - amount * Math.pow(r, 1.6);
    }

    return {
        gradeColor: gradeColor, GRADE_PRESETS: GRADE_PRESETS,
        presetStrength: presetStrength, autoLevels: autoLevels,
        vignetteFactor: vignetteFactor, rgb2hsv: rgb2hsv
    };
});
