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

console.log("\n" + (failures ? "SELFTEST FAILED: " + failures : "ALL CORE SELFTESTS PASSED"));
process.exit(failures ? 1 : 0);
