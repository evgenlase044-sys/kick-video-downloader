/* Kick Clip Studio — web/core/text/canvasText.js
 * PLAN §12 (seed)/§16.4: canvas text engine — the SAME deterministic
 * time-functions the export renderer will use. No CSS animations, no
 * wall-clock: every property is a pure function of cue-local time.
 * Pure parts are Node-compatible (UMD) for verification. */
(function (root, factory) {
    const mod = factory();
    if (typeof module !== "undefined" && module.exports) module.exports = mod;
    root.CoreCanvasText = mod;
})(typeof self !== "undefined" ? self : this, function () {
    "use strict";
    const TM = (typeof CoreTimeMap !== "undefined") ? CoreTimeMap : require("../timeMap.js");
    // styles.json is fetched asynchronously in the browser; use the embedded
    // fallback until window.STYLES_JSON arrives, so draws never crash.
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

    /** Grapheme-ish split: code points (surrogate pairs kept together). */
    function graphemes(s) {
        return Array.from(String(s || ""));
    }

    /**
     * Per-word state at cue-local time t (seconds), deterministic (§12.6).
     * word: {word, s, e, hot, color}; style: entry from styles.json.
     * Returns null when the word is not yet visible.
     */
    function wordState(word, t, style, opts) {
        const o = opts || {};
        const s = word.s != null ? word.s : 0;
        const e = word.e != null ? word.e : (s + 1.0);
        if (t < s - 1e-6) return null;                    // not yet visible
        const animName = word.anim || (style && style.animatorIn) || "word_pop_spring";
        const anim = (STYLES().animators || {})[animName] || {};
        const outAnim = (STYLES().animators || {})[(style && style.animatorOut) || "out_blur_fade"] || {};
        const cueEnd = o.cueEnd != null ? o.cueEnd : Infinity;
        const st = {
            visible: true,
            scale: 1, opacity: 1, blur: 0, glowBoost: 1, dy: 0
        };
        // ---- in animator -------------------------------------------------
        const tin = t - s;
        if (animName === "word_pop_spring") {
            const p = TM.springParams(anim.overshoot || 0.18, (anim.settleMs || 300) / 1000);
            const raw = TM.spring(tin, p);                 // 0..1 with overshoot
            st.scale = (anim.scaleFrom || 0.55) + (1 - (anim.scaleFrom || 0.55)) * raw;
            st.opacity = TM.clamp01(tin / ((anim.opacityMs || 50) / 1000));
            st.blur = Math.max(0, (anim.blurFrom || 6) * (1 - TM.clamp01(tin / ((anim.blurMs || 90) / 1000))));
        } else if (animName === "char_type") {
            st.scale = 1; st.opacity = 1;
        } else if (animName === "slam") {
            const k = TM.clamp01(tin / ((anim.easeInMs || 120) / 1000));
            st.scale = (anim.scaleFrom || 2.2) + (1 - (anim.scaleFrom || 2.2)) * k * k;
            st.glowBoost = 1 + ((anim.glowBoost || 2) - 1) * (1 - k);
        } else if (animName === "none") {
            st.scale = 1; st.opacity = 1;
        }
        // ---- out animator -------------------------------------------------
        const outMs = (outAnim.ms || 180) / 1000;
        const tout = cueEnd - t;                            // time until cue end
        if (isFinite(tout) && tout < outMs && outAnim.blurTo) {
            const k = TM.clamp01(1 - tout / outMs);
            st.opacity *= (1 - k);
            st.blur = Math.max(st.blur, (outAnim.blurTo || 10) * k);
            st.scale *= 1 - (1 - (outAnim.scaleTo || 0.94)) * k;
        }
        if (st.opacity <= 0.01) return null;
        return st;
    }

    /** Line layout: max 3 rows, greedy fill by measured width (§12.3 seed). */
    function layoutLines(words, measureFn, maxWidth) {
        const lines = [[]];
        let w = 0;
        for (const word of words) {
            const ww = measureFn(word.text);
            const need = (w > 0 ? measureFn(" ") : 0) + ww;
            if (w + need > maxWidth && lines[lines.length - 1].length) {
                if (lines.length >= 3) break;               // max 3 rows (supports Russian phrases)
                lines.push([]);
                w = 0;
            }
            lines[lines.length - 1].push(word);
            w += (w > 0 ? measureFn(" ") : 0) + ww;
        }
        return lines.filter(l => l.length);
    }

    /** Pure word visibility window (frames) used by the §7.4 parity gate. */
    function wordFrameParity(word, fps) {
        return {
            preview: TM.wordVisibleFrame(word.s, fps),
            ass: TM.wordAssStartFrame(word.s, fps),
            delta: Math.abs(TM.wordVisibleFrame(word.s, fps) - TM.wordAssStartFrame(word.s, fps))
        };
    }

    /**
     * Draw the active cue on a 2D context (browser). Deterministic: same
     * (cue, t) always renders the same frame.
     * cue: { words: [{word, s, e, hot, color}], end, styleName, x, y }
     * coords are canvas-normalized 0..1; sizes are fractions of canvas height.
     */
    function drawCue(ctx, cue, t, W, H, styleOverride) {
        if (!cue || !cue.words || !cue.words.length) return;
        const styleName = cue.styleName || "viral_italic";
        const SM = STYLES();
        const style = Object.assign({}, SM.styles[styleName] || SM.styles.viral_italic, styleOverride || {});
        const fontSize = Math.round(H * (cue.sizeRatio || 0.058));
        const fontStr = (style.italic ? "italic " : "") + (style.weight || "900") + " " + fontSize + 'px "' + (style.font || "Montserrat ExtraBold") + '"';
        ctx.save();
        ctx.font = fontStr;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        const maxW = W * 0.92;
        const entries = cue.words.map(w => ({
            text: style.caps !== false ? String(w.word).toUpperCase() : String(w.word),
            s: w.s, e: w.e, hot: !!w.hot, color: w.color || null
        }));
        const lines = layoutLines(entries, s => ctx.measureText(s).width, maxW);
        const lineH = fontSize * 1.18;
        const baseY = (cue.y != null ? cue.y * H : H * 0.68);
        const startX = (cue.x != null ? cue.x * W : W / 2);
        let idx = 0;
        const totalEntries = entries.length;
        for (let li = 0; li < lines.length; li++) {
            const line = lines[li];
            // measure this line
            let lw = 0;
            const widths = line.map(en => {
                const w = ctx.measureText(en.text).width;
                lw += w + (line.indexOf(en) > 0 ? ctx.measureText(" ").width : 0);
                return w;
            });
            const spaceW = ctx.measureText(" ").width;
            let x = startX - lw / 2;
            const y = baseY + (li - (lines.length - 1) / 2) * lineH;
            for (let wi = 0; wi < line.length; wi++) {
                const en = line[wi];
                const st = wordState(en, t, style, { cueEnd: cue.end });
                const wpx = widths[wi];
                if (st) {
                    ctx.save();
                    ctx.globalAlpha = st.opacity;
                    const cx = x + wpx / 2;
                    ctx.translate(cx, y + st.dy);
                    ctx.scale(st.scale, st.scale);
                    const col = en.hot ? (style.accent || "#FF2B2B") : (en.color || style.color || "#fff");
                    ctx.font = fontStr;
                    ctx.textAlign = "center";
                    ctx.textBaseline = "middle";
                    if (st.blur > 0.1) ctx.filter = "blur(" + (st.blur * (H / 1080)).toFixed(2) + "px)";
                    // glow behind the glyph (never earlier than the word: alpha
                    // is multiplied by word opacity, so it follows visibility)
                    if (style.glow) {
                        ctx.shadowColor = style.glowColor || col;
                        ctx.shadowBlur = fontSize * 0.25 * style.glow * st.glowBoost * st.opacity;
                        ctx.shadowOffsetY = 0;
                        ctx.fillStyle = col;
                        ctx.fillText(en.text, 0, 0);
                        ctx.shadowBlur = 0;
                    }
                    if (style.stroke) {
                        ctx.lineWidth = fontSize * style.stroke;
                        ctx.strokeStyle = style.strokeColor || "#000";
                        ctx.lineJoin = "round";
                        ctx.strokeText(en.text, 0, 0);
                    }
                    if (style.shadow) {
                        ctx.shadowColor = "rgba(0,0,0," + (style.shadow.alpha || 0.6) + ")";
                        ctx.shadowBlur = fontSize * (style.shadow.blur || 0.08);
                        ctx.shadowOffsetY = fontSize * (style.shadow.offsetY || 0.06);
                    }
                    ctx.fillStyle = col;
                    ctx.fillText(en.text, 0, 0);
                    ctx.restore();
                }
                x += wpx + spaceW;
                idx++;
            }
        }
        ctx.restore();
        return { lines: lines.length, entries: totalEntries };
    }

    return {
        graphemes: graphemes,
        wordState: wordState,
        layoutLines: layoutLines,
        wordFrameParity: wordFrameParity,
        drawCue: drawCue,
        styles: STYLES()
    };
});