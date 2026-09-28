/* Kick Clip Studio — web/core/text/canvasText.js
 * PLAN §12 (seed)/§16.4: canvas text engine — the SAME deterministic
 * time-functions the export renderer will use. No CSS animations, no
 * wall-clock: every property is a pure function of cue-local time.
 * Pure parts are Node-compatible (UMD) for verification.
 *
 * Audit fixes:
 *  - no more lost words: layout is max 2 rows (Shorts readability); when a
 *    phrase does not fit, the font shrinks (down to 72%), and if it still
 *    does not fit the cue is split into PAGES of ≤2 rows; the page holding
 *    the active word is shown. Every word is shown at some point.
 *  - karaoke: the active word is highlighted (style.activeColor), hot words
 *    use the accent colour; pop strength scales with word importance.
 *  - animators wave / shimmer / rise / spin / tremble implemented.
 *  - text is clamped to the 1080x1920 safe zone (x 40..1040, y 150..1650). */
(function (root, factory) {
    const mod = factory();
    if (typeof module !== "undefined" && module.exports) module.exports = mod;
    root.CoreCanvasText = mod;
})(typeof self !== "undefined" ? self : this, function () {
    "use strict";
    const TM = (typeof CoreTimeMap !== "undefined") ? CoreTimeMap : require("../timeMap.js");
    const _EMBED = (function () {
        try { return require("../styles.json"); } catch (e) {
            return {
                animators: {
                    word_pop_spring: { scaleFrom: 0.55, overshoot: 0.18, settleMs: 300, opacityMs: 50, blurFrom: 6, blurMs: 90 },
                    char_type: { msPerGrapheme: 38 }, slam: { scaleFrom: 2.2, easeInMs: 120 },
                    out_blur_fade: { ms: 180, blurTo: 10, scaleTo: 0.94 }, none: {}
                },
                styles: { viral_italic: { weight: "900", caps: true, color: "#FFFFFF", accent: "#FF2B2B", stroke: 0.07, glow: 0.35, animatorIn: "word_pop_spring" } }
            };
        }
    })();
    function STYLES() {
        if (typeof self !== "undefined" && self.STYLES_JSON) return self.STYLES_JSON;
        return _EMBED;
    }

    // UI ids that differ from styles.json ids (mrbeast -> mrbeast_3d etc.)
    const STYLE_ALIASES = { mrbeast: "mrbeast_3d", mr_beast: "mrbeast_3d", beast: "mrbeast_3d" };
    function resolveStyleName(name) {
        const SM = STYLES();
        const styles = SM.styles || {};
        if (name && styles[name]) return name;
        const alias = STYLE_ALIASES[String(name || "").toLowerCase()];
        if (alias && styles[alias]) return alias;
        if (name) {
            const n = String(name).toLowerCase();
            for (const k of Object.keys(styles)) {
                if (k.toLowerCase() === n || k.toLowerCase().split("_")[0] === n) return k;
            }
        }
        return styles.viral_italic ? "viral_italic" : Object.keys(styles)[0];
    }

    // 1080x1920 safe zone (UI of TikTok/Shorts/Reels: right button column, captions at the bottom)
    const SAFE = { x0: 40 / 1080, x1: 1040 / 1080, y0: 150 / 1920, y1: 1650 / 1920 };

    function graphemes(s) { return Array.from(String(s || "")); }

    /** Importance 0..1: hot/flagged words and numbers pop harder. */
    function importance(word) {
        if (word.importance != null) return Math.max(0, Math.min(1, +word.importance));
        if (word.hot) return 1;
        const t = String(word.word != null ? word.word : word.text || "");
        if (/\d/.test(t)) return 0.8;
        if (/[!?]/.test(t)) return 0.7;
        return 0.35;
    }

    /**
     * Per-word state at cue-local time t (seconds), deterministic (§12.6).
     * Returns null when the word is not yet visible.
     */
    function wordState(word, t, style, opts) {
        const o = opts || {};
        const s = word.s != null ? word.s : 0;
        const e = word.e != null ? word.e : (s + 1.0);
        if (t < s - 1e-6) return null;
        const animName = word.anim || (style && style.animatorIn) || "word_pop_spring";
        const anim = (STYLES().animators || {})[animName] || {};
        const outAnim = (STYLES().animators || {})[(style && style.animatorOut) || "out_blur_fade"] || {};
        const cueEnd = o.cueEnd != null ? o.cueEnd : Infinity;
        const st = { visible: true, scale: 1, opacity: 1, blur: 0, glowBoost: 1, dy: 0, dx: 0, rot: 0,
                     active: t >= s && t < e, shimmer: 0 };
        const tin = t - s;
        // pop strength by importance (not the same jump on every word)
        const imp = o.emphasis === false ? 1 : (0.55 + 0.45 * importance(word));
        if (animName === "word_pop_spring") {
            const p = TM.springParams(anim.overshoot || 0.18, (anim.settleMs || 300) / 1000);
            const raw = TM.spring(tin, p);
            const from = 1 - (1 - (anim.scaleFrom || 0.55)) * imp;
            st.scale = from + (1 - from) * raw;
            st.opacity = TM.clamp01(tin / ((anim.opacityMs || 50) / 1000));
            st.blur = Math.max(0, (anim.blurFrom || 6) * (1 - TM.clamp01(tin / ((anim.blurMs || 90) / 1000))));
        } else if (animName === "slam") {
            const k = TM.clamp01(tin / ((anim.easeInMs || 120) / 1000));
            const from = 1 + ((anim.scaleFrom || 2.2) - 1) * imp;
            st.scale = from + (1 - from) * k * k;
            st.glowBoost = 1 + ((anim.glowBoost || 2) - 1) * (1 - k);
        } else if (animName === "rise") {
            const k = TM.clamp01(tin / ((anim.ms || 220) / 1000));
            const ease = 1 - Math.pow(1 - k, 3);
            st.dy = (anim.distance || 0.6) * (1 - ease);       // in font-size units
            st.opacity = k;
        } else if (animName === "spin") {
            const k = TM.clamp01(tin / ((anim.ms || 260) / 1000));
            const ease = 1 - Math.pow(1 - k, 3);
            st.rot = (anim.degrees || -90) * (1 - ease) * Math.PI / 180;
            st.scale = 0.6 + 0.4 * ease;
            st.opacity = k;
        } else if (animName === "wave") {
            st.dy = (anim.amp || 0.08) * Math.sin(2 * Math.PI * (anim.freq || 1.6) * t + (o.index || 0) * 0.7);
        } else if (animName === "tremble") {
            const a = (anim.amp || 0.035) * imp;
            st.dx = a * Math.sin(2 * Math.PI * 23 * t + (o.index || 0) * 1.3);
            st.dy = a * Math.cos(2 * Math.PI * 19 * t + (o.index || 0) * 2.1);
        } else if (animName === "shimmer") {
            st.shimmer = 0.5 + 0.5 * Math.sin(2 * Math.PI * (anim.freq || 0.8) * t - (o.index || 0) * 0.5);
        }
        // karaoke: the active word gets a small persistent lift
        if (st.active && o.karaoke !== false) st.scale *= 1 + 0.06 * imp;
        const outMs = (outAnim.ms || 180) / 1000;
        const tout = cueEnd - t;
        if (isFinite(tout) && tout < outMs && outAnim.blurTo) {
            const k = TM.clamp01(1 - tout / outMs);
            st.opacity *= (1 - k);
            st.blur = Math.max(st.blur, (outAnim.blurTo || 10) * k);
            st.scale *= 1 - (1 - (outAnim.scaleTo || 0.94)) * k;
        }
        if (st.opacity <= 0.01) return null;
        return st;
    }

    /** Greedy line wrap. NEVER drops words: returns every line it needs. */
    function layoutLines(words, measureFn, maxWidth) {
        const lines = [[]];
        let w = 0;
        const sp = measureFn(" ");
        for (const word of words) {
            const ww = measureFn(word.text);
            const need = (w > 0 ? sp : 0) + ww;
            if (w + need > maxWidth && lines[lines.length - 1].length) {
                lines.push([]);
                w = 0;
            }
            lines[lines.length - 1].push(word);
            w += (w > 0 ? sp : 0) + ww;
        }
        return lines.filter(l => l.length);
    }

    /**
     * Fit words into ≤maxLines rows: shrink the font step by step down to
     * minScale; if still too long, split into pages of ≤maxLines rows.
     * measureAt(text, scale) -> width. Returns {scale, pages:[[line,...],...]}.
     */
    function fitLayout(words, measureAt, maxWidth, maxLines, minScale) {
        const ML = maxLines || 2, MS = minScale || 0.72;
        let scale = 1;
        for (; scale >= MS - 1e-9; scale -= 0.04) {
            const sc = scale;
            const lines = layoutLines(words, s => measureAt(s, sc), maxWidth);
            if (lines.length <= ML) return { scale: sc, pages: [lines] };
        }
        scale = MS;
        const lines = layoutLines(words, s => measureAt(s, MS), maxWidth);
        const pages = [];
        for (let i = 0; i < lines.length; i += ML) pages.push(lines.slice(i, i + ML));
        return { scale: scale, pages: pages };
    }

    /** Page to show at cue-local t: the one with the latest started word. */
    function pageAt(pages, t) {
        let idx = 0;
        for (let p = 0; p < pages.length; p++) {
            const first = pages[p][0] && pages[p][0][0];
            if (first && (first.s != null ? first.s : 0) <= t + 1e-6) idx = p;
        }
        return idx;
    }

    function wordFrameParity(word, fps) {
        return {
            preview: TM.wordVisibleFrame(word.s, fps),
            ass: TM.wordAssStartFrame(word.s, fps),
            delta: Math.abs(TM.wordVisibleFrame(word.s, fps) - TM.wordAssStartFrame(word.s, fps))
        };
    }

    function clampToSafe(cx, cy, blockW, blockH, W, H) {
        const x0 = SAFE.x0 * W + blockW / 2, x1 = SAFE.x1 * W - blockW / 2;
        const y0 = SAFE.y0 * H + blockH / 2, y1 = SAFE.y1 * H - blockH / 2;
        return {
            x: x0 <= x1 ? Math.min(x1, Math.max(x0, cx)) : W / 2,
            y: y0 <= y1 ? Math.min(y1, Math.max(y0, cy)) : H / 2
        };
    }

    function fontFor(style, px) {
        return (style.italic ? "italic " : "") + (style.weight || "900") + " " + Math.round(px) + 'px "' +
            (style.font || "Montserrat ExtraBold") + '", "Anton", "Arial Black", sans-serif';
    }

    /**
     * Draw the active cue on a 2D context (browser). Deterministic.
     * cue: { words: [{word, s, e, hot, color, importance}], end, styleName, x, y, sizeRatio }
     */
    function drawCue(ctx, cue, t, W, H, styleOverride) {
        if (!cue || !cue.words || !cue.words.length) return;
        const SM = STYLES();
        const styleName = resolveStyleName(cue.styleName || "viral_italic");
        const style = Object.assign({}, SM.styles[styleName] || {}, styleOverride || {});
        const baseSize = H * (cue.sizeRatio || 0.058);
        const maxW = (SAFE.x1 - SAFE.x0) * W;
        const entries = cue.words.map((w, i) => ({
            text: style.caps !== false ? String(w.word).toUpperCase() : String(w.word),
            word: w.word, s: w.s, e: w.e, hot: !!w.hot, color: w.color || null,
            importance: w.importance, anim: w.anim, index: i
        }));
        ctx.save();
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        const measureAt = (s, sc) => { ctx.font = fontFor(style, baseSize * sc); return ctx.measureText(s).width; };
        const fit = fitLayout(entries, measureAt, maxW, cue.maxLines || 2, 0.72);
        const lines = fit.pages[pageAt(fit.pages, t)] || [];
        const fontSize = baseSize * fit.scale;
        const fontStr = fontFor(style, fontSize);
        ctx.font = fontStr;
        const lineH = fontSize * 1.18;
        const spaceW = ctx.measureText(" ").width;
        const lineWidths = lines.map(line => line.reduce((a, en, i) => a + ctx.measureText(en.text).width + (i ? spaceW : 0), 0));
        const blockW = Math.max(0, ...lineWidths) + fontSize * (style.stroke || 0) * 2;
        const blockH = lines.length * lineH;
        const pos = clampToSafe(cue.x != null ? cue.x * W : W / 2, cue.y != null ? cue.y * H : H * 0.68, blockW, blockH, W, H);
        if (style.tilt || style.bob) {              // declared in styles.json, now drawn
            const bob = style.bob ? (style.bob.amp || 3) * (H / 1920) * Math.sin(2 * Math.PI * (style.bob.freq || 1.2) * t) : 0;
            ctx.translate(pos.x, pos.y + bob);
            if (style.tilt) ctx.rotate(style.tilt * Math.PI / 180);
            ctx.translate(-pos.x, -pos.y);
        }
        for (let li = 0; li < lines.length; li++) {
            const line = lines[li];
            let x = pos.x - lineWidths[li] / 2;
            const y = pos.y + (li - (lines.length - 1) / 2) * lineH;
            for (let wi = 0; wi < line.length; wi++) {
                const en = line[wi];
                const wpx = ctx.measureText(en.text).width;
                const st = wordState(en, t, style, { cueEnd: cue.end, index: en.index,
                                                     karaoke: cue.karaoke !== false });
                if (st) {
                    ctx.save();
                    ctx.globalAlpha = st.opacity;
                    ctx.translate(x + wpx / 2 + st.dx * fontSize, y + st.dy * fontSize);
                    if (st.rot) ctx.rotate(st.rot);
                    ctx.scale(st.scale, st.scale);
                    let col = en.color || style.color || "#fff";
                    if (en.hot) col = style.accent || "#FF2B2B";
                    else if (st.active && cue.karaoke !== false) col = style.activeColor || style.accent2 || "#FFE14D";
                    ctx.font = fontStr;
                    ctx.textAlign = "center";
                    ctx.textBaseline = "middle";
                    if (st.blur > 0.1) ctx.filter = "blur(" + (st.blur * (H / 1080)).toFixed(2) + "px)";
                    // char_type: grapheme-by-grapheme reveal (deterministic)
                    let text = en.text;
                    const animName = en.anim || style.animatorIn;
                    if (animName === "char_type") {
                        const a = (SM.animators || {}).char_type || {};
                        const g = graphemes(text);
                        const n = Math.floor(Math.max(0, t - (en.s || 0)) * 1000 / (a.msPerGrapheme || 38)) + 1;
                        text = g.slice(0, Math.min(g.length, n)).join("");
                        ctx.textAlign = "left";
                        ctx.translate(-wpx / 2, 0);
                    }
                    if (style.extrude) {                       // 3D extrusion (mrbeast_3d): px @1920
                        const ex = typeof style.extrude === "number" ? { depth: style.extrude } : style.extrude;
                        const depth = Math.max(1, Math.round((ex.depth || 10) * H / 1920));
                        ctx.fillStyle = ex.color || style.strokeColor || "#000";
                        for (let d = depth; d > 0; d--) ctx.fillText(text, d * 0.5, d);
                    }
                    if (style.glow) {
                        ctx.shadowColor = style.glowColor || col;
                        ctx.shadowBlur = fontSize * 0.25 * style.glow * st.glowBoost * st.opacity * (1 + st.shimmer);
                        ctx.fillStyle = col;
                        ctx.fillText(text, 0, 0);
                        ctx.shadowBlur = 0;
                    }
                    if (style.stroke) {
                        ctx.lineWidth = fontSize * style.stroke;
                        ctx.strokeStyle = style.strokeColor || "#000";
                        ctx.lineJoin = "round";
                        ctx.strokeText(text, 0, 0);
                    }
                    if (style.shadow) {
                        ctx.shadowColor = "rgba(0,0,0," + (style.shadow.alpha || 0.6) + ")";
                        ctx.shadowBlur = fontSize * (style.shadow.blur || 0.08);
                        ctx.shadowOffsetY = fontSize * (style.shadow.offsetY || 0.06);
                    }
                    ctx.fillStyle = col;
                    ctx.fillText(text, 0, 0);
                    ctx.restore();
                }
                x += wpx + spaceW;
            }
        }
        ctx.restore();
        return { lines: lines.length, pages: fit.pages.length, scale: fit.scale, entries: entries.length };
    }

    return {
        graphemes: graphemes,
        wordState: wordState,
        layoutLines: layoutLines,
        fitLayout: fitLayout,
        pageAt: pageAt,
        importance: importance,
        resolveStyleName: resolveStyleName,
        clampToSafe: clampToSafe,
        SAFE: SAFE,
        wordFrameParity: wordFrameParity,
        drawCue: drawCue,
        styles: STYLES()
    };
});
