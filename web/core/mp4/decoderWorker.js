/* Kick Clip Studio — web/core/mp4/decoderWorker.js
 * PLAN §16 P1: one worker per asset. Fetches the MP4, demuxes the avc1 track,
 * drives a WebCodecs VideoDecoder (decodeQueueSize ≤ 4), keeps a ring cache
 * of ≤ 12 decoded frames (LRU, close() on eviction) and ships a CLONE of the
 * requested frame to the main thread (which closes it after drawing).
 *
 * Protocol in:  {type:'init', url}  {type:'frame', t, fps}  {type:'reset'}  {type:'close'}
 * Protocol out: {type:'ready', codec, frameCount, fps, width, height, description}
 *               {type:'far', t}                       // scrub jump: use the proxy
 *               {type:'frame', display, t, frame}     // frame is transferred
 *               {type:'error', message}
 */
"use strict";
importScripts("core/mp4/demux.js", "core/mp4/frameIndex.js", "core/mp4/ringCache.js");

const RING_CAP = 12;            // §16 P1: ring cache ≤ 12 VideoFrames
const MAX_QUEUE = 4;            // decodeQueueSize ≤ 4
const SCRUB_LIMIT_SEC = 1.5;    // beyond this -> proxy preview, decode continues

let fileBuf = null;
let track = null;
let index = null;
let decoder = null;
let cache = null;
let lastTarget = -1e9;
let busy = false;
const pending = [];

// decode-order bookkeeping: outputs arrive from submitBase upwards
let submitBase = 0;
let outputCounter = 0;

const waiters = [];
function drainWaiters() {
    while (waiters.length && decoder && decoder.decodeQueueSize <= MAX_QUEUE) {
        waiters.shift()();
    }
}
function waitQueue() {
    return new Promise(resolve => waiters.push(resolve));
}

function out(msg, transfer) { self.postMessage(msg, transfer || []); }

function sampleBytes(sampleIdx) {
    const start = track.offsets[sampleIdx];
    const size = track.sizes[sampleIdx];
    return fileBuf.subarray(start, start + size);
}

function feed(sampleIdx) {
    const chunk = new EncodedVideoChunk({
        type: track.sync[sampleIdx] ? "key" : "delta",
        timestamp: Math.round(track.pts[sampleIdx] / track.timescale * 1e6),
        duration: Math.round((track.durations[sampleIdx] || 0) / track.timescale * 1e6),
        data: sampleBytes(sampleIdx)
    });
    decoder.decode(chunk);
}

async function handleFrame(t, fps) {
    // §16 P1 frame selection: floor(src·fps + 1e-6)
    const displayPos = CoreFrameIndex.frameAt(t, fps || index.fps);
    const clamped = Math.max(0, Math.min(displayPos, index.frameCount - 1));
    const dtSec = Math.abs((clamped - lastTarget) / (fps || index.fps));
    const isFar = lastTarget !== -1e9 && dtSec > SCRUB_LIMIT_SEC;
    lastTarget = clamped;
    if (isFar) out({ type: "far", t: t });          // main thread shows the proxy frame

    if (cache.has(clamped)) {
        const hit = cache.get(clamped);
        const clone = hit.clone();
        out({ type: "frame", display: clamped, t: t, frame: clone }, [clone]);
        return;
    }
    const plan = CoreFrameIndex.decodePlan(index, clamped);
    if (!plan) throw new Error("empty sample table");
    submitBase = plan.startSample;
    outputCounter = 0;
    for (let s = plan.startSample; s <= plan.targetSample; s++) {
        if (decoder.decodeQueueSize > MAX_QUEUE) await waitQueue();
        feed(s);
    }
    // wait until the target sample's output landed in the cache
    const deadline = Date.now() + 3000;
    while (!cache.has(clamped) && Date.now() < deadline) {
        await new Promise(r => setTimeout(r, 4));
        drainWaiters();
    }
    const hit = cache.get(clamped);
    if (!hit) throw new Error("decode timeout for display " + clamped);
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
            cache = new CoreRingCache(RING_CAP, f => { try { f.close(); } catch (e) {} });
            decoder = new VideoDecoder({
                output(f) {
                    // outputs arrive in decode order starting at submitBase
                    const display = (submitBase + outputCounter < track.sampleCount)
                        ? index.displayOf[submitBase + outputCounter] : -1;
                    outputCounter++;
                    if (display >= 0) cache.put(display, f.clone());
                    f.close();
                    drainWaiters();
                },
                error(e) { out({ type: "error", message: String(e && e.message || e) }); }
            });
            decoder.configure({
                codec: track.codec,
                codedWidth: track.width,
                codedHeight: track.height,
                description: track.description,
                optimizeForLatency: true
            });
            out({
                type: "ready",
                codec: track.codec,
                frameCount: index.frameCount,
                fps: index.fps,
                width: track.width,
                height: track.height,
                description: null
            });
        } else if (msg.type === "frame") {
            pending.push(msg);
            if (!busy) {
                busy = true;
                while (pending.length) {
                    const m = pending.shift();
                    await handleFrame(m.t, m.fps);
                }
                busy = false;
            }
        } else if (msg.type === "reset") {
            lastTarget = -1e9;
        } else if (msg.type === "close") {
            if (decoder) { try { decoder.close(); } catch (e) {} }
            if (cache) cache.clear();
        }
    } catch (e) {
        busy = false;
        out({ type: "error", message: String(e && e.message || e) });
    }
};
