/* Kick Clip Studio — web/core/render/composer.js
 * PLAN §5/§8: renderFrame core for Composition JSON. Evaluates the
 * composition at frame f into a RESOLUTION-INDEPENDENT draw list; the
 * browser executor (2D + WebGL2 grade) rasterizes it. pixelAt() implements
 * the same pipeline as a per-point color function so the §7.4 scale-parity
 * gate (SSIM ≥ 0.99, grain off) is verifiable numerically, without a GPU.
 * Pure JS, Node-testable. */
(function (root, factory) {
    const mod = factory();
    if (typeof module !== "undefined" && module.exports) module.exports = mod;
    root.CoreComposer = mod;
})(typeof self !== "undefined" ? self : this, function () {
    "use strict";
    const TM = (typeof CoreTimeMap !== "undefined") ? CoreTimeMap : require("../timeMap.js");
    const GEO = (typeof CoreGeometry !== "undefined") ? CoreGeometry : require("../geometry.js");
    const CMP = (typeof CoreComposition !== "undefined") ? CoreComposition : require("../composition.js");
    const LUT = (typeof CoreLut3D !== "undefined") ? CoreLut3D : require("../lut3d.js");

    /**
     * renderFrame(comp, f, scale) -> draw list.
     * comp: §8.1; f: FRAME index on the composition grid (§8.2);
     * scale: 1 = 1080x1920 reference. Every rect is in reference px and the
     * executor multiplies by `scale`, so the list is identical for any scale.
     */
    function renderFrame(comp, f, opts) {
        const o = opts || {};
        CMP.validate(comp);
        const W = comp.canvas.w, H = comp.canvas.h;
        const fps = comp.canvas.fps;
        const t = f / fps;
        const assets = comp.assets || {};
        const tracks = comp.tracks || {};
        const ops = [];
        const videoLayers = comp.layers.filter(l => l.type === "video");
        // bottom (z high) -> top (z low): list order = paint order
        const sorted = videoLayers.slice().sort((a, b) => (b.z || 0) - (a.z || 0));

        for (const layer of sorted) {
            const mt = CMP.mapTime(layer, t);
            const asset = assets[layer.asset];
            if (!asset) continue;
            const srcRect = srcRectForLayer(layer, mt.src, asset);
            if (!srcRect) continue;
            let dstRect;
            if (layer.pip) {
                const pr = GEO.pipRect(W, H, layer.pip);
                dstRect = GEO.coverInto(srcRect, pr.dx, pr.dy, pr.dw, pr.dh);
            } else {
                dstRect = GEO.coverInto(srcRect, 0, 0, W, H);
            }
            // attach normalized source & destination rects (scale-free)
            dstRect.op = "video";
            dstRect.asset = layer.asset;
            dstRect.layerId = layer.id;
            dstRect.round = !!layer.mask;
            dstRect.sn = { x: srcRect.sx / aW_(asset), y: srcRect.sy / aH_(asset),
                           w: srcRect.sw / aW_(asset), h: srcRect.sh / aH_(asset) };
            dstRect.dn = { x: dstRect.dx / W, y: dstRect.dy / H,
                           w: dstRect.dw / W, h: dstRect.dh / H };
            ops.push(dstRect);
        }

        // static bars (§ export parity)
        if (comp.barTop > 0) ops.push({ op: "bars", band: "top", h: comp.barTop });
        if (comp.barBottom > 0) ops.push({ op: "bars", band: "bottom", h: comp.barBottom });

        // fx layers (§15): flash + shake offsets are part of the frame state
        let shake = { dx: 0, dy: 0 };
        for (const layer of comp.layers) {
            if (layer.type !== "fx") continue;
            const st = evalFx(layer, t, fps);
            if (!st) continue;
            if (layer.kind === "flash") ops.push({ op: "flash", color: layer.color || "white", alpha: st });
            if (layer.kind === "shake") {
                shake.dx += (layer.amp || 12) * st * Math.sin(2 * Math.PI * (layer.freq || 7) * t);
                shake.dy += (layer.amp || 12) * st * Math.cos(2 * Math.PI * (layer.freq || 7) * 9 / 7 * t);
            }
        }

        // text layers: cues with cue-local time (same engine as the monitor)
        const textCues = [];
        for (const layer of comp.layers) {
            if (layer.type !== "text") continue;
            const mt = CMP.mapTime(layer, t);
            const words = (layer.words || []).map(w => ({
                word: w.t, s: w.s, e: w.e, hot: !!w.hot, color: w.color || null
            }));
            textCues.push({
                words: words,
                end: layer.time ? (layer.time.out || 0) - (layer.time.in || 0) : undefined,
                styleName: layer.style || "viral_italic",
                x: layer.transform ? layer.transform.x : 0.5,
                y: layer.transform ? layer.transform.y : 0.68,
                localT: mt.local
            });
        }

        const gradeOn = comp.layers.some(l => l.type === "video" &&
            l.effects && l.effects.some(e => e.type === "grade" && e.on !== false));

        return {
            w: W, h: H, fps: fps, t: t, scale: opts.scale != null ? opts.scale : 1,
            ops: ops, textCues: textCues, shake: shake,
            grade: { on: gradeOn, lutN: o.lut ? o.lut.N : 0 },
            vignette: comp.vignette != null ? comp.vignette : 0,
            flash: ops.some(o2 => o2.op === "flash")
        };
    }

    function aW_(asset) { return asset.w || 1; }
    function aH_(asset) { return asset.h || 1; }

    /** Source rect (asset px) for a video layer at source time srcT. */
    function srcRectForLayer(layer, srcT, asset) {
        const crop = layer.crop || { space: "source", x: 0, y: 0, w: 1, h: 1 };
        const box = { x: crop.x, y: crop.y, w: crop.w, h: crop.h };
        return GEO.boxPx(aW_(asset), aH_(asset), box);
    }

    /** §15 flash envelope: attack 12%, exponential decay. */
    function flashEnvelope(p) {
        if (p < 0 || p > 1) return 0;
        return p < 0.12 ? p / 0.12 : Math.exp(-(p - 0.12) * 4.2);
    }
    function evalFx(layer, t, fps) {
        const s0 = layer.in != null ? layer.in : layer.start;
        const e0 = layer.out != null ? layer.out : layer.end;
        if (s0 == null || e0 == null) return 0;
        return flashEnvelope((t - s0) / Math.max(1e-3, e0 - s0));
    }

    /**
     * pixelAt(comp, f, u, v, opts) — the full pipeline color at normalized
     * output point (u,v) WITHOUT text (text parity is covered by the frame
     * gate) with grain off: bands -> grade LUT -> vignette -> flash(screen).
     * opts.sourcePixel(assetName, sxNorm, syNorm, srcT) -> [r,g,b] 0..1
     * opts.lut — parsed LUT (§14.6). Resolution-independent by construction:
     * identical for any scale, which the §7.4 SSIM gate verifies.
     */
    function pixelAt(comp, f, u, v, opts) {
        const o = opts || {};
        const frame = renderFrame(comp, f, o);
        // find the TOPMOST video op covering (u,v), minus shake offset
        let color = null;
        const u2 = u - frame.shake.dx / frame.w;
        const v2 = v - frame.shake.dy / frame.h;
        for (let i = frame.ops.length - 1; i >= 0; i--) {
            const op = frame.ops[i];
            if (op.op !== "video") continue;
            // dst rect in output-normalized coords (op rects are in asset px
            // after coverInto — recompute normalized dst from op fields)
            if (op.dn == null) continue;
            if (u2 >= op.dn.x && u2 <= op.dn.x + op.dn.w && v2 >= op.dn.y && v2 <= op.dn.y + op.dn.h) {
                const su = (op.sn.x + (u2 - op.dn.x) / op.dn.w * op.sn.w);
                const sv = (op.sn.y + (v2 - op.dn.y) / op.dn.h * op.sn.h);
                color = o.sourcePixel(op.asset, su, sv, frame.t);
                break;
            }
        }
        if (!color) color = [0, 0, 0];
        let c = color.slice();
        if (frame.grade.on && o.lut) {
            const g = LUT.sample(o.lut, c[0], c[1], c[2]);
            c = g;
        }
        if (frame.vignette) {
            const dx = (u - 0.5) * 2, dy = (v - 0.5) * 2;
            const r2 = Math.min(1, dx * dx + dy * dy);
            const k = 1 - frame.vignette * Math.pow(r2, 0.8);
            c = [c[0] * k, c[1] * k, c[2] * k];
        }
        for (const op of frame.ops) {
            if (op.op !== "flash") continue;
            const a = op.alpha;
            const fc = { white: [1, 1, 1], red: [1, 0.13, 0.13], green: [0.22, 1, 0] }[op.color] || [1, 1, 1];
            c = [1 - (1 - c[0]) * (1 - fc[0] * a), 1 - (1 - c[1]) * (1 - fc[1] * a), 1 - (1 - c[2]) * (1 - fc[2] * a)];
        }
        return c.map(x => Math.max(0, Math.min(1, x)));
    }

    /** SSIM over paired luminance samples (§7.4: ≥ 0.99, grain off). */
    function ssimPairs(a, b) {
        const C1 = 0.01 * 0.01, C2 = 0.03 * 0.03;
        const n = a.length;
        let ma = 0, mb = 0;
        for (let i = 0; i < n; i++) { ma += a[i]; mb += b[i]; }
        ma /= n; mb /= n;
        let va = 0, vb = 0, cov = 0;
        for (let i = 0; i < n; i++) {
            va += (a[i] - ma) * (a[i] - ma);
            vb += (b[i] - mb) * (b[i] - mb);
            cov += (a[i] - ma) * (b[i] - mb);
        }
        va /= n; vb /= n; cov /= n;
        return ((2 * ma * mb + C1) * (2 * cov + C2)) / ((ma * ma + mb * mb + C1) * (va + vb + C2));
    }

    /** §7.4 scale-parity: pixel function at scale=1-downscale vs scale=s. */
    function scaleParity(comp, f, opts, points, scale) {
        const s = scale || 0.4;
        const lums1 = [], lums2 = [];
        const rng = mulberry(12345);
        for (let i = 0; i < (points || 50); i++) {
            const u = rng(), v = rng();
            const c1 = pixelAt(comp, f, u, v, opts);   // scale=1 reference
            const c2 = pixelAt(comp, f, u, v, Object.assign({}, opts, { scale: s }));
            lums1.push(0.2126 * c1[0] + 0.7152 * c1[1] + 0.0722 * c1[2]);
            lums2.push(0.2126 * c2[0] + 0.7152 * c2[1] + 0.0722 * c2[2]);
        }
        return ssimPairs(lums1, lums2);
    }

    function mulberry(seed) {
        let a = seed >>> 0;
        return function () {
            a |= 0; a = (a + 0x6D2B79F5) | 0;
            let t = Math.imul(a ^ (a >>> 15), 1 | a);
            t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
            return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
        };
    }

    return {
        renderFrame: renderFrame,
        pixelAt: pixelAt,
        ssimPairs: ssimPairs,
        scaleParity: scaleParity,
        flashEnvelope: flashEnvelope
    };
});
