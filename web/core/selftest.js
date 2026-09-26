/* Kick Clip Studio — web/core/selftest.js
 * Node-runnable checks of the pure preview/export-shared logic (PLAN §16,
 * VERIFICATION §7.4/§7.5 gates that are testable without a browser):
 *   - frame grid + ±1/fps stepping                       (§16.5)
 *   - master-clock follower rates                        (§16.3)
 *   - split from ONE file -> both bands same sourceId    (§7.4 clap gate)
 *   - word_pop_spring overshoot 18%±2 / settle 300±30ms  (§7.5)
 *   - word visible frame == ASS start frame ± 1          (§7.4)
 *   - own 65^3 LUT parses and samples trilinearly        (§14.6)
 * Run: node web/core/selftest.js  [--lut ../../tv_grade.cube]   */
"use strict";
const TM = require("./timeMap.js");
const GEO = require("./geometry.js");
const LUT = require("./lut3d.js");
const TXT = require("./text/canvasText.js");
const DEMUX = require("./mp4/demux.js");
const FI = require("./mp4/frameIndex.js");
const RingCache = require("./mp4/ringCache.js");
const CMP = require("./composition.js");
const COMP = require("./render/composer.js");

let failures = 0, current = "";
function check(cond, label, extra) {
    if (cond) console.log("  PASS  " + label);
    else { console.log("  FAIL  " + label + (extra != null ? "  " + extra : "")); failures++; }
}
function section(name) { current = name; console.log("\n[" + name + "]"); }

// ── frame grid ──────────────────────────────────────────────────────────
section("frame grid (§16.5)");
check(TM.frameSnap(1.234567, 60) === Math.round(1.234567 * 60) / 60, "frameSnap snaps to 1/60 grid");
check(TM.frameSnap(0.008, 60) === 0 && Math.abs(TM.frameSnap(0.012, 60) - 1 / 60) < 1e-9,
      "frameSnap rounds to nearest frame");
check(TM.stepFrames(1.0, 60, 1) === 1.0 + 1 / 60 || Math.abs(TM.stepFrames(1.0, 60, 1) - (60 + 1) / 60) < 1e-9,
      "stepFrames +1 on the grid");
check(Math.abs(TM.stepFrames(2 / 60, 60, -1) - 1 / 60) < 1e-9, "stepFrames -1 on the grid");

// ── master clock follower ───────────────────────────────────────────────
section("master clock (§16.3)");
check(TM.clockCorrection(1.000, 1.000).action === "none", "no drift -> none");
check(TM.clockCorrection(1.020, 1.000).action === "rate" && TM.clockCorrection(1.020, 1.000).rate === 0.97,
      "video 20ms ahead -> rate 0.97");
check(TM.clockCorrection(0.980, 1.000).action === "rate" && TM.clockCorrection(0.980, 1.000).rate === 1.03,
      "video 20ms behind -> rate 1.03");
check(TM.clockCorrection(1.200, 1.000).action === "seek", "200ms drift -> seek");
check(TM.clockCorrection(1.1501, 1.000).action === "seek", "just beyond 150ms drift -> seek (§16.3: > 150ms)");
check(TM.clockCorrection(1.090, 1.000).action === "rate", "90ms drift -> rate");

// ── geometry: split from one file is frame-synced by construction ───────
section("split sync (§7.4 clap gate)");
const ops = GEO.composeDrawOps({
    format: "split_adhd", srcW: 1280, srcH: 720, outW: 1080, outH: 1920,
    cropBox: { x: 0.6, y: 0.05, w: 0.4, h: 0.4 }, bgBox: { x: 0, y: 0, w: 1, h: 1 },
    sourceId: "one_file.mp4"
});
check(ops.length === 2, "split produces top+bottom bands", ops.length);
check(ops[0].band === "top" && ops[1].band === "bottom", "band order");
check(ops.every(o => o.sourceId === "one_file.mp4"),
      "BOTH halves carry the same sourceId (one <video>, one decoded frame)");
check(Math.abs((ops[0].dh) - Math.round(1920 * 0.45 / 2) * 2) < 1 && ops[0].dy === 0 && ops[1].dy === ops[0].dh,
      "bands tile the canvas without gaps", JSON.stringify([ops[0].dh, ops[1].dy]));
