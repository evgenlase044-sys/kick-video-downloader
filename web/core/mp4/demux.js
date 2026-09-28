/* Kick Clip Studio — web/core/mp4/demux.js
 * PLAN §16 P1: minimal ISO-BMFF demuxer (progressive H.264/HEVC): codec
 * string, avcC/hvcC description, sample table (stsz/stco/stsc/stts/ctts/stss).
 * Audit fixes: sync samples (old code tested `stss.size`, a box has no size
 * field -> EVERY sample was a keyframe; no stss -> TypeError); per-sample
 * durations from stts (VFR); hvc1/hev1; explicit errors for fMP4/MPEG-TS. */
(function (root, factory) {
    const mod = factory();
    if (typeof module !== "undefined" && module.exports) module.exports = mod;
    root.CoreDemux = mod;
})(typeof self !== "undefined" ? self : this, function () {
    "use strict";
    function rdU32(v, o) { return (v[o] << 24 | v[o + 1] << 16 | v[o + 2] << 8 | v[o + 3]) >>> 0; }
    function rdI32(v, o) { return v[o] << 24 | v[o + 1] << 16 | v[o + 2] << 8 | v[o + 3]; }
    function rdU16(v, o) { return v[o] << 8 | v[o + 1]; }
    function rdU64(v, o) { return rdU32(v, o) * 4294967296 + rdU32(v, o + 4); }
    function type(v, o) { return String.fromCharCode(v[o], v[o + 1], v[o + 2], v[o + 3]); }

    function walkBoxes(v, start, end, out) {
        let o = start;
        while (o + 8 <= end) {
            let size = rdU32(v, o);
            const t = type(v, o + 4);
            let body = o + 8;
            if (size === 1) { size = rdU64(v, o + 8); body = o + 16; }
            else if (size === 0) size = end - o;
            if (size < 8 || o + size > end) break;
            out.push({ type: t, start: o, bodyStart: body, end: o + size });
            o += size;
        }
        return out;
    }
    function findBox(v, start, end, path) {
        let cur = [];
        walkBoxes(v, start, end, cur);
        let last = null;
        for (const name of path) {
            const hit = cur.find(b => b.type === name);
            if (!hit) return null;
            last = hit;
            cur = [];
            walkBoxes(v, hit.bodyStart, hit.end, cur);
        }
        return last;
    }
    function findBoxesAll(v, start, end, name) {
        return walkBoxes(v, start, end, []).filter(b => b.type === name);
    }
    const hex2 = x => x.toString(16).toUpperCase().padStart(2, "0");
    function parseAvcC(v, s, e) {
        if (e - s < 7) return null;
        return { codec: "avc1." + hex2(v[s + 1]) + hex2(v[s + 2]) + hex2(v[s + 3]), description: v.slice(s, e) };
    }
    function parseHvcC(v, s, e, fourcc) {
        if (e - s < 23) return null;
        const b1 = v[s + 1];
        let compat = rdU32(v, s + 2), rev = 0;
        for (let i = 0; i < 32; i++) { rev = (rev << 1) | (compat & 1); compat >>>= 1; }
        const cons = [];
        for (let i = 0; i < 6; i++) cons.push(v[s + 6 + i]);
        while (cons.length && cons[cons.length - 1] === 0) cons.pop();
        let codec = fourcc + "." + ["", "A", "B", "C"][(b1 >> 6) & 3] + (b1 & 31) + "." +
            (rev >>> 0).toString(16).toUpperCase() + "." + (((b1 >> 5) & 1) ? "H" : "L") + v[s + 12];
        for (const c of cons) codec += "." + c.toString(16).toUpperCase();
        return { codec: codec, description: v.slice(s, e) };
    }

    function parseVideoTrack(buf) {
        const v = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
        if (v.length > 376 && v[0] === 0x47 && v[188] === 0x47) throw new Error("MPEG-TS input: remux to MP4 first");
        const moov = findBox(v, 0, v.length, ["moov"]);
        if (!moov) throw new Error("no moov box");
        const fragmented = findBoxesAll(v, 0, v.length, "moof").length > 0 || !!findBox(v, moov.bodyStart, moov.end, ["mvex"]);
        for (const trak of findBoxesAll(v, moov.bodyStart, moov.end, "trak")) {
            const hdlr = findBox(v, trak.bodyStart, trak.end, ["mdia", "hdlr"]);
            if (!hdlr || type(v, hdlr.bodyStart + 8) !== "vide") continue;
            const mdhd = findBox(v, trak.bodyStart, trak.end, ["mdia", "mdhd"]);
            if (!mdhd) continue;
            const timescale = v[mdhd.bodyStart] === 1 ? rdU32(v, mdhd.bodyStart + 20) : rdU32(v, mdhd.bodyStart + 12);
            const stbl = findBox(v, trak.bodyStart, trak.end, ["mdia", "minf", "stbl"]);
            if (!stbl) continue;
            const stsd = findBox(v, stbl.bodyStart, stbl.end, ["stsd"]);
            if (!stsd) continue;
            let codec = null, description = null, width = 0, height = 0;
            for (const entry of walkBoxes(v, stsd.bodyStart + 8, stsd.end, [])) {
                const isAvc = entry.type === "avc1" || entry.type === "avc3";
                const isHevc = entry.type === "hvc1" || entry.type === "hev1";
                if (!isAvc && !isHevc) continue;
                width = rdU16(v, entry.bodyStart + 24);
                height = rdU16(v, entry.bodyStart + 26);
                const cfg = walkBoxes(v, entry.bodyStart + 78, entry.end, []).find(b => b.type === (isAvc ? "avcC" : "hvcC"));
                const parsed = cfg && (isAvc ? parseAvcC(v, cfg.bodyStart, cfg.end) : parseHvcC(v, cfg.bodyStart, cfg.end, entry.type));
                if (parsed) { codec = parsed.codec; description = parsed.description; break; }
            }
            if (!codec) continue;
            const stsz = findBox(v, stbl.bodyStart, stbl.end, ["stsz"]);
            if (!stsz) throw new Error("no stsz box");
            const uniformSize = rdU32(v, stsz.bodyStart + 4);
            const sampleCount = rdU32(v, stsz.bodyStart + 8);
            if (sampleCount === 0) throw new Error(fragmented ? "fragmented MP4 (moof) is not supported by the exact-frame path" : "video track has no samples");
            const sizes = new Uint32Array(sampleCount);
            for (let i = 0; i < sampleCount; i++) sizes[i] = uniformSize !== 0 ? uniformSize : rdU32(v, stsz.bodyStart + 12 + i * 4);
            const stco = findBox(v, stbl.bodyStart, stbl.end, ["stco"]);
            const co64 = findBox(v, stbl.bodyStart, stbl.end, ["co64"]);
            let chunkCount = 0, chunkOffsets = null;
            if (stco) {
                chunkCount = rdU32(v, stco.bodyStart + 4);
                chunkOffsets = new Float64Array(chunkCount);
                for (let i = 0; i < chunkCount; i++) chunkOffsets[i] = rdU32(v, stco.bodyStart + 8 + i * 4);
            } else if (co64) {
                chunkCount = rdU32(v, co64.bodyStart + 4);
                chunkOffsets = new Float64Array(chunkCount);
                for (let i = 0; i < chunkCount; i++) chunkOffsets[i] = rdU64(v, co64.bodyStart + 8 + i * 8);
            } else throw new Error("no stco/co64");
            const stsc = findBox(v, stbl.bodyStart, stbl.end, ["stsc"]);
            if (!stsc) throw new Error("no stsc box");
            const stscTab = [];
            for (let i = 0; i < rdU32(v, stsc.bodyStart + 4); i++) {
                stscTab.push({ first: rdU32(v, stsc.bodyStart + 8 + i * 12), per: rdU32(v, stsc.bodyStart + 12 + i * 12) });
            }
            const stts = findBox(v, stbl.bodyStart, stbl.end, ["stts"]);
            if (!stts) throw new Error("no stts box");
            const dts = new Float64Array(sampleCount), durations = new Float64Array(sampleCount);
            let di = 0, dtsAcc = 0;
            for (let e = 0; e < rdU32(v, stts.bodyStart + 4) && di < sampleCount; e++) {
                const count = rdU32(v, stts.bodyStart + 8 + e * 8), delta = rdU32(v, stts.bodyStart + 12 + e * 8);
                for (let k = 0; k < count && di < sampleCount; k++) { dts[di] = dtsAcc; durations[di] = delta; dtsAcc += delta; di++; }
            }
            const lastDelta = di > 0 ? durations[di - 1] : 0;
            while (di < sampleCount) { dts[di] = dtsAcc; durations[di] = lastDelta; dtsAcc += lastDelta; di++; }
            const ctts = findBox(v, stbl.bodyStart, stbl.end, ["ctts"]);
            const cts = new Int32Array(sampleCount);
            if (ctts) {
                const ver = v[ctts.bodyStart];
                let o = ctts.bodyStart + 8, ci = 0;
                for (let e = 0; e < rdU32(v, ctts.bodyStart + 4) && ci < sampleCount; e++, o += 8) {
                    const count = rdU32(v, o), off = ver === 0 ? rdU32(v, o + 4) : rdI32(v, o + 4);
                    for (let k = 0; k < count && ci < sampleCount; k++) cts[ci++] = off;
                }
            }
            // stss present -> only listed samples; absent -> all are sync
            const stss = findBox(v, stbl.bodyStart, stbl.end, ["stss"]);
            const sync = new Uint8Array(sampleCount);
            if (stss) {
                const n = rdU32(v, stss.bodyStart + 4);
                for (let i = 0; i < n; i++) {
                    const idx = rdU32(v, stss.bodyStart + 8 + i * 4) - 1;
                    if (idx >= 0 && idx < sampleCount) sync[idx] = 1;
                }
                if (n === 0) sync[0] = 1;
            } else sync.fill(1);
            const offsets = new Float64Array(sampleCount);
            let s = 0;
            for (let chunk = 1; chunk <= chunkCount && s < sampleCount; chunk++) {
                let per = 0;
                for (let e = stscTab.length - 1; e >= 0; e--) if (stscTab[e].first <= chunk) { per = stscTab[e].per; break; }
                let off = chunkOffsets[chunk - 1];
                for (let k = 0; k < per && s < sampleCount; k++) { offsets[s] = off; off += sizes[s]; s++; }
            }
            const pts = new Float64Array(sampleCount);
            let minPts = Infinity;
            for (let i = 0; i < sampleCount; i++) { pts[i] = dts[i] + cts[i]; if (pts[i] < minPts) minPts = pts[i]; }
            if (isFinite(minPts)) for (let i = 0; i < sampleCount; i++) pts[i] -= minPts;
            return { codec, description, timescale, width, height, sampleCount, sizes, offsets, dts, pts, cts,
                     sync, durations, duration: dtsAcc / timescale };
        }
        throw new Error(fragmented ? "fragmented MP4 (moof) is not supported by the exact-frame path" : "no avc1/hvc1 video track found");
    }

    function displayOrder(track) {
        const idx = [];
        for (let i = 0; i < track.sampleCount; i++) idx.push(i);
        idx.sort((a, b) => (track.pts[a] - track.pts[b]) || (track.dts[a] - track.dts[b]));
        return idx;
    }
    function guessFps(track) {
        const d = [];
        for (let i = 0; i < Math.min(track.sampleCount, 300); i++) if (track.durations[i] > 0) d.push(track.durations[i]);
        if (!d.length) return 30.0;
        d.sort((a, b) => a - b);
        return d[d.length >> 1] ? track.timescale / d[d.length >> 1] : 30.0;
    }
    return { parseVideoTrack, displayOrder, guessFps, _walk: walkBoxes, _findBox: findBox };
});
