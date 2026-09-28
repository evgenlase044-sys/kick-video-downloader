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
    const LENS = (typeof CoreLens !== "undefined") ? CoreLens : require("./lens.js");
    const GRADE = (typeof CoreGrade !== "undefined") ? CoreGrade : require("./grade.js");
    const LUTM = (typeof CoreLut3D !== "undefined") ? CoreLut3D : require("../lut3d.js");
    const EF = (typeof CoreEffects !== "undefined") ? CoreEffects : require("./effects.js");

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
        // fx layers (§15): flash + shake offsets + zoom/lens/threshold/whip
        let shake = { dx: 0, dy: 0 };
        let zoom = { scale: 1, radialForce: 0 };
        let lensP = null;
        let thresholdOn = false;
        const timeRemaps = [];
        for (const layer of comp.layers) {
            if (layer.type !== "fx") continue;
            const st = evalFx(layer, t, fps);
            if (!st && layer.kind !== "ramp" && layer.kind !== "freeze") continue;
            if (layer.kind === "flash") ops.push({ op: "flash", color: layer.color || "white", alpha: st });
            if (layer.kind === "shake") {
                shake.dx += (layer.amp || 12) * st * Math.sin(2 * Math.PI * (layer.freq || 7) * t);
                shake.dy += (layer.amp || 12) * st * Math.cos(2 * Math.PI * (layer.freq || 7) * 9 / 7 * t);
            }
            if (layer.kind === "zoom") {
                const zp = EF.zoomPunch(t, { A: layer.amp != null ? layer.amp : 0.15,
                                             overshoot: 0.12, settleMs: 220,
                                             at: layer.in != null ? layer.in : layer.start });
                zoom = zp;
            }
            if (layer.kind === "lens") {
                lensP = lensPunchState(layer, t);
            }
            if (layer.kind === "threshold") thresholdOn = t >= (layer.in != null ? layer.in : layer.start) &&
                                                  t <= (layer.out != null ? layer.out : layer.end);
            if (layer.kind === "whip") {
                const w = EF.whip(t, { at: layer.in != null ? layer.in : layer.start,
                                       durMs: ((layer.out != null ? layer.out : layer.end) -
                                               (layer.in != null ? layer.in : layer.start)) * 1000,
                                       dir: layer.color === "left" ? -1 : 1 });
                shake.dx += w.dx * W;
            }
            if (layer.kind === "freeze" || layer.kind === "ramp") {
                timeRemaps.push({ kind: layer.kind, s0: layer.in != null ? layer.in : layer.start,
                                  e0: layer.out != null ? layer.out : layer.end });
            }
        }

        const sorted = videoLayers.slice().sort((a, b) => (b.z || 0) - (a.z || 0));

        for (const layer of sorted) {
            let mt = CMP.mapTime(layer, t);
            // §15 time-remap: freeze holds the source time, ramp re-times it
            const remap = timeRemaps.find(r => t >= r.s0 && t <= r.e0);
            if (remap) {
                const srcAtStart = CMP.mapTime(layer, remap.s0).src;
                if (remap.kind === "freeze") {
                    mt = { local: mt.local, src: srcAtStart };
                } else {
                    const local = t - remap.s0;
                    mt = { local: mt.local, src: srcAtStart +
                           integrateRamp(local, remap.e0 - remap.s0) };
                }
            }
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
            dstRect.srcT = mt.src;
            dstRect.op = "video";
            dstRect.asset = layer.asset;
            dstRect.layerId = layer.id;
            dstRect.round = !!layer.mask;
            dstRect.sn = { x: srcRect.sx / aW_(asset), y: srcRect.sy / aH_(asset),
                           w: srcRect.sw / aW_(asset), h: srcRect.sh / aH_(asset) };
            dstRect.dn = { x: dstRect.dx / W, y: dstRect.dy / H,
                           w: dstRect.dw / W, h: dstRect.dh / H };
            // §13/§14 per-layer effects: lens params + grade preset params
            const effects = layer.effects || [];
            for (const fx of effects) {
                if (fx.type === "lens") {
                    const preset = LENS.LENS_PRESETS[fx.preset] || {};
                    const p = Object.assign({}, preset, fx.params || {});
                    // §8.2: animatable k1/ca resolve through evalAnim
                    p.k1 = CMP.evalAnim(fx.k1 != null ? fx.k1 : p.k1 || 0, mt.local);
                    p.ca = CMP.evalAnim(fx.ca != null ? fx.ca : p.ca || 0, mt.local);
                    p.W = W; p.H = H; p.aspect = W / H;
                    if (lensP) {
                        p.k1 = (p.k1 || 0) + lensP.k1;
                        p.ca = (p.ca || 0) + lensP.ca;
                    }
                    dstRect.lens = p;
                } else if (fx.type === "grade") {
                    const preset = GRADE.GRADE_PRESETS[fx.preset || "viral_punch"];
                    if (preset) {
                        dstRect.grade = GRADE.presetStrength(fx.preset || "viral_punch",
                                                             fx.strength != null ? fx.strength : 1);
                    } else if (fx.params) {
                        dstRect.grade = fx.params;
                    }
                }
            }
            ops.push(dstRect);
        }

        // static bars (§ export parity)
        if (comp.barTop > 0) ops.push({ op: "bars", band: "top", h: comp.barTop });
        if (comp.barBottom > 0) ops.push({ op: "bars", band: "bottom", h: comp.barBottom });

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
        let gradeVignette = 0;
        for (const l of comp.layers) {
            if (l.type !== "video" || !l.effects) continue;
            for (const e of l.effects) {
                if (e.type === "grade") {
                    const preset = GRADE.GRADE_PRESETS[e.preset || "viral_punch"];
                    if (preset && preset.vignette) gradeVignette = Math.max(gradeVignette, preset.vignette);
                }
            }
        }

        return {
            w: W, h: H, fps: fps, t: t, scale: opts.scale != null ? opts.scale : 1,
            ops: ops, textCues: textCues, shake: shake,
            grade: { on: gradeOn, lutN: o.lut ? o.lut.N : 0 },
            zoom: zoom,
            threshold: thresholdOn,
            vignette: comp.vignette != null ? comp.vignette : 0,
            gradeVignette: gradeVignette,
            flash: ops.some(o2 => o2.op === "flash")
        };
    }

    /** §13.3 Lens Punch state at absolute time t. */
    function lensPunchState(layer, t) {
        const at = layer.in != null ? layer.in : layer.start;
        const dur = ((layer.out != null ? layer.out : layer.end) - at) || 0.25;
        const p = Math.max(0, Math.min(1, (t - at) / dur));
        if (p <= 0) return { k1: 0, ca: 0 };
        const bell = Math.exp(-Math.pow((p - 0.32) / 0.35, 2));
        return { k1: (layer.amp != null ? layer.amp : 0.18) * bell,
                 ca: (layer.peak != null ? layer.peak : 3) * bell };
    }
        /** §15 speed ramp integral: 0.35x (in) -> 1.8x (mid) -> 1x (out). */
    function integrateRamp(local, dur) {
        const half = Math.max(1e-3, dur / 2);
        let acc = 0.35 * Math.min(local, half);
        if (local > half) acc += (0.35 + 1.8) / 2 * Math.min(local - half, half);
        if (local > dur) acc += (1.8 + 1.0) / 2 * Math.min(local - dur, dur);
        if (local > dur * 1.5) acc += 1.0 * (local - dur * 1.5);
        return acc;
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
                if (op.lens) {
                    // §13: distortion + CA per channel, then grade
                    color = LENS.sampleColor(
                        (lu, lv) => o.sourcePixel(op.asset, lu, lv, frame.t),
                        su, sv, op.lens, frame.t);
                } else {
                    color = o.sourcePixel(op.asset, su, sv, frame.t);
                }
                if (op.grade) {
                    color = GRADE.gradeColor(color, op.grade, o.lut || null);
                } else if (o.lut) {
                    color = LUT.sample(o.lut, color[0], color[1], color[2]);
                }
                break;
            }
        }
        if (!color) color = [0, 0, 0];
        let c = color.slice();
        if (frame.grade.on && o.lut) {
            const g = LUT.sample(o.lut, c[0], c[1], c[2]);
            c = g;
        }
        let vig = frame.vignette;
        if (!vig && frame.gradeVignette) vig = frame.gradeVignette;
        if (vig) {
            // §14.4: 1 - amount * r^1.6 (corner-normalized radius)
            const dxn = (u - 0.5) * 2, dyn = (v - 0.5) * 2;
            const r = Math.min(1, Math.hypot(dxn, dyn) / Math.hypot(1, 1));
            const k = 1 - vig * Math.pow(r, 1.6);
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