check(ops[0].sx >= 0 && ops[0].sx + ops[0].sw <= 1280 + 1e-6 && ops[0].sy >= 0 && ops[0].sy + ops[0].sh <= 720 + 1e-6,
      "top band source rect inside frame");
const full = GEO.composeDrawOps({ format: "fullscreen", srcW: 1280, srcH: 720, outW: 1080, outH: 1920, sourceId: "f.mp4" });
check(full.length === 1 && full[0].dw === 1080 && full[0].dh === 1920, "fullscreen covers the canvas");

// ── word_pop_spring (§7.5): overshoot 18%±2, settle 300±30 ms ───────────
section("word_pop_spring (§7.5)");
const p = TM.springParams(0.18, 0.30);
let peak = 0, peakT = 0, settled = 0;
for (let i = 0; i <= 3000; i++) {
    const t = i / 10000;
    const v = TM.spring(t, p);
    if (v > peak) { peak = v; peakT = t; }
    if (Math.abs(v - 1) >= 0.02) settled = t;   // last time outside the ±2% band
}
settled += 0.0001;                              // settles right after
const overshootPct = (peak - 1) * 100;
check(Math.abs(overshootPct - 18) <= 2, "overshoot 18% ±2", overshootPct.toFixed(2) + "%");
check(Math.abs(settled - 0.30) <= 0.03, "settle 300 ms ±30", (settled * 1000).toFixed(0) + " ms");
check(Math.abs(TM.spring(0, p)) < 1e-6, "spring starts at 0");

// ── word frame parity preview vs ASS (§7.4) ─────────────────────────────
section("word frame parity (§7.4)");
for (const s of [0.0, 0.017, 0.123, 1.5, 2.9833]) {
    const par = TXT.wordFrameParity({ s: s }, 60);
    check(par.delta <= 1, "word @ " + s + "s: preview frame vs ASS start frame ±1",
          "preview=" + par.preview + " ass=" + par.ass);
}
const ws0 = TXT.wordState({ word: "ТЕСТ", s: 0.5, e: 1.0 }, 0.4, TXT.styles.styles.viral_italic);
check(ws0 === null, "word invisible before s");
let maxScale = 0;
for (let i = 1; i <= 20; i++) {
    const st = TXT.wordState({ word: "ТЕСТ", s: 0.5, e: 1.0 }, 0.5 + i / 100, TXT.styles.styles.viral_italic);
    if (st) maxScale = Math.max(maxScale, st.scale);
}
check(maxScale > 1.05 && maxScale < 1.12, "word pop overshoot peak scale ~1.08 (18% of 0.55->1 travel)", maxScale.toFixed(3));
const ws1 = TXT.wordState({ word: "ТЕСТ", s: 0.5, e: 1.0 }, 0.55, TXT.styles.styles.viral_italic);
check(ws1 && ws1.visible && ws1.opacity > 0 && ws1.scale > 0.7, "word rises from 0.55 immediately after s",
      ws1 && JSON.stringify({ scale: +ws1.scale.toFixed(3), opacity: +ws1.opacity.toFixed(2) }));
const ws2 = TXT.wordState({ word: "ТЕСТ", s: 0.5, e: 1.0 }, 2.0, TXT.styles.styles.viral_italic, { cueEnd: 1.0 });
check(ws2 === null, "word fades out by cue end + out window");

