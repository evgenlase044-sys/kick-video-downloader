/* Kick Clip Studio — web/studio/overlay_export.js  (audit §2 / REMAINING_FIXES §1)
 *
 * ONE text renderer for preview and file. Before an export request leaves the
 * page (/api/export-pack or /api/export-queue), every clip's captions/text are
 * rendered frame by frame with the SAME CoreCanvasText.drawCue() the canvas
 * monitor uses, into a transparent canvas, and only CHANGED frames are streamed
 * as PNG to /ws/overlay/{clip_id}. The server disables the ASS text for that
 * clip and burns this layer on top in the final encode (studio/export_pipeline.py).
 * If anything fails the clip keeps the old ASS text (never no captions).
 *
 * Also (preview AND export, both go through drawCue): key words in colour,
 * optional auto-emoji, export templates (fps/grade/text style), Backspace guard. */
(function () {
    "use strict";
    if (window.__studioOverlayExport) return;
    window.__studioOverlayExport = true;

    const LS = {
        get(k, d) { try { const v = localStorage.getItem("studio." + k); return v == null ? d : v; } catch (e) { return d; } },
        set(k, v) { try { localStorage.setItem("studio." + k, String(v)); } catch (e) {} }
    };
    const cfg = () => ({
        canvasText: LS.get("canvasText", "1") === "1",
        hotWords: LS.get("hotWords", "1") === "1",
        autoEmoji: LS.get("autoEmoji", "0") === "1",
        template: LS.get("exportTemplate", "")
    });
    const TEMPLATES = {
        hype: { fps: 60, style: "viral_italic", hot: true },
        story: { fps: 30, style: "story_clean", hot: true },
        clean: { fps: 30, style: "viral_italic", hot: false }
    };

    const SWEAR = /(ху[йяеёи]|пизд|бля|еба|ёба|еб[уа]|сук[аи]|нахуй|хер|fuck|shit|bitch|damn|wtf)/i;
    const TURN = /^(но|однако|вдруг|внезапно|короче|оказалось|реально|серьезно|серьёзно|стоп|жесть|капец|омг|omg|bro|бро)$/i;
    const EMOJI = [
        [/(ха[ха]+|ахах|лол|lol|lmao|смешн|ор[уё])/i, "😂"], [/(огон|fire|жар|пожар)/i, "🔥"],
        [/(умер|смерть|dead|труп|убил|kill)/i, "💀"], [/(деньг|бабк|донат|\$|₽|money|рубл|доллар)/i, "💰"],
        [/(шок|что\?!|what|страш|жуть|жесть)/i, "😱"], [/(любл|love|сердц)/i, "❤️"],
        [/(побед|win|топ|лучш|gg)/i, "🏆"], [/(злой|бесит|ярост|rage)/i, "😡"]
    ];
    function cleanWord(w) { return String(w || "").replace(/^[«"'(\[]+|[»"'),.:;\]]+$/g, ""); }
    function hotScore(word, i, words) {
        const raw = String(word.word != null ? word.word : word.text || "");
        const w = cleanWord(raw);
        if (!w || w.length < 2 && !/\d/.test(w)) return 0;
        let s = 0;
        if (/\d|%|\$|₽|€/.test(w)) s = Math.max(s, 0.95);
        if (SWEAR.test(w)) s = Math.max(s, 0.9);
        if (/[!?]$/.test(raw)) s = Math.max(s, 0.75);
        if (TURN.test(w)) s = Math.max(s, 0.7);
        if (w.length >= 3 && w === w.toUpperCase() && /[A-ZА-ЯЁ]/.test(w)) s = Math.max(s, 0.8);
        const prev = i > 0 ? String(words[i - 1].word || words[i - 1].text || "") : ".";
        if (/^[A-ZА-ЯЁ][a-zа-яё]+/.test(w) && !/[.!?…]$/.test(prev) && i > 0) s = Math.max(s, 0.85);
        return s;
    }
    function markHotWords(words) {
        if (!words || !words.length || words.some(w => w.hot)) return words;
        const scored = words.map((w, i) => ({ i: i, s: hotScore(w, i, words) })).filter(x => x.s >= 0.7);
        const budget = Math.max(1, Math.floor(words.length / 3));
        const pick = new Set(scored.sort((a, b) => b.s - a.s).slice(0, budget).map(x => x.i));
        return words.map((w, i) => pick.has(i) ? Object.assign({}, w, { hot: true, importance: 1 }) : w);
    }
    function addEmoji(words) {
        const out = [];
        let used = 0;
        for (const w of words || []) {
            out.push(w);
            if (used >= 2 || /\p{Extended_Pictographic}/u.test(String(w.word || ""))) continue;
            const hit = EMOJI.find(([rx]) => rx.test(cleanWord(w.word)));
            if (hit) { out.push({ word: hit[1], s: w.s, e: w.e, emoji: true, importance: 0.9 }); used++; }
        }
        return out;
    }
    window.StudioTextSmarts = { hotScore: hotScore, markHotWords: markHotWords, addEmoji: addEmoji };

    function wrapDrawCue() {
        const T = window.CoreCanvasText;
        if (!T || T.__studioWrapped) return !!T;
        const orig = T.drawCue;
        T.drawCue = function (ctx, cue, t, W, H, styleOverride) {
            if (cue && Array.isArray(cue.words) && cue.words.length) {
                const c = cfg();
                if (c.hotWords || c.autoEmoji) {
                    let words = cue.words;
                    if (c.hotWords && cue.hotWords !== false) words = markHotWords(words);
                    if (c.autoEmoji) words = addEmoji(words);
                    if (words !== cue.words) cue = Object.assign({}, cue, { words: words });
                }
            }
            return orig.call(this, ctx, cue, t, W, H, styleOverride);
        };
        T.__studioWrapped = true;
        return true;
    }
    if (!wrapDrawCue()) document.addEventListener("DOMContentLoaded", wrapDrawCue);

    document.addEventListener("keydown", function (e) {
        if (e.key !== "Backspace") return;
        const el = e.target;
        const editable = el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName));
        if (!editable) e.preventDefault();
    }, true);

    function clipDuration(c) {
        if (Array.isArray(c.layers) && c.layers.length) {
            return Math.max(0.1, ...c.layers.map(l => (+l.out_start || 0) + (+l.duration || 0)));
        }
        if (Array.isArray(c.segments) && c.segments.length) {
            return Math.max(0.1, c.segments.reduce((a, s) => a + Math.max(0, s.end_time - s.start_time), 0));
        }
        return Math.max(0.1, (+c.end_time || 0) - (+c.start_time || 0));
    }
    function srcToOut(c, t) {
        if (Array.isArray(c.segments) && c.segments.length) {
            let acc = 0;
            for (const s of c.segments) {
                if (t >= s.start_time - 1e-3 && t <= s.end_time + 1e-3) return acc + Math.max(0, t - s.start_time);
                acc += Math.max(0, s.end_time - s.start_time);
            }
            return null;
        }
        return t - (+c.start_time || 0);
    }
    function norm(v, size, dflt) {
        if (v == null || v === "" || isNaN(+v)) return dflt;
        v = +v;
        return v > 1.5 ? v / size : v;
    }
    function wordTime(w, key) {
        const v = w["abs_" + key] != null ? w["abs_" + key] : w[key];
        return v == null ? null : +v;
    }
    function buildCues(c, W, H, tplStyle, tplHot) {
        const isSplit = c.format === "split_adhd";
        const sizeRatio = 0.058 * (+c.sub_size || 1) * (isSplit ? 0.9 : 1);
        const dflt = { x: 0.5, y: isSplit ? 0.225 : 0.68 };
        const mode = c.subtitle_mode || null;
        const items = Array.isArray(c.text_items) ? c.text_items : [];
        const asr = ti => ti && Array.isArray(ti.words) && ti.words.length;
        const cues = [];
        const useItems = mode === "timeline" || mode == null ? items : items.filter(ti => !asr(ti));
        for (const ti of useItems) {
            if (!ti || typeof ti !== "object") continue;
            const start = +(ti.start != null ? ti.start : ti.startTime || 0);
            const end = +(ti.end != null ? ti.end : start + (+ti.duration || 2));
            if (!(end > start)) continue;
            let raw = asr(ti) ? ti.words : null;
            if (!raw) {
                const text = String(ti.text != null ? ti.text : ti.title || "").trim();
                if (!text) continue;
                raw = text.split(/\s+/).map(word => ({ word: word, start: 0, end: end - start }));
            }
            const first = wordTime(raw[0], "start") || 0;
            cues.push({
                start: start, end: end,
                cue: {
                    words: raw.map(w => ({
                        word: String(w.word != null ? w.word : w.text || ""),
                        s: Math.max(0, (wordTime(w, "start") != null ? wordTime(w, "start") : first) - first),
                        e: Math.max(0.05, (wordTime(w, "end") != null ? wordTime(w, "end") : first + (end - start)) - first),
                        hot: !!w.hot, color: w.color || null
                    })),
                    end: Math.max(0.2, end - start),
                    styleName: tplStyle || ti.style || ti.styleName || ti.subtitleStyle || c.subtitle_template || "acid",
                    x: norm(ti.x, W, dflt.x), y: norm(ti.y, H, dflt.y),
                    sizeRatio: sizeRatio, hotWords: tplHot
                }
            });
        }
        if (mode !== "timeline" && mode !== "none") {
            const inOut = !!c.subs_in_output_time;
            for (const seg of (Array.isArray(c.subtitles) ? c.subtitles : [])) {
                const ws = Array.isArray(seg.words) && seg.words.length ? seg.words
                    : String(seg.text || "").trim().split(/\s+/).filter(Boolean)
                        .map(word => ({ word: word, start: seg.start, end: seg.end }));
                if (!ws.length) continue;
                const s0 = inOut ? +seg.start : srcToOut(c, +seg.start);
                const e0 = inOut ? +seg.end : srcToOut(c, +seg.end);
                if (s0 == null || e0 == null || !(e0 > s0)) continue;
                const base = +seg.start;
                cues.push({
                    start: s0, end: e0,
                    cue: {
                        words: ws.map(w => ({
                            word: String(w.word || ""),
                            s: Math.max(0, (wordTime(w, "start") != null ? wordTime(w, "start") : base) - base),
                            e: Math.max(0.05, (wordTime(w, "end") != null ? wordTime(w, "end") : +seg.end) - base),
                            hot: !!w.hot
                        })),
                        end: Math.max(0.2, e0 - s0),
                        styleName: tplStyle || c.subtitle_template || "acid",
                        x: dflt.x, y: dflt.y, sizeRatio: sizeRatio, hotWords: tplHot
                    }
                });
            }
        }
        return cues.sort((a, b) => a.start - b.start);
    }

    let stylesPromise = null;
    function ensureStyles() {
        if (window.STYLES_JSON) return Promise.resolve();
        if (!stylesPromise) {
            stylesPromise = origFetch("/core/styles.json", { credentials: "same-origin" })
                .then(r => r.json()).then(j => { window.STYLES_JSON = j; }).catch(() => {});
        }
        return stylesPromise;
    }
    function makeCanvas(w, h) {
        if (typeof OffscreenCanvas !== "undefined") return new OffscreenCanvas(w, h);
        const c = document.createElement("canvas");
        c.width = w; c.height = h;
        return c;
    }
    function toPng(canvas) {
        if (canvas.convertToBlob) return canvas.convertToBlob({ type: "image/png" });
        return new Promise(res => canvas.toBlob(res, "image/png"));
    }
    function fnv(buf) {
        let h = 0x811c9dc5;
        const u = new Uint32Array(buf.buffer, buf.byteOffset, buf.byteLength >> 2);
        for (let i = 0; i < u.length; i++) { h ^= u[i]; h = Math.imul(h, 16777619) >>> 0; }
        return h;
    }
    function toast(msg, sticky) {
        let el = document.getElementById("stOvToast");
        if (!el) {
            el = document.createElement("div");
            el.id = "stOvToast";
            el.style.cssText = "position:fixed;left:50%;bottom:22px;transform:translateX(-50%);z-index:10000;" +
                "background:#15161a;color:#eee;border:1px solid #333;border-radius:10px;padding:8px 14px;font:13px system-ui";
            document.body.appendChild(el);
        }
        el.textContent = msg;
        el.style.display = "block";
        clearTimeout(el._t);
        if (!sticky) el._t = setTimeout(() => { el.style.display = "none"; }, 4000);
    }
    function openWs(clipId) {
        const proto = location.protocol === "https:" ? "wss:" : "ws:";
        return new WebSocket(proto + "//" + location.host + "/ws/overlay/" + encodeURIComponent(clipId));
    }

    async function renderAndUpload(clip, fps, label) {
        const T = window.CoreCanvasText;
        const vertical = clip.format !== "cinematic_16_9";
        const W = vertical ? 1080 : 1920, H = vertical ? 1920 : 1080;
        const tpl = TEMPLATES[cfg().template] || null;
        const cues = buildCues(clip, W, H, tpl ? tpl.style : null, tpl && !tpl.hot ? false : undefined);
        if (!cues.length) return { skipped: "no text" };
        const dur = clipDuration(clip);
        const frames = Math.max(1, Math.ceil(dur * fps - 1e-6));
        const cv = makeCanvas(W, H), ctx = cv.getContext("2d");
        const small = makeCanvas(W / 5, H / 5), sctx = small.getContext("2d", { willReadFrequently: true });
        const ws = openWs(clip.id);
        ws.binaryType = "arraybuffer";
        let acked = 0, sent = 0, final = null, failed = null;
        const waiters = [];
        ws.onmessage = ev => {
            let m = {};
            try { m = JSON.parse(ev.data); } catch (e) {}
            if (m.ack != null) acked = m.ack;
            if (m.ok != null) final = m;
            if (m.error) failed = m.error;
            while (waiters.length) waiters.shift()();
        };
        ws.onclose = () => { if (!final && !failed) failed = "overlay socket closed"; while (waiters.length) waiters.shift()(); };
        await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("overlay socket failed")); });
        ws.send(JSON.stringify({ w: W, h: H, fps: fps, frames: frames }));
        const wait = () => new Promise(r => waiters.push(r));
        let lastHash = -1;
        for (let f = 0; f < frames; f++) {
            if (failed) throw new Error(failed);
            const t = f / fps;
            ctx.clearRect(0, 0, W, H);
            for (const c of cues) {
                if (t >= c.start - 1e-6 && t < c.end) T.drawCue(ctx, c.cue, t - c.start, W, H, c.cue.styleOverride);
            }
            sctx.clearRect(0, 0, small.width, small.height);
            sctx.drawImage(cv, 0, 0, small.width, small.height);
            const h = fnv(sctx.getImageData(0, 0, small.width, small.height).data);
            if (f === 0 || h !== lastHash) {
                lastHash = h;
                const png = new Uint8Array(await (await toPng(cv)).arrayBuffer());
                const msg = new Uint8Array(4 + png.length);
                new DataView(msg.buffer).setUint32(0, f, true);
                msg.set(png, 4);
                while (sent - acked >= 32 && !failed) await wait();
                ws.send(msg.buffer);
                sent++;
            }
            if (f % 30 === 0) {
                toast("Текст как в превью: " + label + " " + Math.round(100 * f / frames) + "%", true);
                await new Promise(r => setTimeout(r, 0));
            }
        }
        ws.send(JSON.stringify({ end: true }));
        while (!final && !failed) await wait();
        if (failed) throw new Error(failed);
        return final;
    }

    function safeId(id, i) {
        let s = String(id == null ? "" : id).replace(/[^A-Za-z0-9_.\-]/g, "_").slice(0, 80);
        if (!s) s = "clip";
        return s + "_" + Date.now().toString(36) + i;
    }

    async function prepareExport(body) {
        const clips = Array.isArray(body.clips) ? body.clips : [];
        const c = cfg();
        const tpl = TEMPLATES[c.template] || null;
        if (!clips.length || (!c.canvasText && !tpl)) return false;
        await ensureStyles();
        if (document.fonts && document.fonts.ready) { try { await document.fonts.ready; } catch (e) {} }
        wrapDrawCue();
        const fps = tpl ? tpl.fps : 60;
        const opts = [];
        let changed = false;
        for (let i = 0; i < clips.length; i++) {
            const clip = clips[i];
            if (!clip || typeof clip !== "object" || clip.src_processed) continue;
            clip.id = safeId(clip.id, i);
            changed = true;
            let overlay = false;
            if (c.canvasText && window.CoreCanvasText) {
                try {
                    const r = await renderAndUpload(clip, fps, (i + 1) + "/" + clips.length);
                    overlay = !!(r && r.ok && !r.empty);
                } catch (e) {
                    console.warn("[studio] canvas text layer failed, ASS text will be used:", e);
                    toast("Текст-слой не собран (" + e.message + ") — будет ASS-текст");
                }
            }
            opts.push({ clip_id: clip.id, template: c.template || null, overlay: overlay });
        }
        if (opts.length) {
            await origFetch("/api/studio/export-options", {
                method: "POST", credentials: "same-origin",
                headers: { "Content-Type": "application/json" }, body: JSON.stringify({ clips: opts })
            }).catch(() => {});
            toast("Экспорт: " + opts.filter(o => o.overlay).length + "/" + opts.length +
                  " клипов с текстом как в превью" + (c.template ? " · шаблон " + c.template : ""));
        }
        return changed;
    }

    const origFetch = window.fetch.bind(window);
    window.fetch = async function (input, init) {
        try {
            const url = typeof input === "string" ? input : (input && input.url) || "";
            const method = String((init && init.method) || (input && input.method) || "GET").toUpperCase();
            if (method === "POST" && /\/api\/export-(pack|queue)(\?|$)/.test(url) && init && typeof init.body === "string") {
                const body = JSON.parse(init.body);
                if (await prepareExport(body)) init = Object.assign({}, init, { body: JSON.stringify(body) });
            }
        } catch (e) {
            console.warn("[studio] export pre-pass skipped:", e);
        }
        return origFetch(input, init);
    };

    function panel() {
        const btn = document.createElement("button");
        btn.id = "stExpBtn";
        btn.textContent = "🎬 Экспорт";
        btn.title = "Шаблон экспорта и текст как в превью";
        btn.style.cssText = "position:fixed;right:150px;bottom:16px;z-index:9999;background:#2d6cdf;color:#fff;border:0;" +
            "border-radius:22px;padding:10px 16px;font:700 14px system-ui;cursor:pointer;box-shadow:0 4px 18px #0008";
        const p = document.createElement("div");
        p.id = "stExpPanel";
        p.style.cssText = "position:fixed;right:150px;bottom:64px;z-index:9999;width:320px;background:#15161a;color:#eee;" +
            "border:1px solid #333;border-radius:12px;padding:12px;font:13px system-ui;display:none";
        const c = cfg();
        p.innerHTML =
            '<div style="font-weight:700;margin-bottom:6px">Экспорт</div>' +
            '<label>Шаблон<select id="stExpTpl" style="width:100%;margin:4px 0;background:#222;color:#eee;border:1px solid #444;border-radius:6px;padding:6px">' +
            '<option value="">— как в проекте —</option><option value="hype">Хайп · 60 fps</option>' +
            '<option value="story">История · 30 fps</option><option value="clean">Чистый · 30 fps</option></select></label>' +
            '<label style="display:block;margin:6px 0"><input type="checkbox" id="stExpCanvas"> Текст в файле = текст в превью</label>' +
            '<label style="display:block;margin:6px 0"><input type="checkbox" id="stExpHot"> Ключевые слова цветом</label>' +
            '<label style="display:block;margin:6px 0"><input type="checkbox" id="stExpEmoji"> Авто-emoji</label>' +
            '<div id="stExpInfo" style="color:#999;margin-top:6px"></div>';
        document.body.appendChild(btn);
        document.body.appendChild(p);
        p.querySelector("#stExpTpl").value = c.template;
        p.querySelector("#stExpCanvas").checked = c.canvasText;
        p.querySelector("#stExpHot").checked = c.hotWords;
        p.querySelector("#stExpEmoji").checked = c.autoEmoji;
        p.querySelector("#stExpTpl").onchange = e => LS.set("exportTemplate", e.target.value);
        p.querySelector("#stExpCanvas").onchange = e => LS.set("canvasText", e.target.checked ? "1" : "0");
        p.querySelector("#stExpHot").onchange = e => LS.set("hotWords", e.target.checked ? "1" : "0");
        p.querySelector("#stExpEmoji").onchange = e => LS.set("autoEmoji", e.target.checked ? "1" : "0");
        btn.onclick = () => {
            p.style.display = p.style.display === "block" ? "none" : "block";
            origFetch("/api/studio/export-report", { credentials: "same-origin" }).then(r => r.json()).then(j => {
                const last = (j.recent || []).filter(r => r.out).slice(-1)[0];
                p.querySelector("#stExpInfo").textContent = "Кодек: " + j.encoder +
                    (last ? " · последний: " + last.out + (last.seek && last.seek.slow_seek ? " ⚠ медленный сик" : "") : "");
            }).catch(() => {});
        };
    }
    if (document.body) panel(); else document.addEventListener("DOMContentLoaded", panel);

    window.StudioOverlayExport = { buildCues: buildCues, clipDuration: clipDuration, srcToOut: srcToOut };
})();
