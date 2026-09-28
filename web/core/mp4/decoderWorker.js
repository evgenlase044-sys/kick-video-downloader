/* Kick Clip Studio — web/core/mp4/decoderWorker.js
 * PLAN §16 P1: one worker per asset; VideoDecoder (decodeQueueSize ≤ 4),
 * ring cache ≤ 12 frames (close() on eviction), clone() to main thread.
 * Audit fixes: frame index on the SOURCE fps (preview sent 60 for 30 fps
 * sources); outputs mapped by timestamp (decoders emit in presentation
 * order - B-frames were cached under wrong indices); flush() after each
 * plan so reorder-held frames come out instead of a 3 s timeout. */
"use strict";
importScripts("core/mp4/demux.js", "core/mp4/frameIndex.js", "core/mp4/ringCache.js");

const RING_CAP = 12;
const MAX_QUEUE = 4;
const SCRUB_LIMIT_SEC = 1.5;

let fileBuf = null, track = null, index = null, decoder = null, cache = null;
let lastTarget = -1e9;
let busy = false;
const pending = [];
const displayByTs = new Map();
const waiters = [];

function drainWaiters() {
    while (waiters.length && decoder && decoder.decodeQueueSize <= MAX_QUEUE) waiters.shift()();
}
function waitQueue() { return new Promise(resolve => waiters.push(resolve)); }
function out(msg, transfer) { self.postMessage(msg, transfer || []); }
function tsOf(i) { return Math.round(track.pts[i] / track.timescale * 1e6); }

function feed(i) {
    const start = track.offsets[i];
    decoder.decode(new EncodedVideoChunk({
        type: track.sync[i] ? "key" : "delta",
        timestamp: tsOf(i),
        duration: Math.round((track.durations[i] || 0) / track.timescale * 1e6),
        data: fileBuf.subarray(start, start + track.sizes[i])
    }));
}

async function handleFrame(t) {
    const srcFps = index.fps;
    const clamped = Math.max(0, Math.min(CoreFrameIndex.frameAt(t, srcFps), index.frameCount - 1));
    const isFar = lastTarget !== -1e9 && Math.abs((clamped - lastTarget) / srcFps) > SCRUB_LIMIT_SEC;
    lastTarget = clamped;
    if (isFar) out({ type: "far", t: t });
    if (!cache.has(clamped)) {
        const plan = CoreFrameIndex.decodePlan(index, clamped);
        if (!plan) throw new Error("empty sample table");
        for (let s = plan.startSample; s <= plan.targetSample; s++) {
            if (decoder.decodeQueueSize > MAX_QUEUE) await waitQueue();
            feed(s);
        }
        await decoder.flush();
    }
    const hit = cache.get(clamped);
    if (!hit) throw new Error("decode produced no frame for display " + clamped);
    const clone = hit.clone();
    out({ type: "frame", display: clamped, t: t, frame: clone }, [clone]);
}

self.onmessage = async function (ev) {
    const msg = ev.data;
    try {
        if (msg.type === "init") {
            const res = await fetch(msg.url);
            if (!res.ok) throw new Error("fetch " + msg.url + " -> " + res.status);
            fileBuf = new Uint8Array(await res.arrayBuffer());
            track = CoreDemux.parseVideoTrack(fileBuf);
            index = CoreFrameIndex.build(track);
            displayByTs.clear();
            for (let i = 0; i < track.sampleCount; i++) displayByTs.set(tsOf(i), index.displayOf[i]);
            cache = new CoreRingCache(RING_CAP, f => { try { f.close(); } catch (e) {} });
            decoder = new VideoDecoder({
                output(f) {
                    const d = displayByTs.has(f.timestamp) ? displayByTs.get(f.timestamp) : -1;
                    if (d >= 0 && !cache.has(d)) cache.put(d, f.clone());
                    f.close();
                    drainWaiters();
                },
                error(e) { out({ type: "error", message: String(e && e.message || e) }); }
            });
            decoder.configure({ codec: track.codec, codedWidth: track.width, codedHeight: track.height,
                                description: track.description, optimizeForLatency: true });
            out({ type: "ready", codec: track.codec, frameCount: index.frameCount, fps: index.fps,
                  width: track.width, height: track.height, description: null });
        } else if (msg.type === "frame") {
            pending.push(msg);
            if (!busy) {
                busy = true;
                while (pending.length) await handleFrame(pending.shift().t);
                busy = false;
            }
        } else if (msg.type === "reset") {
            lastTarget = -1e9;
        } else if (msg.type === "close") {
            if (decoder) { try { decoder.close(); } catch (e) {} }
            if (cache) cache.clear();
            fileBuf = null;
        }
    } catch (e) {
        busy = false;
        out({ type: "error", message: String(e && e.message || e) });
    }
};