// ── own LUT parses and samples (§14.6) ──────────────────────────────────
section("own 65^3 LUT (§14.6)");
const fs = require("fs");
const path = require("path");
const lutPath = path.join(__dirname, "..", "..", "tv_grade.cube");
const lut = LUT.parseCube(fs.readFileSync(lutPath, "utf8"));
check(lut.N === 65, "LUT_3D_SIZE 65", lut.N);
check(lut.title.indexOf("Kick Clip Studio") >= 0, "own preset title", lut.title);
const black = LUT.sample(lut, 0, 0, 0);
const white = LUT.sample(lut, 1, 1, 1);
check(black.every(v => v < 0.1), "blacks stay near black", JSON.stringify(black));
check(white.every(v => v > 0.9), "whites stay near white", JSON.stringify(white));
const mid = LUT.sample(lut, 0.5, 0.5, 0.5);
check(mid.every(v => isFinite(v) && v >= 0 && v <= 1), "mid sample in range", JSON.stringify(mid));
// trilinear: sample exactly at a grid node must equal the stored value
const n1 = lut.N - 1;
const g = LUT.sample(lut, 0.25, 0.25, 0.25);
const gx = Math.round(0.25 * n1);
const stored = [lut.data[(((gx * lut.N) + gx) * lut.N + gx) * 3],
                lut.data[(((gx * lut.N) + gx) * lut.N + gx) * 3 + 1],
                lut.data[(((gx * lut.N) + gx) * lut.N + gx) * 3 + 2]];
check(Math.abs(g[0] - stored[0]) < 1e-6, "node sampling == stored value");

// ── P1: demux + frame index (§16 P1) ───────────────────────────────────
section("P1 demux + frame index (§16)");
const fs2 = require("fs");
const path2 = require("path");
const testMp4 = path2.join(__dirname, "..", "..", "scratch", "_demux_test.mp4");
if (fs2.existsSync(testMp4)) {
    const track = DEMUX.parseVideoTrack(fs2.readFileSync(testMp4));
    check(track.codec.startsWith("avc1."), "codec string from avcC", track.codec);
    check(track.description && track.description.length > 8, "avcC description extracted");
    check(track.sampleCount === 60 && Math.abs(track.duration - 2.0) < 0.01,
          "sample table complete", track.sampleCount + " samples, " + track.duration.toFixed(2) + "s");
    const idx = FI.build(track);
    // §16 P1 frame selection: floor(src·fps + 1e-6)
    check(FI.frameAt(0.0, 30) === 0 && FI.frameAt(0.0333, 30) === 0 && FI.frameAt(0.034, 30) === 1,
          "frameAt = floor(src*fps + 1e-6)");
    check(FI.frameAt(1.999, 30) === 59, "frameAt at the end");
    const plan = FI.decodePlan(idx, 17);
    check(plan && plan.startSample <= plan.targetSample, "decode plan: sync <= target",
          JSON.stringify(plan));
    // B-frames: display order differs from decode order
    let swapped = false;
    for (let i = 0; i < idx.order.length; i++) if (idx.order[i] !== i) { swapped = true; break; }
    check(swapped, "B-frame display order handled");
    // pts non-decreasing in display order
    let mono = true;
    for (let i = 1; i < idx.order.length; i++) {
        if (idx.ptsSec[idx.order[i]] < idx.ptsSec[idx.order[i - 1]] - 1e-6) { mono = false; break; }
    }
    check(mono, "display pts monotonic");
} else {
    console.log("  SKIP  " + testMp4 + " not generated");
}

// ── P1: ring cache ≤12 with close() accounting ─────────────────────────
section("P1 ring cache (§16)");
{
    let closed = [];
    const rc = new RingCache(12, f => closed.push(f));
    for (let i = 0; i < 20; i++) rc.put(i, { n: i });
    check(rc.size === 12, "capacity respected", rc.size);
    check(closed.length === 8, "evicted frames closed (no leaks)", closed.length);
    check(closed.every((f, i) => f.n === i), "LRU eviction order");
    rc.put(5, { n: 5 });
    check(rc.get(5).n === 5, "LRU get refreshes");
    rc.clear();
    check(rc.closed === 21, "clear closes everything (incl. re-insert eviction)", rc.closed);
}

