/* Kick Clip Studio — web/core/render/yuv.js
 * PLAN §17.2: RGB(A) -> yuv420p packing in the renderer itself, BT.709
 * limited range (the shader output must equal the encoder input):
 *   Y'  = 16 + 219 · Y709
 *   Cb  = 128 + 224 · (B' − Y'g) / 1.8556,  Cr = 128 + 224 · (R' − Y'g) / 1.5748
 * Chroma: 2x2 box average. Pure JS (UMD) — round-trip verified in Node. */
(function (root, factory) {
    const mod = factory();
    if (typeof module !== "undefined" && module.exports) module.exports = mod;
    root.CoreYuv = mod;
})(typeof self !== "undefined" ? self : this, function () {
    "use strict";

    function rgb2yuv709(r, g, b) {
        const y = 0.2126 * r + 0.7152 * g + 0.0722 * b;
        return {
            Y: 16 + 219 * y,
            Cb: 128 + 224 * (b - y) / 1.8556,
            Cr: 128 + 224 * (r - y) / 1.5748
        };
    }

    /**
     * Pack RGBA into yuv420p planes (BT.709 limited).
     * Returns { y: Uint8Array(w*h), u: Uint8Array(w*h/4), v: ... , w, h }.
     */
    function packYuv420(rgba, w, h) {
        const yP = new Uint8Array(w * h);
        const cw = w >> 1, ch = h >> 1;
        const uP = new Uint8Array(cw * ch);
        const vP = new Uint8Array(cw * ch);
        const uAcc = new Float64Array(cw * ch);
        const vAcc = new Float64Array(cw * ch);
        for (let y = 0; y < h; y++) {
            for (let x = 0; x < w; x++) {
                const i = (y * w + x) * 4;
                const c = rgb2yuv709(rgba[i] / 255, rgba[i + 1] / 255, rgba[i + 2] / 255);
                yP[y * w + x] = Math.max(16, Math.min(235, Math.round(c.Y)));
                const cu = Math.max(16, Math.min(240, Math.round(c.Cb)));
                const cv = Math.max(16, Math.min(240, Math.round(c.Cr)));
                if ((y & 1) === 0 && (x & 1) === 0) {
                    const ci = (y >> 1) * cw + (x >> 1);
                    uAcc[ci] = cu;
                    vAcc[ci] = cv;
                } else {
                    const ci = (y >> 1) * cw + (x >> 1);
                    uAcc[ci] = (uAcc[ci] + cu) / 2;
                    vAcc[ci] = (vAcc[ci] + cv) / 2;
                }
            }
        }
        for (let i = 0; i < uP.length; i++) {
            uP[i] = Math.round(uAcc[i]);
            vP[i] = Math.round(vAcc[i]);
        }
        return { y: yP, u: uP, v: vP, w: w, h: h };
    }

    /** Interleave the three planes into the raw frame layout ffmpeg expects. */
    function interleave(pl) {
        const cw = pl.w >> 1, ch = pl.h >> 1;
        const out = new Uint8Array(pl.w * pl.h + cw * ch * 2);
        out.set(pl.y, 0);
        out.set(pl.u, pl.w * pl.h);
        out.set(pl.v, pl.w * pl.h + cw * ch);
        return out;
    }

    return {
        rgb2yuv709: rgb2yuv709,
        packYuv420: packYuv420,
        interleave: interleave
    };
});
