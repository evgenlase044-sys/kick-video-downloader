/* Kick Clip Studio — web/core/render/yuv.js
 * PLAN §17.2: RGB(A) -> yuv420p, BT.709 limited range.
 * Chroma: true 2x2 box average (sum / count). The old running
 * `(acc + c) / 2` weighted pixels 1/8,1/8,1/4,1/2 and shifted chroma to the
 * bottom-right pixel (coloured fringes on text edges). Pure JS (UMD). */
(function (root, factory) {
    const mod = factory();
    if (typeof module !== "undefined" && module.exports) module.exports = mod;
    root.CoreYuv = mod;
})(typeof self !== "undefined" ? self : this, function () {
    "use strict";

    function rgb2yuv709(r, g, b) {
        const y = 0.2126 * r + 0.7152 * g + 0.0722 * b;
        return { Y: 16 + 219 * y, Cb: 128 + 224 * (b - y) / 1.8556, Cr: 128 + 224 * (r - y) / 1.5748 };
    }

    function packYuv420(rgba, w, h) {
        const yP = new Uint8Array(w * h);
        const cw = (w + 1) >> 1, ch = (h + 1) >> 1;
        const uP = new Uint8Array(cw * ch), vP = new Uint8Array(cw * ch);
        const uAcc = new Float64Array(cw * ch), vAcc = new Float64Array(cw * ch);
        const nAcc = new Uint8Array(cw * ch);
        for (let y = 0; y < h; y++) {
            const crow = (y >> 1) * cw;
            for (let x = 0; x < w; x++) {
                const i = (y * w + x) * 4;
                const c = rgb2yuv709(rgba[i] / 255, rgba[i + 1] / 255, rgba[i + 2] / 255);
                yP[y * w + x] = Math.max(16, Math.min(235, Math.round(c.Y)));
                const ci = crow + (x >> 1);
                uAcc[ci] += c.Cb; vAcc[ci] += c.Cr; nAcc[ci]++;
            }
        }
        for (let i = 0; i < uP.length; i++) {
            const n = nAcc[i] || 1;
            uP[i] = Math.max(16, Math.min(240, Math.round(uAcc[i] / n)));
            vP[i] = Math.max(16, Math.min(240, Math.round(vAcc[i] / n)));
        }
        return { y: yP, u: uP, v: vP, w: w, h: h };
    }

    function interleave(pl) {
        const cw = (pl.w + 1) >> 1, ch = (pl.h + 1) >> 1;
        const out = new Uint8Array(pl.w * pl.h + cw * ch * 2);
        out.set(pl.y, 0);
        out.set(pl.u, pl.w * pl.h);
        out.set(pl.v, pl.w * pl.h + cw * ch);
        return out;
    }

    return { rgb2yuv709: rgb2yuv709, packYuv420: packYuv420, interleave: interleave };
});