// ── шаг 1: composition mapTime / evalAnim (§8) ─────────────────────────
section("шаг 1 mapTime + evalAnim (§8)");
{
    const layer = { time: { in: 3, srcIn: 2512.3 } };
    const mt = CMP.mapTime(layer, 5);
    check(Math.abs(mt.local - 2) < 1e-9 && Math.abs(mt.src - 2514.3) < 1e-9, "mapTime linear");
    const ramp = { time: { in: 0, srcIn: 0, speed: { k: [[0, 1], [1, 0.5], [2, 2]] } } };
    const m1 = CMP.mapTime(ramp, 1);
    check(Math.abs(m1.src - 0.75) < 1e-6, "speed ramp integral 0..1s = 0.75", m1.src.toFixed(4));
    const m2 = CMP.mapTime(ramp, 2);
    check(Math.abs(m2.src - 2.0) < 1e-6, "speed ramp integral 0..2s = 2.0", m2.src.toFixed(4));
    check(CMP.evalAnim(0.5, 0) === 0.5, "static value");
    const kf = { k: [[0, 0], [1, 100, "linear"], [2, 100]] };
    check(Math.abs(CMP.evalAnim(kf, 0.5) - 50) < 1e-9, "linear keyframes");
    const hold = { k: [[0, 7, "hold"], [1, 9]] };
    check(CMP.evalAnim(hold, 0.5) === 7 && CMP.evalAnim(hold, 1.5) === 9, "hold then jump");
    const snap = { k: [[0, 0, "snap"], [1, 10]] };
    check(CMP.evalAnim(snap, 0.5) > 9, "snap ease fast-out", CMP.evalAnim(snap, 0.5).toFixed(2));
    const bez = { k: [[0, 0], [1, 1, ["bezier", 0.33, 0, 0.67, 1]]] };
    check(Math.abs(CMP.evalAnim(bez, 0.5) - 0.5) < 0.05, "ease bezier symmetric", CMP.evalAnim(bez, 0.5).toFixed(3));
    const spr = { spring: { O: 0.18, Ts: 0.3 }, from: 0, to: 1, at: 0 };
    let peak = 0;
    for (let i = 0; i <= 3000; i++) peak = Math.max(peak, CMP.evalAnim(spr, i / 10000));
    check(Math.abs((peak - 1) * 100 - 18) <= 2, "spring evalAnim overshoot 18%±2", ((peak - 1) * 100).toFixed(1) + "%");
    check(CMP.evalAnim(spr, -0.1) === 0, "spring holds `from` before `at`");
    const keys = [{ t: 0, x: 0.5, y: 0.5, w: 0.1, h: 0.1 }, { t: 1, x: 0.52, y: 0.5, w: 0.1, h: 0.1 }];
    const fc = CMP.followCam(keys, { deadZone: 0.04, maxSpeed: 0.6, Ts: 0.35, sampleFps: 60 });
    const c0 = fc(0.5);
    check(Math.abs(c0.x - 0.5) < 0.005, "follow-cam dead zone keeps crop still", c0.x.toFixed(4));
    const far = CMP.followCam([{ t: 0, x: 0.5, y: 0.5 }, { t: 1, x: 0.9, y: 0.5 }],
                              { deadZone: 0.01, maxSpeed: 0.6, Ts: 0.35, sampleFps: 60 })(1.0);
    check(far.x > 0.75 && far.x < 0.9, "follow-cam follows within max speed", far.x.toFixed(3));
}

