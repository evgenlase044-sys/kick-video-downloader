/* Kick Clip Studio — web/studio/discipline.js
 * Вкладка «Дисциплина»: вирусные мотивационные эдиты.
 * Материалы (drag&drop) + один трек -> план с бэкенда ->
 * проект на слоях (клипы, картинки-лупы, музыка, FX, финальная плашка).
 * Таб-ки переключение — локально, editor.js не трогаем. */
(function () {
    "use strict";

    const DEFAULT_MUSIC_SRC = "C:\\Users\\artba\\Downloads\\YTDown.com_YouTube_Media_ObIsBktleQs_LEAN-ON-HARDTEKK_001_1080p.mp4";

    const S = {
        materials: [],   // filenames in downloads/
        musicFile: null, // e.g. discipline_music.m4a
        analysis: null,
        loops: []
    };

    function $(id) { return document.getElementById(id); }
    function status(msg) {
        const el = $("discStatus");
        if (el) el.textContent = msg;
    }
    async function api(path, body) {
        const res = await fetch(path, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body || {})
        });
        const j = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error((j && j.detail) || ("HTTP " + res.status));
        return j;
    }
    async function refreshLibrary() {
        try {
            if (window.Studio && window.Studio.fetchLibrary) await window.Studio.fetchLibrary();
        } catch (e) { /* library tab owns it */ }
    }

    function initTabs() {
        const btn = $("tabBtnDiscipline"), panel = $("tabContentDiscipline");
        if (!btn || !panel || btn.dataset.discWired) return;
        btn.dataset.discWired = "1";
        btn.addEventListener("click", () => {
            document.querySelectorAll(".dock-tab").forEach(b => b.classList.remove("active"));
            document.querySelectorAll(".dock-panel-content").forEach(p => p.classList.remove("active"));
            btn.classList.add("active");
            panel.classList.add("active");
        });
    }

    function renderMaterials() {
        const box = $("discMaterialsList");
        if (!box) return;
        box.innerHTML = "";
        if (!S.materials.length) {
            box.innerHTML = '<div class="pack-empty-hint">Пока пусто — перетащи видео или импортируй по пути.</div>';
            return;
        }
        S.materials.forEach((name, i) => {
            const row = document.createElement("div");
            row.className = "template-row";
            row.innerHTML = '<span class="template-name"></span>';
            row.querySelector(".template-name").textContent = (i + 1) + ". " + name;
            const del = document.createElement("button");
            del.className = "btn-sm btn-danger";
            del.textContent = "✕";
            del.title = "Убрать";
            del.onclick = () => { S.materials.splice(i, 1); renderMaterials(); };
            row.appendChild(del);
            box.appendChild(row);
        });
    }

    function addMaterial(name) {
        if (!name) return;
        if (!S.materials.includes(name)) S.materials.push(name);
        renderMaterials();
    }

    async function importPath(path) {
        path = (path || "").trim();
        if (!path) return;
        status("Импорт " + path + " …");
        const j = await api("/api/media/import", { path });
        await refreshLibrary();
        addMaterial(j.filename || path.split(/[\\/]/).pop());
        status("Импортировано: " + (j.filename || path));
    }

    function initDrop() {
        const z = $("discDropZone");
        if (!z || z.dataset.discWired) return;
        z.dataset.discWired = "1";
        const css = ".disc-drop{border:1px dashed #2a3642;border-radius:10px;padding:18px;text-align:center;color:#8a9bb0;font:13px system-ui;margin-bottom:8px;cursor:pointer}.disc-drop.over{border-color:#39ff00;color:#39ff00;background:rgba(57,255,0,.06)}";
        const st = document.createElement("style");
        st.textContent = css;
        document.head.appendChild(st);
        ["dragenter", "dragover"].forEach(ev => z.addEventListener(ev, (e) => {
            e.preventDefault(); z.classList.add("over");
        }));
        ["dragleave", "drop"].forEach(ev => z.addEventListener(ev, (e) => {
            e.preventDefault(); z.classList.remove("over");
        }));
        z.addEventListener("drop", async (e) => {
            try {
                const raw = e.dataTransfer.getData("application/json");
                if (raw) {
                    const item = JSON.parse(raw);
                    if (item && item.filename) {
                        addMaterial(item.filename);
                        status("Добавлено: " + item.filename);
                        return;
                    }
                }
            } catch (err) { /* fall through to files */ }
            const files = (e.dataTransfer && e.dataTransfer.files) || [];
            for (const f of files) {
                try {
                    const fd = new FormData();
                    fd.append("file", f, f.name);
                    status("Загрузка " + f.name + " …");
                    const res = await fetch("/api/media/upload", { method: "POST", body: fd });
                    const j = await res.json();
                    if (!res.ok) throw new Error(j.detail || res.statusText);
                    await refreshLibrary();
                    addMaterial(j.filename);
                } catch (err) {
                    status("Ошибка: " + err.message);
                    return;
                }
            }
            if (files.length) status("Добавлено файлов: " + files.length);
        });
    }

    async function ensureMusic() {
        const srcEl = $("discMusicSrc");
        const src = (srcEl && srcEl.value.trim()) || DEFAULT_MUSIC_SRC;
        status("Импорт трека …");
        const j = await api("/api/studio/discipline/music", { source_path: src });
        S.musicFile = j.music_file;
        S.analysis = j.analysis || null;
        const st = $("discMusicStatus");
        if (st) st.textContent = j.music_file + " · дроп " + ((j.analysis && j.analysis.drop) || "?") + "с";
        await refreshLibrary();
        status("Трек готов: " + j.music_file);
        return j;
    }

    async function extractStills() {
        if (!S.materials.length) { status("Сначала добавь материалы."); return; }
        $("discStillsStatus").textContent = "извлекаю…";
        S.loops = [];
        for (const name of S.materials) {
            try {
                status("Кадры: " + name + " …");
                const j = await api("/api/studio/discipline/stills", { filename: name, n: 6 });
                for (const lp of (j.loops || [])) if (!S.loops.includes(lp)) S.loops.push(lp);
            } catch (err) {
                status("Кадры (" + name + "): " + err.message);
            }
        }
        await refreshLibrary();
        $("discStillsStatus").textContent = "картинок-луп: " + S.loops.length;
        status(S.loops.length ? ("Готово, лупов: " + S.loops.length) : "Кадры не извлечены — эдит соберётся только из видео.");
    }

    async function build() {
        if (!S.materials.length) { status("Добавь хотя бы одно видео."); return; }
        try {
            if (!S.musicFile) await ensureMusic();
            const dur = Number(($("discDurSelect") || {}).value || 21);
            const pics = Number(($("discPicsSelect") || {}).value || 4);
            status("Планирую эдит …");
            const plan = await api("/api/studio/discipline/plan", {
                materials: S.materials, music_file: S.musicFile,
                music_offset: 0, target_dur: dur, n_pics: pics
            });
            if (!window.Studio || !window.Studio.applyDisciplinePlan) {
                status("Редактор ещё грузится — подожди и нажми снова.");
                return;
            }
            const hasClips = (() => {
                try {
                    return document.querySelectorAll(".timeline-clip").length > 0;
                } catch (e) { return false; }
            })();
            const clear = hasClips ? window.confirm("Очистить таймлайн и построить эдит?") : true;
            if (!hasClips || clear) {
                window.Studio.applyDisciplinePlan(plan, { clear: true });
                status("Готово: " + plan.duration + "с, дроп " + plan.drop + "с. Жми «Экспортировать пак».");
            } else {
                status("Отменено.");
            }
        } catch (err) {
            status("Ошибка: " + err.message);
        }
    }

    function init() {
        initTabs();
        initDrop();
        renderMaterials();
        const srcEl = $("discMusicSrc");
        if (srcEl && !srcEl.value) srcEl.value = DEFAULT_MUSIC_SRC;
        const b = (id, fn) => { const el = $(id); if (el && !el.dataset.discWired) { el.dataset.discWired = "1"; el.addEventListener("click", fn); } };
        b("discImportBtn", () => importPath(($("discPathInput") || {}).value).catch(e => status("Ошибка: " + e.message)));
        b("discMusicBtn", () => ensureMusic().catch(e => status("Ошибка: " + e.message)));
        b("discStillsBtn", () => extractStills());
        b("discBuildBtn", () => build());
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
    else init();
})();
