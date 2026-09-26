/* Kick Clip Studio — web/core/mp4/demux.js
 * PLAN §16 P1: minimal ISO-BMFF (MP4) demuxer for H.264 progressive files —
 * exactly what ffmpeg/kick downloads produce. Extracts the avc1 track:
 * codec string, avcC description (for WebCodecs VideoDecoder) and the full
 * sample table (stsz/stco/stsc/stts/ctts/stss) with DTS+PTS per sample.
 * Pure JS, Node-testable. No external dependencies (the .cube/BMFF parsing
 * is ours; mp4box.js from the plan is replaced by this audited subset). */
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

    /** Walk boxes in [start,end): yield {type, start, bodyStart, end}. */
    function walkBoxes(v, start, end, out) {
        let o = start;
        while (o + 8 <= end) {
            let size = rdU32(v, o);
            const t = type(v, o + 4);
            let body = o + 8;
            if (size === 1) { // 64-bit size
                size = rdU64(v, o + 8);
                body = o + 16;
            } else if (size === 0) {
                size = end - o;
            }
            if (size < 8 || o + size > end) break;
            out.push({ type: t, start: o, bodyStart: body, end: o + size });
            o += size;
        }
        return out;
    }

    function findBox(v, start, end, path) {
        let boxes = [];
        walkBoxes(v, start, end, boxes);
        let cur = boxes;
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
        const boxes = [];
        walkBoxes(v, start, end, boxes);
        return boxes.filter(b => b.type === name);
    }

    function parseAvcC(v, bodyStart, end) {
        // avcC: configurationVersion(1) AVCProfileIndication(1) profile_compat(1)
        // level(1) ... SPS/PPS lists. WebCodecs wants these 4 bytes + NAL arrays.
        if (end - bodyStart < 7) return null;
        const profile = v[bodyStart + 1], compat = v[bodyStart + 2], level = v[bodyStart + 3];
        const hex2 = x => x.toString(16).toUpperCase().padStart(2, "0");
        return {
            codec: "avc1." + hex2(profile) + hex2(compat) + hex2(level),
            description: v.slice(bodyStart, end)
        };
    }

    /**
     * Parse an MP4 buffer; returns info for the first video track:
     * { codec, description, timescale, width, height, sampleCount,
     *   sizes:Uint32Array, dts:Float64Array, pts:Float64Array, ctsOffset:Int32Array,
     *   sync:Uint8Array, durations:Float64Array, duration }
     */
    function parseVideoTrack(buf) {
        const v = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
        const moov = findBox(v, 0, v.length, ["moov"]);
        if (!moov) throw new Error("no moov box");
        const traks = findBoxesAll(v, moov.bodyStart, moov.end, "trak");
        for (const trak of traks) {
            const hdlr = findBox(v, trak.bodyStart, trak.end, ["mdia", "hdlr"]);
            if (!hdlr) continue;
            const handler = type(v, hdlr.bodyStart + 8);
            if (handler !== "vide") continue;

            const mdhd = findBox(v, trak.bodyStart, trak.end, ["mdia", "mdhd"]);
            if (!mdhd) continue;
            const ver = v[mdhd.bodyStart];
            const timescale = ver === 1 ? rdU32(v, mdhd.bodyStart + 20) : rdU32(v, mdhd.bodyStart + 12);

            const stbl = findBox(v, trak.bodyStart, trak.end, ["mdia", "minf", "stbl"]);
            if (!stbl) continue;

            // sample description → avc1 → avcC
            const stsd = findBox(v, stbl.bodyStart, stbl.end, ["stsd"]);
            if (!stsd) continue;
            const entries = [];
            walkBoxes(v, stsd.bodyStart + 8, stsd.end, entries); // skip version/flags + entry_count
            let codec = null, description = null, width = 0, height = 0;
            for (const entry of entries) {
                if (entry.type !== "avc1" && entry.type !== "avc3") continue;
                // visual sample entry: 6b reserved + 2b data_ref_idx + 16b pre + w(2)+h(2)...
                width = rdU16(v, entry.bodyStart + 24);
                height = rdU16(v, entry.bodyStart + 26);
                const children = [];
                walkBoxes(v, entry.bodyStart + 78, entry.end, children);
                const avcC = children.find(b => b.type === "avcC");
                if (avcC) {
                    const parsed = parseAvcC(v, avcC.bodyStart, avcC.end);
                    codec = parsed.codec;
                    description = parsed.description;
                    break;
                }
            }
            if (!codec) continue;

            // sample sizes
            const stsz = findBox(v, stbl.bodyStart, stbl.end, ["stsz"]);
            const uniformSize = rdU32(v, stsz.bodyStart + 4);
            const sampleCount = rdU32(v, stsz.bodyStart + 8);
            const sizes = new Uint32Array(sampleCount);
            for (let i = 0; i < sampleCount; i++) {
                sizes[i] = uniformSize !== 0 ? uniformSize : rdU32(v, stsz.bodyStart + 12 + i * 4);
            }

            // chunk offsets
            const stco = findBox(v, stbl.bodyStart, stbl.end, ["stco"]);
            const co64 = findBox(v, stbl.bodyStart, stbl.end, ["co64"]);
            let chunkCount = 0, chunkOffsets = null, is64 = false;
            if (stco) {
                chunkCount = rdU32(v, stco.bodyStart + 4);
                chunkOffsets = new Float64Array(chunkCount);
                for (let i = 0; i < chunkCount; i++) chunkOffsets[i] = rdU32(v, stco.bodyStart + 8 + i * 4);
            } else if (co64) {
                chunkCount = rdU32(v, co64.bodyStart + 4);
                chunkOffsets = new Float64Array(chunkCount);
                is64 = true;
                for (let i = 0; i < chunkCount; i++) chunkOffsets[i] = rdU64(v, co64.bodyStart + 8 + i * 8);
            } else {
                throw new Error("no stco/co64");
            }

            // sample-to-chunk
            const stsc = findBox(v, stbl.bodyStart, stbl.end, ["stsc"]);
            const stscCount = rdU32(v, stsc.bodyStart + 4);
            const stscTab = [];
            for (let i = 0; i < stscCount; i++) {
                stscTab.push({
                    first: rdU32(v, stsc.bodyStart + 8 + i * 12),
                    per: rdU32(v, stsc.bodyStart + 8 + i * 12 + 4),
                    desc: rdU32(v, stsc.bodyStart + 8 + i * 12 + 8)
                });
            }

            // decode timestamps
            const stts = findBox(v, stbl.bodyStart, stbl.end, ["stts"]);
            const sttsCount = rdU32(v, stts.bodyStart + 4);
            const sttsTab = [];
            for (let i = 0; i < sttsCount; i++) {
                sttsTab.push({
                    count: rdU32(v, stts.bodyStart + 8 + i * 8),
                    delta: rdU32(v, stts.bodyStart + 8 + i * 8 + 4)
                });
            }

            // composition offsets (B-frames)
            const ctts = findBox(v, stbl.bodyStart, stbl.end, ["ctts"]);
            const cttsTab = [];
            if (ctts) {
                const cttsVer = v[ctts.bodyStart];
                const cttsCount = rdU32(v, ctts.bodyStart + 4);
                let o = ctts.bodyStart + 8;
                for (let i = 0; i < cttsCount; i++) {
                    const count = rdU32(v, o);
                    const off = cttsVer === 0 ? rdU32(v, o + 4) : rdI32(v, o + 4);
                    cttsTab.push({ count: count, off: off });
                    o += 8;
                }
            }

            // sync samples (1-based); absent = all keyframes
            const stss = findBox(v, stbl.bodyStart, stbl.end, ["stss"]);
            const syncSet = new Set();
            if (stss) {
                const stssCount = rdU32(v, stss.bodyStart + 4);
                for (let i = 0; i < stssCount; i++) syncSet.add(rdU32(v, stss.bodyStart + 8 + i * 4) - 1);
            }

            // build sample table in decode order
            const dts = new Float64Array(sampleCount);
            const cts = new Int32Array(sampleCount);
            let di = 0, dtsAcc = 0, ti = 0, tiLeft = sttsTab.length ? sttsTab[0].count : 0;
            let ci = 0, ciLeft = cttsTab.length ? cttsTab[0].count : 0;
            while (di < sampleCount && ti < sttsTab.length) {
                dts[di] = dtsAcc;
                dtsAcc += sttsTab[ti].delta;
                di++;
                if (--tiLeft === 0 && ti + 1 < sttsTab.length) { ti++; tiLeft = sttsTab[ti].count; }
            }
            if (cttsTab.length) {
                for (let i = 0; i < sampleCount && ci < cttsTab.length; i++) {
                    cts[i] = cttsTab[ci].off;
                    if (--ciLeft === 0 && ci + 1 < cttsTab.length) { ci++; ciLeft = cttsTab[ci].count; }
                }
            }

            // chunk → sample byte offsets
            const offsets = new Float64Array(sampleCount);
            let s = 0;
            for (let chunk = 1; chunk <= chunkCount && s < sampleCount; chunk++) {
                let per = 0;
                for (let e = stscTab.length - 1; e >= 0; e--) {
                    if (stscTab[e].first <= chunk) { per = stscTab[e].per; break; }
                }
                let off = chunkOffsets[chunk - 1];
                for (let k = 0; k < per && s < sampleCount; k++) {
                    offsets[s] = off;
                    off += sizes[s];
                    s++;
                }
            }

            const sync = new Uint8Array(sampleCount);
            for (let i = 0; i < sampleCount; i++) {
                sync[i] = stss.size ? (syncSet.has(i) ? 1 : 0) : 1;
            }

            const pts = new Float64Array(sampleCount);
            const durations = new Float64Array(sampleCount);
            let minPts = Infinity;
            for (let i = 0; i < sampleCount; i++) {
                pts[i] = dts[i] + cts[i];
                if (pts[i] < minPts) minPts = pts[i];
                durations[i] = sttsTab.length ? sttsTab[0].delta : 0;
            }
            // normalize presentation start to 0 (equivalent of a single elst shift)
            if (isFinite(minPts)) {
                for (let i = 0; i < sampleCount; i++) pts[i] -= minPts;
            }

            return {
                codec: codec,
                description: description,
                timescale: timescale,
                width: width,
                height: height,
                sampleCount: sampleCount,
                sizes: sizes,
                offsets: offsets,
                dts: dts,
                pts: pts,
                cts: cts,
                sync: sync,
                durations: durations,
                duration: dtsAcc / timescale
            };
        }
        throw new Error("no avc1 video track found");
    }

    /** Display order: indices sorted by (pts, dts). */
    function displayOrder(track) {
        const idx = [];
        for (let i = 0; i < track.sampleCount; i++) idx.push(i);
        idx.sort((a, b) => (track.pts[a] - track.pts[b]) || (track.dts[a] - track.dts[b]));
        return idx;
    }

    /** Display fps: median stts delta → fps (robust against VFR jitter). */
    function guessFps(track) {
        const stts = [];
        // reuse deltas from dts[] directly
        const deltas = [];
        for (let i = 1; i < Math.min(track.sampleCount, 300); i++) {
            deltas.push(track.dts[i] - track.dts[i - 1]);
        }
        if (!deltas.length) return 30.0;
        deltas.sort((a, b) => a - b);
        const median = deltas[deltas.length >> 1];
        if (!median) return 30.0;
        return track.timescale / median;
    }

    return {
        parseVideoTrack: parseVideoTrack,
        displayOrder: displayOrder,
        guessFps: guessFps,
        _walk: walkBoxes,
        _findBox: findBox
    };
});