// ── шаг 1: composer draw list + scale parity SSIM (§7.4) ───────────────
section("шаг 1 composer + scale parity (§7.4)");
{
    const comp = {
        version: 3, canvas: { w: 1080, h: 1920, fps: 60, bg: "#000" }, duration: 2,
        assets: { src: { path: "x.mp4", w: 1280, h: 720, fps: 60 } },
        layers: [
            { id: "bg", type: "video", asset: "src", z: 0,
              time: { in: 0, out: 2, srcIn: 10 },
              crop: { space: "source", x: 0.05, y: 0.1, w: 0.9, h: 0.8 },
              effects: [{ type: "grade", preset: "viral_punch" }] },
            { id: "cam", type: "video", asset: "src", z: 1,
              time: { in: 0, out: 2, srcIn: 10 },
              crop: { space: "source", x: 0.6, y: 0.05, w: 0.35, h: 0.35 },
              pip: { x: 0.688, y: 0.018, w: 0.30 } },
            { id: "fx1", type: "fx", kind: "flash", in: 0.4, out: 0.58, color: "white", peak: 0.85 }
        ]
    };
    const frame = COMP.renderFrame(comp, 30, { scale: 1 });
    check(frame.w === 1080 && frame.h === 1920 && frame.t === 0.5, "renderFrame frame -> t = f/fps");
    check(frame.ops.filter(o => o.op === "video").length === 2, "two video layers in draw list");
    check(frame.grade.on === true, "grade flag from effects");
    check(frame.ops.every(o => o.op !== "video" || (o.sn && o.dn)), "normalized sn/dn rects on video ops");
    check(Math.abs(COMP.flashEnvelope(0) - 0) < 1e-9 && Math.abs(COMP.flashEnvelope(0.12) - 1) < 1e-9,
          "flash envelope: attack to peak at 12%");
    check(Math.abs(COMP.flashEnvelope(0.5) - Math.exp(-0.38 * 4.2)) < 1e-9, "flash envelope: exp decay");
    // §7.4 scale parity: SSIM >= 0.99 on 50 points, grain off
    const lut = LUT.parseCube(fs2.readFileSync(path2.join(__dirname, "..", "..", "tv_grade.cube"), "utf8"));
    const opts = { lut: lut, sourcePixel: (a, su, sv, st) =>
        [0.5 + 0.5 * Math.sin(su * 6.28 + st), 0.5 + 0.5 * Math.cos(sv * 6.28), 0.5] };
    const ssim = COMP.scaleParity(comp, 30, opts, 50, 0.4);
    check(ssim >= 0.99, "scale parity SSIM >= 0.99 on 50 points (scale 1 vs 0.4)", ssim.toFixed(5));
    const ssim2 = COMP.scaleParity(comp, 90, opts, 50, 0.25);
    check(ssim2 >= 0.99, "scale parity SSIM >= 0.99 at another frame/scale", ssim2.toFixed(5));
}

