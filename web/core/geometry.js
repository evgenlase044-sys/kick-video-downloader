/* Kick Clip Studio — web/core/geometry.js
 * PLAN §9.2/§16: exact monitor<->source geometry, draw rects for the
 * canvas monitor (mirrors the export split/crop math so preview == export).
 * Node-compatible (UMD) for verification. */
(function (root, factory) {
    const mod = factory();
    if (typeof module !== "undefined" && module.exports) module.exports = mod;
    root.CoreGeometry = mod;
})(typeof self !== "undefined" ? self : this, function () {
    "use strict";

    function clamp(x, a, b) { return x < a ? a : (x > b ? b : x); }

    /** Where the video really sits inside a letterboxed element (§9.2). */
    function contentRect(el, vw, vh) {
        const r = el.getBoundingClientRect();
        const s = Math.min(r.width / vw, r.height / vh);
        const w = vw * s, h = vh * s;
        return {
            x: r.left + (r.width - w) / 2,
            y: r.top + (r.height - h) / 2,
            w: w, h: h
        };
    }

    /** Element px -> normalized source coords (§9.2). */
    function toSource(px, py, cr) {
        return {
            x: clamp((px - cr.x) / cr.w, 0, 1),
            y: clamp((py - cr.y) / cr.h, 0, 1)
        };
    }

    /** Normalized 0..1 source box -> pixel rect. */
    function boxPx(srcW, srcH, box) {
        const b = box || { x: 0, y: 0, w: 1, h: 1 };
        const x = clamp(b.x, 0, 1), y = clamp(b.y, 0, 1);
        const w = clamp(b.w, 0.01, 1 - x), h = clamp(b.h, 0.01, 1 - y);
        return { sx: x * srcW, sy: y * srcH, sw: w * srcW, sh: h * srcH };
    }

    /** Cover-fit a source sub-rect into a destination rect (center crop). */
    function coverInto(src, dx, dy, dw, dh) {
        const scale = Math.max(dw / src.sw, dh / src.sh);
        const w = src.sw * scale, h = src.sh * scale;
        // the visible center of the source sub-rect lands at the dst center
        const cx = src.sx + src.sw / 2, cy = src.sy + src.sh / 2;
        return {
            sx: clamp(cx - dw / scale / 2, 0, Math.max(0, src.sx + src.sw - dw / scale)),
            sy: clamp(cy - dh / scale / 2, 0, Math.max(0, src.sy + src.sh - dh / scale)),
            sw: dw / scale, sh: dh / scale,
            dx: dx, dy: dy, dw: dw, dh: dh
        };
    }

    /** Contain-fit (letterbox) of a source sub-rect into a destination rect. */
    function containInto(src, dx, dy, dw, dh) {
        const scale = Math.min(dw / src.sw, dh / src.sh);
        const w = src.sw * scale, h = src.sh * scale;
        return {
            sx: src.sx, sy: src.sy, sw: src.sw, sh: src.sh,
            dx: dx + (dw - w) / 2, dy: dy + (dh - h) / 2, dw: w, dh: h
        };
    }

    /**
     * Compose draw-ops for the canvas monitor (mirrors export §_export_layered_clip).
     * One draw-op per band; every op carries its `sourceId` so the caller can
     * assert that a split from ONE file draws both halves from the same decoded
     * frame — frame-synced by construction (§7.4 clap gate).
     *
     * opts: { format, srcW, srcH, outW, outH, cropBox, bgBox, sourceId, topRatio }
     */
    function composeDrawOps(opts) {
        const fmt = opts.format || "fullscreen";
        const srcW = opts.srcW, srcH = opts.srcH;
        const outW = opts.outW, outH = opts.outH;
        const srcId = opts.sourceId != null ? opts.sourceId : "base";
        const ops = [];
        if (fmt === "split_adhd") {
            const topH = Math.round(outH * (opts.topRatio != null ? opts.topRatio : 0.45) / 2) * 2;
            const botH = outH - topH;
            const cam = coverInto(boxPx(srcW, srcH, opts.cropBox), 0, 0, outW, topH);
            const bg = coverInto(boxPx(srcW, srcH, opts.bgBox || { x: 0, y: 0, w: 1, h: 1 }), 0, topH, outW, botH);
            cam.sourceId = srcId; bg.sourceId = srcId;
            ops.push(Object.assign(cam, { band: "top" }));
            ops.push(Object.assign(bg, { band: "bottom" }));
        } else if (fmt === "talking_head_9_16") {
            const full = coverInto(boxPx(srcW, srcH, opts.cropBox), 0, 0, outW, outH);
            full.sourceId = srcId; full.band = "full";
            ops.push(full);
        } else { // fullscreen and any legacy formats
            const full = coverInto(boxPx(srcW, srcH, opts.cropBox), 0, 0, outW, outH);
            full.sourceId = srcId; full.band = "full";
            ops.push(full);
        }
        return ops;
    }

    /** PiP window rect on the output canvas from a normalized pipBox. */
    function pipRect(outW, outH, pipBox) {
        const p = pipBox || { x: 0.688, y: 0.018, w: 0.30 };
        const w = clamp(p.w, 0.05, 0.9) * outW;
        const h = w * 9 / 16; // PiP windows are webcam-shaped
        const x = clamp(p.x, 0, 1) * outW;
        const y = clamp(p.y != null ? p.y : 0.018, 0, 1) * outH;
        return { dx: Math.round(x), dy: Math.round(y), dw: Math.round(w), dh: Math.round(h) };
    }

    return {
        clamp: clamp,
        contentRect: contentRect,
        toSource: toSource,
        boxPx: boxPx,
        coverInto: coverInto,
        containInto: containInto,
        composeDrawOps: composeDrawOps,
        pipRect: pipRect
    };
});
