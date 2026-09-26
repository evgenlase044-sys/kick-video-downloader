/* Kick Clip Studio — web/core/mp4/frameIndex.js
 * PLAN §16 P1: display-frame index over a demuxed avc1 track.
 *   - frame selection follows FFmpeg's fps filter: floor(src·fps + 1e-6)
 *   - decode plan: nearest sync sample ≤ target (decode order), then all
 *     samples up to the target's decode position
 * Node-compatible for verification. */
(function (root, factory) {
    const mod = factory();
    if (typeof module !== "undefined" && module.exports) module.exports = mod;
    root.CoreFrameIndex = mod;
})(typeof self !== "undefined" ? self : this, function () {
    "use strict";

    const DEMUX = (typeof CoreDemux !== "undefined") ? CoreDemux : require("./demux.js");

    /** floor(src·fps + 1e-6) — matches the ffmpeg `fps` filter round=down (§16). */
    function frameAt(srcTime, fps) {
        return Math.max(0, Math.floor(srcTime * fps + 1e-6));
    }

    function build(track) {
        const order = DEMUX.displayOrder(track);          // display pos -> sample idx
        const displayOf = new Int32Array(track.sampleCount);
        for (let d = 0; d < order.length; d++) displayOf[order[d]] = d;
        const ptsSec = new Float64Array(track.sampleCount);
        for (let i = 0; i < track.sampleCount; i++) ptsSec[i] = track.pts[i] / track.timescale;
        const syncSamples = [];
        for (let i = 0; i < track.sampleCount; i++) {
            if (track.sync[i]) syncSamples.push({ sample: i, display: displayOf[i] });
        }
        return {
            track: track,
            order: order,
            displayOf: displayOf,
            ptsSec: ptsSec,
            syncSamples: syncSamples,
            frameCount: track.sampleCount,
            // display position of a source time
            displayIndexAt(t) { return Math.min(frameAt(t, this.fps), this.frameCount - 1); },
            fps: DEMUX.guessFps(track)
        };
    }

    /** Decode plan for a display position: from which sample to feed the decoder. */
    function decodePlan(index, displayPos) {
        if (!index.frameCount) return null;
        displayPos = Math.max(0, Math.min(displayPos, index.frameCount - 1));
        const sample = index.order[displayPos];
        // nearest sync at or before (by decode order) the target sample
        let startSample = 0;
        for (let i = index.syncSamples.length - 1; i >= 0; i--) {
            if (index.syncSamples[i].sample <= sample) { startSample = index.syncSamples[i].sample; break; }
        }
        return { startSample: startSample, targetSample: sample, targetDisplay: displayPos };
    }

    /** True when frame at displayPos is itself a sync sample (no GOP walk). */
    function isSync(index, displayPos) {
        return !!index.track.sync[index.order[displayPos]];
    }

    return { frameAt: frameAt, build: build, decodePlan: decodePlan, isSync: isSync };
});
