/* Node selftest for web/studio/overlay_export.js (pure parts). */
"use strict";
const assert = require("assert");
const path = require("path");
const store = {};
global.localStorage = { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = v; } };
const listeners = [];
global.document = { body: null, fonts: null, addEventListener: (t, f) => listeners.push([t, f]),
                    getElementById: () => null, createElement: () => ({ style: {} }) };
global.location = { protocol: "http:", host: "127.0.0.1:8765" };
let drawn = null;
global.window = global;
window.fetch = async () => ({ json: async () => ({}) });
window.CoreCanvasText = { drawCue: (ctx, cue) => { drawn = cue; return { ok: 1 }; } };
require(path.join(__dirname, "overlay_export.js"));

const S = window.StudioTextSmarts, O = window.StudioOverlayExport;
const words = ["и", "тут", "Шрек", "проиграл", "100", "баксов", "бля"].map((w, i) => ({ word: w, s: i * 0.2, e: i * 0.2 + 0.2 }));
const hot = S.markHotWords(words).filter(w => w.hot).map(w => w.word);
assert.deepStrictEqual(hot.sort(), ["100", "бля"].sort(), "hot=" + hot);
assert.ok(S.hotScore(words[2], 2, words) >= 0.85, "names mid-sentence are key words");
assert.strictEqual(S.hotScore(words[1], 1, words), 0, "plain words are not");
assert.strictEqual(S.markHotWords([{ word: "x", hot: true }, { word: "100" }])[1].hot, undefined, "existing flags respected");
const em = S.addEmoji([{ word: "ахаха", s: 0, e: 1 }, { word: "огонь", s: 1, e: 2 }, { word: "деньги", s: 2, e: 3 }]);
assert.deepStrictEqual(em.filter(w => w.emoji).map(w => w.word), ["😂", "🔥"]);
window.CoreCanvasText.drawCue({}, { words: words }, 0, 1080, 1920);
assert.ok(drawn.words.some(w => w.hot), "wrapper applies hot words");
window.CoreCanvasText.drawCue({}, { words: words, hotWords: false }, 0, 1080, 1920);
assert.ok(!drawn.words.some(w => w.hot), "template 'clean' disables hot words");
const clip = {
    format: "split_adhd", start_time: 100, end_time: 110, sub_size: 1, subtitle_template: "mrbeast",
    text_items: [{ text: "ОЧЕНЬ ДЛИННАЯ ФРАЗА ИЗ МНОГИХ СЛОВ", start: 1, end: 3, x: 0.5, y: 0.3 },
                 { start: 4, end: 6, words: [{ word: "а", abs_start: 104.0, abs_end: 104.3 }, { word: "б", abs_start: 104.5, abs_end: 105 }] }],
    subtitles: [{ start: 106, end: 108, text: "сгенерённый текст", words: [{ word: "сгенерённый", start: 106, end: 107 }, { word: "текст", start: 107, end: 108 }] }]
};
let cues = O.buildCues(clip, 1080, 1920);
assert.strictEqual(cues.length, 3);
assert.strictEqual(cues[0].cue.words.length, 6, "plain text split into words (no lost words)");
assert.strictEqual(cues[0].cue.y, 0.3);
assert.strictEqual(cues[1].cue.words[1].s, 0.5, "word offsets relative to the first word (editor cueAt)");
assert.strictEqual(cues[2].start, 6, "generated subs mapped source->output");
assert.strictEqual(cues[2].cue.styleName, "mrbeast");
clip.subtitle_mode = "none";
cues = O.buildCues(clip, 1080, 1920);
assert.strictEqual(cues.length, 1, "mode none: only non-ASR text items");
clip.subtitle_mode = "generated";
clip.segments = [{ start_time: 100, end_time: 102 }, { start_time: 106, end_time: 110 }];
cues = O.buildCues(clip, 1080, 1920);
const gen = cues.find(c => c.cue.words[0].word === "сгенерённый");
assert.strictEqual(gen.start, 2, "multi-segment mapping");
assert.strictEqual(O.clipDuration(clip), 6);
assert.strictEqual(O.clipDuration({ layers: [{ out_start: 2, duration: 5 }, { out_start: 0, duration: 3 }] }), 7);
assert.ok(listeners.length >= 1);
console.log("overlay_export selftest: OK");
