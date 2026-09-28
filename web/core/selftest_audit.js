/* Kick Clip Studio — web/core/selftest_audit.js
 * Regression checks for the audit fixes that are testable in Node:
 *   - text layout never drops words (fitLayout pages) and stays ≤2 rows/page
 *   - style id aliases (mrbeast -> mrbeast_3d)
 *   - composer ramp == shared timeRemap curve (preview == export), duration preserving
 *   - yuv420 chroma is the true 2x2 mean
 * Run: node web/core/selftest_audit.js */
"use strict";
const TXT = require("./text/canvasText.js");
const TR = require("./timeRemap.js");
const COMP = require("./render/composer.js");
const YUV = require("./render/yuv.js");

let failures = 0;
function check(cond, label, extra) {
    if (cond) console.log("  PASS  " + label);
    else { console.log("  FAIL  " + label + (extra != null ? "  " + extra : "")); failures++; }
}

console.log("\n[text layout: no lost words]");
{
    const phrase = "ЭТО ОЧЕНЬ ДЛИННАЯ РУССКАЯ ФРАЗА КОТОРАЯ РАНЬШЕ ТЕРЯЛА СЛОВА ПОСЛЕ ВТОРОЙ СТРОКИ И ЭТО БЫЛО ПЛОХО";
    const words = phrase.split(" ").map((w, i) => ({ text: w, s: i * 0.25 }));
    const measure = (s, sc) => s.length * 38 * sc;
    const fit = TXT.fitLayout(words, measure, 1000, 2, 0.72);
    const shown = [].concat(...fit.pages.map(p => [].concat(...p)));
    check(shown.length === words.length, "every word lands on some page", shown.length + "/" + words.length);
    check(fit.pages.every(p => p.length <= 2), "≤2 rows per page");
    check(TXT.pageAt(fit.pages, 0) === 0 && TXT.pageAt(fit.pages, 99) === fit.pages.length - 1,
          "page follows the active word");
    const short = TXT.fitLayout(words.slice(0, 3), measure, 1000, 2, 0.72);
    check(short.pages.length === 1 && short.scale === 1, "short phrase: one page, full size");
    check(TXT.layoutLines(words, s => measure(s, 1), 1000).reduce((a, l) => a + l.length, 0) === words.length,
          "layoutLines keeps all words");
    check(TXT.resolveStyleName("mrbeast") === "mrbeast_3d", "UI id 'mrbeast' resolves to styles.json 'mrbeast_3d'");
    const c = TXT.clampToSafe(1080, 1900, 400, 200, 1080, 1920);
    check(c.x + 200 <= 1040 + 1e-6 && c.y + 100 <= 1650 + 1e-6, "text block clamped to the safe zone");
}

console.log("\n[ramp: preview == export curve]");
{
    const comp = {
        version: 3, canvas: { w: 1080, h: 1920, fps: 60, bg: "#000" }, duration: 3,
        assets: { src: { path: "x.mp4", w: 1280, h: 720, fps: 60 } },
        layers: [
            { id: "bg", type: "video", asset: "src", z: 0, time: { in: 0, out: 3, srcIn: 0 },
              crop: { space: "source", x: 0, y: 0, w: 1, h: 1 } },
            { id: "fxr", type: "fx", kind: "ramp", in: 0.6, out: 1.2 }
        ]
    };
    let maxErr = 0;
    for (let f = 36; f <= 72; f++) {
        const srcT = COMP.renderFrame(comp, f, {}).ops[0].srcT;
        const want = TR.remapTime(f / 60, [{ kind: "ramp", in: 0.6, out: 1.2 }]);
        maxErr = Math.max(maxErr, Math.abs(srcT - want));
    }
    check(maxErr < 1e-9, "composer ramp == timeRemap.js curve", maxErr.toExponential(2));
    const end = COMP.renderFrame(comp, 72, {}).ops[0].srcT;
    const after = COMP.renderFrame(comp, 73, {}).ops[0].srcT;
    check(Math.abs(end - 1.2) < 1e-9 && after > end, "duration preserving: back in sync, no jump at the window end",
          end.toFixed(4) + " -> " + after.toFixed(4));
}

console.log("\n[yuv420: true 2x2 chroma mean]");
{
    const w = 2, h = 2, rgba = new Uint8Array(16);
    const px = [[255, 0, 0], [0, 0, 255], [0, 255, 0], [255, 255, 255]];
    px.forEach((c, i) => { rgba[i * 4] = c[0]; rgba[i * 4 + 1] = c[1]; rgba[i * 4 + 2] = c[2]; rgba[i * 4 + 3] = 255; });
    const pl = YUV.packYuv420(rgba, w, h);
    let cb = 0, cr = 0;
    px.forEach(c => { const y = YUV.rgb2yuv709(c[0] / 255, c[1] / 255, c[2] / 255); cb += y.Cb; cr += y.Cr; });
    cb /= 4; cr /= 4;
    check(Math.abs(pl.u[0] - cb) <= 1 && Math.abs(pl.v[0] - cr) <= 1, "U/V = mean of the 4 pixels",
          "u=" + pl.u[0] + " want " + cb.toFixed(1) + ", v=" + pl.v[0] + " want " + cr.toFixed(1));
}

console.log("\n" + (failures ? "AUDIT SELFTEST FAILED: " + failures : "ALL AUDIT SELFTESTS PASSED"));
process.exit(failures ? 1 : 0);