// ── шаг 2: golden-кадры эффектов §7.5 (детерминированная математика) ────
section("шаг 2 golden: SDF/Kawase/motion blur/эффекты §15 (§7.5)");
{
    const GOLD = require("./render/golden.json");
    const E = require("./render/effects.js");
    const YUV = require("./render/yuv.js");
    // §12.8 noise golden
    check(E.pcg(1) === GOLD.pcg["1"] && E.pcg(42) === GOLD.pcg["42"] &&
          E.pcg(0xdeadbeef) === GOLD.pcg["3735928559"], "pcg hash golden");
    check(Math.abs(E.noise1(7, 0.5) - GOLD.noise1["7_0.5"]) < 1e-6 &&
          Math.abs(E.noise1(7, 3.5) - GOLD.noise1["7_3.5"]) < 1e-6, "value noise golden");
    // JFA golden: 8x8, pixel at (3,4)
    const Wj = 8, Hj = 8, mj = new Uint8Array(Wj * Hj);
    mj[4 * Wj + 3] = 255;
    const dj = E.jumpFlood(mj, Wj, Hj);
    check(dj[4 * Wj + 3] === GOLD.jfa_8x8.center &&
          Math.abs(dj[4 * Wj + 0] - GOLD.jfa_8x8.left3) < 1e-6 &&
          Math.abs(dj[7 * Wj + 7] - GOLD.jfa_8x8.diag) < 1e-6, "jump-flood distance golden");
    check(E.strokeAlpha(0, 1) === GOLD.stroke_r1.d0 &&
          Math.abs(E.strokeAlpha(1, 1) - GOLD.stroke_r1.d1) < 1e-9 &&
          E.strokeAlpha(2, 1) === GOLD.stroke_r1.d2, "SDF stroke smoothstep golden");
    // Kawase: energy conservation + spread
    const Wk = 32, Hk = 32, src = new Float32Array(Wk * Hk);
    src[16 * Wk + 16] = 255;
    const bl = E.kawaseBlur(src, Wk, Hk, 2);
    let sum = 0, maxv = 0;
    for (const v of bl) { sum += v; maxv = Math.max(maxv, v); }
    check(Math.abs(sum - GOLD.kawase2_impulse_255.energy) < 0.5, "Kawase energy preserved", sum.toFixed(1));
    check(maxv > 0 && maxv < 255, "Kawase spreads the impulse", maxv.toFixed(2));
    // glow coupling: no glow without text (§7.2), opacity^1.5
    check(E.glowAlpha(0, 0.5) === GOLD.glowAlpha.o0, "glow alpha is ZERO when word opacity is 0");
    check(Math.abs(E.glowAlpha(0.5, 0.5) - GOLD.glowAlpha["o05_0.5"]) < 1e-4, "glowAlpha = opacity^1.5 * amount");
    // zoom punch golden
    const zp = E.zoomPunch(0.1, { A: 0.15, overshoot: 0.12, settleMs: 220 });
    check(Math.abs(zp.scale - GOLD.zoomPunch.scale_100ms_A015) < 1e-4, "zoom punch scale golden", zp.scale.toFixed(5));
    let peak = 0;
    for (let i = 0; i <= 400; i++) peak = Math.max(peak, E.zoomPunch(i / 1000, { A: 0.15, overshoot: 0.12, settleMs: 220 }).scale);
    check(Math.abs(peak - GOLD.zoomPunch.peakScale_A015_O012) < GOLD.zoomPunch.peakTolerance,
          "zoom punch peak = 1 + A*(1+overshoot)", peak.toFixed(5));
    // shake golden + constant overscan (N11)
    const sh = E.shake(0.2, { amp: 14, freq: 9, tauMs: 120, seed: 7, dur: 0.35, W: 1080 });
    check(Math.abs(sh.dx - GOLD.shake_seed7.dx_200ms) < 1e-4 &&
          Math.abs(sh.dy - GOLD.shake_seed7.dy_200ms) < 1e-4 &&
          Math.abs(sh.rot - GOLD.shake_seed7.rot_200ms) < 1e-4 &&
          Math.abs(sh.env - GOLD.shake_seed7.env_200ms) < 1e-4, "shake state golden (seed 7 @200ms)");
    const sh0 = E.shake(2.0, { amp: 14, freq: 9, tauMs: 120, seed: 7, dur: 0.35, W: 1080 });
    check(sh0.env === 0 && sh0.dx === 0, "shake is zero after its duration (no permanent shake)");
    check(Math.abs(sh.overscan - GOLD.shake_seed7.overscan_amp14_w1080) < 1e-6,
          "shake constant overscan 1+2*amp/W (N11)");
    // §17.2 YUV pack: BT.709 limited, plane sizes, formula fidelity
    const Yl = YUV.rgb2yuv709(1, 1, 1);
    check(Math.abs(Yl.Y - 235) < 1e-9 && Math.abs(Yl.Cb - 128) < 1e-9, "BT.709 white = Y235 Cb128");
    const Yb = YUV.rgb2yuv709(0, 0, 0);
    check(Math.abs(Yb.Y - 16) < 1e-9 && Math.abs(Yb.Cb - 128) < 1e-9, "BT.709 black = Y16");
    const wT = 16, hT = 16, rgba = new Uint8Array(wT * hT * 4);
    let acc = 7;
    for (let i = 0; i < rgba.length; i += 4) {
        acc = (acc * 1103515245 + 12345) >>> 0;
        rgba[i] = acc & 255; rgba[i + 1] = (acc >> 8) & 255; rgba[i + 2] = (acc >> 16) & 255; rgba[i + 3] = 255;
    }
    const pl = YUV.packYuv420(rgba, wT, hT);
    check(pl.y.length === wT * hT && pl.u.length === wT * hT / 4 && pl.v.length === wT * hT / 4,
          "yuv420 plane sizes");
    let maxErr = 0;
    for (let y = 0; y < hT; y++) {
        for (let x = 0; x < wT; x++) {
            const i = (y * wT + x) * 4;
            const c = YUV.rgb2yuv709(rgba[i] / 255, rgba[i + 1] / 255, rgba[i + 2] / 255);
            maxErr = Math.max(maxErr, Math.abs(pl.y[y * wT + x] - c.Y));
        }
    }
    check(maxErr <= 1.0, "Y plane within 1 LSB of the BT.709 formula", maxErr.toFixed(3));
    const raw = YUV.interleave(pl);
    check(raw.length === wT * hT * 3 / 2, "raw frame = w*h*1.5 bytes (WS protocol)");
}

console.log("\n" + (failures ? "SELFTEST FAILED: " + failures : "ALL CORE SELFTESTS PASSED"));
process.exit(failures ? 1 : 0);
