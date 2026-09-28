/* Kick Clip Studio — web/studio/moments.js
 * Moment finder panel (audit §6): ranks the loaded VOD by audio bursts,
 * optional chat log and speech, optionally re-ranked by an LLM. Click a
 * moment to jump there; "Шаблон" previews the one-click template fx plan.
 * Self-contained: talks only to /api/studio/* (token cookie is sent). */
(function () {
    "use strict";
    if (window.__studioMoments) return;
    window.__studioMoments = true;

    function fmt(t) {
        t = Math.max(0, t || 0);
        const h = Math.floor(t / 3600), m = Math.floor(t % 3600 / 60), s = Math.floor(t % 60);
        return (h ? h + ":" + String(m).padStart(2, "0") : m) + ":" + String(s).padStart(2, "0");
    }
    function currentFile() {
        const v = document.getElementById("studioVideoPlayer") || document.querySelector("video[data-file]");
        if (v && v.getAttribute("data-file")) return v.getAttribute("data-file");
        if (v && v.currentSrc) {
            const m = /[?&]filename=([^&]+)/.exec(v.currentSrc) || /\/([^\/?#]+\.(mp4|mkv|mov|webm|ts))/i.exec(v.currentSrc);
            if (m) return decodeURIComponent(m[1]);
        }
        return "";
    }
    function seek(t) {
        if (typeof window.studioSeek === "function") return window.studioSeek(t);
        if (typeof window.seekTo === "function") return window.seekTo(t);
        const v = document.getElementById("studioVideoPlayer") || document.querySelector("video");
        if (v) { v.currentTime = t; v.dispatchEvent(new Event("timeupdate")); }
    }
    function el(tag, attrs, text) {
        const e = document.createElement(tag);
        for (const k in (attrs || {})) e.setAttribute(k, attrs[k]);
        if (text != null) e.textContent = text;
        return e;
    }

    const css = el("style", {}, [
        "#stMomBtn{position:fixed;right:16px;bottom:16px;z-index:9999;background:#ff2b2b;color:#fff;border:0;",
        "border-radius:22px;padding:10px 16px;font:700 14px system-ui;cursor:pointer;box-shadow:0 4px 18px #0008}",
        "#stMomPanel{position:fixed;right:16px;bottom:64px;z-index:9999;width:380px;max-height:70vh;overflow:auto;",
        "background:#15161a;color:#eee;border:1px solid #333;border-radius:12px;padding:12px;font:13px system-ui;display:none}",
        "#stMomPanel input,#stMomPanel select{width:100%;margin:4px 0;background:#222;color:#eee;border:1px solid #444;",
        "border-radius:6px;padding:6px}#stMomPanel button{margin:4px 4px 4px 0;background:#2d6cdf;color:#fff;border:0;",
        "border-radius:6px;padding:6px 10px;cursor:pointer}.stMom{border-top:1px solid #2a2a2a;padding:8px 0;cursor:pointer}",
        ".stMom:hover{background:#1f2026}.stMom b{color:#ffe14d}.stMom small{color:#999;display:block}"
    ].join(""));
    document.head.appendChild(css);

    const btn = el("button", { id: "stMomBtn", title: "Найти лучшие моменты" }, "🔥 Моменты");
    const panel = el("div", { id: "stMomPanel" });
    panel.innerHTML =
        '<div style="font-weight:700;margin-bottom:6px">Автопоиск моментов</div>' +
        '<label>Файл в downloads/<input id="stMomFile" placeholder="video.mp4"></label>' +
        '<label>Лог чата (JSON/JSONL в downloads/, необязательно)<input id="stMomChat" placeholder="chat.json"></label>' +
        '<label>Шаблон<select id="stMomTpl"><option value="hype">Хайп</option><option value="story">История</option>' +
        '<option value="clean">Чистый</option></select></label>' +
        '<label><input type="checkbox" id="stMomLlm" style="width:auto"> Ранжировать LLM (Groq)</label><br>' +
        '<button id="stMomRun">Найти топ-10</button><span id="stMomStatus"></span><div id="stMomList"></div>';
    document.body.appendChild(btn);
    document.body.appendChild(panel);
    btn.onclick = () => {
        panel.style.display = panel.style.display === "block" ? "none" : "block";
        const f = panel.querySelector("#stMomFile");
        if (!f.value) f.value = currentFile();
    };

    panel.querySelector("#stMomRun").onclick = async () => {
        const status = panel.querySelector("#stMomStatus");
        const list = panel.querySelector("#stMomList");
        const body = {
            filename: panel.querySelector("#stMomFile").value.trim(),
            chat_file: panel.querySelector("#stMomChat").value.trim() || null,
            use_llm: panel.querySelector("#stMomLlm").checked,
            words: Array.isArray(window.studioTranscriptWords) ? window.studioTranscriptWords : null,
            top_k: 10
        };
        if (!body.filename) { status.textContent = " укажите файл"; return; }
        status.textContent = " анализ… (4-часовой VOD ~1–3 мин)";
        list.innerHTML = "";
        try {
            const r = await fetch("/api/studio/moments", { method: "POST", credentials: "same-origin",
                headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
            const j = await r.json();
            if (!r.ok) throw new Error(j.detail || r.status);
            status.textContent = " найдено: " + j.moments.length;
            const tpl = panel.querySelector("#stMomTpl").value;
            j.moments.forEach((m, i) => {
                const row = el("div", { class: "stMom" });
                row.innerHTML = "<b>#" + (i + 1) + "</b> " + fmt(m.start) + " – " + fmt(m.end) +
                    " · скор " + m.score.toFixed(2) +
                    (m.hook ? "<br>🪝 " + m.hook.replace(/</g, "&lt;") : "") +
                    "<small>" + Object.entries(m.signals).map(([k, v]) => k + " " + v.toFixed(2)).join(" · ") +
                    (m.reason ? " — " + m.reason.replace(/</g, "&lt;") : "") + "</small>";
                row.onclick = () => seek(m.start);
                const plan = el("button", {}, "Шаблон");
                plan.onclick = async (ev) => {
                    ev.stopPropagation();
                    const beats = [{ t: m.peak - m.start, intensity: Math.min(1, 0.6 + m.score / 2) }];
                    const pr = await fetch("/api/studio/templates/plan", { method: "POST", credentials: "same-origin",
                        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ template: tpl, beats: beats }) });
                    const pj = await pr.json();
                    window.studioLastPlan = { moment: m, template: tpl, fx: pj.fx };
                    document.dispatchEvent(new CustomEvent("studio:template-plan", { detail: window.studioLastPlan }));
                    plan.textContent = "✓ " + (pj.fx || []).length + " fx";
                };
                row.appendChild(plan);
                list.appendChild(row);
            });
        } catch (e) {
            status.textContent = " ошибка: " + e.message;
        }
    };
})();
