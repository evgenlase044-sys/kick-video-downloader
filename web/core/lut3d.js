/* Kick Clip Studio — web/core/lut3d.js
 * PLAN §14.6: parse .cube LUTs (own tv_grade.cube 65^3) and sample them
 * trilinearly — the same array feeds the WebGL2 sampler3D in the preview
 * grade pass and (later) the export LUT bake, so preview == export.
 * Node-compatible (UMD) for verification. */
(function (root, factory) {
    const mod = factory();
    if (typeof module !== "undefined" && module.exports) module.exports = mod;
    root.CoreLut3D = mod;
})(typeof self !== "undefined" ? self : this, function () {
    "use strict";

    /**
     * Parse an ASCII .cube file. Returns { N, data: Float32Array(N^3*3), title }.
     * Data is stored red-fastest exactly like the .cube ordering, ready for a
     * gl.RGB / gl.TEXTURE_3D upload.
     */
    function parseCube(text) {
        let N = 0, title = "";
        const vals = [];
        const lines = String(text).split(/\r?\n/);
        for (let raw of lines) {
            const line = raw.trim();
            if (!line || line.startsWith("#")) continue;
            if (line.startsWith("TITLE")) { title = line.slice(5).trim().replace(/^"|"$/g, ""); continue; }
            if (line.startsWith("LUT_3D_SIZE")) { N = parseInt(line.split(/\s+/)[1], 10); continue; }
            if (line.startsWith("LUT_1D_SIZE") || line.startsWith("DOMAIN_") ||
                line.startsWith("LUT_3D_INPUT_RANGE")) continue;
            const parts = line.split(/\s+/);
            if (parts.length !== 3) continue;
            const r = parseFloat(parts[0]), g = parseFloat(parts[1]), b = parseFloat(parts[2]);
            if (!isFinite(r) || !isFinite(g) || !isFinite(b)) continue;
            vals.push(r, g, b);
        }
        if (!N || vals.length !== N * N * N * 3) {
            throw new Error("Invalid .cube: expected " + (N ? N * N * N * 3 : "?") + " values, got " + vals.length);
        }
        return { N: N, data: new Float32Array(vals), title: title };
    }

    /** Trilinear sample at (r,g,b) in 0..1. Mirrors ffmpeg lut3d interp=trilinear. */
    function sample(lut, r, g, b) {
        const N = lut.N, D = lut.data;
        const n1 = N - 1;
        const clampv = v => v < 0 ? 0 : (v > 1 ? 1 : v);
        r = clampv(r); g = clampv(g); b = clampv(b);
        const fx = r * n1, fy = g * n1, fz = b * n1;
        const x0 = Math.min(Math.floor(fx), n1 - 1), y0 = Math.min(Math.floor(fy), n1 - 1), z0 = Math.min(Math.floor(fz), n1 - 1);
        const tx = fx - x0, ty = fy - y0, tz = fz - z0;
        // red fastest (x), then green (y), then blue (z)
        function at(x, y, z, ch) {
            const idx = ((z * N + y) * N + x) * 3 + ch;
            return D[idx];
        }
        const out = [0, 0, 0];
        for (let ch = 0; ch < 3; ch++) {
            const c000 = at(x0, y0, z0, ch), c100 = at(x0 + 1, y0, z0, ch);
            const c010 = at(x0, y0 + 1, z0, ch), c110 = at(x0 + 1, y0 + 1, z0, ch);
            const c001 = at(x0, y0, z0 + 1, ch), c101 = at(x0 + 1, y0, z0 + 1, ch);
            const c011 = at(x0, y0 + 1, z0 + 1, ch), c111 = at(x0 + 1, y0 + 1, z0 + 1, ch);
            const c00 = c000 + (c100 - c000) * tx;
            const c10 = c010 + (c110 - c010) * tx;
            const c01 = c001 + (c101 - c001) * tx;
            const c11 = c011 + (c111 - c011) * tx;
            const c0 = c00 + (c10 - c00) * ty;
            const c1 = c01 + (c11 - c01) * ty;
            out[ch] = c0 + (c1 - c0) * tz;
        }
        return out;
    }

    return { parseCube: parseCube, sample: sample };
});
