// Kick Video Studio - Timeline & NLE Editor Engine
(function() {
    "use strict";

    // Studio Editor State
    const state = {
        currentTime: 0,         // sequence playhead in seconds
        totalDuration: 30,      // total sequence length in seconds
        zoom: 80,               // pixels per second (20 to 250)
        isPlaying: false,
        activeTool: "select",   // "select" or "split"
        selectedClipId: null,
        selectedRegionId: null, // selected export region (нарезка)
        regions: [],            // export regions = нарезки = очередь экспорта
        // Dynamic layer list (unlimited layers). Order = z-order (first = top for video).
        trackList: [],
        tracks: {},             // trackId -> clips[]
        mediaLibrary: [],
        lastFrameTime: 0,
        // Viral Shorts Clipper & Groq Whisper Subtitles State
        clipper: {
            format: "split_adhd",       // split_adhd, talking_head_9_16, cinematic_16_9
            sourceFile: "",
            bgFile: "",
            noBg: true,
            cropPreset: "top_right",    // legacy, unused by TV templates
            platform: "KICK",           // legacy, unused by TV templates
            streamerHandle: "@jesusavgn",
            inTime: null,
            outTime: null,
            subtitleTemplate: "acid",   // acid, lime, cyan, yellow, meme, ...
            subFont: "Anton",           // Anton | Bebas Neue | Russo One | Oswald | Montserrat | Lobster | Arial Black | Impact
            subSize: 1.0,               // 0.7 .. 1.4
            subGlow: 45,                // 0 .. 100
            subAnim: "pop",             // pop | wave | none
            wordsPerCue: 3,             // max words per subtitle clip
            subLang: "ru",              // transcribe language
            exportSeparate: false,      // each region -> own file
            colorGrade: "tv",             // none | tv (AE-град + превью)
            flashCuts: true,           // белые вспышки между нарезками
            cropBox: null,              // область вебки {x,y,w,h} 0..1 (page-recording стримы)
            bgBox: null,                // область фона/геймплея {x,y,w,h} 0..1 (низ сплита)
            hotWords: false,            // §12.6: длина-эвристика выкл. по умолчанию — акценты вручную
            markers: [],                // §7.1: ручные маркеры во время просмотра VOD
            subtitles: [],              // list of segments with word timestamps
            pack: []                    // legacy, replaced by state.regions
        },
        previewFps: 60,                 // §16.5: preview frame grid (±1/fps stepping)
        aspectRatio: "16:9",            // "16:9" or "9:16"
        previewStopAt: null             // auto-pause position for moment preview
    };

    // ── Dynamic Track Model (unlimited layers) ──
    function defaultTrackList() {
        return [
            { id: "v3", kind: "text",  name: "Субтитры / Текст", hidden: false, locked: false, muted: false },
            { id: "v2", kind: "video", name: "Оверлей / Вебка",  hidden: false, locked: false, muted: false },
            { id: "v1", kind: "video", name: "Основное видео",   hidden: false, locked: false, muted: false },
            { id: "a1", kind: "audio", name: "Звук стрима",      hidden: false, locked: false, muted: false },
            { id: "a2", kind: "audio", name: "Фон / Музыка",     hidden: false, locked: false, muted: false }
        ];
    }
    function ensureTracksInitialized() {
        if (!Array.isArray(state.trackList) || state.trackList.length === 0) {
            state.trackList = defaultTrackList();
            state.tracks = {};
        }
        state.trackList.forEach(t => {
            if (!Array.isArray(state.tracks[t.id])) state.tracks[t.id] = [];
        });
    }
    function trackOrder() {
        ensureTracksInitialized();
        return state.trackList.map(t => t.id);
    }
    function getTrack(tid) {
        return state.trackList.find(t => t.id === tid) || null;
    }
    function isTrackLocked(tid) {
        const t = getTrack(tid);
        return !!(t && t.locked);
    }
    function trackClips(tid) {
        ensureTracksInitialized();
        return state.tracks[tid] || [];
    }
    function textTrackId() {
        const t = state.trackList.find(t => t.kind === "text");
        return t ? t.id : null;
    }
    function firstVideoTrackId() {
        // bottom-most video track = main layer
        const vids = state.trackList.filter(t => t.kind === "video");
        return vids.length ? vids[vids.length - 1].id : null;
    }
    function videoTrackIds() {
        return state.trackList.filter(t => t.kind === "video").map(t => t.id);
    }
    function audioTrackIds() {
        return state.trackList.filter(t => t.kind === "audio").map(t => t.id);
    }
    function trackTagLabel(tid) {
        const t = getTrack(tid);
        if (!t) return "—";
        const prefix = t.kind === "audio" ? "A" : (t.kind === "text" ? "T" : "V");
        return `${prefix}${state.trackList.indexOf(t) + 1}`;
    }
    function trackDisplayName(tid) {
        const t = getTrack(tid);
        return t ? `${trackTagLabel(tid)} · ${t.name}` : "Слой";
    }
    function isAudioFile(media) {
        if (!media) return false;
        const ext = String(media.filename || "").split(".").pop().toLowerCase();
        return ["mp3", "wav", "m4a", "aac", "ogg", "flac"].includes(ext);
    }

    // DOM Elements Cache
    let videoEl, monitorOverlay, noClipPlaceholder, videoMonitor;
    let subtitlesMonitorOverlay, badgeMonitorOverlay, aspectRatioToggleBtn;
    let rulerCanvas, rulerCtx, timeRuler, lanesContainer, playhead, trackLanesArea, timelineScrollContainer;
    let headerCurrentTime, headerTotalTime, monitorCurrentTc;
    let playIcon, pauseIcon, btnPlayPause;
    let mediaLibraryList, mediaCountBadge, libraryEmptyState;
    let tabBtnLibrary, tabBtnKick, tabBtnClipper, tabBtnInspector;
    let tabContentLibrary, tabContentKick, tabContentClipper, tabContentInspector;
    let inspectorEmpty, inspectorDetails, inspectorClipTitle, inspectorTrackBadge;
    let inspectorStartTime, inspectorDuration, clipVolumeSlider, clipVolumeVal, clipOpacitySlider, clipOpacityVal;

    // Helpers: Format seconds to 00:00:00:00 (Timecode format at 60fps)
    function formatTimecode(seconds, fps = 60) {
        if (isNaN(seconds) || seconds < 0) seconds = 0;
        const totalFrames = Math.floor(seconds * fps);
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = Math.floor(seconds % 60);
        const f = totalFrames % fps;

        const pad = (n) => String(n).padStart(2, "0");
        return `${pad(h)}:${pad(m)}:${pad(s)}:${pad(f)}`;
    }

    function formatDurationShort(sec) {
        if (sec === null || sec === undefined || isNaN(sec) || sec < 0) return "--:--";
        const s = Math.floor(sec);
        const m = Math.floor(s / 60);
        const remS = s % 60;
        const pad = (n) => String(n).padStart(2, "0");
        return `${pad(m)}:${pad(remS)}`;
    }

    // Initialize Studio on DOM Ready
    document.addEventListener("DOMContentLoaded", () => {
        ensureTracksInitialized();
        initDOMElements();
        initTabs();
        renderTracksDOM();
        initCanvas();
        initTransport();
        initTimelineInteraction();
        initTools();
        initInspector();
        initClipperPanel();
        initMultiPreview();
        initCanvasMonitor();
        initTimelineMarkers();
        initCutsTree();
        initTrackingUI();
        initTemplates();
        initDockToggle();
        initResizers();
        try {
            const tab = new URLSearchParams(location.search).get("tab");
            if (tab === "clipper" || tab === "kick" || tab === "library" || tab === "inspector") {
                switchTab(tab);
            }
        } catch (e) {}
        initSfxLibrary();
        restoreProject();
        renderPackClips();
        recalcTotalDuration();
        updateTimecodeDisplays();
        updatePlayheadPosition();
        updateMarkerRangeUI();
        fetchLibrary();

        // Global Keyboard Shortcuts
        window.addEventListener("keydown", (e) => {
            if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT") return;
            if (e.code === "Space") {
                e.preventDefault();
                togglePlay();
            } else if (e.code === "KeyC") {
                splitClipAtPlayhead();
            } else if (e.code === "KeyN") {
                addRegionFromPlayhead();
            } else if (e.code === "KeyS") {
                splitSelectedRegion();
            } else if (e.code === "KeyI") {
                const r = findRegionById(state.selectedRegionId);
                if (r) {
                    const end = r.startTime + r.duration;
                    r.startTime = Math.max(0, Math.min(state.currentTime, end - 0.3));
                    r.duration = end - r.startTime;
                    renderRegionsLane(); renderRegionsList(); updateRegionToolbarUI(); saveProject();
                } else addRegionFromPlayhead();
            } else if (e.code === "KeyO") {
                const r = findRegionById(state.selectedRegionId);
                if (r) {
                    r.duration = Math.max(0.3, state.currentTime - r.startTime);
                    renderRegionsLane(); renderRegionsList(); updateRegionToolbarUI(); saveProject();
                }
            } else if (e.code === "KeyV") {
                setTool("select");
            } else if (e.code === "KeyM") {
                // §7.1: маркер в текущей точке (Shift+M — с заметкой)
                addMarkerAtPlayhead(e.shiftKey);
            } else if (e.code === "Enter") {
                addRegionFromNearestMarker();
            } else if (e.code === "KeyF") {
                // §7.3: вспышка ровно в плейхеде (Shift+F — цвет по кругу)
                const colors = ["white", "red", "green"];
                if (state._fxColorIdx == null) state._fxColorIdx = 0;
                const col = e.shiftKey ? colors[(state._fxColorIdx++) % colors.length] : "white";
                addEffectAtPlayhead("flash", col, { duration: 0.18, peak: 0.95, fxPeak: 0.95, fxSound: "impact_epic" });  // studio:flash-fxpeak
            } else if (e.code === "KeyX") {
                // §7.3: шейк 14 px / 350 мс в плейхеде
                addEffectAtPlayhead("shake", "white", { duration: 0.35, fxAmp: 14, fxSound: "whoosh_fast" });
            } else if (e.code === "KeyZ") {
                // §7.3: zoom punch 1->1.15, пружина 12%/220 мс (+ радиальный смаз в рендерере)
                addEffectAtPlayhead("zoom", "white", { duration: 0.35, fxPeak: 0.15, fxSound: "whoosh_cinematic" });
            } else if (e.code === "KeyL") {
                // §7.3: Lens punch (§13.3): бочка + CA, 250 мс
                addEffectAtPlayhead("lens", "white", { duration: 0.25, fxPeak: 0.18, fxSound: "whoosh_magic" });
            } else if (e.code === "KeyB") {
                // §7.3: threshold hit, 2 кадра
                addEffectAtPlayhead("threshold", "white", { duration: 0.067, fxPeak: 0.45, fxSound: "hit_small" });
            } else if (e.code === "KeyW") {
                // §7.3: whip-переход НА БЛИЖАЙШЕМ РЕЗЕ
                addEffectAtPlayhead("whip", "white", { duration: 0.12, fxSound: "whoosh_fast", snapToCut: true });
            } else if (e.code === "KeyR") {
                // §7.3: speed ramp 0.35x -> 1.8x вокруг плейхеда (маркер для рендерера)
                addEffectAtPlayhead("ramp", "white", { duration: 0.6, fxSound: "riser" });
            } else if (e.code === "KeyE") {
                // §7.3: стоп-кадр + зум 0.6 с (маркер для рендерера)
                addEffectAtPlayhead("freeze", "white", { duration: 0.6, fxSound: "camera_click" });
            } else if (e.code === "KeyP" && e.altKey) {
                saveChannelPreset();
            } else if (e.code === "KeyP") {
                applyChannelPreset();
            } else if (e.code === "Delete" || e.code === "Backspace") {
                if (state.selectedRegionId) {
                    deleteSelectedRegion();
                } else if (state.selectedClipId) {
                    deleteSelectedClip();
                }
            } else if (e.code === "ArrowLeft" || e.code === "Comma") {
                if (state.isPlaying) pausePlayback();
                seekRelative(e.shiftKey ? -1 : -1 / (state.previewFps || 60));
            } else if (e.code === "ArrowRight" || e.code === "Period") {
                if (state.isPlaying) pausePlayback();
                seekRelative(e.shiftKey ? 1 : 1 / (state.previewFps || 60));
            } else if (e.code === "Home") {
                seekTo(0);
            } else if (e.code === "End") {
                seekTo(state.totalDuration);
            }
        });

        // Window resize event for canvas & timeline scaling
        window.addEventListener("resize", () => {
            resizeCanvas();
            renderTimeline();
        });
    });

    function initDOMElements() {
        videoEl = document.getElementById("studioVideoPlayer");
        videoMonitor = document.getElementById("videoMonitor");
        monitorOverlay = document.getElementById("monitorOverlay");
        noClipPlaceholder = document.getElementById("noClipPlaceholder");
        subtitlesMonitorOverlay = document.getElementById("subtitlesMonitorOverlay");
        badgeMonitorOverlay = document.getElementById("badgeMonitorOverlay");
        aspectRatioToggleBtn = document.getElementById("aspectRatioToggleBtn");

        rulerCanvas = document.getElementById("rulerCanvas");
        rulerCtx = rulerCanvas.getContext("2d");
        timeRuler = document.getElementById("timeRuler");
        lanesContainer = document.getElementById("lanesContainer");
        playhead = document.getElementById("playhead");
        trackLanesArea = document.getElementById("trackLanesArea");
        timelineScrollContainer = document.getElementById("timelineScrollContainer");

        headerCurrentTime = document.getElementById("headerCurrentTime");
        headerTotalTime = document.getElementById("headerTotalTime");
        monitorCurrentTc = document.getElementById("monitorCurrentTc");

        btnPlayPause = document.getElementById("btnPlayPause");
        playIcon = document.getElementById("playIcon");
        pauseIcon = document.getElementById("pauseIcon");

        mediaLibraryList = document.getElementById("mediaLibraryList");
        mediaCountBadge = document.getElementById("mediaCountBadge");
        libraryEmptyState = document.getElementById("libraryEmptyState");

        tabBtnLibrary = document.getElementById("tabBtnLibrary");
        tabBtnKick = document.getElementById("tabBtnKick");
        tabBtnClipper = document.getElementById("tabBtnClipper");
        tabBtnInspector = document.getElementById("tabBtnInspector");

        tabContentLibrary = document.getElementById("tabContentLibrary");
        tabContentKick = document.getElementById("tabContentKick");
        tabContentClipper = document.getElementById("tabContentClipper");
        tabContentInspector = document.getElementById("tabContentInspector");

        inspectorEmpty = document.getElementById("inspectorEmpty");
        inspectorDetails = document.getElementById("inspectorDetails");
        inspectorClipTitle = document.getElementById("inspectorClipTitle");
        inspectorTrackBadge = document.getElementById("inspectorTrackBadge");
        inspectorStartTime = document.getElementById("inspectorStartTime");
        inspectorDuration = document.getElementById("inspectorDuration");
        clipVolumeSlider = document.getElementById("clipVolumeSlider");
        clipVolumeVal = document.getElementById("clipVolumeVal");
        clipOpacitySlider = document.getElementById("clipOpacitySlider");
        clipOpacityVal = document.getElementById("clipOpacityVal");
    }

    // Tabs Switcher
    function initTabs() {
        const tabs = [
            { btn: tabBtnLibrary, content: tabContentLibrary, id: "library" },
            { btn: tabBtnKick, content: tabContentKick, id: "kick" },
            { btn: tabBtnClipper, content: tabContentClipper, id: "clipper" },
            { btn: tabBtnInspector, content: tabContentInspector, id: "inspector" }
        ];

        tabs.forEach(t => {
            if (!t.btn || !t.content) return;
            t.btn.addEventListener("click", () => {
                tabs.forEach(o => {
                    if (o.btn) o.btn.classList.remove("active");
                    if (o.content) o.content.classList.remove("active");
                });
                t.btn.classList.add("active");
                t.content.classList.add("active");
            });
        });
    }

    function switchTab(tabId) {
        if (tabId === "library" && tabBtnLibrary) tabBtnLibrary.click();
        else if (tabId === "kick" && tabBtnKick) tabBtnKick.click();
        else if (tabId === "clipper" && tabBtnClipper) tabBtnClipper.click();
        else if (tabId === "inspector" && tabBtnInspector) tabBtnInspector.click();
    }

    // Canvas & Time Ruler: virtual ruler (fixed viewport canvas, scroll-offset drawing).
    // Fixes "page breaks on zoom": canvas is never wider than the visible area,
    // lanes carry the full logical width, ruler redraws on scroll/zoom.
    const MAX_LANES_PX = 400000;
    function timelineContentWidth() {
        const padSec = 30;
        const total = Math.ceil((state.totalDuration + padSec) * state.zoom);
        return Math.max(400, Math.min(MAX_LANES_PX, total));
    }
    function visibleLanesWidth() {
        if (!timelineScrollContainer) return 800;
        return Math.max(200, timelineScrollContainer.clientWidth - 180);
    }
    function initCanvas() {
        resizeCanvas();
        if (timelineScrollContainer) {
            timelineScrollContainer.addEventListener("scroll", () => drawRuler(), { passive: true });
        }
    }

    function resizeCanvas() {
        if (!rulerCanvas || !timelineScrollContainer) return;
        const totalPixels = timelineContentWidth();
        const visW = visibleLanesWidth();

        if (trackLanesArea) {
            trackLanesArea.style.width = `${totalPixels}px`;
            trackLanesArea.style.minWidth = `${totalPixels}px`;
        }
        if (lanesContainer) {
            lanesContainer.style.width = `${totalPixels}px`;
            lanesContainer.style.minWidth = `${totalPixels}px`;
        }
        if (timeRuler) {
            timeRuler.style.width = `${totalPixels}px`;
            timeRuler.style.minWidth = `${totalPixels}px`;
        }
        // Virtual canvas: only as wide as visible viewport (crash-proof at any zoom)
        const dpr = Math.min(2, window.devicePixelRatio || 1);
        rulerCanvas.width = Math.max(50, Math.floor(visW * dpr));
        rulerCanvas.height = 28 * dpr;
        rulerCanvas.style.width = `${visW}px`;
        rulerCanvas.style.height = "28px";
        rulerCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
        drawRuler();
    }

    function drawRuler() {
        if (!rulerCtx || !rulerCanvas || !timelineScrollContainer) return;
        const dpr = Math.min(2, window.devicePixelRatio || 1);
        const visW = visibleLanesWidth();
        // Keep canvas in sync with viewport size (resize-safe)
        const wantW = Math.max(50, Math.floor(visW * dpr));
        if (rulerCanvas.width !== wantW) {
            rulerCanvas.width = wantW;
            rulerCanvas.height = 28 * dpr;
            rulerCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
        }
        const scrollLeft = timelineScrollContainer.scrollLeft || 0;
        rulerCtx.clearRect(0, 0, visW, 28);

        const zoom = state.zoom;
        let step = 1; // major tick interval in seconds
        if (zoom < 12) step = 10;
        else if (zoom < 28) step = 5;
        else if (zoom < 60) step = 2;
        else if (zoom > 160) step = 0.5;

        rulerCtx.fillStyle = "#8E99A2";
        rulerCtx.font = "10px 'JetBrains Mono', monospace";
        rulerCtx.textAlign = "left";
        rulerCtx.strokeStyle = "rgba(255, 255, 255, 0.14)";
        rulerCtx.lineWidth = 1;

        const startSec = Math.floor((scrollLeft / zoom) / step) * step;
        const endSec = (scrollLeft + visW) / zoom + step;
        // Align ticks to absolute timeline (subtract scroll offset for screen x)
        for (let sec = Math.max(0, startSec); sec <= endSec; sec += step) {
            // avoid float drift
            const rSec = Math.round(sec * 100) / 100;
            const x = Math.round(rSec * zoom - scrollLeft) + 0.5;

            // Major tick
            rulerCtx.beginPath();
            rulerCtx.moveTo(x, 0);
            rulerCtx.lineTo(x, 14);
            rulerCtx.stroke();

            // Format label (MM:SS)
            const m = Math.floor(rSec / 60);
            const s = Math.floor(rSec % 60);
            const label = `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
            rulerCtx.fillText(label, x + 4, 20);

            // Minor ticks
            const subSteps = step >= 5 ? 5 : 4;
            for (let sub = 1; sub < subSteps; sub++) {
                const subSec = rSec + (step / subSteps) * sub;
                const subX = Math.round(subSec * zoom - scrollLeft) + 0.5;
                if (subX < 0 || subX > visW) continue;
                rulerCtx.beginPath();
                rulerCtx.moveTo(subX, 0);
                rulerCtx.lineTo(subX, 6);
                rulerCtx.stroke();
            }
        }
    }

    // Media Library Fetch & Display
    async function fetchLibrary() {
        try {
            const res = await fetch("/api/media/library");
            if (res.ok) {
                state.mediaLibrary = await res.json();
                renderMediaLibrary();
                // Fresh start: put the first available video straight on V1
                // so layers and preview are alive immediately, not empty.
                let hasSave = false;
                try { hasSave = !!localStorage.getItem(PROJECT_KEY); } catch (e) {}
                if (!hasSave && totalClipCount() === 0 && state.mediaLibrary.length > 0) {
                    const vid = state.mediaLibrary.find(m => !isAudioFile(m)) || state.mediaLibrary[0];
                    addMediaToTimeline(vid, firstVideoTrackId() || "v1", 0);
                    state.clipper.sourceFile = vid.filename;
                }
            }
        } catch (e) {
            console.error("Ошибка загрузки библиотеки ресурсов:", e);
        }
    }

    function renderMediaLibrary() {
        if (!mediaLibraryList) return;
        mediaLibraryList.innerHTML = "";
        if (mediaCountBadge) mediaCountBadge.textContent = state.mediaLibrary.length;

        if (state.mediaLibrary.length === 0) {
            if (libraryEmptyState) {
                mediaLibraryList.appendChild(libraryEmptyState);
                libraryEmptyState.classList.remove("hidden");
            }
            return;
        }

        if (libraryEmptyState) libraryEmptyState.classList.add("hidden");

        state.mediaLibrary.forEach(item => {
            const card = document.createElement("div");
            card.className = "media-card";
            card.draggable = true;
            card.title = "Перетащите на таймлайн или кликните «На таймлайн»";

            card.addEventListener("dragstart", (e) => {
                e.dataTransfer.setData("application/json", JSON.stringify(item));
                e.dataTransfer.effectAllowed = "copy";
                card.style.opacity = "0.5";
            });

            card.addEventListener("dragend", () => {
                card.style.opacity = "1";
            });

            const thumbWrap = document.createElement("div");
            thumbWrap.className = "media-thumb-wrap";
            const img = document.createElement("img");
            img.src = item.thumb_url || "";
            img.alt = item.title;
            img.onerror = () => { img.style.display = "none"; };
            const durTag = document.createElement("span");
            durTag.className = "media-card-duration";
            durTag.textContent = item.duration_str || "00:00";
            thumbWrap.appendChild(img);
            thumbWrap.appendChild(durTag);

            const infoWrap = document.createElement("div");
            infoWrap.className = "media-info-wrap";

            const title = document.createElement("div");
            title.className = "media-title-text";
            title.textContent = item.title;
            title.title = item.filename;

            const badges = document.createElement("div");
            badges.className = "media-meta-badges";
            const resBadge = document.createElement("span");
            resBadge.className = "badge-res";
            resBadge.textContent = item.height ? `${item.height}p` : "HD";
            const sizeBadge = document.createElement("span");
            sizeBadge.className = "badge-size";
            sizeBadge.textContent = item.size_formatted;
            badges.appendChild(resBadge);
            badges.appendChild(sizeBadge);

            const actions = document.createElement("div");
            actions.className = "media-card-actions";

            const addBtn = document.createElement("button");
            addBtn.className = "btn-add-track";
            addBtn.innerHTML = "На таймлайн";
            addBtn.addEventListener("click", () => {
                addMediaToTimeline(item, "v1");
            });

            const toClipperBtn = document.createElement("button");
            toClipperBtn.className = "mini-action-btn";
            toClipperBtn.title = "Сделать это видео источником для нарезок Shorts";
            toClipperBtn.textContent = "В Shorts";
            toClipperBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                state.clipper.sourceFile = item.filename;
                switchTab("clipper");
            });

            const delBtn = document.createElement("button");
            delBtn.className = "btn-del-media";
            delBtn.title = "Удалить файл из библиотеки";
            delBtn.innerHTML = "×";
            delBtn.addEventListener("click", async (e) => {
                e.stopPropagation();
                const ok = await showConfirm(`Удалить видео «${item.filename}»?`, "Удалить");
                if (ok) {
                    await deleteMediaFile(item.filename);
                }
            });

            actions.appendChild(addBtn);
            actions.appendChild(toClipperBtn);
            actions.appendChild(delBtn);

            infoWrap.appendChild(title);
            infoWrap.appendChild(badges);
            infoWrap.appendChild(actions);

            card.appendChild(thumbWrap);
            card.appendChild(infoWrap);

            mediaLibraryList.appendChild(card);
        });
    }

    async function deleteMediaFile(filename) {
        try {
            const res = await fetch("/api/media/delete", {
                method: "DELETE",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ filename })
            });
            if (res.ok) {
                if (window.__canvasMonitor && typeof window.__canvasMonitor.dropMedia === "function") {
                    try { window.__canvasMonitor.dropMedia(filename); } catch (_) {}
                }
                fetchLibrary();
            }
        } catch (e) {
            console.error("Ошибка удаления:", e);
        }
    }

    // Add media to timeline at current playhead or after last clip
    function addMediaToTimeline(media, trackId = null, desiredStartTime = null) {
        ensureTracksInitialized();
        const mediaIsAudio = isAudioFile(media);
        const mediaIsImage = media && media.kind === "image";
        // Auto-route by file type: audio files to an audio track, videos/images to a video track
        if (!trackId || !getTrack(trackId)) trackId = firstVideoTrackId() || trackOrder()[0];
        if (mediaIsAudio) {
            const auds = audioTrackIds();
            if (auds.length) trackId = auds[auds.length - 1];
        } else if (getTrack(trackId) && (getTrack(trackId).kind === "audio" || getTrack(trackId).kind === "text")) {
            const vids = videoTrackIds();
            if (vids.length) trackId = vids[vids.length - 1];
        }
        const trackClipsArr = trackClips(trackId);
        let startTime = desiredStartTime !== null ? desiredStartTime : state.currentTime;

        if (desiredStartTime === null && trackClipsArr.length > 0) {
            const lastClip = trackClipsArr[trackClipsArr.length - 1];
            if (startTime < lastClip.startTime + lastClip.duration) {
                startTime = lastClip.startTime + lastClip.duration;
            }
        }

        const duration = media.duration > 0 ? media.duration : 15;

        const newClip = {
            id: "clip_" + Date.now() + "_" + Math.random().toString(36).substr(2, 5),
            trackId: trackId,
            startTime: startTime,
            duration: duration,
            sourceOffset: 0,
            sourceDuration: duration,
            media: media,
            volume: 1.0,
            opacity: 1.0
        };

        trackClipsArr.push(newClip);
        trackClipsArr.sort((a, b) => a.startTime - b.startTime);
        state.tracks[trackId] = trackClipsArr;

        selectClip(newClip.id);
        recalcTotalDuration();
        renderTimeline();
        renderCutsTree();
        seekTo(startTime);
    }

    // Recalculate Sequence Duration
    function recalcTotalDuration() {
        let maxEnd = 30;
        Object.values(state.tracks).forEach(track => {
            track.forEach(clip => {
                const clipEnd = clip.startTime + clip.duration;
                if (clipEnd > maxEnd) maxEnd = clipEnd;
            });
        });
        state.totalDuration = Math.ceil(maxEnd);
        if (headerTotalTime) headerTotalTime.textContent = formatTimecode(state.totalDuration);
        resizeCanvas();
    }

    // Render Timeline Clips across all dynamic tracks
    function renderTimeline() {
        ensureTracksInitialized();
        state.trackList.forEach(track => {
            const lane = document.getElementById("lane_" + track.id);
            if (!lane) return;

            // Remove existing clips
            lane.querySelectorAll(".timeline-clip").forEach(el => el.remove());

            const clips = state.tracks[track.id] || [];
            clips.forEach(clip => {
                const clipEl = document.createElement("div");
                clipEl.className = `timeline-clip clip-${track.kind}`;
                if (clip.isFx) {
                    clipEl.classList.add("clip-fx", "fx-" + (clip.fxKind || "flash"));
                    const stripe = { white: "#ffffff", green: "#39ff00", red: "#ff2222", bw: "#888888" }[clip.fxColor || "white"] || "#ffffff";
                    clipEl.style.setProperty("--fx-stripe", stripe);
                    clip.title = fxLabel(clip);
                }
                if (clip.id === state.selectedClipId) {
                    clipEl.classList.add("selected");
                }
                clipEl.id = clip.id;

                const left = clip.startTime * state.zoom;
                const width = Math.max(30, clip.duration * state.zoom);
                clipEl.style.left = `${left}px`;
                clipEl.style.width = `${width}px`;

                // Thumb & text column
                const thumbMini = document.createElement("div");
                thumbMini.className = "clip-thumb-mini";
                const img = document.createElement("img");
                img.src = (clip.media && clip.media.thumb_url) ? clip.media.thumb_url : "";
                img.onerror = () => { thumbMini.style.display = "none"; };
                thumbMini.appendChild(img);

                const textCol = document.createElement("div");
                textCol.className = "clip-text-content";
                const titleLbl = document.createElement("div");
                titleLbl.className = "clip-title-label";
                titleLbl.textContent = (clip.media && clip.media.title) ? clip.media.title : (clip.title || "Клип");
                const durLbl = document.createElement("div");
                durLbl.className = "clip-dur-label";
                durLbl.textContent = `${clip.duration.toFixed(1)}s`;
                textCol.appendChild(titleLbl);
                textCol.appendChild(durLbl);

                // Cut badge: shows source offset so different нарезки of one file are distinguishable
                if (clip.media && (clip.sourceOffset || 0) > 0.01) {
                    const cutBadge = document.createElement("div");
                    cutBadge.className = "clip-cut-badge";
                    cutBadge.textContent = `✂ ${formatDurationShort(clip.sourceOffset)}`;
                    cutBadge.title = `Источник: с ${formatDurationShort(clip.sourceOffset)} по ${formatDurationShort(clip.sourceOffset + clip.duration)}`;
                    clipEl.appendChild(cutBadge);
                }

                // Tracked badge
                if (clip.trackPath && clip.trackPath.length) {
                    const trkBadge = document.createElement("div");
                    trkBadge.className = "clip-track-badge";
                    trkBadge.textContent = "◎ track";
                    trkBadge.title = `Трекинг объекта: ${clip.trackPath.length} ключей`;
                    clipEl.appendChild(trkBadge);
                }

                // Trim Handles
                const leftHandle = document.createElement("div");
                leftHandle.className = "clip-handle clip-handle-left";
                leftHandle.title = "Подрезка начала";
                initTrimHandle(leftHandle, clip, "left");

                const rightHandle = document.createElement("div");
                rightHandle.className = "clip-handle clip-handle-right";
                rightHandle.title = "Подрезка конца";
                initTrimHandle(rightHandle, clip, "right");

                clipEl.appendChild(leftHandle);
                clipEl.appendChild(thumbMini);
                clipEl.appendChild(textCol);
                clipEl.appendChild(rightHandle);

                // Razor click or selection
                clipEl.addEventListener("mousedown", (e) => {
                    if (e.target.classList.contains("clip-handle")) return;
                    e.stopPropagation();

                    if (state.activeTool === "split") {
                        // Razor tool split at click point
                        const rect = clipEl.getBoundingClientRect();
                        const clickSec = clip.startTime + ((e.clientX - rect.left) / state.zoom);
                        splitClipAtTimestamp(clip, clickSec);
                        return;
                    }

                    selectClip(clip.id);
                    initClipDrag(clipEl, clip, e);
                });

                lane.appendChild(clipEl);
            });
        });

        updateMarkerRangeUI();
        renderRegionsLane();
        updatePlayheadPosition();
    }

    // ── Dynamic Tracks DOM: headers + lanes are (re)built from state.trackList ──
    const TRACK_ICONS = {
        eye: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>',
        lock: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>'
    };
    function renderTracksDOM() {
        ensureTracksInitialized();
        const headersList = document.getElementById("trackHeadersList");
        if (headersList) {
            headersList.innerHTML = "";
            // Header cell aligned with the regions lane
            const rgHead = document.createElement("div");
            rgHead.className = "track-header region-header-spacer";
            rgHead.innerHTML = `<div class="track-title-row"><span class="track-tag tag-region">R</span><span class="track-name">Нарезки</span></div><div class="track-btns"></div>`;
            const rgAdd = document.createElement("button");
            rgAdd.className = "track-action-btn";
            rgAdd.textContent = "+";
            rgAdd.title = "Новая нарезка от плейхеда";
            rgAdd.addEventListener("click", addRegionFromPlayhead);
            rgHead.querySelector(".track-btns").appendChild(rgAdd);
            headersList.appendChild(rgHead);
            state.trackList.forEach(track => {
                const header = document.createElement("div");
                header.className = "track-header";
                header.dataset.trackId = track.id;

                const titleRow = document.createElement("div");
                titleRow.className = "track-title-row";
                const tag = document.createElement("span");
                tag.className = "track-tag " + (track.kind === "text" ? "tag-sub" : (track.kind === "audio" ? "tag-audio" : "tag-video"));
                tag.textContent = trackTagLabel(track.id);
                const name = document.createElement("span");
                name.className = "track-name";
                name.textContent = track.name;
                name.title = "Двойной клик — переименовать слой";
                name.addEventListener("dblclick", () => {
                    showPrompt("Название слоя:", track.name).then(newName => {
                        if (newName && newName.trim()) {
                            track.name = newName.trim().slice(0, 40);
                            renderTracksDOM();
                        }
                    });
                });
                titleRow.appendChild(tag);
                titleRow.appendChild(name);

                const btns = document.createElement("div");
                btns.className = "track-btns";

                if (track.kind === "audio") {
                    const mute = document.createElement("button");
                    mute.className = "track-action-btn track-mute-btn" + (track.muted ? " muted" : "");
                    mute.textContent = track.muted ? "M×" : "M";
                    mute.title = "Заглушить звук дорожки";
                    mute.addEventListener("click", () => {
                        track.muted = !track.muted;
                        mute.classList.toggle("muted", track.muted);
                        mute.textContent = track.muted ? "M×" : "M";
                        syncVideoToCurrentTime();
                    });
                    btns.appendChild(mute);
                } else {
                    const eye = document.createElement("button");
                    eye.className = "track-action-btn track-eye-btn" + (track.hidden ? " off" : "");
                    eye.innerHTML = TRACK_ICONS.eye;
                    eye.title = "Показать/скрыть слой";
                    eye.addEventListener("click", () => {
                        track.hidden = !track.hidden;
                        eye.classList.toggle("off", track.hidden);
                        renderTimeline();
                        syncVideoToCurrentTime();
                        updateLiveSubtitleOverlay();
                    });
                    btns.appendChild(eye);
                }

                const lock = document.createElement("button");
                lock.className = "track-action-btn track-lock-btn" + (track.locked ? " on" : "");
                lock.innerHTML = TRACK_ICONS.lock;
                lock.title = "Заблокировать слой";
                lock.addEventListener("click", () => {
                    track.locked = !track.locked;
                    lock.classList.toggle("on", track.locked);
                    renderTimeline();
                });
                btns.appendChild(lock);

                const up = document.createElement("button");
                up.className = "track-action-btn track-move-btn";
                up.textContent = "↑";
                up.title = "Слой выше (ближе к зрителю)";
                up.addEventListener("click", () => moveTrack(track.id, -1));
                const down = document.createElement("button");
                down.className = "track-action-btn track-move-btn";
                down.textContent = "↓";
                down.title = "Слой ниже (дальше от зрителя)";
                down.addEventListener("click", () => moveTrack(track.id, 1));
                btns.appendChild(up);
                btns.appendChild(down);

                const del = document.createElement("button");
                del.className = "track-action-btn track-del-btn";
                del.textContent = "×";
                del.title = "Удалить слой (и все его клипы)";
                del.addEventListener("click", () => removeTrack(track.id));
                btns.appendChild(del);

                header.appendChild(titleRow);
                header.appendChild(btns);
                headersList.appendChild(header);
            });
        }

        // Lanes
        if (lanesContainer) {
            lanesContainer.querySelectorAll(".track-lane").forEach(el => el.remove());
            const playheadEl = document.getElementById("playhead");
            state.trackList.forEach(track => {
                const lane = document.createElement("div");
                lane.className = "track-lane lane-kind-" + track.kind;
                lane.dataset.trackId = track.id;
                lane.id = "lane_" + track.id;
                const hint = document.createElement("div");
                hint.className = "lane-drop-hint";
                hint.textContent = track.kind === "audio"
                    ? `${track.name} — перетащите сюда звук`
                    : (track.kind === "text" ? `${track.name}` : `${track.name} — перетащите видео`);
                lane.appendChild(hint);
                if (playheadEl) {
                    lanesContainer.insertBefore(lane, playheadEl);
                } else {
                    lanesContainer.appendChild(lane);
                }
            });
            bindLaneInteractions();
        }
        syncLanesHeight();
    }

    let laneInteractionsBound = false;
    function bindLaneInteractions() {
        // Drag&drop and scrubbing are delegated on lanesContainer (see initTimelineInteraction)
        laneInteractionsBound = true;
    }

    function syncLanesHeight() {
        // Headers column and lanes must stay aligned; both use fixed heights per kind.
        const col = document.querySelector(".track-headers-col");
        if (col) col.style.setProperty("--tracks-count", String(state.trackList.length));
    }

    function addTrack(kind) {
        ensureTracksInitialized();
        const countSame = state.trackList.filter(t => t.kind === kind).length;
        const newTrack = {
            id: "t" + Date.now().toString(36) + Math.random().toString(36).slice(2, 5),
            kind,
            name: kind === "audio" ? `Звук ${countSame + 1}` : (kind === "text" ? `Текст ${countSame + 1}` : `Видео ${countSame + 1}`),
            hidden: false, locked: false, muted: false
        };
        if (kind === "audio") {
            state.trackList.push(newTrack); // lowest audio lane at the bottom
        } else if (kind === "text") {
            const firstVideoIdx = state.trackList.findIndex(t => t.kind === "video");
            state.trackList.splice(firstVideoIdx >= 0 ? firstVideoIdx : 0, 0, newTrack);
        } else {
            // new video layer goes on top of existing video layers (below text)
            let insertIdx = state.trackList.findIndex(t => t.kind === "video");
            if (insertIdx < 0) insertIdx = state.trackList.findIndex(t => t.kind === "text") + 1;
            if (insertIdx < 0) insertIdx = 0;
            state.trackList.splice(insertIdx, 0, newTrack);
        }
        state.tracks[newTrack.id] = [];
        renderTracksDOM();
        renderTimeline();
        recalcTotalDuration();
        return newTrack.id;
    }

    function moveTrack(trackId, dir) {
        ensureTracksInitialized();
        const i = state.trackList.findIndex(t => t.id === trackId);
        const j = i + dir;
        if (i < 0 || j < 0 || j >= state.trackList.length) return;
        const [t] = state.trackList.splice(i, 1);
        state.trackList.splice(j, 0, t);
        renderTracksDOM();
        renderTimeline();
        syncVideoToCurrentTime();
        updateTvPreview();
        saveProject();
    }
    function removeTrack(trackId) {
        ensureTracksInitialized();
        const track = getTrack(trackId);
        if (!track) return;
        const clips = state.tracks[trackId] || [];
        if (state.trackList.length <= 1) return;
        const delMsg = clips.length
            ? `Удалить слой «${track.name}» и ${clips.length} клип(ов) на нём?`
            : `Удалить слой «${track.name}»?`;
        showConfirm(delMsg, "Удалить").then(ok => {
            if (!ok) return;
            state.trackList = state.trackList.filter(t => t.id !== trackId);
            delete state.tracks[trackId];
            if (state.selectedClipId && clips.some(c => c.id === state.selectedClipId)) {
                state.selectedClipId = null;
            }
            selectClip(state.selectedClipId);
            recalcTotalDuration();
            renderTracksDOM();
            renderTimeline();
            syncVideoToCurrentTime();
            renderCutsTree();
            saveProject();
        });
    }

    // Transcribe Track Select Sync
    function syncTranscribeTrackSelect() {
        const sel = document.getElementById("inspectorTranscribeTrack");
        if (!sel) return;
        const curVal = sel.value;
        sel.innerHTML = "";
        const textTracks = state.trackList.filter(t => t.kind === "text");
        textTracks.forEach(t => {
            const opt = document.createElement("option");
            opt.value = t.id;
            opt.textContent = `Слой: ${t.name}`;
            sel.appendChild(opt);
        });
        const newOpt = document.createElement("option");
        newOpt.value = "__new__";
        newOpt.textContent = "+ Создать новый отдельный слой";
        sel.appendChild(newOpt);
        if (curVal && (curVal === "__new__" || textTracks.some(t => t.id === curVal))) {
            sel.value = curVal;
        } else if (textTracks.length > 0) {
            sel.value = textTracks[0].id;
        }
    }

    // Clip Selection & Inspector Sync
    function selectClip(clipId) {
        state.selectedClipId = clipId;
        if (clipId) {
            state.selectedRegionId = null;
            renderRegionsLane();
            renderRegionsList();
            updateRegionToolbarUI();
        }
        document.querySelectorAll(".timeline-clip").forEach(el => {
            el.classList.toggle("selected", el.id === clipId);
        });

        const clip = findClipById(clipId);
        if (clip) {
            if (inspectorEmpty) inspectorEmpty.classList.add("hidden");
            if (inspectorDetails) inspectorDetails.classList.remove("hidden");
            if (inspectorClipTitle) inspectorClipTitle.textContent = (clip.media && clip.media.title) || clip.title || "Клип";
            if (inspectorTrackBadge) inspectorTrackBadge.textContent = trackDisplayName(clip.trackId);
            if (inspectorStartTime) inspectorStartTime.textContent = formatTimecode(clip.startTime);
            if (inspectorDuration) inspectorDuration.textContent = formatTimecode(clip.duration);
            if (clipVolumeSlider) clipVolumeSlider.value = Math.round(clip.volume * 100);
            if (clipVolumeVal) clipVolumeVal.textContent = `${Math.round(clip.volume * 100)}%`;
            if (clipOpacitySlider) clipOpacitySlider.value = Math.round(clip.opacity * 100);
            if (clipOpacityVal) clipOpacityVal.textContent = `${Math.round(clip.opacity * 100)}%`;

            // Adjust controls based on track kind (Text/Subtitles vs Media Clips)
            const track = getTrack(clip.trackId);
            const isSubTrack = isTextClip(clip);
            const isMediaClip = !!(clip.media);
            const isFxClip = !!clip.isFx;
            const volGroup = document.getElementById("inspectorVolumeGroup");
            const opGroup = document.getElementById("inspectorOpacityGroup");
            const subSec = document.getElementById("inspectorSubtitleSection");
            const transSec = document.getElementById("inspectorTranscribeSection");
            const trkSec = document.getElementById("inspectorTrackingSection");
            const fxSec = document.getElementById("inspectorFxSection");
            const rgPanel = document.getElementById("regionInspector");
            const subTextInput = document.getElementById("inspectorSubtitleTextInput");
            if (rgPanel) rgPanel.classList.add("hidden");

            if (isFxClip) {
                if (volGroup) volGroup.classList.add("hidden");
                if (opGroup) opGroup.classList.add("hidden");
                if (subSec) subSec.classList.add("hidden");
                if (transSec) transSec.classList.add("hidden");
                if (trkSec) trkSec.classList.add("hidden");
                if (fxSec) fxSec.classList.remove("hidden");
                syncFxInspector(clip);
            } else if (isSubTrack) {
                if (volGroup) volGroup.classList.add("hidden");
                if (opGroup) opGroup.classList.add("hidden");
                if (subSec) subSec.classList.remove("hidden");
                if (transSec) transSec.classList.add("hidden");
                if (fxSec) fxSec.classList.add("hidden");
                if (subTextInput) subTextInput.value = clip.title || "";
                const lbl = document.getElementById("subEditorLabel");
                if (lbl) lbl.textContent = clip.freeText ? "Редактирование текста" : "Редактирование субтитра";
                // position & shake only for free text (subtitles keep template layout)
                const posRow = document.getElementById("textPosRow");
                const shakeRow = document.getElementById("textShakeRow");
                if (posRow) posRow.style.display = clip.freeText ? "" : "none";
                if (shakeRow) shakeRow.style.display = clip.freeText ? "" : "";
                syncTextInspector(clip);
                document.querySelectorAll("#inspectorSubtitleSection .mini-style-btn").forEach(b => {
                    b.classList.toggle("active", (clip.subtitleStyle || state.clipper.subtitleTemplate) === b.dataset.style);
                });
            } else {
                if (volGroup) volGroup.classList.remove("hidden");
                if (opGroup) opGroup.classList.remove("hidden");
                if (subSec) subSec.classList.add("hidden");
                if (transSec) transSec.classList.remove("hidden");
                if (fxSec) fxSec.classList.add("hidden");
                syncTranscribeTrackSelect();
            }
            // Tracking available for any media clip
            if (trkSec) {
                if (isMediaClip) trkSec.classList.remove("hidden");
                else trkSec.classList.add("hidden");
            }
            // Music ducking: only for audio clips
            const duckRow = document.getElementById("musicDuckRow");
            const duckCheck = document.getElementById("musicDuckCheck");
            const isAudioClip = isMediaClip && isAudioFile(clip.media);
            if (duckRow) duckRow.style.display = isAudioClip ? "" : "none";
            if (duckCheck) duckCheck.checked = !!clip.musicDuck;
            updateTrackingUI(clip);
        } else {
            if (inspectorEmpty) inspectorEmpty.classList.remove("hidden");
            if (inspectorDetails) inspectorDetails.classList.add("hidden");
        }
    }

    // ── FX inspector: every flash/bars/shake element is fully tunable ──
    function syncFxInspector(clip) {
        const sec = document.getElementById("inspectorFxSection");
        if (!sec || !clip) return;
        const set = (id, val) => {
            const el = document.getElementById(id);
            if (el && el.value !== undefined && String(el.value) !== String(val)) el.value = val;
        };
        // Populate FX track selection
        const fxTrkSel = document.getElementById("fxTrackSelect");
        if (fxTrkSel) {
            fxTrkSel.innerHTML = "";
            const candidateTracks = state.trackList.filter(t => t.kind === "video" || t.kind === "effect" || isFxTrack(t));
            candidateTracks.forEach(t => {
                const opt = document.createElement("option");
                opt.value = t.id;
                opt.textContent = `${isFxTrack(t) ? "⚡ [FX]" : "[Видео]"} ${t.name}`;
                fxTrkSel.appendChild(opt);
            });
            if (clip.trackId) fxTrkSel.value = clip.trackId;
            if (!fxTrkSel.dataset.bound) {
                fxTrkSel.dataset.bound = "1";
                fxTrkSel.addEventListener("change", () => {
                    const c = findClipById(state.selectedClipId);
                    if (!c || !c.isFx) return;
                    const newTrk = fxTrkSel.value;
                    if (newTrk && newTrk !== c.trackId) {
                        const oldTrk = c.trackId;
                        state.tracks[oldTrk] = (state.tracks[oldTrk] || []).filter(x => x.id !== c.id);
                        c.trackId = newTrk;
                        (state.tracks[newTrk] = state.tracks[newTrk] || []).push(c);
                        state.tracks[newTrk].sort((a, b) => a.startTime - b.startTime);
                        renderTracksDOM();
                        renderTimeline();
                        updateTvPreview();
                        saveProject();
                    }
                });
            }
        }
        set("fxKindSelect", clip.fxKind || "flash");
        set("fxColorSelect", clip.fxColor || "white");
        set("fxPeakSlider", Math.round((clip.fxPeak != null ? clip.fxPeak : 0.75) * 100));
        set("fxSoundSelect", clip.fxSound || "camera_click");
        set("fxGainSlider", Math.round((clip.fxGain != null ? clip.fxGain : 1.0) * 100));
        set("fxBarHSlider", clip.fxBarH || 120);
        set("fxAmpSlider", clip.fxAmp || 12);
        set("fxFreqSlider", clip.fxFreq || 7);
        const pv = document.getElementById("fxPeakVal");
        if (pv) pv.textContent = `${Math.round((clip.fxPeak != null ? clip.fxPeak : 0.75) * 100)}%`;
        const gv = document.getElementById("fxGainVal");
        if (gv) gv.textContent = `${Math.round((clip.fxGain != null ? clip.fxGain : 1.0) * 100)}%`;
        const bv = document.getElementById("fxBarHVal");
        if (bv) bv.textContent = `${clip.fxBarH || 120}px`;
        const av = document.getElementById("fxAmpVal");
        if (av) av.textContent = `${clip.fxAmp || 12}px`;
        const fv = document.getElementById("fxFreqVal");
        if (fv) fv.textContent = `${clip.fxFreq || 7} Гц`;
        const colorRow = document.getElementById("fxColorRow");
        const peakRow = document.getElementById("fxPeakRow");
        const soundRow = document.getElementById("fxSoundRow");
        const barRow = document.getElementById("fxBarHRow");
        const ampRow = document.getElementById("fxAmpRow");
        const freqRow = document.getElementById("fxFreqRow");
        const isFlash = (clip.fxKind || "flash") === "flash";
        if (colorRow) colorRow.style.display = isFlash ? "" : "none";
        if (peakRow) peakRow.style.display = isFlash ? "" : "none";
        if (soundRow) soundRow.style.display = isFlash ? "" : "none";
        if (barRow) barRow.style.display = clip.fxKind === "bars" ? "" : "none";
        if (ampRow) ampRow.style.display = clip.fxKind === "shake" ? "" : "none";
        if (freqRow) freqRow.style.display = clip.fxKind === "shake" ? "" : "none";
        if (!sec.dataset.fxBound) {
            sec.dataset.fxBound = "1";
            const colSel = document.getElementById("fxColorSelect");
            if (colSel) {
                colSel.addEventListener("change", () => {
                    const sndSel = document.getElementById("fxSoundSelect");
                    const defMap = { white: "camera_click", green: "approve", red: "cancel", bw: "whoosh_fast" };
                    if (sndSel && defMap[colSel.value]) {
                        sndSel.value = defMap[colSel.value];
                        const c = findClipById(state.selectedClipId);
                        if (c && c.isFx) c.fxSound = sndSel.value;
                    }
                });
            }
            const upd = () => {
                const c = findClipById(state.selectedClipId);
                if (!c || !c.isFx) return;
                const g = (id) => document.getElementById(id);
                c.fxKind = g("fxKindSelect") ? g("fxKindSelect").value : "flash";
                c.fxColor = g("fxColorSelect") ? g("fxColorSelect").value : "white";
                c.fxPeak = g("fxPeakSlider") ? (parseInt(g("fxPeakSlider").value, 10) || 75) / 100 : 0.75;
                c.fxSound = g("fxSoundSelect") ? g("fxSoundSelect").value : "camera_click";
                c.fxGain = g("fxGainSlider") ? (parseInt(g("fxGainSlider").value, 10) || 100) / 100 : 1.0;
                c.fxBarH = g("fxBarHSlider") ? parseInt(g("fxBarHSlider").value, 10) || 120 : 120;
                c.fxAmp = g("fxAmpSlider") ? parseInt(g("fxAmpSlider").value, 10) || 12 : 12;
                c.fxFreq = g("fxFreqSlider") ? parseInt(g("fxFreqSlider").value, 10) || 7 : 7;
                c.title = fxLabel(c);
                syncFxInspector(c);
                renderTimeline();
                updateTvPreview();
                saveProject();
            };
            ["fxKindSelect", "fxColorSelect", "fxPeakSlider", "fxSoundSelect",
             "fxGainSlider", "fxBarHSlider", "fxAmpSlider", "fxFreqSlider"].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.addEventListener("input", upd);
                if (el) el.addEventListener("change", upd);
            });
        }
    }
    // ── Text inspector: full AE-style params for subtitle & free-text clips ──
    function syncTextInspector(clip) {
        const sec = document.getElementById("inspectorSubtitleSection");
        if (!sec || !clip) return;
        const set = (id, val) => {
            const el = document.getElementById(id);
            if (el && el.value !== undefined && String(el.value) !== String(val)) el.value = val;
        };
        // Populate text track selection (allows moving text to any text or video track)
        const txtTrkSel = document.getElementById("textTrackSelect");
        if (txtTrkSel) {
            txtTrkSel.innerHTML = "";
            const candidateTracks = state.trackList.filter(t => t.kind === "text" || t.kind === "video");
            candidateTracks.forEach(t => {
                const opt = document.createElement("option");
                opt.value = t.id;
                opt.textContent = `${t.kind === "text" ? "[Текст]" : "[Видео]"} ${t.name}`;
                txtTrkSel.appendChild(opt);
            });
            if (clip.trackId) txtTrkSel.value = clip.trackId;
            if (!txtTrkSel.dataset.bound) {
                txtTrkSel.dataset.bound = "1";
                txtTrkSel.addEventListener("change", () => {
                    const c = findClipById(state.selectedClipId);
                    if (!c || !isTextClip(c)) return;
                    const newTrk = txtTrkSel.value;
                    if (newTrk && newTrk !== c.trackId) {
                        const oldTrk = c.trackId;
                        state.tracks[oldTrk] = (state.tracks[oldTrk] || []).filter(x => x.id !== c.id);
                        c.trackId = newTrk;
                        (state.tracks[newTrk] = state.tracks[newTrk] || []).push(c);
                        state.tracks[newTrk].sort((a, b) => a.startTime - b.startTime);
                        renderTracksDOM();
                        renderTimeline();
                        updateTvPreview();
                        saveProject();
                    }
                });
            }
        }
        // Text color picker
        const clrInp = document.getElementById("textColorInput");
        if (clrInp) {
            clrInp.value = clip.textColor || "#ffffff";
            if (!clrInp.dataset.bound) {
                clrInp.dataset.bound = "1";
                const onClr = () => {
                    const c = findClipById(state.selectedClipId);
                    if (!c || !isTextClip(c)) return;
                    c.textColor = clrInp.value;
                    updateLiveSubtitleOverlay();
                    updateTvPreview();
                    saveProject();
                };
                clrInp.addEventListener("input", onClr);
                clrInp.addEventListener("change", onClr);
            }
        }
        const curStyle = clip.subtitleStyle || state.clipper.subtitleTemplate || "acid";
        document.querySelectorAll("#inspectorSubtitleSection .mini-style-btn").forEach(b => {
            b.classList.toggle("active", b.dataset.style === curStyle);
        });
        set("textFontSelect", clip.textFont || "Montserrat ExtraBold");
        const sizePct = Math.round((clip.textSize != null ? clip.textSize : 6.0) * 100) / 1; // stored in % of height
        set("textSizeSlider", Math.round(clip.textSize != null ? clip.textSize : 6.0));
        set("textGlowSlider", clip.textGlow != null ? clip.textGlow : 65);
        set("textAnimInSelect", clip.textAnimIn || "pop");
        set("textAnimOutSelect", clip.textAnimOut || "fade");
        set("textXSlider", Math.round((clip.textX != null ? clip.textX : 0.5) * 100));
        set("textYSlider", Math.round((clip.textY != null ? clip.textY : 0.72) * 100));
        const shc = document.getElementById("textShakeCheck");
        if (shc) shc.checked = !!clip.textShake;
        const upd = (id) => {
            const el = document.getElementById(id);
            if (!el) return;
            const v = document.getElementById(id + "Val") || document.getElementById(id.replace("Slider", "Val"));
            if (v) v.textContent = el.value + (id === "textSizeSlider" ? "%" : (id.includes("Slider") && id !== "textGlowSlider" ? "%" : ""));
        };
        upd("textSizeSlider"); upd("textGlowSlider"); upd("textXSlider"); upd("textYSlider");
        if (!sec.dataset.textBound) {
            sec.dataset.textBound = "1";
            const pull = () => {
                const c = findClipById(state.selectedClipId);
                if (!c || !isTextClip(c)) return;
                const g = (id) => document.getElementById(id);
                if (g("textFontSelect")) c.textFont = g("textFontSelect").value;
                if (g("textSizeSlider")) c.textSize = parseInt(g("textSizeSlider").value, 10) || 6;
                if (g("textGlowSlider")) c.textGlow = parseInt(g("textGlowSlider").value, 10) || 65;
                if (g("textAnimInSelect")) c.textAnimIn = g("textAnimInSelect").value;
                if (g("textAnimOutSelect")) c.textAnimOut = g("textAnimOutSelect").value;
                if (g("textXSlider")) c.textX = (parseInt(g("textXSlider").value, 10) || 50) / 100;
                if (g("textYSlider")) c.textY = (parseInt(g("textYSlider").value, 10) || 72) / 100;
                if (g("textShakeCheck")) c.textShake = !!g("textShakeCheck").checked;
                if (g("textStrokeSlider")) c.textStroke = parseInt(g("textStrokeSlider").value, 10) || 0;
                if (g("textSpacingSlider")) c.textSpacing = parseInt(g("textSpacingSlider").value, 10) || 0;
                updateLiveSubtitleOverlay();
                updateTvPreview();
                saveProject();
            };
            ["textFontSelect", "textAnimInSelect", "textAnimOutSelect"].forEach(id => {
                const el = document.getElementById(id);
                if (el) { el.addEventListener("change", pull); el.addEventListener("input", pull); }
            });
            ["textSizeSlider", "textGlowSlider", "textXSlider", "textYSlider", "textStrokeSlider", "textSpacingSlider"].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.addEventListener("input", () => {
                    const c = findClipById(state.selectedClipId);
                    if (!c || !isTextClip(c)) return;
                    const val = parseInt(el.value, 10) || 0;
                    if (id === "textSizeSlider") { c.textSize = val; const v = document.getElementById("textSizeVal"); if (v) v.textContent = val + "%"; }
                    if (id === "textGlowSlider") { c.textGlow = val; const v = document.getElementById("textGlowVal"); if (v) v.textContent = String(val); }
                    if (id === "textXSlider") { c.textX = val / 100; const v = document.getElementById("textXVal"); if (v) v.textContent = val + "%"; }
                    if (id === "textYSlider") { c.textY = val / 100; const v = document.getElementById("textYVal"); if (v) v.textContent = val + "%"; }
                    if (id === "textStrokeSlider") { c.textStroke = val; const v = document.getElementById("textStrokeVal"); if (v) v.textContent = val; }
                    if (id === "textSpacingSlider") { c.textSpacing = val; const v = document.getElementById("textSpacingVal"); if (v) v.textContent = val; }
                    updateLiveSubtitleOverlay();
                    updateTvPreview();
                    saveProject();
                });
            });
            const shc = document.getElementById("textShakeCheck");
            if (shc) shc.addEventListener("change", pull);
        }
    }
    // ── Region inspector panel (shown instead of clip details) ──
    function showRegionInspector(r) {
        if (inspectorEmpty) inspectorEmpty.classList.add("hidden");
        if (inspectorDetails) inspectorDetails.classList.add("hidden");
        const panel = document.getElementById("regionInspector");
        if (!panel || !r) return;
        panel.classList.remove("hidden");
        const nameEl = document.getElementById("regionNameInput");
        const timesEl = document.getElementById("regionTimesLabel");
        if (nameEl && document.activeElement !== nameEl) nameEl.value = r.name || "";
        if (timesEl) timesEl.textContent = `${formatDurationShort(r.startTime)} → ${formatDurationShort(r.startTime + r.duration)} (${r.duration.toFixed(1)}с)`;
        const wpc = document.getElementById("regionWordsPerCue");
        if (wpc) wpc.value = String(state.clipper.wordsPerCue || 3);
        const rFont = document.getElementById("regionSubFont");
        if (rFont) rFont.value = TV_FONT_OK(state.clipper.subFont) ? state.clipper.subFont : "Russo One";
        const rSize = document.getElementById("regionSubSize");
        if (rSize) { rSize.value = Math.round((state.clipper.subSize || 1) * 100); const v = document.getElementById("regionSubSizeVal"); if (v) v.textContent = `${rSize.value}%`; }
        const rGlow = document.getElementById("regionSubGlow");
        if (rGlow) { rGlow.value = state.clipper.subGlow != null ? state.clipper.subGlow : 55; const v = document.getElementById("regionSubGlowVal"); if (v) v.textContent = String(rGlow.value); }
        const rAnim = document.getElementById("regionSubAnim");
        if (rAnim) rAnim.value = state.clipper.subAnim || "pop";
        const lang = document.getElementById("regionTranscribeLang");
        if (lang) lang.value = state.clipper.subLang || "ru";
    }
    async function transcribeRegion(r) {
        if (!r) return;
        const mc = resolvePackSource(r.startTime);
        if (!mc || !mc.media) {
            showToast("Под полосой нарезки нет видео на слоях — положи видео под неё.", "info");
            return;
        }
        const wpc = document.getElementById("regionWordsPerCue");
        if (wpc) state.clipper.wordsPerCue = parseInt(wpc.value, 10) || 3;
        // все параметры генерации — из свойств нарезки (шрифт/размер/свечение/анимация)
        const rFont = document.getElementById("regionSubFont");
        if (rFont) state.clipper.subFont = rFont.value;
        const rSize = document.getElementById("regionSubSize");
        if (rSize) state.clipper.subSize = (parseInt(rSize.value, 10) || 100) / 100;
        const rGlow = document.getElementById("regionSubGlow");
        if (rGlow) state.clipper.subGlow = parseInt(rGlow.value, 10) || 55;
        const rAnim = document.getElementById("regionSubAnim");
        if (rAnim) state.clipper.subAnim = rAnim.value;
        const langEl = document.getElementById("regionTranscribeLang");
        const lang = (langEl && langEl.value) || state.clipper.subLang || "ru";
        const styleEl = document.querySelector("#regionInspector .mini-style-btn.active");
        if (styleEl) state.clipper.subtitleTemplate = styleEl.dataset.style;
        const a = convertTimelineToSourceTime(mc, r.startTime);
        const b = convertTimelineToSourceTime(mc, r.startTime + r.duration);
        if (!(b > a + 0.2)) { showToast("Нарезка вне длины источника.", "info"); return; }
        const btn = document.getElementById("regionTranscribeBtn");
        const spin = document.getElementById("regionTranscribeSpinner");
        if (spin) spin.style.display = "inline-block";
        if (btn) btn.disabled = true;
        try {
            const res = await fetch("/api/transcribe", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    filename: mc.media.filename,
                    start_time: a, duration: b - a,
                    language: lang || undefined,
                    model: "whisper-large-v3-turbo"
                })
            });
            if (!res.ok) { showToast("Ошибка Groq Whisper API: " + (await res.text()), "err"); return; }
            const data = await res.json();
            const words = data.words || [];
            if (!words.length) { showToast("Речь не обнаружена.", "err"); return; }
            const tg = {
                kind: "region", id: r.id, filename: mc.media.filename,
                srcStart: a, srcEnd: b, tlStart: r.startTime,
                srcToTl: (src) => mc.startTime + (src - (mc.sourceOffset || 0))
            };
            const batchId = Date.now() + "_" + Math.floor(Math.random() * 1e6);
            state._lastTranscribe = { words, tg, batchId };
            // повторная транскрибация региона: прежние субтитры этого отрезка
            // удаляются, чтобы слова не дублировались на слое
            for (const tid of trackOrder()) {
                const trk = getTrack(tid);
                if (!trk || trk.kind === "audio") continue;
                state.tracks[tid] = (state.tracks[tid] || []).filter(c => {
                    if (c.isFx || c.media || !c.isText || c.freeText) return true;
                    const ov = c.startTime < r.startTime + r.duration - 0.02 &&
                               c.startTime + c.duration > r.startTime + 0.02;
                    return !ov;
                });
            }
            const made = wordsToTimelineClips(words, tg, batchId);
            state.clipper.subtitles = ((textTrackId() && state.tracks[textTrackId()]) || []).slice(-60).map(c => ({
                id: c.id, text: c.title, abs_start: c.startTime, abs_end: c.startTime + c.duration,
                words: (c.words || []).map(w => ({ ...w }))
            }));
            renderSubtitlesCues(state.clipper.subtitles);
            updateLiveSubtitleOverlay();
            recalcTotalDuration();
            renderTimeline();
            renderCutsTree();
            saveProject();
            showToast(`Готово: фрагментов на слое титров — ${made}.`, "ok");
        } catch (e) {
            showToast("Сетевая ошибка: " + e.message, "err");
        } finally {
            if (spin) spin.style.display = "none";
            if (btn) btn.disabled = false;
        }
    }

    function findClipById(clipId) {
        for (const track of Object.values(state.tracks)) {
            const found = track.find(c => c.id === clipId);
            if (found) return found;
        }
        return null;
    }

    // Moving Clips on Timeline & across tracks (horizontal scrub + vertical track switch)
    function isTextClip(clip) {
        if (!clip) return false;
        if (clip.isFx) return false;
        if (clip.isText) return true;
        if (clip.media) return false;
        const t = getTrack(clip.trackId);
        return !!((t && t.kind === "text") && clip.title);
    }
    function canPlaceOnTrack(clip, trackId) {
        const target = getTrack(trackId);
        if (!target) return false;
        // FX overlays live on video or effect tracks
        if (clip.isFx) return target.kind === "video" || target.kind === "effect" || isFxTrack(target);
        // Text (subtitles & free text) can live on text tracks AND video tracks
        if (isTextClip(clip)) return target.kind === "text" || target.kind === "video";
        if (target.kind === "text") return false;
        if (target.kind === "audio") return isAudioFile(clip.media);
        // video track: any video or image clip (not audio-only)
        return !isAudioFile(clip.media);
    }
    function trackFromClientY(clientY) {
        for (const tid of trackOrder()) {
            const lane = document.getElementById("lane_" + tid);
            if (!lane) continue;
            const r = lane.getBoundingClientRect();
            if (clientY >= r.top && clientY <= r.bottom) return tid;
        }
        return null;
    }
    function clearLaneHighlights() {
        trackOrder().forEach(tid => {
            const lane = document.getElementById("lane_" + tid);
            if (lane) lane.classList.remove("drop-target");
        });
    }
    function initClipDrag(clipEl, clip, startEvent) {
        if (isTrackLocked(clip.trackId)) return;
        startEvent.preventDefault();
        const startMouseX = startEvent.clientX;
        const initialStart = clip.startTime;
        const originTrack = clip.trackId;
        let hoverTrack = originTrack;
        clipEl.classList.add("dragging");

        function onMouseMove(moveEvent) {
            const deltaPx = moveEvent.clientX - startMouseX;
            const deltaSec = deltaPx / state.zoom;
            let newStart = Math.max(0, initialStart + deltaSec);
            newStart = Math.round(newStart * 20) / 20; // Snap to 0.05s

            const t = trackFromClientY(moveEvent.clientY);
            hoverTrack = (t && canPlaceOnTrack(clip, t) && !isTrackLocked(t)) ? t : originTrack;
            clearLaneHighlights();
            if (hoverTrack !== originTrack) {
                const lane = document.getElementById("lane_" + hoverTrack);
                if (lane) lane.classList.add("drop-target");
            }
            // Live horizontal feedback on the dragged element
            clipEl.style.left = `${newStart * state.zoom}px`;
            clipEl.dataset.pendingStart = String(newStart);
            clipEl.dataset.pendingTrack = hoverTrack;
            if (inspectorStartTime) inspectorStartTime.textContent = formatTimecode(newStart);
        }

        function onMouseUp(upEvent) {
            window.removeEventListener("mousemove", onMouseMove);
            window.removeEventListener("mouseup", onMouseUp);
            clipEl.classList.remove("dragging");
            clearLaneHighlights();
            const newStart = clipEl.dataset.pendingStart !== undefined ? parseFloat(clipEl.dataset.pendingStart) : initialStart;
            const newTrack = clipEl.dataset.pendingTrack || originTrack;
            delete clipEl.dataset.pendingStart;
            delete clipEl.dataset.pendingTrack;
            clip.startTime = Math.max(0, newStart);
            if (newTrack !== originTrack) {
                state.tracks[originTrack] = (state.tracks[originTrack] || []).filter(c => c.id !== clip.id);
                clip.trackId = newTrack;
                (state.tracks[newTrack] = state.tracks[newTrack] || []).push(clip);
                renderTracksDOM();
            }
            trackOrder().forEach(tid => { if (state.tracks[tid]) state.tracks[tid].sort((a, b) => a.startTime - b.startTime); });
            selectClip(clip.id);
            recalcTotalDuration();
            renderTimeline();
            renderCutsTree();
            syncVideoToCurrentTime();
            saveProject();
            void upEvent;
        }

        window.addEventListener("mousemove", onMouseMove);
        window.addEventListener("mouseup", onMouseUp);
    }

    // Trimming Clip (Left or Right Edge) — clamped to the actual resource length:
    // a media clip can never be stretched beyond sourceDuration - sourceOffset.
    function initTrimHandle(handleEl, clip, side) {
        handleEl.addEventListener("mousedown", (e) => {
            e.stopPropagation();
            e.preventDefault();
            const startMouseX = e.clientX;
            const initStartTime = clip.startTime;
            const initDuration = clip.duration;
            const initOffset = clip.sourceOffset;
            const isMedia = !!clip.media;
            const sourceDur = isMedia
                ? Math.max(0, (clip.sourceDuration || (clip.media && clip.media.duration) || 0))
                : Infinity;
            const maxAvail = isMedia ? Math.max(0.05, sourceDur - initOffset) : Infinity; // max extendable length

            function onMouseMove(moveEvent) {
                const deltaPx = moveEvent.clientX - startMouseX;
                const deltaSec = deltaPx / state.zoom;

                if (side === "right") {
                    let newDur = initDuration + deltaSec;
                    if (isMedia && sourceDur > 0) {
                        newDur = Math.min(newDur, Math.max(0.1, sourceDur - initOffset));
                    }
                    clip.duration = Math.max(0.1, newDur);
                } else if (side === "left") {
                    let delta = deltaSec;
                    if (isMedia) {
                        delta = Math.max(-initOffset, delta);
                    }
                    delta = Math.min(delta, initDuration - 0.1);
                    clip.startTime = Math.max(0, initStartTime + delta);
                    clip.duration = initDuration - delta;
                    clip.sourceOffset = Math.max(0, initOffset + delta);
                }

                renderTimeline();
                if (state.selectedClipId === clip.id) {
                    if (inspectorDuration) inspectorDuration.textContent = formatTimecode(clip.duration);
                    if (inspectorStartTime) inspectorStartTime.textContent = formatTimecode(clip.startTime);
                }
            }

            function onMouseUp() {
                window.removeEventListener("mousemove", onMouseMove);
                window.removeEventListener("mouseup", onMouseUp);
                recalcTotalDuration();
                renderTimeline();
                renderCutsTree();
                saveProject();
            }

            window.addEventListener("mousemove", onMouseMove);
            window.addEventListener("mouseup", onMouseUp);
        });
    }

    // Drag and Drop from Media Library onto Track Lanes (delegated: lanes are dynamic)
    function initTimelineInteraction() {
        if (!lanesContainer) return;

        lanesContainer.addEventListener("dragover", (e) => {
            if (!e.target.closest(".track-lane")) return;
            e.preventDefault();
            e.dataTransfer.dropEffect = "copy";
            const lane = e.target.closest(".track-lane");
            lane.classList.add("dragover");
        });

        lanesContainer.addEventListener("dragleave", (e) => {
            const lane = e.target.closest(".track-lane");
            if (lane) lane.classList.remove("dragover");
        });

        lanesContainer.addEventListener("drop", (e) => {
            const laneEl = e.target.closest(".track-lane");
            if (!laneEl) return;
            e.preventDefault();
            laneEl.classList.remove("dragover");

            try {
                const raw = e.dataTransfer.getData("application/json");
                if (!raw) return;
                const media = JSON.parse(raw);
                const targetTid = laneEl.dataset.trackId;
                const target = getTrack(targetTid);

                const rect = laneEl.getBoundingClientRect();
                const dropX = e.clientX - rect.left;
                const dropTime = Math.max(0, dropX / state.zoom);

                const kind = media.kind || (isAudioFile(media) ? "audio" : "video");
                if (kind === "image") {
                    // images become looped still-clips via the server, then land on a video lane
                    prepareImageClip(media, targetTid, dropTime);
                    return;
                }
                let finalTid = targetTid;
                if (target && target.kind === "text") {
                    const vids = videoTrackIds();
                    const auds = audioTrackIds();
                    finalTid = isAudioFile(media) ? (auds[0] || finalTid) : (vids[vids.length - 1] || vids[0] || finalTid);
                } else if (target && target.kind === "audio" && !isAudioFile(media)) {
                    const vids = videoTrackIds();
                    if (vids.length) finalTid = vids[vids.length - 1];
                }
                addMediaToTimeline(media, finalTid, dropTime);
            } catch (err) {
                console.error("Drop error:", err);
            }
        });

        // Clicking on Ruler or Lanes moves Playhead
        if (timeRuler) timeRuler.addEventListener("mousedown", onScrubStart);
        lanesContainer.addEventListener("mousedown", (e) => {
            if (e.target.closest(".timeline-clip")) return;
            if (e.target.closest(".region-block") || e.target.closest(".region-flash")) return;
            if (state.selectedRegionId) selectRegion(null);
            onScrubStart(e);
        });
    }

    // Images from the library become looped video clips (server renders a still-mp4)
    async function prepareImageClip(media, targetTid, dropTime) {
        const target = getTrack(targetTid);
        if (target && (target.kind === "text" || target.kind === "audio")) {
            const vids = videoTrackIds();
            if (vids.length) targetTid = vids[vids.length - 1];
        }
        try {
            const res = await fetch("/api/prepare-image", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ filename: media.filename, duration: 5.0 })
            });
            if (!res.ok) {
                showToast("Не удалось подготовить изображение: " + (await res.text()), "err");
                return;
            }
            const entry = await res.json();
            addMediaToTimeline(entry, targetTid, dropTime);
            fetchLibrary();
        } catch (err) {
            console.error("prepare-image error:", err);
            showToast("Ошибка подготовки изображения: " + err.message, "err");
        }
    }

    // Scrubbing with Playhead (uses lanes-area rect: stable under scroll + virtual ruler)
    function lanesTimeFromClientX(clientX) {
        const ref = trackLanesArea || lanesContainer;
        if (!ref) return 0;
        const rect = ref.getBoundingClientRect();
        return Math.max(0, (clientX - rect.left) / state.zoom);
    }
    function onScrubStart(e) {
        if (!lanesContainer) return;
        e.preventDefault();
        seekTo(lanesTimeFromClientX(e.clientX));

        function onMouseMove(moveEvent) {
            seekTo(lanesTimeFromClientX(moveEvent.clientX));
        }

        function onMouseUp() {
            window.removeEventListener("mousemove", onMouseMove);
            window.removeEventListener("mouseup", onMouseUp);
        }

        window.addEventListener("mousemove", onMouseMove);
        window.addEventListener("mouseup", onMouseUp);
    }

    // Seek Playhead to precise time
    function seekTo(timeSec) {
        state.previewStopAt = null; // manual seek cancels moment preview
        state.currentTime = Math.max(0, Math.min(state.totalDuration, timeSec));
        updatePlayheadPosition();
        updateTimecodeDisplays();
        syncVideoToCurrentTime();
        updateLiveSubtitleOverlay();
        requestServerPreviewFrame();
    }

    function seekRelative(deltaSec) {
        seekTo(state.currentTime + deltaSec);
    }

    function updatePlayheadPosition() {
        if (!playhead) return;
        const x = Math.round(state.currentTime * state.zoom);
        playhead.style.transform = `translateX(${x}px)`;
    }

    function updateTimecodeDisplays() {
        const tc = formatTimecode(state.currentTime);
        if (headerCurrentTime) headerCurrentTime.textContent = tc;
        if (monitorCurrentTc) monitorCurrentTc.textContent = tc;
    }

     // Multi-layer preview: bottom video track fullscreen + top video track PiP overlay
    // + simultaneous audio mix across ALL audio tracks. Elements are pooled dynamically.
    // studio:audio-master-clock - WebAudio master clock for drift-free preview.
    let _audioCtx = null, _masterClock = null;
    function ensureAudioClock() {
        if (_masterClock) return _masterClock;
        try {
            const AC = window.AudioContext || window.webkitAudioContext;
            if (!AC) return null;
            _audioCtx = new AC();
            if (_audioCtx.state === "suspended") _audioCtx.resume().catch(function(){});
            if (window.CoreTimeMap && window.CoreTimeMap.makeAudioClock) {
                _masterClock = window.CoreTimeMap.makeAudioClock(_audioCtx);
            }
        } catch(e) {}
        return _masterClock;
    }
    let overlayVideoEl = null, masterGain = 1.0;
    const audioEls = {}; // trackId -> <audio>
    function activeClipOn(trackId, t) {
        const track = getTrack(trackId);
        if (!track || track.hidden) return null;
        const list = state.tracks[trackId] || [];
        // half-open interval [start, end): on a clip boundary the NEXT clip wins
        return list.find(c => t >= c.startTime && t < c.startTime + c.duration && c.media) || null;
    }
    // Returns active media clips on video tracks, topmost first (max 2 used for preview)
    function activeVideoLayers(t) {
        const out = [];
        for (const tid of videoTrackIds()) {
            const clip = activeClipOn(tid, t);
            if (clip) out.push(clip);
            if (out.length >= 2) break;
        }
        return out;
    }
    const __proxyCache = new Map();
    function __proxyUrlCached(filename) {
        if (!__proxyCache.has(filename)) {
            __proxyCache.set(filename, null);   // null = pending
            fetch("/api/proxy", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ filename: filename })
            }).then(r => r.json()).then(d => {
                if (d && d.proxy) {
                    __proxyCache.set(filename, "/api/media/stream?file=.proxies/" + d.proxy);
                }
            }).catch(() => {});
        }
        return __proxyCache.get(filename);       // may be null on first call (P0 meanwhile)
    }

    // ── §16 P0: canvas monitor — ONE canvas over the monitor, ONE hidden
    // <video> per unique file, master-clock sync, canvas text (no CSS anims),
    // WebGL2 grade with the own 65^3 LUT. Active for the 9:16 Shorts view. ──
    function initCanvasMonitor() {
        if (!window.CoreCanvasMonitor || !videoMonitor || window.__canvasMonitor) return;
        const canvas = document.createElement("canvas");
        canvas.id = "studioCanvasMonitor";
        videoMonitor.appendChild(canvas);
        const hooks = {
            settings() {
                return {
                    enabled: state.aspectRatio === "9:16",
                    playing: state.isPlaying,
                    fps: state.previewFps || 60,
                    format: state.clipper.format,
                    cropBox: state.clipper.cropBox,
                    bgBox: state.clipper.bgBox,
                    topRatio: 0.45,
                    barTop: Math.max(0, Math.min(640, parseInt(state.clipper.barTop, 10) || 0)),
                    barBottom: Math.max(0, Math.min(640, parseInt(state.clipper.barBottom, 10) || 0)),
                    gradeOn: state.clipper.colorGrade === "tv"
                };
            },
            videoClips(t) {
                // ALL active video layers, topmost first — no cap of 2 (§16.5)
                const out = [];
                for (const tid of videoTrackIds()) {
                    const clip = activeClipOn(tid, t);
                    if (clip) out.push(clip);
                }
                return out;
            },
            targetTime(clip, t) { return clipTargetTime(clip, t); },
            pipBoxFor(clip) { return pipForClip(clip); },
            trackBoxFor(clip, t) {
                return clip.trackPath && clip.trackPath.length ? trackPosAt(clip, t) : null;
            },
            faceAnchor(baseClip, t) {
                if (!baseClip) return null;
                const box = baseClip.trackPath && baseClip.trackPath.length ? trackPosAt(baseClip, t) : null;
                if (!box) return null;
                // studio:face-anchor-norm - canvasMonitor reads anchor.x / anchor.y
                // as 0..1 of the frame; an array gave NaN (broken zoom transform).
                let fx_ = box.x + box.w / 2, fy_ = box.y + box.h / 2;
                if (!isFinite(fx_) || !isFinite(fy_)) return null;
                if (fx_ > 1.001 || fy_ > 1.001) {       // track box in source pixels
                    const m = baseClip.media || {};
                    const mw = Number(m.width || m.w || (videoEl && videoEl.videoWidth)) || 1920;
                    const mh = Number(m.height || m.h || (videoEl && videoEl.videoHeight)) || 1080;
                    fx_ /= mw; fy_ /= mh;
                }
                // studio:face-anchor-split - For split_adhd the face box is in
                // SOURCE coordinates (full frame) while the zoom is applied to the
                // OUTPUT canvas 1080x1920 where the face sits inside the TOP band
                // 1080x864 (cropBox -> top). Map SOURCE center -> OUTPUT uv:
                //   x_out = (fx_src - cropBox.x)/cropBox.w  (0..1 full width)
                //   y_out = (fy_src - cropBox.y)/cropBox.h * (topH / outH)
                // Cover-fit aspect mismatch is second order for the anchor (face
                // is near the crop centre) so linear mapping is sufficient.
                if (state.clipper.format === "split_adhd" && state.clipper.cropBox) {
                    const cb = state.clipper.cropBox;
                    const bw = Math.max(1e-6, cb.w), bh = Math.max(1e-6, cb.h);
                    const nx = (fx_ - cb.x) / bw;
                    const ny = (fy_ - cb.y) / bh;
                    const outH = 1920, topH = Math.round(outH * 0.45 / 2) * 2;
                    fx_ = nx;
                    fy_ = ny * (topH / outH);
                }
                // keep the punch inside the frame even for a face at the very edge
                return { x: Math.max(0.15, Math.min(0.85, fx_)), y: Math.max(0.15, Math.min(0.85, fy_)) };
            },
            cueAt(t) {
                const clip = currentCueClip(t);
                if (!clip) return null;
                const raw = Array.isArray(clip.words) && clip.words.length
                    ? clip.words
                    : [{ word: clip.title || "", abs_start: clip.startTime, abs_end: clip.startTime + clip.duration }];
                const first = raw.length ? (raw[0].abs_start != null ? raw[0].abs_start : 0) : 0;
                const words = raw.map(w => ({
                    word: w.word || "",
                    s: Math.max(0, (w.abs_start != null ? w.abs_start : first) - first),
                    e: Math.max(0.05, (w.abs_end != null ? w.abs_end : (w.abs_start || first) + 0.3) - first),
                    hot: !!w.hot,
                    color: w.color || null
                }));
                const isSplit = state.clipper.format === "split_adhd";
                return {
                    words: words,
                    end: Math.max(0.2, clip.duration),
                    styleName: clip.subtitleStyle || state.clipper.subtitleTemplate || "acid",
                    x: clip.textX != null ? clip.textX : 0.5,
                    y: clip.textY != null ? clip.textY : (isSplit ? 0.225 : 0.68),
                    localT: Math.max(0, t - clip.startTime),
                    sizeRatio: 0.058 * (state.clipper.subSize || 1.0) * (isSplit ? 0.9 : 1.0)
                };
            },
            // studio:text-z-canvas - canvasMonitor needs z to decide under/over text
            textZ(t) {
                const idx = trackOrder().findIndex(function (tid) { const tr = getTrack(tid); return tr && tr.kind === "text"; });
                return idx >= 0 ? idx : null;
            },
            fxAt(t) {
                const out = [];
                const order = trackOrder();
                for (let zi = 0; zi < order.length; zi++) {
                    const tid = order[zi];
                    for (const c of (state.tracks[tid] || [])) {
                        if (!c.isFx) continue;
                        out.push({
                            kind: c.fxKind || "flash", color: c.fxColor || "white",
                            peak: c.fxPeak != null ? c.fxPeak : 0.75,
                            amp: c.fxAmp || 12, freq: c.fxFreq || 7,
                            start: c.startTime, end: c.startTime + c.duration,
                            z: zi, anchor: c.anchor || null
                        });
                    }
                }
                return out;
            },
            now() { return state.currentTime; },
            // §16 P1: WebCodecs exact frames with per-asset worker + proxy scrub
            decoderFor(clip) {
                if (!window.CoreWebCodecs || !window.CoreWebCodecs.supported()) return null;
                const media = clip.media || {};
                if (!media.filename) return null;
                const proxyUrl = __proxyUrlCached(media.filename);
                return window.CoreWebCodecs.decoderFor(media.filename, media.stream_url,
                    proxyUrl, state.previewFps || 60);
            }
        };
        const mon = new window.CoreCanvasMonitor(canvas, hooks);
        window.__canvasMonitor = mon;
        mon.loadLut("/api/grade/lut").catch(() => {});
    }

    function clipTargetTime(clip, t) {
        return Math.max(0, (clip.sourceOffset || 0) + (t - clip.startTime));
    }
    function ensureElMedia(el, clip) {
        if (!el || !clip || !clip.media) return;
        const want = clip.media.stream_url;
        const cur = el.getAttribute("data-file") || "";
        if (cur !== clip.media.filename) {
            el.src = want;
            el.setAttribute("data-file", clip.media.filename);
        }
    }
    function initMultiPreview() {
        if (!videoMonitor || !videoEl) return;
        if (!document.getElementById("studioOverlayPlayer")) {
            overlayVideoEl = document.createElement("video");
            overlayVideoEl.id = "studioOverlayPlayer";
            overlayVideoEl.preload = "auto";
            overlayVideoEl.playsInline = true;
            overlayVideoEl.muted = false;
            overlayVideoEl.className = "overlay-pip hidden";
            videoMonitor.appendChild(overlayVideoEl);
        } else {
            overlayVideoEl = document.getElementById("studioOverlayPlayer");
        }
        const mv = document.getElementById("monitorVolume");
        if (mv) masterGain = parseFloat(mv.value || "1");
    }
    function getAudioEl(trackId) {
        if (!audioEls[trackId]) {
            const el = document.createElement("audio");
            el.preload = "auto";
            el.style.display = "none";
            el.dataset.trackId = trackId;
            if (videoMonitor) videoMonitor.appendChild(el);
            audioEls[trackId] = el;
        }
        return audioEls[trackId];
    }
    function setElTime(el, target) {
        if (!el) return;
        try {
            if (!isFinite(target)) return;
            if (Math.abs((el.currentTime || 0) - target) > 0.12) el.currentTime = target;
        } catch (e) { /* seek while loading */ }
    }
    function setPlaceholderText(title, sub) {
        if (!noClipPlaceholder) return;
        const h = noClipPlaceholder.querySelector("h3");
        const p = noClipPlaceholder.querySelector("p");
        if (h && title) h.textContent = title;
        if (p && sub) p.textContent = sub;
    }
    // Interpolated tracking position for a clip at timeline time t (normalized coords)
    function trackPosAt(clip, t) {
        if (!clip || !clip.trackPath || !clip.trackPath.length) return null;
        const local = t - clip.startTime;
        const path = clip.trackPath;
        if (local <= path[0].t) return path[0];
        if (local >= path[path.length - 1].t) return path[path.length - 1];
        for (let i = 0; i < path.length - 1; i++) {
            const a = path[i], b = path[i + 1];
            if (local >= a.t && local <= b.t) {
                const k = (b.t - a.t) > 1e-6 ? (local - a.t) / (b.t - a.t) : 0;
                return {
                    t: local,
                    x: a.x + (b.x - a.x) * k,
                    y: a.y + (b.y - a.y) * k,
                    w: a.w + (b.w - a.w) * k,
                    h: a.h + (b.h - a.h) * k
                };
            }
        }
        return path[path.length - 1];
    }
    // Position the PiP overlay according to a tracked path (or default corner).
    // Clamped: the element can never leave the visible frame area.
    function applyTrackingTransform(el, clip, t) {
        if (!el) return;
        const pos = trackPosAt(clip, t);
        if (pos) {
            const w = Math.max(0.04, Math.min(1, pos.w));
            const x = Math.max(0, Math.min(1 - w, pos.x));
            const y = Math.max(0, Math.min(1 - 0.02, pos.y));
            el.style.left = `${x * 100}%`;
            el.style.top = `${y * 100}%`;
            el.style.right = "auto";
            el.style.width = `${w * 100}%`;
            el.style.height = "auto";
            el.style.aspectRatio = "auto";
            el.style.maxHeight = "none";
            el.style.objectFit = "fill";
        } else {
            el.style.left = "";
            el.style.top = "";
            el.style.right = "";
            el.style.width = "";
            el.style.height = "";
            el.style.aspectRatio = "";
            el.style.maxHeight = "";
            el.style.objectFit = "";
        }
    }
    // Synchronize HTML5 Video with active timeline clips (multi-layer compositing)
    function syncVideoToCurrentTime() {
        if (!videoEl) return;
        ensureTracksInitialized();
        // Empty project: clear stale frames, show placeholder
        if (totalClipCount() === 0) {
            const hadSrc = !!(videoEl.currentSrc || videoEl.src);
            if (hadSrc) resetMonitorMedia();
            if (monitorOverlay) monitorOverlay.style.display = "flex";
            setPlaceholderText("Монитор предпросмотра", "Перетащите видео из Библиотеки ресурсов на панель слоёв внизу");
            if (noClipPlaceholder) noClipPlaceholder.classList.remove("hidden");
            return;
        }
        const t = state.currentTime;
        const layers = activeVideoLayers(t); // [topmost, ...] max 2
        const over = layers.length >= 2 ? layers[0] : null;   // PiP layer
        const base = layers.length >= 1 ? layers[layers.length - 1] : null; // fullscreen base

        // GAP under playhead: hide video completely — no stale frame in empty space
        const hasLoadedVideo = !!(videoEl.currentSrc || videoEl.src);
        if (monitorOverlay) {
            if (base) monitorOverlay.style.display = "none";
            else monitorOverlay.style.display = "flex";
        }
        if (noClipPlaceholder) {
            if (base) noClipPlaceholder.classList.add("hidden");
            else noClipPlaceholder.classList.remove("hidden");
        }

        // Base layer (bottom-most visible video track with an active clip)
        if (base && base.media) {
            ensureElMedia(videoEl, base);
            setElTime(videoEl, clipTargetTime(base, t));
            videoEl.style.opacity = String(base.opacity ?? 1);
            const baseTrack = getTrack(base.trackId);
            videoEl.muted = !!(baseTrack && baseTrack.muted);
            videoEl.volume = Math.max(0, Math.min(1, (base.volume ?? 1) * masterGain));
            videoEl.style.display = "block";
            if (state.isPlaying && videoEl.paused && videoEl.src) videoEl.play().catch(() => {});
        } else {
            if (!videoEl.paused) { try { videoEl.pause(); } catch (e) {} }
            videoEl.style.display = "none"; // hide stale frame in the gap
            setPlaceholderText("Нет клипа под плейхедом", "Промежуток таймлайна пуст — переместите клип или плейхед");
        }

        // Overlay PiP (only when explicitly configured as PiP or tracked)
        const isOverPip = !!(over && over.media && (over.isPip || over.pipBox || (over.trackPath && over.trackPath.length)));
        if (overlayVideoEl) {
            if (isOverPip) {
                ensureElMedia(overlayVideoEl, over);
                setElTime(overlayVideoEl, clipTargetTime(over, t));
                overlayVideoEl.style.opacity = String(over.opacity ?? 1);
                const overTrack = getTrack(over.trackId);
                overlayVideoEl.muted = !!(overTrack && overTrack.muted);
                overlayVideoEl.volume = Math.max(0, Math.min(1, (over.volume ?? 1) * masterGain));
                overlayVideoEl.classList.remove("hidden");
                applyTrackingTransform(overlayVideoEl, over, t);
                if (state.isPlaying && overlayVideoEl.paused && overlayVideoEl.src) {
                    overlayVideoEl.play().catch(() => {});
                }
                if (!state.isPlaying && !overlayVideoEl.paused) overlayVideoEl.pause();
            } else {
                if (!overlayVideoEl.paused) overlayVideoEl.pause();
                overlayVideoEl.classList.add("hidden");
                applyTrackingTransform(overlayVideoEl, null, t);
            }
        }

        // Simultaneous audio across all audio tracks
        audioTrackIds().forEach(tid => {
            const clip = activeClipOn(tid, t);
            const track = getTrack(tid);
            syncAudioEl(getAudioEl(tid), clip, track ? track.muted : false);
        });
        // cleanup audio elements of removed tracks
        Object.keys(audioEls).forEach(tid => {
            if (!getTrack(tid)) {
                try { audioEls[tid].pause(); audioEls[tid].remove(); } catch (e) {}
                delete audioEls[tid];
            }
        });
        updateOverlayBadge();
        // §16 P0: draw the composite on the canvas monitor; when it is active
        // it takes over the Shorts preview entirely (updateTvPreview bails).
        if (window.__canvasMonitor) {
            const canvasActive = window.__canvasMonitor.renderAt(state.currentTime);
            if (window.__canvasMonitor.canvas) {
                window.__canvasMonitor.canvas.classList.toggle("active", !!canvasActive);
            }
        }
        updateTvPreview();
    }
    function totalClipCount() {
        ensureTracksInitialized();
        return trackOrder().reduce((n, t) => n + ((state.tracks[t] || []).length), 0);
    }
    function resetMonitorMedia() {
        [videoEl, overlayVideoEl, ...Object.values(audioEls)].forEach(el => {
            if (!el) return;
            try { el.pause(); } catch (e) {}
            el.removeAttribute("src");
            el.removeAttribute("data-file");
            try { el.load(); } catch (e) {}
        });
        if (overlayVideoEl) overlayVideoEl.classList.add("hidden");
        const badge = document.getElementById("pipBadge");
        if (badge) badge.classList.add("hidden");
    }
    function syncAudioEl(el, clip, trackMuted) {
        if (!el) return;
        if (clip && clip.media && !trackMuted) {
            ensureElMedia(el, clip);
            setElTime(el, clipTargetTime(clip, state.currentTime));
            el.volume = Math.max(0, Math.min(1, (clip.volume ?? 1) * masterGain));
            el.muted = false;
            if (state.isPlaying && el.paused && el.src) el.play().catch(() => {});
            if (!state.isPlaying && !el.paused) el.pause();
        } else {
            if (!el.paused) el.pause();
        }
    }
    function updateOverlayBadge() {
        // PIP-бейдж убран из интерфейса — всегда скрыт
        const badge = document.getElementById("pipBadge");
        if (badge) badge.classList.add("hidden");
    }

    // Transport Play / Pause
    function initTransport() {
        if (btnPlayPause) btnPlayPause.addEventListener("click", togglePlay);

        const btnToStart = document.getElementById("btnToStart");
        const btnToEnd = document.getElementById("btnToEnd");
        const btnStepBack = document.getElementById("btnStepBack");
        const btnStepForward = document.getElementById("btnStepForward");

        if (btnToStart) btnToStart.addEventListener("click", () => seekTo(0));
        if (btnToEnd) btnToEnd.addEventListener("click", () => seekTo(state.totalDuration));
        // Frame-accurate stepping: pause first, then step exactly 1 frame (assume 30fps timeline, 60fps TC)
        if (btnStepBack) btnStepBack.addEventListener("click", () => { pausePlayback(); seekRelative(-1 / 30); });
        if (btnStepForward) btnStepForward.addEventListener("click", () => { pausePlayback(); seekRelative(1 / 30); });

        // Volume & Mute (master gain applied to all layers)
        const monitorVolume = document.getElementById("monitorVolume");
        const muteToggleBtn = document.getElementById("muteToggleBtn");

        if (monitorVolume) {
            monitorVolume.addEventListener("input", (e) => {
                masterGain = parseFloat(e.target.value || "1");
                syncVideoToCurrentTime();
            });
        }

        if (muteToggleBtn) {
            muteToggleBtn.addEventListener("click", () => {
                const anyMuted = videoEl && videoEl.muted;
                [videoEl, overlayVideoEl, ...Object.values(audioEls)].forEach(el => { if (el) el.muted = !anyMuted; });
                muteToggleBtn.style.opacity = !anyMuted ? "0.4" : "1";
            });
        }

        // Fullscreen
        const fullscreenBtn = document.getElementById("fullscreenBtn");
        if (fullscreenBtn && videoMonitor) {
            fullscreenBtn.addEventListener("click", () => {
                if (!document.fullscreenElement) {
                    videoMonitor.requestFullscreen().catch(() => {});
                } else {
                    document.exitFullscreen();
                }
            });
        }

        // Aspect Ratio Switcher (16:9 vs 9:16 Shorts)
        if (aspectRatioToggleBtn && videoMonitor) {
            aspectRatioToggleBtn.addEventListener("click", () => {
                if (state.aspectRatio === "16:9") {
                    state.aspectRatio = "9:16";
                    aspectRatioToggleBtn.textContent = "9:16";
                    aspectRatioToggleBtn.classList.add("active-9-16");
                    videoMonitor.classList.add("vertical-9-16");
                } else {
                    state.aspectRatio = "16:9";
                    aspectRatioToggleBtn.textContent = "16:9";
                    aspectRatioToggleBtn.classList.remove("active-9-16");
                    videoMonitor.classList.remove("vertical-9-16");
                }
                syncVideoToCurrentTime();
                updateTvPreview();
            });
        }
    }

    function togglePlay() {
        if (state.isPlaying) {
            pausePlayback();
        } else {
            startPlayback();
        }
    }

    // Wait (bounded) until media elements finish seeking, so playback starts
    // with a real decoded frame instead of a frozen picture.
    function waitSeeked(elements, timeoutMs = 450) {
        const pending = elements.filter(el => el && el.src && el.readyState < 3);
        if (!pending.length) return Promise.resolve();
        return new Promise(resolve => {
            let done = false;
            const finish = () => { if (!done) { done = true; resolve(); } };
            pending.forEach(el => {
                el.addEventListener("seeked", finish, { once: true });
                el.addEventListener("canplay", finish, { once: true });
            });
            setTimeout(finish, timeoutMs);
        });
    }

    // studio:audio-master-clock - wall clock + audio master correction
    let _clockBase = 0, _clockStartPerf = 0;
    function driveMasterClock() {
        const mc = ensureAudioClock();
        if (!mc) return null;
        return mc;
    }
    async function startPlayback() {
        if (state.isPlaying) return;
        state.isPlaying = true;
        if (playIcon) playIcon.classList.add("hidden");
        if (pauseIcon) pauseIcon.classList.remove("hidden");

        if (state.currentTime >= state.totalDuration) {
            state.currentTime = 0;
        }

        syncVideoToCurrentTime();
        // Ensure every visible active element is actually playing before starting the clock
        [videoEl, overlayVideoEl, ...Object.values(audioEls)].forEach(el => {
            if (el && el.src && el.paused && el.style.display !== "none") {
                if (el === overlayVideoEl && el.classList.contains("hidden")) return;
                el.play().catch(() => {});
            }
        });
        await waitSeeked([videoEl, overlayVideoEl, ...Object.values(audioEls)]);

        // studio:audio-master-clock - seed from current playhead, audio clock drives it
        _clockBase = state.currentTime;
        _clockStartPerf = performance.now();
        const mc = driveMasterClock();
        if (mc) { try { /* prime clock */ mc(); } catch(e){} }
        state.lastFrameTime = performance.now();
        requestAnimationFrame(playbackLoop);
    }

    function pausePlayback() {
        state.isPlaying = false;
        if (playIcon) playIcon.classList.remove("hidden");
        if (pauseIcon) pauseIcon.classList.add("hidden");
        [videoEl, overlayVideoEl, ...Object.values(audioEls)].forEach(el => {
            if (el && !el.paused) { try { el.pause(); } catch (e) {} }
        });
        const tvp = document.getElementById("tvPreview");
        if (tvp) tvp.querySelectorAll("video").forEach(v => {
            if (!v.paused) { try { v.pause(); } catch (e) {} }
        });
    }

    function playbackLoop(timestamp) {
        if (!state.isPlaying) return;

        // studio:audio-master-clock - if available, derive time from audio clock, else wall clock
        let deltaSec;
        const mc = _masterClock;
        if (mc) {
            try {
                const masterElapsed = mc();
                const want = _clockBase + masterElapsed;
                // clamp jitter: don't jump more than 0.2s per frame
                const diff = want - state.currentTime;
                if (Math.abs(diff) > 0.2) deltaSec = diff;
                else deltaSec = Math.max(0, Math.min(0.2, diff + (timestamp - state.lastFrameTime)/1000 * 0.15));
                // blend: mostly audio clock, small wall contribution to avoid stalls
                deltaSec = (want - state.currentTime) * 0.85 + (timestamp - state.lastFrameTime)/1000 * 0.15;
                deltaSec = Math.max(0, Math.min(0.12, deltaSec));
            } catch(e) {
                deltaSec = (timestamp - state.lastFrameTime) / 1000;
            }
        } else {
            deltaSec = (timestamp - state.lastFrameTime) / 1000;
        }
        state.lastFrameTime = timestamp;

        state.currentTime += deltaSec;

        if (state.currentTime >= state.totalDuration) {
            seekTo(state.totalDuration);
            pausePlayback();
            return;
        }

        // Moment preview: stop exactly at OUT marker
        if (state.previewStopAt !== null && state.currentTime >= state.previewStopAt) {
            const stop = state.previewStopAt;
            state.previewStopAt = null;
            pausePlayback();
            seekTo(stop);
            return;
        }

        updatePlayheadPosition();
        updateTimecodeDisplays();
        triggerFxSounds(state.currentTime - Math.min(deltaSec, 0.25), state.currentTime);
        // Drift correction every frame keeps multi-layer A/V in sync;
        // syncVideoToCurrentTime also resumes any element that went silent/stale.
        syncVideoToCurrentTime();
        updateLiveSubtitleOverlay();
        autoScrollFollowPlayhead();

        requestAnimationFrame(playbackLoop);
    }
    function autoScrollFollowPlayhead() {
        if (!timelineScrollContainer) return;
        const x = state.currentTime * state.zoom;
        const sl = timelineScrollContainer.scrollLeft;
        const visW = visibleLanesWidth();
        if (x < sl || x > sl + visW * 0.9) {
            timelineScrollContainer.scrollLeft = Math.max(0, x - visW * 0.3);
        }
    }

    // Tools & Split Operations
    function initTools() {
        const selectBtn = document.getElementById("toolSelectBtn");
        const splitBtn = document.getElementById("toolSplitBtn");
        const deleteBtn = document.getElementById("toolDeleteBtn");
        const clearBtn = document.getElementById("timelineClearBtn");

        const zoomSlider = document.getElementById("timelineZoomSlider");
        const zoomInBtn = document.getElementById("zoomInBtn");
        const zoomOutBtn = document.getElementById("zoomOutBtn");
        const zoomFitBtn = document.getElementById("zoomFitBtn");

        if (selectBtn) selectBtn.addEventListener("click", () => setTool("select"));
        if (splitBtn) splitBtn.addEventListener("click", splitClipAtPlayhead);
        if (deleteBtn) deleteBtn.addEventListener("click", deleteSelectedClip);

        if (clearBtn) {
            clearBtn.addEventListener("click", () => {
                showConfirm("Очистить все дорожки таймлайна?", "Очистить").then(ok => {
                if (ok) {
                    // Пересобираем дорожки по ТЕКУЩЕМУ списку (кастомные слои не теряются),
                    // плюс чистим полосу нарезок — иначе регионы переживают очистку
                    const tracks = {};
                    (state.trackList || []).forEach(t => { tracks[t.id] = []; });
                    state.tracks = tracks;
                    state.regions = [];
                    selectClip(null);
                    recalcTotalDuration();
                    renderTimeline();
                    if (typeof renderRegionsLane === "function") renderRegionsLane();
                    if (typeof renderRegionsList === "function") renderRegionsList();
                    if (typeof updateRegionToolbarUI === "function") updateRegionToolbarUI();
                    seekTo(0);
                }
                });
            });
        }

        // Zoom controls
        if (zoomSlider) {
            zoomSlider.addEventListener("input", (e) => {
                setZoom(parseInt(e.target.value, 10));
            });
        }

        if (zoomInBtn) {
            zoomInBtn.addEventListener("click", () => {
                setZoom(Math.min(400, state.zoom + 25));
            });
        }

        if (zoomOutBtn) {
            zoomOutBtn.addEventListener("click", () => {
                setZoom(Math.max(8, state.zoom - 25));
            });
        }

        if (zoomFitBtn) {
            zoomFitBtn.addEventListener("click", () => {
                const visW = visibleLanesWidth();
                const fitZoom = Math.max(8, Math.min(300, Math.floor(visW / Math.max(1, state.totalDuration + 2))));
                setZoom(fitZoom);
            });
        }
        // Keep zoom slider in sync when setZoom clamps outside slider range
        const _zs = document.getElementById("timelineZoomSlider");
        if (_zs) { _zs.min = "8"; _zs.max = "400"; }

        // Local file import
        const importBtn = document.getElementById("importMediaBtn");
        const localFileInput = document.getElementById("localFileInput");
        const refreshLibraryBtn = document.getElementById("refreshLibraryBtn");

        if (importBtn && localFileInput) {
            importBtn.addEventListener("click", () => localFileInput.click());
            localFileInput.addEventListener("change", async (e) => {
                const file = e.target.files[0];
                if (!file) return;
                importBtn.disabled = true;
                try {
                    // Path 1 (best): real binary upload — works in browser and Electron
                    const fd = new FormData();
                    fd.append("file", file, file.name);
                    let res = await fetch("/api/media/upload", { method: "POST", body: fd });
                    if (!res.ok && file.path) {
                        // Path 2 (Electron fallback): server-side copy by path
                        res = await fetch("/api/media/import", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ path: file.path })
                        });
                    }
                    if (res.ok) {
                        const data = await res.json().catch(() => null);
                        await fetchLibrary();
                        if (data && data.filename) selectClipperSource(data.filename);
                        switchTab("library");
                    } else {
                        showToast("Не удалось импортировать файл: " + (await res.text()), "err");
                    }
                } catch (err) {
                    console.error("Import error:", err);
                    showToast("Ошибка импорта: " + err.message, "err");
                } finally {
                    importBtn.disabled = false;
                    localFileInput.value = "";
                }
            });
        }

        if (refreshLibraryBtn) refreshLibraryBtn.addEventListener("click", fetchLibrary);
    }

    function setTool(toolName) {
        state.activeTool = toolName;
        const selectBtn = document.getElementById("toolSelectBtn");
        const splitBtn = document.getElementById("toolSplitBtn");
        if (selectBtn) selectBtn.classList.toggle("active", toolName === "select");
        if (splitBtn) splitBtn.classList.toggle("active", toolName === "split");
    }

    function setZoom(newZoom) {
        state.zoom = Math.max(8, Math.min(400, Math.round(newZoom)));
        const zoomSlider = document.getElementById("timelineZoomSlider");
        if (zoomSlider) zoomSlider.value = Math.max(20, Math.min(250, state.zoom));

        const scrollContainer = document.getElementById("timelineScrollContainer");
        const anchorSec = state.currentTime;
        // Keep playhead anchored: measure before, restore after layout
        const beforeLeft = anchorSec * state.zoom;

        resizeCanvas();
        renderTimeline();

        if (scrollContainer) {
            const visW = Math.max(200, scrollContainer.clientWidth - 180);
            const target = Math.max(0, anchorSec * state.zoom - visW * 0.4);
            scrollContainer.scrollLeft = target;
            void beforeLeft;
            drawRuler();
        }
    }

    // Resizable panels: left dock width + timeline height (persisted)
    const DOCK_W_KEY = "kick_studio_dock_w";
    const TL_H_KEY = "kick_studio_tl_h";
    function initResizers() {
        const dock = document.getElementById("leftDock");
        const dockR = document.getElementById("dockResizer");
        const tl = document.getElementById("timelinePanel");
        const tlR = document.getElementById("timelineResizer");
        try {
            const w = parseInt(localStorage.getItem(DOCK_W_KEY) || "", 10);
            if (dock && w >= 300 && w <= 680) dock.style.width = w + "px";
            const h = parseInt(localStorage.getItem(TL_H_KEY) || "", 10);
            if (tl && h >= 200 && h <= 640) tl.style.height = h + "px";
        } catch (e) {}

        function dragY(el, onMove) {
            el.addEventListener("mousedown", (e) => {
                e.preventDefault();
                e.stopPropagation();
                el.classList.add("dragging");
                document.body.style.cursor = getComputedStyle(el).cursor;
                document.body.style.userSelect = "none";
                const move = (ev) => onMove(ev);
                const up = () => {
                    el.classList.remove("dragging");
                    document.body.style.cursor = "";
                    document.body.style.userSelect = "";
                    window.removeEventListener("mousemove", move);
                    window.removeEventListener("mouseup", up);
                    resizeCanvas();
                    renderTimeline();
                };
                window.addEventListener("mousemove", move);
                window.addEventListener("mouseup", up);
            });
        }

        if (dock && dockR) {
            dragY(dockR, (ev) => {
                const w = Math.max(300, Math.min(680, ev.clientX - dock.getBoundingClientRect().left));
                dock.style.width = w + "px";
                try { localStorage.setItem(DOCK_W_KEY, String(Math.round(w))); } catch (e) {}
            });
        }
        if (tl && tlR) {
            dragY(tlR, (ev) => {
                const rect = tl.getBoundingClientRect();
                const h = Math.max(200, Math.min(640, rect.bottom - ev.clientY));
                tl.style.height = h + "px";
                try { localStorage.setItem(TL_H_KEY, String(Math.round(h))); } catch (e) {}
            });
        }
    }
    function initDockToggle() {
        const btn = document.getElementById("dockToggleBtn");
        const dock = document.getElementById("leftDock");
        if (btn && dock) btn.addEventListener("click", () => {
            dock.classList.toggle("collapsed");
            setTimeout(() => { resizeCanvas(); renderTimeline(); }, 50);
        });
    }
    // ── In/Out Markers on the Layers Panel (метки нарезки прямо на таймлайне) ──
    // ── Regions (нарезки): единое понятие разметки и очереди экспорта ──
    // Каждая нарезка = stretchable-блок на полосе над слоями. Все нарезки идут в экспорт.
    const FLASH_DUR = 0.22;
    function sortedRegions() {
        return [...(state.regions || [])].sort((a, b) => a.startTime - b.startTime);
    }
    function findRegionById(id) {
        return (state.regions || []).find(r => r.id === id) || null;
    }
    function selectRegion(id) {
        state.selectedRegionId = id || null;
        if (id) state.selectedClipId = null;
        document.querySelectorAll(".timeline-clip").forEach(el => el.classList.remove("selected"));
        renderRegionsLane();
        renderRegionsList();
        updateRegionToolbarUI();
        const r = id ? findRegionById(id) : null;
        if (r) {
            showRegionInspector(r);
        } else {
            const panel = document.getElementById("regionInspector");
            if (panel) panel.classList.add("hidden");
            selectClip(state.selectedClipId);
        }
    }
    function addRegionFromPlayhead() {
        const start = Math.max(0, state.currentTime);
        const dur = 5.0;
        const n = (state.regions || []).length;
        const r = {
            id: "rg_" + Date.now().toString(36),
            name: `Нарезка ${n + 1}`,
            startTime: start,
            duration: dur,
            noFlashAfter: false
        };
        state.regions = [...(state.regions || []), r];
        state.selectedRegionId = r.id;
        state.selectedClipId = null;
        recalcTotalDuration();
        renderTimeline();
        renderRegionsLane();
        renderRegionsList();
        updateRegionToolbarUI();
        syncVideoToCurrentTime();
        updateTvPreview();
        saveProject();
        return r;
    }
    function deleteSelectedRegion() {
        const r = findRegionById(state.selectedRegionId);
        if (!r) return;
        state.regions = (state.regions || []).filter(x => x.id !== r.id);
        state.selectedRegionId = null;
        renderRegionsLane();
        renderRegionsList();
        updateRegionToolbarUI();
        saveProject();
    }
    function splitSelectedRegion() {
        const r = findRegionById(state.selectedRegionId);
        if (!r) { showToast("Выбери нарезку на полосе нарезок.", "info"); return; }
        const t = state.currentTime;
        if (!(t > r.startTime + 0.2 && t < r.startTime + r.duration - 0.2)) {
            showToast("Поставь плейхед внутрь выбранной нарезки, затем «Разделить».", "info");
            return;
        }
        const second = {
            id: "rg_" + Date.now().toString(36),
            name: r.name + " (2)",
            startTime: t,
            duration: (r.startTime + r.duration) - t,
            noFlashAfter: r.noFlashAfter
        };
        r.duration = t - r.startTime;
        state.regions = [...state.regions, second];
        state.selectedRegionId = second.id;
        renderRegionsLane();
        renderRegionsList();
        updateRegionToolbarUI();
        saveProject();
    }
    function previewSelectedRegion() {
        const r = findRegionById(state.selectedRegionId);
        if (!r) { showToast("Выбери нарезку на полосе нарезок.", "info"); return; }
        pausePlayback();
        seekTo(r.startTime);
        state.previewStopAt = r.startTime + r.duration;
        startPlayback();
    }
    function updateRegionToolbarUI() {
        const durLbl = document.getElementById("tlRegionDur");
        const r = findRegionById(state.selectedRegionId);
        const expBtn = document.getElementById("exportPackBtn");
        if (durLbl) {
            durLbl.textContent = r ? formatDurationShort(r.duration) : "--:--";
            durLbl.classList.toggle("ok", !!r);
        }
        if (expBtn) expBtn.disabled = !(state.regions && state.regions.length);
    }
    function initTimelineMarkers() {
        // Toolbar нарезок (старые IN/OUT убраны из интерфейса)
        const bind = (id, fn) => { const el = document.getElementById(id); if (el) el.addEventListener("click", fn); };
        bind("tlAddRegionBtn", addRegionFromPlayhead);
        bind("tlPreviewRegionBtn", previewSelectedRegion);
        bind("tlSplitRegionBtn", splitSelectedRegion);
        bind("tlDeleteRegionBtn", deleteSelectedRegion);
    }
    // Shim: старые вызовы обновления меток теперь обновляют полосу нарезок
    function setMarker() {}
    function nudgeMarker() {}
    function updateMarkerRangeUI() { updateRegionToolbarUI(); }
    // Source file for the current cut: media of the clip under the IN marker (or selected)
    function resolvePackSource(timelineT) {
        const sel = findClipById(state.selectedClipId);
        if (sel && sel.media && !isTextClip(sel)) {
            const clipEnd = sel.startTime + sel.duration;
            if (timelineT >= sel.startTime - 0.001 && timelineT <= clipEnd + 0.001) return sel;
        }
        for (const tid of trackOrder()) {
            const clip = (state.tracks[tid] || []).find(c =>
                c.media && timelineT >= c.startTime && timelineT <= c.startTime + c.duration);
            if (clip) return clip;
        }
        return sel && sel.media ? sel : null;
    }
    function convertTimelineToSourceTime(clip, timelineT) {
        return Math.max(0, Math.min(
            (clip.sourceDuration || clip.media.duration || 0),
            (clip.sourceOffset || 0) + (timelineT - clip.startTime)
        ));
    }
    // ── Region lane: stretchable export blocks above the layers ──
    function ensureRegionLane() {
        if (!lanesContainer) return null;
        let lane = document.getElementById("regionLane");
        if (!lane) {
            lane = document.createElement("div");
            lane.id = "regionLane";
            lane.className = "region-lane";
            lane.title = "Полоса нарезок: тяни блоки и края — всё уйдёт в экспорт";
            lanesContainer.insertBefore(lane, lanesContainer.firstChild);
        }
        return lane;
    }
    function renderRegionsLane() {
        const lane = ensureRegionLane();
        if (!lane) return;
        lane.querySelectorAll(".region-block,.region-flash,.marker-tick").forEach(el => el.remove());
        // §7.1: маркеры видны на обзорной полосе вместе с нарезками
        (state.clipper.markers || []).forEach(m => {
            const tick = document.createElement("div");
            tick.className = "marker-tick" + (m.note ? " noted" : "");
            tick.style.left = `${m.t * state.zoom}px`;
            tick.title = `Маркер @ ${m.t.toFixed(2)}с${m.note ? " — " + m.note : ""}`;
            tick.addEventListener("dblclick", (e) => {
                e.stopPropagation();
                seekTo(m.t);
            });
            lane.appendChild(tick);
        });
        const regs = sortedRegions();
        const W = timelineContentWidth();
        lane.style.width = `${W}px`;
        lane.style.minWidth = `${W}px`;
        regs.forEach((r, idx) => {
            const el = document.createElement("div");
            el.className = "region-block" + (r.id === state.selectedRegionId ? " selected" : "");
            el.dataset.regionId = r.id;
            el.style.left = `${r.startTime * state.zoom}px`;
            el.style.width = `${Math.max(24, r.duration * state.zoom)}px`;
            el.title = `${r.name} — тяни за края, двойной клик — переименовать`;
            el.innerHTML = `<span class="region-handle left"></span><span class="region-label"></span><span class="region-handle right"></span>`;
            el.querySelector(".region-label").textContent = `${idx + 1} · ${r.name} · ${r.duration.toFixed(1)}с`;
            // interactions
            el.addEventListener("pointerdown", (e) => regionPointerDown(e, r, el));
            el.addEventListener("dblclick", (e) => {
                e.stopPropagation();
                showPrompt("Название нарезки:", r.name).then(name => {
                    if (name && name.trim()) {
                        r.name = name.trim().slice(0, 40);
                        renderRegionsLane();
                        renderRegionsList();
                        saveProject();
                    }
                });
            });
            lane.appendChild(el);
        });
    }
    function regionPointerDown(e, r, el) {
        if (e.button !== 0) return;
        e.stopPropagation();
        e.preventDefault();
        // lightweight select WITHOUT rebuilding the lane (rebuild would kill the drag)
        state.selectedRegionId = r.id;
        state.selectedClipId = null;
        document.querySelectorAll(".timeline-clip").forEach(x => x.classList.remove("selected"));
        document.querySelectorAll(".region-block").forEach(x => x.classList.toggle("selected", x.dataset.regionId === r.id));
        renderRegionsList();
        updateRegionToolbarUI();
        showRegionInspector(r);
        const edge = e.target.classList.contains("region-handle")
            ? (e.target.classList.contains("left") ? "left" : "right") : "move";
        const startX = e.clientX;
        const initStart = r.startTime, initDur = r.duration;
        try { el.setPointerCapture(e.pointerId); } catch (err) {}
        const onMove = (ev) => {
            const d = (ev.clientX - startX) / state.zoom;
            if (edge === "move") {
                r.startTime = Math.max(0, Math.round((initStart + d) * 20) / 20);
            } else if (edge === "left") {
                const ns = Math.max(0, Math.round((initStart + d) * 20) / 20);
                const nd = initDur - (ns - initStart);
                if (nd >= 0.3) { r.startTime = ns; r.duration = nd; }
            } else {
                r.duration = Math.max(0.3, Math.round((initDur + d) * 20) / 20);
            }
            el.style.left = `${r.startTime * state.zoom}px`;
            el.style.width = `${Math.max(24, r.duration * state.zoom)}px`;
            updateRegionToolbarUI();
        };
        const onUp = () => {
            window.removeEventListener("pointermove", onMove);
            window.removeEventListener("pointerup", onUp);
            window.removeEventListener("pointercancel", onUp);
            recalcTotalDuration();
            renderRegionsLane();
            renderRegionsList();
            updateRegionToolbarUI();
            saveProject();
        };
        window.addEventListener("pointermove", onMove);
        window.addEventListener("pointerup", onUp);
        window.addEventListener("pointercancel", onUp);
    }
    // Split clip at playhead (any track, any position strictly inside clip)
    function splitClipAtPlayhead() {
        const splitTime = state.currentTime;
        let clipToSplit = null;

        if (state.selectedClipId) {
            const sel = findClipById(state.selectedClipId);
            if (sel && !isTrackLocked(sel.trackId) &&
                splitTime > sel.startTime + 0.02 && splitTime < sel.startTime + sel.duration - 0.02) {
                clipToSplit = sel;
            }
        }

        if (!clipToSplit) {
            // Priority: topmost video layer first, then others
            for (const tid of trackOrder()) {
                if (isTrackLocked(tid)) continue;
                const track = state.tracks[tid] || [];
                clipToSplit = track.find(c => splitTime > c.startTime + 0.02 && splitTime < c.startTime + c.duration - 0.02);
                if (clipToSplit) break;
            }
        }

        if (clipToSplit) {
            splitClipAtTimestamp(clipToSplit, splitTime);
        }
    }

    function splitClipAtTimestamp(clipToSplit, splitTime) {
        if (!clipToSplit) return;
        if (isTrackLocked(clipToSplit.trackId)) return;
        if (splitTime <= clipToSplit.startTime + 0.02 || splitTime >= clipToSplit.startTime + clipToSplit.duration - 0.02) {
            return;
        }

        const leftDuration = splitTime - clipToSplit.startTime;
        const rightDuration = clipToSplit.duration - leftDuration;

        const rightClip = {
            ...clipToSplit,
            id: "clip_" + Date.now() + "_split",
            startTime: splitTime,
            duration: rightDuration,
            sourceOffset: (clipToSplit.sourceOffset || 0) + leftDuration,
            media: clipToSplit.media ? { ...clipToSplit.media } : clipToSplit.media,
            words: clipToSplit.words ? clipToSplit.words.map(w => ({ ...w })) : clipToSplit.words
        };

        clipToSplit.duration = leftDuration;
        // Subtitle word timings: partition words between left/right halves
        if (clipToSplit.trackId === "v3" && clipToSplit.words && clipToSplit.words.length) {
            const cutAbs = splitTime;
            const leftWords = [], rightWords = [];
            clipToSplit.words.forEach(w => {
                const ws = (w.abs_start !== undefined) ? w.abs_start : (clipToSplit.startTime + (w.start || 0));
                ((ws < cutAbs) ? leftWords : rightWords).push(w);
            });
            clipToSplit.words = leftWords;
            rightClip.words = rightWords;
            if (leftWords.length) clipToSplit.title = leftWords.map(w => w.word).join(" ");
            if (rightWords.length) rightClip.title = rightWords.map(w => w.word).join(" ");
        }

        const trackList = state.tracks[clipToSplit.trackId];
        trackList.push(rightClip);
        trackList.sort((a, b) => a.startTime - b.startTime);

        selectClip(rightClip.id);
        renderTimeline();
    }

    function deleteSelectedClip() {
        if (!state.selectedClipId) return;
        const clip = findClipById(state.selectedClipId);
        if (clip && isTrackLocked(clip.trackId)) return;
        trackOrder().forEach(trackId => {
            state.tracks[trackId] = (state.tracks[trackId] || []).filter(c => c.id !== state.selectedClipId);
        });
        selectClip(null);
        recalcTotalDuration();
        renderTimeline();
        renderCutsTree();
        syncVideoToCurrentTime();
        saveProject();
    }

    // Inspector Properties & Groq Subtitles Controls
    function initInspector() {
        if (clipVolumeSlider) {
            clipVolumeSlider.addEventListener("input", (e) => {
                const clip = findClipById(state.selectedClipId);
                if (clip) {
                    clip.volume = Math.max(0, Math.min(2, parseFloat(e.target.value) / 100));
                    if (clipVolumeVal) clipVolumeVal.textContent = `${e.target.value}%`;
                    syncVideoToCurrentTime();
                }
            });
        }

        if (clipOpacitySlider) {
            clipOpacitySlider.addEventListener("input", (e) => {
                const clip = findClipById(state.selectedClipId);
                if (clip) {
                    clip.opacity = parseFloat(e.target.value) / 100;
                    if (clipOpacityVal) clipOpacityVal.textContent = `${e.target.value}%`;
                    // Apply through the compositor: opacity belongs to the clip,
                    // not to whichever element happens to be fullscreen right now
                    syncVideoToCurrentTime();
                }
            });
        }

        const deleteBtn = document.getElementById("inspectorDeleteBtn");
        if (deleteBtn) deleteBtn.addEventListener("click", deleteSelectedClip);

        // Music ducking toggle (audio clips): background music ducks under voice
        const duckCheck = document.getElementById("musicDuckCheck");
        if (duckCheck) duckCheck.addEventListener("change", (e) => {
            const clip = findClipById(state.selectedClipId);
            if (clip) {
                clip.musicDuck = !!e.target.checked;
                saveProject();
            }
        });

        // Text editing: type any phrase, words redistribute evenly (works on ANY layer)
        const subTextInput = document.getElementById("inspectorSubtitleTextInput");
        if (subTextInput) {
            subTextInput.addEventListener("input", (e) => {
                const clip = findClipById(state.selectedClipId);
                if (clip && isTextClip(clip)) {
                    clip.title = e.target.value;
                    const parts = String(e.target.value || "").split(/\s+/).filter(Boolean);
                    const n = Math.max(1, parts.length);
                    if (clip.freeText) {
                        // free text renders as one block, no per-word spread needed
                        delete clip.words;
                    } else {
                        clip.words = parts.map((w, i) => ({
                            word: w,
                            abs_start: clip.startTime + (clip.duration * i) / n,
                            abs_end: clip.startTime + (clip.duration * (i + 1)) / n
                        }));
                    }
                    renderTimeline();
                    updateLiveSubtitleOverlay();
                    updateTvPreview();
                    saveProject();
                }
            });
            subTextInput.addEventListener("change", () => { renderTimeline(); updateTvPreview(); saveProject(); });
        }

        // Subtitle style buttons in inspector subtitle section: style of THIS clip
        document.querySelectorAll("#inspectorSubtitleSection .mini-style-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll("#inspectorSubtitleSection .mini-style-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                state.clipper.subtitleTemplate = btn.dataset.style;
                const clip = findClipById(state.selectedClipId);
                if (clip && isTextClip(clip)) clip.subtitleStyle = btn.dataset.style;
                document.querySelectorAll(".style-card").forEach(c => {
                    c.classList.toggle("active", c.dataset.style === btn.dataset.style);
                });
                document.querySelectorAll("#inspectorTranscribeSection .mini-style-btn").forEach(b => {
                    b.classList.toggle("active", b.dataset.style === btn.dataset.style);
                });
                updateLiveSubtitleOverlay();
                updateTvPreview();
                saveProject();
            });
        });

        // Inspector Transcribe section mini style buttons
        document.querySelectorAll("#inspectorTranscribeSection .mini-style-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll("#inspectorTranscribeSection .mini-style-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                state.clipper.subtitleTemplate = btn.dataset.style;
                document.querySelectorAll(".style-card").forEach(c => {
                    c.classList.toggle("active", c.dataset.style === btn.dataset.style);
                });
                document.querySelectorAll("#inspectorSubtitleSection .mini-style-btn").forEach(b => {
                    b.classList.toggle("active", b.dataset.style === btn.dataset.style);
                });
                updateLiveSubtitleOverlay();
                updateTvPreview();
            });
        });

        // Slider label bindings for transcribe section
        const trSizeSlider = document.getElementById("inspectorTranscribeSizeSlider");
        const trSizeVal = document.getElementById("inspectorTranscribeSizeVal");
        if (trSizeSlider && trSizeVal) {
            trSizeSlider.addEventListener("input", () => {
                trSizeVal.textContent = trSizeSlider.value + "%";
            });
        }
        const trGlowSlider = document.getElementById("inspectorTranscribeGlowSlider");
        const trGlowVal = document.getElementById("inspectorTranscribeGlowVal");
        if (trGlowSlider && trGlowVal) {
            trGlowSlider.addEventListener("input", () => {
                trGlowVal.textContent = trGlowSlider.value;
            });
        }

        // Groq Whisper auto-transcribe trigger for selected clip
        const inspTransBtn = document.getElementById("inspectorTranscribeBtn");
        const inspTransSpinner = document.getElementById("inspectorTranscribeSpinner");
        if (inspTransBtn) {
            inspTransBtn.addEventListener("click", async () => {
                const clip = findClipById(state.selectedClipId);
                if (!clip) {
                    showToast("Выберите клип на таймлайне для распознавания.", "info");
                    return;
                }

                let mediaFilename = null;
                if (clip.media && clip.media.filename) {
                    mediaFilename = clip.media.filename;
                } else if (state.clipper.sourceFile) {
                    mediaFilename = state.clipper.sourceFile;
                } else if (state.mediaLibrary.length > 0) {
                    mediaFilename = state.mediaLibrary[0].filename;
                }

                if (!mediaFilename) {
                    showToast("Не удалось определить исходный медиафайл клипа.", "err");
                    return;
                }

                const lang = document.getElementById("inspectorTranscribeLang")?.value || "ru";
                const activeStyleBtn = document.querySelector("#inspectorTranscribeSection .mini-style-btn.active");
                const styleVal = activeStyleBtn ? activeStyleBtn.dataset.style : (state.clipper.subtitleTemplate || "acid");
                state.clipper.subtitleTemplate = styleVal;

                const targetTrack = document.getElementById("inspectorTranscribeTrack")?.value;
                const fontVal = document.getElementById("inspectorTranscribeFont")?.value || "Montserrat ExtraBold";
                const sizeVal = parseFloat(document.getElementById("inspectorTranscribeSizeSlider")?.value || "6");
                const glowVal = parseInt(document.getElementById("inspectorTranscribeGlowSlider")?.value || "65", 10);
                const animVal = document.getElementById("inspectorTranscribeAnim")?.value || "pop";
                const hotWordsVal = !!document.getElementById("inspectorTranscribeHotWords")?.checked;
                const wpcSel = document.getElementById("inspectorWordsPerCue");
                const wordsPerCue = wpcSel ? (parseInt(wpcSel.value, 10) || 3) : 3;

                state.clipper.subFont = fontVal;
                state.clipper.subSize = sizeVal / 6.0;
                state.clipper.subGlow = glowVal;
                state.clipper.subAnim = animVal;
                state.clipper.hotWords = hotWordsVal;
                state.clipper.wordsPerCue = wordsPerCue;

                if (inspTransSpinner) inspTransSpinner.style.display = "inline-block";
                inspTransBtn.disabled = true;

                try {
                    const res = await fetch("/api/transcribe", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            filename: mediaFilename,
                            start_time: clip.sourceOffset || 0.0,
                            duration: clip.duration,
                            language: lang || undefined,
                            model: "whisper-large-v3-turbo"
                        })
                    });

                    if (!res.ok) {
                        const err = await res.text();
                        showToast(`Ошибка Groq Whisper API: ${err}`, "err");
                        return;
                    }

                    const data = await res.json();
                    const words = data.words || [];
                    if (!words.length) {
                        showToast("В выбранном клипе речь не обнаружена.", "err");
                        return;
                    }
                    const srcOff = clip.sourceOffset || 0;
                    const tg = {
                        kind: "clip", id: clip.id,
                        filename: mediaFilename,
                        srcStart: srcOff, srcEnd: srcOff + clip.duration,
                        tlStart: clip.startTime,
                        srcToTl: (src) => clip.startTime + (src - srcOff)
                    };
                    const batchId = Date.now() + "_" + Math.floor(Math.random() * 1e6);
                    state._lastTranscribe = { words, tg, batchId };
                    const made = wordsToTimelineClips(words, tg, batchId, {
                        targetTrackId: targetTrack,
                        textFont: fontVal,
                        textSize: sizeVal,
                        textGlow: glowVal,
                        textAnimIn: animVal,
                        wordsPerCue: wordsPerCue,
                        hotWords: hotWordsVal,
                        subtitleStyle: styleVal
                    });

                    recalcTotalDuration();
                    renderTracksDOM();
                    renderTimeline();
                    renderSubtitlesCues(state.clipper.subtitles);
                    updateLiveSubtitleOverlay();
                    updateTvPreview();
                    saveProject();
                    syncTranscribeTrackSelect();
                    showToast(`Готово: фрагментов на слое титров — ${made} (слов на фрагмент: ${wordsPerCue}).`, "ok");
                } catch (e) {
                    console.error("Transcribe error:", e);
                    showToast("Ошибка сети: " + e.message, "err");
                } finally {
                    if (inspTransSpinner) inspTransSpinner.style.display = "none";
                    inspTransBtn.disabled = false;
                }
            });
        }
    }

    // ── Tab 3: SHORTS TEMPLATE STUDIO ──
    // Источник и метки IN/OUT живут на панели слоёв: клип на таймлайне + маркеры I/O.
    function initClipperPanel() {
        // One-click TV presets (как в примерах): выставляют формат + TV-цветокор
        // + белые вспышки + зелёные субтитры одним нажатием
        function syncTvPresetUI() {
            const isSplit = state.clipper.format === "split_adhd"
                && state.clipper.colorGrade === "tv" && !!state.clipper.flashCuts;
            const isFull = state.clipper.format === "talking_head_9_16"
                && state.clipper.colorGrade === "tv" && !!state.clipper.flashCuts;
            const ps = document.getElementById("presetTvSplit");
            const pf = document.getElementById("presetTvFull");
            if (ps) ps.classList.toggle("active", isSplit);
            if (pf) pf.classList.toggle("active", isFull);
        }
        function applyTvPreset(kind) {
            if (kind === "split") {
                state.clipper.format = "split_adhd";
                state.clipper.cropPreset = "center";
            } else {
                state.clipper.format = "talking_head_9_16";
                state.clipper.cropPreset = "center";
            }
            state.clipper.colorGrade = "tv";
            state.clipper.flashCuts = true;
            state.clipper.subtitleTemplate = "acid";
            state.aspectRatio = "9:16";
            const artBtn = document.getElementById("aspectRatioToggleBtn");
            if (artBtn) {
                artBtn.textContent = "9:16";
                artBtn.classList.add("active-9-16");
            }
            if (videoMonitor) videoMonitor.classList.add("vertical-9-16");
            document.querySelectorAll(".format-card").forEach(c => c.classList.toggle("active", c.dataset.format === state.clipper.format));
            document.querySelectorAll(".crop-btn").forEach(b => b.classList.toggle("active", b.dataset.crop === state.clipper.cropPreset));
            document.querySelectorAll(".style-card").forEach(c => c.classList.toggle("active", c.dataset.style === "acid"));
            document.querySelectorAll(".grade-btn").forEach(b => b.classList.toggle("active", b.dataset.grade === "tv"));
            document.querySelectorAll(".flash-btn").forEach(b => b.classList.toggle("active", b.dataset.flash === "on"));
            syncTvPresetUI();
            updateClipperUI();
            applyPreviewLook();
            updateBadgeOverlay();
            updateLiveSubtitleOverlay();
            syncVideoToCurrentTime();
            updateTvPreview();
            saveProject();
        }
        const presetSplitBtn = document.getElementById("presetTvSplit");
        const presetFullBtn = document.getElementById("presetTvFull");
        if (presetSplitBtn) presetSplitBtn.addEventListener("click", () => applyTvPreset("split"));
        if (presetFullBtn) presetFullBtn.addEventListener("click", () => applyTvPreset("full"));
        window.__syncTvPresetUI = syncTvPresetUI;
        // Format Cards
        const formatCards = document.querySelectorAll(".format-card");
        formatCards.forEach(card => {
            card.addEventListener("click", () => {
                formatCards.forEach(c => c.classList.remove("active"));
                card.classList.add("active");
                state.clipper.format = card.dataset.format;
                // H7: Shorts-формат немедленно переводит монитор в 9:16
                const shortsFmt = state.clipper.format === "split_adhd" || state.clipper.format === "talking_head_9_16";
                state.aspectRatio = shortsFmt ? "9:16" : "16:9";
                const artBtn = document.getElementById("aspectRatioToggleBtn");
                if (artBtn) {
                    artBtn.textContent = state.aspectRatio;
                    artBtn.classList.toggle("active-9-16", shortsFmt);
                }
                if (videoMonitor) videoMonitor.classList.toggle("vertical-9-16", shortsFmt);
                updateClipperUI();
                applyPreviewLook();
                updateTvPreview();
                updateLiveSubtitleOverlay();
                syncVideoToCurrentTime();
                if (window.__syncTvPresetUI) window.__syncTvPresetUI();
            });
        });

        // Facecam Crop Preset buttons
        document.querySelectorAll(".crop-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".crop-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                state.clipper.cropPreset = btn.dataset.crop;
            });
        });

        // Platform Badge buttons & Streamer Handle
        document.querySelectorAll(".plat-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".plat-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                state.clipper.platform = btn.dataset.platform;
                updateBadgeOverlay();
            });
        });

        const handleInput = document.getElementById("clipperHandleInput");
        if (handleInput) {
            handleInput.addEventListener("input", (e) => {
                state.clipper.streamerHandle = e.target.value.trim();
                updateBadgeOverlay();
            });
        }

        // TV-обработка: цветокор и вспышки (влияют на экспорт и превью)
        document.querySelectorAll(".grade-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".grade-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                state.clipper.colorGrade = btn.dataset.grade;
                applyPreviewLook();
                if (window.__syncTvPresetUI) window.__syncTvPresetUI();
            });
        });
        // flash transitions are FX layer elements now (see addFxClip)
        // Области кадра: соло-режим выбора с зафиксированными пропорциями под 9:16
        const cropDrawBtn = document.getElementById("cropBoxDrawBtn");
        const bgDrawBtn = document.getElementById("bgBoxDrawBtn");
        const cropResetBtn = document.getElementById("cropBoxResetBtn");
        if (cropDrawBtn) cropDrawBtn.addEventListener("click", () => enterPickMode("face"));
        if (bgDrawBtn) bgDrawBtn.addEventListener("click", () => enterPickMode("bg"));
        if (cropResetBtn) cropResetBtn.addEventListener("click", () => {
            state.clipper.cropBox = null;
            state.clipper.bgBox = null;
            updateCropBoxUI();
            updateTvPreview();
            saveProject();
        });
        initPickMode();
        initSubSettings();

        // Region inspector wiring: rename / transcribe with full params / delete
        const regionNameEl = document.getElementById("regionNameInput");
        if (regionNameEl) regionNameEl.addEventListener("change", (e) => {
            const r = findRegionById(state.selectedRegionId);
            if (r && e.target.value.trim()) {
                r.name = e.target.value.trim().slice(0, 40);
                renderRegionsLane();
                renderRegionsList();
                saveProject();
            }
        });
        document.querySelectorAll("#regionInspector .mini-style-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll("#regionInspector .mini-style-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                state.clipper.subtitleTemplate = btn.dataset.style;
                document.querySelectorAll(".style-card").forEach(c => {
                    c.classList.toggle("active", c.dataset.style === btn.dataset.style);
                });
                updateLiveSubtitleOverlay();
                saveProject();
            });
        });
        // Region generation params: live sliders/selects write to clipper defaults
        const rSizeEl = document.getElementById("regionSubSize");
        if (rSizeEl) rSizeEl.addEventListener("input", () => {
            state.clipper.subSize = (parseInt(rSizeEl.value, 10) || 100) / 100;
            const v = document.getElementById("regionSubSizeVal");
            if (v) v.textContent = `${rSizeEl.value}%`;
            updateTvPreview(); saveProject();
        });
        const rGlowEl = document.getElementById("regionSubGlow");
        if (rGlowEl) rGlowEl.addEventListener("input", () => {
            state.clipper.subGlow = parseInt(rGlowEl.value, 10) || 55;
            const v = document.getElementById("regionSubGlowVal");
            if (v) v.textContent = String(rGlowEl.value);
            updateTvPreview(); saveProject();
        });
        ["regionSubFont", "regionSubAnim"].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.addEventListener("change", () => {
                if (id === "regionSubFont") state.clipper.subFont = el.value;
                else state.clipper.subAnim = el.value;
                updateTvPreview(); saveProject();
            });
        });
        const regionTransBtn = document.getElementById("regionTranscribeBtn");
        if (regionTransBtn) regionTransBtn.addEventListener("click", () => {
            transcribeRegion(findRegionById(state.selectedRegionId));
        });
        const regionDelBtn = document.getElementById("regionDeleteBtn");
        if (regionDelBtn) regionDelBtn.addEventListener("click", deleteSelectedRegion);
        // Inspector words-per-cue for clip transcription
        const inspWpc = document.getElementById("inspectorWordsPerCue");
        if (inspWpc) inspWpc.addEventListener("change", (e) => {
            state.clipper.wordsPerCue = parseInt(e.target.value, 10) || 3;
            saveProject();
        });

        // Цели транскрибации: выбранные нарезки (источник под их началом) и/или выбранный клип слоя
        function collectTranscribeTargets() {
            const out = [];
            const regs = sortedRegions().filter(r => r.id === state.selectedRegionId);
            const list = regs.length ? regs : [];
            for (const r of list) {
                const mc = resolvePackSource(r.startTime);
                if (!mc || !mc.media) continue;
                const a = convertTimelineToSourceTime(mc, r.startTime);
                const b = convertTimelineToSourceTime(mc, r.startTime + r.duration);
                if (!(b > a + 0.2)) continue;
                out.push({
                    kind: "region", id: r.id,
                    filename: mc.media.filename,
                    srcStart: a, srcEnd: b,
                    tlStart: r.startTime,
                    srcToTl: (src) => mc.startTime + (src - (mc.sourceOffset || 0))
                });
            }
            const sel = findClipById(state.selectedClipId);
            if (sel && sel.media && !isTextClip(sel)) {
                const a = (sel.sourceOffset || 0);
                const b = a + sel.duration;
                out.push({
                    kind: "clip", id: sel.id,
                    filename: sel.media.filename,
                    srcStart: a, srcEnd: b,
                    tlStart: sel.startTime,
                    srcToTl: (src) => sel.startTime + (src - a)
                });
            }
            return out;
        }
        // Subtitle Style Template Cards
        document.querySelectorAll(".style-card").forEach(card => {
            card.addEventListener("click", () => {
                document.querySelectorAll(".style-card").forEach(c => c.classList.remove("active"));
                card.classList.add("active");
                const styleId = card.dataset.style;
                state.clipper.subtitleTemplate = styleId;
                // Sync all inspector mini buttons
                document.querySelectorAll("#inspectorSubtitleSection .mini-style-btn, #inspectorTranscribeSection .mini-style-btn, #regionInspector .mini-style-btn").forEach(b => {
                    b.classList.toggle("active", b.dataset.style === styleId);
                });
                const clip = findClipById(state.selectedClipId);
                if (clip && isTextClip(clip)) {
                    clip.subtitleStyle = styleId;
                }
                updateLiveSubtitleOverlay();
                updateTvPreview();
                renderTimeline();
                saveProject();
            });
        });

        // Apply subtitles to timeline text track
        const applySubtitlesBtn = document.getElementById("applySubtitlesToTimelineBtn");
        if (applySubtitlesBtn) {
            applySubtitlesBtn.addEventListener("click", () => {
                if (!state.clipper.subtitles || state.clipper.subtitles.length === 0) {
                    showToast("Сначала сгенерируйте субтитры.", "info");
                    return;
                }
                applySubtitlesToTrackV3();
            });
        }

        // Сборка payload экспорта из нарезок таймлайна + слов-клипов слоя титров
        // Субтитры уходят в ВЫХОДНОМ времени нарезки (subs_in_output_time) —
        // сервер больше не перемапливает их повторно (раньше это резало половину реплик)
        // collectRegionSubtitles -> module scope (studio:hoist-collectors)
        // Свободный текст (не субтитры): полные параметры как у субтитров
        // collectRegionTextItems -> module scope (studio:hoist-collectors)
        function resolveRegionSource(r) {
            const mc = resolvePackSource(r.startTime);
            if (!mc || !mc.media) return null;
            const a = convertTimelineToSourceTime(mc, r.startTime);
            // Multi-clip regions (discipline edits) run past this clip's source:
            // the layered exporter only consumes `layers`, so b just needs to be
            // a sane, increasing span — fall back to the region length.
            let b = convertTimelineToSourceTime(mc, r.startTime + r.duration);
            if (!(b > a + 0.2)) b = a + Math.max(0.3, r.duration);
            return { mc, a, b };
        }
        // FX overlays + sounds + timeline audio mapped into one region's output.
        // z = позиция слоя в trackList (0 = верхний): вспышка под верхними
        // элементами НЕ действует на них (сервер жжёт её только под композитом)
        // collectRegionFx -> module scope (studio:hoist-collectors)
        function collectRegionAudio(r) {
            const out = [];
            for (const tid of trackOrder()) {
                const track = getTrack(tid);
                if (!track || track.kind !== "audio") continue;
                for (const c of (state.tracks[tid] || [])) {
                    if (!c.media || c.isFx) continue;
                    const cs = c.startTime, ce = c.startTime + c.duration;
                    if (ce <= r.startTime + 0.02 || cs >= r.startTime + r.duration - 0.02) continue;
                    const inFront = Math.max(0, r.startTime - cs);
                    out.push({
                        filename: c.media.filename,
                        src_offset: (c.sourceOffset || 0) + inFront,
                        out_start: Math.max(0, cs - r.startTime),
                        duration: Math.min(ce, r.startTime + r.duration) - Math.max(cs, r.startTime),
                        gain: c.volume != null ? c.volume : 1.0,
                        loop: !!c.musicDuck,
                        duck: !!c.musicDuck
                    });
                }
            }
            return out;
        }
        // Слои для экспорта: каждый видео-/имидж-элемент под нарезкой, снизу вверх.
        // z = индекс трека (0 = верхний трек). База = самый нижний активный клип.
        // Все пересекающиеся клипы трека (последовательный таймлайн дисциплины
        // раньше терял всё после первого клипа — экспортировались только 3 секунды).
        function collectRegionLayers(r) {
            const order = trackOrder();
            const layers = [];
            for (let zi = order.length - 1; zi >= 0; zi--) {
                const tid = order[zi];
                const track = getTrack(tid);
                if (!track || track.kind !== "video") continue;
                const seq = (state.tracks[tid] || []).filter(x =>
                    x.media && !x.isFx &&
                    x.startTime < r.startTime + r.duration - 0.02 &&
                    x.startTime + x.duration > r.startTime + 0.02);
                seq.sort((a, b) => a.startTime - b.startTime);
                for (const c of seq) {
                    const covS = Math.max(c.startTime, r.startTime);
                    const covE = Math.min(c.startTime + c.duration, r.startTime + r.duration);
                    const dur = covE - covS;
                    if (dur <= 0.05) continue;
                    layers.push({
                        source_file: c.media.filename,
                        src_offset: Math.max(0, (c.sourceOffset || 0) + (covS - c.startTime)),
                        duration: dur,
                        out_start: Math.max(0, covS - r.startTime),
                        opacity: c.opacity != null ? c.opacity : 1.0,
                        volume: c.volume != null ? c.volume : 1.0,
                        muted: !!(getTrack(c.trackId) && getTrack(c.trackId).muted),
                        pip: zi === order.length - 1 ? null : pipForClip(c),
                        track_path: (c.trackPath && c.trackPath.length) ? c.trackPath : null,
                        scale_from: (c.discScaleFrom != null) ? c.discScaleFrom : null,
                        scale_in: (c.discScaleIn != null) ? c.discScaleIn : 0.35,
                        tint: c.discTint || null,
                        z: zi
                    });
                }
            }
            return layers;
        }
        function buildExportItems() {
            const regs = sortedRegions();
            if (!regs.length) return { items: [], skipped: [] };
            const resolved = [];
            const skipped = [];
            for (const r of regs) {
                const s = resolveRegionSource(r);
                if (!s) { skipped.push(r.name); continue; }
                resolved.push({ r, ...s });
            }
            if (!resolved.length) return { items: [], skipped };
            const common = {
                format: state.clipper.format,
                crop_preset: state.clipper.cropPreset || "top_right",
                platform: "KICK",
                streamer_handle: state.clipper.streamerHandle || "@shorts",
                subtitle_template: state.clipper.subtitleTemplate || "acid",
                sub_font: state.clipper.subFont || "Anton",
                sub_size: state.clipper.subSize || 1.0,
                sub_glow: state.clipper.subGlow != null ? state.clipper.subGlow : 55,
                sub_anim: state.clipper.subAnim || "pop",
                color_grade: state.clipper.colorGrade || "tv",
                flash_cuts: false,
                crop_box: state.clipper.cropBox || null,
                bg_box: state.clipper.bgBox || null,
                bar_top: parseInt(state.clipper.barTop, 10) || 0,
                bar_bottom: parseInt(state.clipper.barBottom, 10) || 0,
                hot_words: state.clipper.hotWords === true,
                // H1: субтитры живут на таймлайне — единый источник правды
                subtitle_mode: "timeline"
            };
            // верхний слой с текстом: FX на треках выше него прожигаются ПОВЕРХ текста
            const tz = trackOrder().findIndex(tid => (getTrack(tid) || {}).kind === "text");
            // Источник — уже готовый шортс (вшиты субтитры и цветокор)?
            // авто-детект ТОЛЬКО по нашим экспортным префиксам/суффиксам + ручной
            // переключатель; обычные слова в имени файла (напр. «ГОТОВЫ») больше
            // не отключают град и субтитры
            const processedRe = /(?:^|[\\/])Short_[^\\/]*\.mp4$|[_-](?:processed|final)\.mp4$/i;
            // Каждая нарезка — всегда отдельный файл (для этого они и размечаются)
            const items = resolved.map(({ r, mc, a, b }) => {
                const fx = collectRegionFx(r);
                const lrs = collectRegionLayers(r);
                const srcProcessed = !!state.clipper.srcProcessed ||
                    !!(lrs.length && lrs[0].source_file && processedRe.test(lrs[0].source_file));
                const outBases = [0];
                return {
                    id: "rg_" + r.id,
                    title: r.name,
                    source_file: mc.media.filename,
                    start_time: a, end_time: b,
                    segments: [{ start_time: a, end_time: b }],
                    subtitles: collectRegionSubtitles([r], outBases),
                    text_items: collectRegionTextItems([r], outBases),
                    subs_in_output_time: true,
                    layers: lrs,
                    overlays: fx.overlays,
                    sounds: fx.sounds,
                    extra_audio: collectRegionAudio(r),
                    skip_flash_at: [],
                    text_z: tz >= 0 ? tz : null,
                    src_processed: srcProcessed,
                    ...common
                };
            });
            return { items, skipped };
        }
        // §7.4/§7.6: очередь экспорта — пакет уходит в фон, редактор остаётся живым
        // studio:tdz-exportPackBtn - declared before its first use
        const exportPackBtn = document.getElementById("exportPackBtn");
        const queueExportBtn = document.createElement("button");
        queueExportBtn.id = "exportQueueBtn";
        queueExportBtn.className = (exportPackBtn && exportPackBtn.className) || "btn";
        queueExportBtn.textContent = "⏳ В очередь";
        queueExportBtn.title = "Поставить все нарезки в очередь экспорта (рендер в фоне, прогресс через SSE)";
        if (exportPackBtn && exportPackBtn.parentElement) {
            exportPackBtn.parentElement.insertBefore(queueExportBtn, exportPackBtn.nextSibling);
        }
        queueExportBtn.addEventListener("click", async () => {
            const built = buildExportItems();
            if (!built.items.length) {
                showToast("Нет нарезок для очереди — создай хотя бы одну (+ Нарезка).", "info");
                return;
            }
            try {
                const res = await fetch("/api/export-queue", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        clips: built.items.map(p => {
                            const { segment_files, ...rest } = p;
                            return { ...rest, overlay_file: null, track_path: null };
                        }),
                        name_template: state.clipper.nameTemplate || "{channel}_{date}_{n}_{title}"
                    })
                });
                if (!res.ok) {
                    showToast("Очередь отклонила запрос: " + (await res.text()), "err");
                    return;
                }
                showToast(`В очереди: ${(await res.json()).queued} нарезок. Рендер идёт в фоне.`, "ok");
                listenExportQueue();
            } catch (e) {
                showToast("Ошибка очереди: " + e.message, "err");
            }
        });

        let queueES = null;
        function listenExportQueue() {
            if (queueES) queueES.close();
            const statusText = document.getElementById("exportStatusText");
            const statusBox = document.getElementById("exportStatusBox");
            if (statusBox) statusBox.classList.remove("hidden");
            queueES = new EventSource("/api/export-queue/stream");
            queueES.onmessage = (ev) => {
                const m = JSON.parse(ev.data);
                if (m.type === "progress") {
                    if (statusText) statusText.textContent =
                        `Очередь экспорта: ${m.done}/${m.total}` +
                        (m.current ? ` — рендерится «${m.current.title}»` : "");
                } else if (m.type === "end") {
                    if (statusText) statusText.textContent =
                        `Очередь экспорта завершена: ${m.done}/${m.total}. Файлы в downloads/exported_packs.`;
                    queueES.close();
                    queueES = null;
                    fetchLibrary();
                }
            };
            queueES.onerror = () => {
                // studio:queue-sse-reconnect
                if (queueES) { queueES.close(); queueES = null; }
                setTimeout(() => {
                    fetch("/api/export-queue/status").then(r => r.json()).then(st => {
                        if (st && st.running && !queueES) listenExportQueue();
                    }).catch(() => {});
                }, 1500);
            };
        }
        // если очередь уже крутится (перезагрузка страницы) — подключаемся снова
        fetch("/api/export-queue/status").then(r => r.json()).then(st => {
            if (st && st.running) listenExportQueue();
        }).catch(() => {});

        // Batch Pack highlights
        const addHighlightBtn = document.getElementById("addHighlightToPackBtn");
        // (exportPackBtn is declared above - studio:tdz-late-removed)

        if (addHighlightBtn) {
            addHighlightBtn.title = "Создать нарезку от плейхеда (то же, что + Нарезка на таймлайне)";
            addHighlightBtn.addEventListener("click", addRegionFromPlayhead);
        }

        if (exportPackBtn) {
            exportPackBtn.addEventListener("click", async () => {
                const built = buildExportItems();
                if (!built.items.length) {
                    showToast(built.skipped.length
                        ? `Нарезки вне клипов на слоях (${built.skipped.join(", ")}) — положи видео на таймлайн под полосы нарезок.`
                        : "Создай хотя бы одну нарезку на полосе над слоями (кнопка + Нарезка).", "info");
                    return;
                }
                if (built.forcedSeparate) {
                    showToast("Нарезки из разных источников — экспортирую каждую отдельным файлом.", "info");
                }

                const spinner = document.getElementById("exportPackSpinner");
                const statusBox = document.getElementById("exportStatusBox");
                const statusText = document.getElementById("exportStatusText");

                if (spinner) spinner.style.display = "inline-block";
                exportPackBtn.disabled = true;
                if (statusBox) statusBox.classList.remove("hidden");
                if (statusText) statusText.textContent = `FFmpeg рендерит ${built.items.length} видео (это занимает несколько минут)...`;

                try {
                    const res = await fetch("/api/export-pack", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            pack_name: "ShortsRegions",
                            clips: built.items.map(p => {
                                const { segment_files, ...rest } = p;
                                return { ...rest, overlay_file: null, track_path: null };
                            })
                        })
                    });

                    if (!res.ok) {
                        showToast("Ошибка экспорта: " + (await res.text()), "err");
                        return;
                    }

                    const data = await res.json();
                    const failedList = Array.isArray(data.failed) ? data.failed : [];
                    if (failedList.length) {
                        statusText.textContent = `Экспортировано: ${data.exported_count}, не удалось: ${failedList.length}. ` +
                            failedList.map(f => `«${f.title}»: ${f.error}`).join(" · ");
                        statusText.classList.add("export-warning");
                    } else {
                        statusText.textContent = `Успешно экспортировано: ${data.exported_count}. Файлы лежат в downloads/exported_packs.`;
                        statusText.classList.remove("export-warning");
                    }
                    renderReadyClips(data.clips || []);
                } catch (e) {
                    console.error("Export error:", e);
                    showToast("Ошибка экспорта: " + e.message, "err");
                } finally {
                    if (spinner) spinner.style.display = "none";
                    exportPackBtn.disabled = false;
                }
            });
        }
    }

    // PiP-окно элемента: только если элемент явно помечен как PiP или трекинг
    function pipForClip(c) {
        if (!c) return null;
        if (c.pipBox) return c.pipBox;
        if (c.trackPath && c.trackPath.length) {
            const p = c.trackPath[0];
            return { x: Math.max(0, p.x), y: Math.max(0, p.y), w: Math.max(0.05, p.w) };
        }
        if (c.isPip) {
            return { x: 0.688, y: 0.018, w: 0.30 };
        }
        return null;
    }
    // ── TV 9:16 composite preview: EXACTLY like the export will look ──
    // Layers bottom→top, PiP windows, FX elements with z-order (an FX under an
    // upper layer never touches it), squeeze-bars + frames + shake coupling,
    // warm TV grade, subtitles with the same fonts/anims as the export.
    function tvPreviewWanted() {
        if (pickMode) return null;
        if ((state.aspectRatio || "16:9") !== "9:16") return null;
        const fmt = state.clipper.format;
        if (fmt !== "split_adhd" && fmt !== "talking_head_9_16") return null;
        const t = state.currentTime;
        const order = trackOrder();
        const layers = [];
        for (let zi = order.length - 1; zi >= 0; zi--) {
            const tid = order[zi];
            const track = getTrack(tid);
            if (!track || track.kind !== "video" || track.hidden) continue;
            const clip = (state.tracks[tid] || []).find(c =>
                c.media && !c.isFx && t >= c.startTime && t < c.startTime + c.duration);
            if (clip) layers.push({ clip, z: zi });
        }
        if (!layers.length) return null;
        return { layers, t };
    }
    // fit a normalized source box into a container: returns css px for the <video>
    function coverBoxToCss(cW, cH, vidAR, box) {
        const b = box || { x: 0, y: 0, w: 1, h: 1 };
        let W = cW / Math.max(0.02, b.w);
        let H = W / vidAR;
        if (H * Math.max(0.02, b.h) < cH) {
            H = cH / Math.max(0.02, b.h);
            W = H * vidAR;
        }
        const left = -(b.x * W) + (W * b.w - cW) / 2;
        const top = -(b.y * H) + (H * b.h - cH) / 2;
        return { w: W, h: H, left, top };
    }
    // default aspect-matched region, anchored RIGHT (talking-head streams keep
    // the face on the right; a centered default grabs excess background)
    function defaultAspectBox(vidAR, targetAspect) {
        let bw, bh;
        if (targetAspect >= vidAR) { bw = 1; bh = vidAR / targetAspect; }
        else { bh = 1; bw = targetAspect / vidAR; }
        bw = Math.min(1, bw); bh = Math.min(1, bh);
        const preset = state.clipper.cropPreset || "center";
        let x = (1 - bw) / 2;
        if (preset === "top_right") x = 1 - bw;
        else if (preset === "top_left") x = 0;
        return { x, y: (1 - bh) / 2, w: bw, h: bh };
    }
    function tvpSetVideo(vid, clip, targetTime) {
        if (!vid || !clip || !clip.media) return;
        if (vid.getAttribute("data-file") !== clip.media.filename) {
            vid.src = clip.media.stream_url;
            vid.setAttribute("data-file", clip.media.filename);
        }
        vid.muted = true;
        const tt = Math.max(0, (clip.sourceOffset || 0) + (targetTime - clip.startTime));
        setElTime(vid, tt);
        if (state.isPlaying) { if (vid.paused) vid.play().catch(() => {}); }
        else if (!vid.paused) { try { vid.pause(); } catch (e) {} }
    }
    function tvpLayoutVideo(vid, cont, box, vidAR) {
        if (!vid || !cont || !vidAR) return;
        const r = cont.getBoundingClientRect();
        if (r.width < 4 || r.height < 4) return;
        const css = coverBoxToCss(r.width, r.height, vidAR, box);
        vid.style.position = "absolute";
        vid.style.width = `${css.w}px`;
        vid.style.height = `${css.h}px`;
        vid.style.left = `${css.left}px`;
        vid.style.top = `${css.top}px`;
        vid.style.maxWidth = "none";
        vid.style.maxHeight = "none";
    }
    // Разбить слова на фрагменты (слов-на-фрагмент из настроек) и положить словами-клипами на V3
    function chunkWordsForCues(words, maxN) {
        const chunks = [];
        let cur = [];
        let curStart = 0;
        for (const w of words) {
            const txt = (w.word || "").trim();
            if (!txt) continue;
            if (!cur.length) curStart = (w.abs_start !== undefined ? w.abs_start : w.start);
            const prev = cur[cur.length - 1];
            const gap = prev ? ((w.abs_start !== undefined ? w.abs_start : w.start) - (prev.abs_end !== undefined ? prev.abs_end : prev.end)) : 0;
            const dur = ((w.abs_end !== undefined ? w.abs_end : w.end)) - curStart;
            const punct = /[.!?……:;]$/.test(prev ? (prev.word || "") : "");
            if (cur.length && (cur.length >= maxN || gap > 0.45 || dur > 2.8 || punct)) {
                chunks.push(cur);
                cur = [];
                curStart = (w.abs_start !== undefined ? w.abs_start : w.start);
            }
            cur.push(w);
        }
        if (cur.length) chunks.push(cur);
        return chunks;
    }
    // Слова (abs = время источника) → клипы-слова на текстовом слое (abs = время таймлайна)
    function wordsToTimelineClips(words, tg, batchId, opts = {}) {
        ensureTracksInitialized();
        let tidText = opts.targetTrackId;
        if (tidText === "__new__") {
            tidText = addTrack("text");
        }
        if (!tidText || !getTrack(tidText)) {
            tidText = textTrackId();
        }
        if (!tidText) {
            tidText = addTrack("text");
        }
        const maxN = Math.max(1, Math.min(6, parseInt(opts.wordsPerCue || state.clipper.wordsPerCue || "3", 10) || 3));
        const styleNow = opts.subtitleStyle || state.clipper.subtitleTemplate || "acid";
        const fontNow = opts.textFont || state.clipper.subFont || "Montserrat ExtraBold";
        const sizeNow = opts.textSize != null ? opts.textSize : 6.0;
        const glowNow = opts.textGlow != null ? opts.textGlow : 65;
        const animNow = opts.textAnimIn || state.clipper.subAnim || "pop";
        const hotWordsNow = opts.hotWords != null ? opts.hotWords : true;
        const chunks = chunkWordsForCues(words, maxN);
        const arr = (state.tracks[tidText] = state.tracks[tidText] || []);
        let made = 0;
        const stamp = batchId || (Date.now() + "_" + Math.floor(Math.random() * 1e6));
        for (const ch of chunks) {
            const w0 = ch[0], w1 = ch[ch.length - 1];
            const s0 = (w0.abs_start !== undefined ? w0.abs_start : w0.start);
            const s1 = (w1.abs_end !== undefined ? w1.abs_end : w1.end);
            // слова вне цели (за пределами отрезка) — пропускаем
            if (s1 <= tg.srcStart + 0.02 || s0 >= tg.srcEnd - 0.02) continue;
            const tl0 = tg.srcToTl(Math.max(tg.srcStart, s0));
            const tl1 = tg.srcToTl(Math.min(tg.srcEnd, s1));
            if (!(tl1 > tl0 + 0.1)) continue;
            const wtl = ch.map(w => ({
                word: w.word,
                abs_start: tg.srcToTl(w.abs_start !== undefined ? w.abs_start : w.start),
                abs_end: tg.srcToTl(w.abs_end !== undefined ? w.abs_end : w.end)
            }));
            arr.push({
                id: "w_" + stamp + "_" + made,
                trackId: tidText,
                startTime: tl0,
                duration: tl1 - tl0,
                sourceOffset: 0,
                sourceDuration: tl1 - tl0,
                title: ch.map(w => (w.word || "").trim()).join(" "),
                words: wtl,
                subtitleStyle: styleNow,
                textFont: fontNow,
                textSize: sizeNow,
                textGlow: glowNow,
                textAnimIn: animNow,
                textHotWords: hotWordsNow,
                isText: true,
                batch: "w_" + stamp,
                media: null,
                volume: 1.0,
                opacity: 1.0,
                fromRegion: tg.kind === "region" ? tg.id : null
            });
            made++;
        }
        arr.sort((a, b) => a.startTime - b.startTime);
        // зеркало для списка «Распознано»
        state.clipper.subtitles = [];
        for (const tid of trackOrder()) {
            const trk = getTrack(tid);
            if (!trk || trk.kind === "audio") continue;
            for (const c of (state.tracks[tid] || [])) {
                if (c.isText && c.title && !c.freeText) {
                    state.clipper.subtitles.push({
                        id: c.id, text: c.title, abs_start: c.startTime, abs_end: c.startTime + c.duration,
                        words: (c.words || []).map(w => ({ ...w }))
                    });
                }
            }
        }
        state.clipper.subtitles.sort((a, b) => a.abs_start - b.abs_start);
        return made;
    }

    function currentCueClip() {
        const t = state.currentTime;
        // text/subtitle clips may live on ANY layer (text or video)
        let fallback = null;
        for (const tid of trackOrder()) {
            const track = getTrack(tid);
            if (!track || track.kind === "audio" || track.hidden) continue;
            for (const c of (state.tracks[tid] || [])) {
                if (c.isFx || c.media || !c.title) continue;
                if (!(t >= c.startTime && t < c.startTime + c.duration)) continue;
                const cue = { text: c.title, template: c.subtitleStyle || state.clipper.subtitleTemplate, clip: c };
                if (!c.freeText) return cue;      // subtitles win over free text
                if (!fallback) fallback = cue;
            }
        }
        if (fallback) return fallback;
        const cues = state.clipper.subtitles || [];
        const cue = cues.find(x => t >= x.abs_start && t <= x.abs_end);
        if (cue && cue.text) return { text: cue.text, template: state.clipper.subtitleTemplate };
        return null;
    }
    // studio:hoist-collectors - region collectors live at MODULE scope: the
    // server preview frame (requestServerPreviewFrame) and the export
    // (initClipperPanel) both call them. They were local to initClipperPanel ->
    // ReferenceError: collectRegionSubtitles is not defined (PR #7 smoke test).
    function collectRegionSubtitles(regs, outBases) {
        // subtitle AND free-text clips from ALL text layers AND video layers
        const tclips = [];
        for (const tid of trackOrder()) {
            const track = getTrack(tid);
            if (!track || track.kind === "audio") continue;
            for (const c of (state.tracks[tid] || [])) {
                if (c.isFx || c.media || !c.title) continue;
                if (!isTextClip(c)) continue;
                tclips.push(c);
            }
        }
        tclips.sort((a, b) => a.startTime - b.startTime);
        const subs = [];
        regs.forEach((r, k) => {
            const base = outBases[k];
            for (const c of tclips) {
                if (c.freeText) continue; // free text -> separate text_items
                const cs = c.startTime, ce = c.startTime + c.duration;
                if (ce <= r.startTime + 0.02 || cs >= r.startTime + r.duration - 0.02) continue;
                const words = Array.isArray(c.words) && c.words.length ? c.words : [{
                    word: c.title || "",
                    abs_start: Math.max(cs, r.startTime),
                    abs_end: Math.min(ce, r.startTime + r.duration)
                }];
                const wout = [];
                for (const w of words) {
                    const ws = Math.max(w.abs_start, r.startTime) - r.startTime;
                    const we = Math.min(w.abs_end, r.startTime + r.duration) - r.startTime;
                    if (!(we > ws + 0.03)) continue;
                    wout.push({ word: w.word, start: base + ws, end: base + we, style: c.subtitleStyle || null });
                }
                if (!wout.length) continue;
                subs.push({
                    text: c.title || "",
                    start: base + Math.max(0, cs - r.startTime),
                    end: base + Math.min(r.duration, ce - r.startTime),
                    abs_start: base + Math.max(0, cs - r.startTime),
                    abs_end: base + Math.min(r.duration, ce - r.startTime),
                    style: c.subtitleStyle || null,
                    words: wout,
                    // позиция, перенесённая вручную на превью (0..1 доли кадра)
                    x: c.textX != null ? c.textX : null,
                    y: c.textY != null ? c.textY : null
                });
            }
        });
        return subs;
    }
    function collectRegionTextItems(regs, outBases) {
        const items = [];
        for (const tid of trackOrder()) {
            const track = getTrack(tid);
            if (!track || track.kind === "audio") continue;
            for (const c of (state.tracks[tid] || [])) {
                if (!c.isText || !c.freeText || !c.title) continue;
                regs.forEach((r, k) => {
                    const base = outBases[k];
                    const cs = c.startTime, ce = c.startTime + c.duration;
                    if (ce <= r.startTime + 0.02 || cs >= r.startTime + r.duration - 0.02) return;
                    const s = base + Math.max(0, cs - r.startTime);
                    const e = base + Math.min(r.duration, ce - r.startTime);
                    if (!(e > s + 0.05)) return;
                    items.push({
                        text: c.title,
                        start: s, end: e,
                        font: c.textFont || state.clipper.subFont || "Montserrat ExtraBold",
                        size: Math.round((c.textSize || 6.0) * 1920 / 100), // % of 1080x1920 height -> px
                        color: c.textColor || "#ffffff",
                        glow: c.textGlow != null ? c.textGlow : 55,
                        anim_in: c.textAnimIn || "pop",
                        anim_out: c.textAnimOut || "fade",
                        x: c.textX != null ? c.textX : 0.5,
                        y: c.textY != null ? c.textY : 0.72,
                        shake: !!c.textShake,
                        stroke: c.textStroke != null ? c.textStroke : 0,
                        spacing: c.textSpacing != null ? c.textSpacing : 0
                    });
                });
            }
        }
        return items;
    }
    // FX overlays + sounds mapped into one region's output.
    // z = позиция слоя в trackList (0 = верхний): вспышка под верхними
    // элементами НЕ действует на них (сервер жжёт её только под композитом)
    function collectRegionFx(r) {
        const overlays = [];
        const sounds = [];
        const order = trackOrder();
        for (let zi = 0; zi < order.length; zi++) {
            const tid = order[zi];
            const track = getTrack(tid);
            if (!track || track.kind !== "video") continue;
            for (const c of (state.tracks[tid] || [])) {
                if (!c.isFx) continue;
                const cs = c.startTime, ce = c.startTime + c.duration;
                if (ce <= r.startTime + 0.02 || cs >= r.startTime + r.duration - 0.02) continue;
                const ov = {
                    start: Math.max(0, cs - r.startTime),
                    end: Math.min(r.duration, ce - r.startTime),
                    kind: c.fxKind || "flash",
                    color: c.fxColor || "white",
                    peak: c.fxPeak != null ? c.fxPeak : 0.75,
                    bar_h: c.fxBarH || 120,
                    amp: c.fxAmp || 12,
                    freq: c.fxFreq || 7,
                    mode: c.fxMode || null,
                    z: zi
                };
                // studio:fx-anchor-export - template face anchor (0..1 of the frame).
                // studio:face-anchor-split - If the punch carries a tracked face
                // anchor via faceAnchor() (anchored zoom), prefer that resolved
                // OUTPUT anchor (already split-mapped). Explicit c.anchor wins.
                let _anchored = null;
                if (c.fxKind === "zoom" && !c.anchor) {
                    // anchor derived from the tracked face box on the BASE layer
                    const base = resolvePackSource(r.startTime);
                    if (base && base.mc) {
                        try {
                            const fa = state.clipper._lastFaceAnchor ||
                                (function () {
                                    const hk = window.__canvasMonitor && window.__canvasMonitor.hooks;
                                    return hk && hk.faceAnchor ? hk.faceAnchor(base.mc, (c.startTime + c.duration / 2)) : null;
                                })();
                            if (fa && isFinite(Number(fa.x)) && isFinite(Number(fa.y))) _anchored = fa;
                        } catch (e) {}
                    }
                    // fallback: compute from the base clip's tracked box directly
                    if (!_anchored) {
                        try {
                            const baseClip = (() => {
                                for (const tid of videoTrackIds()) {
                                    for (const cl of (state.tracks[tid] || [])) {
                                        if (!cl.isFx && cl.media && cl.trackPath && cl.trackPath.length) return cl;
                                    }
                                }
                                return null;
                            })();
                            if (baseClip) {
                                const mid = c.startTime + c.duration / 2;
                                const box = trackPosAt(baseClip, mid);
                                if (box) {
                                    let fx_ = box.x + box.w / 2, fy_ = box.y + box.h / 2;
                                    if (fx_ > 1.001 || fy_ > 1.001) {
                                        const mw = Number(baseClip.media && (baseClip.media.width || baseClip.media.w)) || 1920;
                                        const mh = Number(baseClip.media && (baseClip.media.height || baseClip.media.h)) || 1080;
                                        fx_ /= mw; fy_ /= mh;
                                    }
                                    if (state.clipper.format === "split_adhd" && state.clipper.cropBox) {
                                        const cb = state.clipper.cropBox;
                                        const bw = Math.max(1e-6, cb.w), bh = Math.max(1e-6, cb.h);
                                        const outH = 1920, topH = Math.round(outH * 0.45 / 2) * 2;
                                        fx_ = (fx_ - cb.x) / bw;
                                        fy_ = ((fy_ - cb.y) / bh) * (topH / outH);
                                    }
                                    _anchored = { x: Math.max(0.15, Math.min(0.85, fx_)), y: Math.max(0.15, Math.min(0.85, fy_)) };
                                }
                            }
                        } catch (e2) {}
                    }
                }
                const an = c.anchor || _anchored;
                if (an && isFinite(Number(an.x)) && isFinite(Number(an.y))) {
                    ov.anchor_x = Math.max(0, Math.min(1, Number(an.x)));
                    ov.anchor_y = Math.max(0, Math.min(1, Number(an.y)));
                }
                overlays.push(ov);
                if (c.fxSound && c.fxSound !== "none") {
                    sounds.push({
                        at: Math.max(0, cs - r.startTime),
                        kind: c.fxSound,
                        gain: c.fxGain != null ? c.fxGain : 1.0
                    });
                }
            }
        }
        return { overlays, sounds };
    }

    // Серверный кадр превью: рендер тем же фильтр-графом, что и экспорт (WYSIWYG)
    let pvTimer = null;
    function hideServerPreviewFrame() {
        const img = document.getElementById("serverFrameImg");
        if (img) img.style.display = "none";
    }
    // studio:preview-frame-v2 - (1) the collectors are module-level now (was a
    // ReferenceError); (2) the stale-frame guard compared with an undefined
    // `token` (ReferenceError in onload: the frame never appeared) -> request
    // sequence number; (3) superseded blob URLs are revoked (leak on scrubbing);
    // (4) a late response never overwrites a newer frame.
    let pvSeq = 0;
    let pvShownUrl = null;
    function requestServerPreviewFrame() {
        if (state.isPlaying) { hideServerPreviewFrame(); return; }
        const r = (state.regions || []).find(rg => state.currentTime >= rg.startTime && state.currentTime < rg.startTime + rg.duration);
        if (!r) { hideServerPreviewFrame(); return; }
        const mc = resolvePackSource(r.startTime);
        if (!mc || !mc.media) { hideServerPreviewFrame(); return; }
        if (pvTimer) clearTimeout(pvTimer);
        const seq = ++pvSeq;
        pvTimer = setTimeout(async () => {
            if (state.isPlaying || seq !== pvSeq) return;
            let subs, tis, fx;
            try {
                subs = collectRegionSubtitles([r], [0]);
                tis = collectRegionTextItems([r], [0]);
                fx = collectRegionFx(r);
            } catch (e) {
                console.warn("[preview-frame] collect failed:", e);
                return;
            }
            const srcTime = (mc.sourceOffset || 0) + (state.currentTime - mc.startTime);
            const payload = {
                source_file: mc.media.filename, src_time: srcTime,
                format: state.clipper.format, crop_box: state.clipper.cropBox || null,
                bg_box: state.clipper.bgBox || null, color_grade: state.clipper.colorGrade,
                subtitle_template: state.clipper.subtitleTemplate, sub_font: state.clipper.subFont,
                sub_size: state.clipper.subSize, hot_words: state.clipper.hotWords !== false,
                subtitles: subs, text_items: tis, overlays: fx.overlays,
                region_time: state.currentTime - r.startTime
            };
            try {
                const res = await fetch("/api/preview-frame", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
                if (!res.ok || seq !== pvSeq) return;
                const blob = await res.blob();
                if (seq !== pvSeq || state.isPlaying) return;
                let img = document.getElementById("serverFrameImg");
                if (!img) {
                    img = document.createElement("img");
                    img.id = "serverFrameImg";
                    img.style.cssText = "position:absolute;inset:0;width:100%;height:100%;object-fit:contain;z-index:30;pointer-events:none;";
                    const mon = document.getElementById("videoMonitor");
                    (mon || document.body).appendChild(img);
                }
                // безмигательная подмена: новый кадр подменяется только после загрузки
                const url = URL.createObjectURL(blob);
                const probe = new Image();
                probe.onload = () => {
                    if (seq !== pvSeq || state.isPlaying) { URL.revokeObjectURL(url); return; }
                    const prev = pvShownUrl;
                    pvShownUrl = url;
                    img.src = url;
                    img.style.display = "block";
                    if (prev && prev !== url) URL.revokeObjectURL(prev);
                };
                probe.onerror = () => URL.revokeObjectURL(url);
                probe.src = url;
            } catch (e) { /* превью не критично */ }
        }, 380);
    }

    // Перетаскивание текста/субтитров прямо по превью (AE-style):
    // тянешь мышью — позиция пишется в клип (textX/textY, 0..1) и учитывается экспортом
    function makePreviewDraggable(el, clip, stage) {
        if (!el || !clip || !stage) return;
        el.style.cursor = "move";
        // контейнер tvpSubs имеет pointer-events:none — включаем на самом тексте,
        // иначе перетаскивание невозможно
        el.style.pointerEvents = "auto";
        el.style.touchAction = "none";
        el.addEventListener("pointerdown", (e) => {
            if (e.button !== 0) return;
            e.preventDefault();
            e.stopPropagation();
            const sr = stage.getBoundingClientRect();
            if (sr.width < 4 || sr.height < 4) return;
            const startX = e.clientX, startY = e.clientY;
            const x0 = clip.textX != null ? clip.textX : (el.offsetLeft / stage.clientWidth || 0.5);
            const y0 = clip.textY != null ? clip.textY : (el.offsetTop / stage.clientHeight || 0.62);
            let lastX = x0, lastY = y0;
            try { el.setPointerCapture(e.pointerId); } catch (err) {}
            const onMove = (ev) => {
                lastX = Math.min(0.98, Math.max(0.02, x0 + (ev.clientX - startX) / sr.width));
                lastY = Math.min(0.98, Math.max(0.02, y0 + (ev.clientY - startY) / sr.height));
                el.style.left = (lastX * 100).toFixed(2) + "%";
                el.style.top = (lastY * 100).toFixed(2) + "%";
                el.style.transform = "translate(-50%,-50%)";
            };
            const onUp = () => {
                el.removeEventListener("pointermove", onMove);
                el.removeEventListener("pointerup", onUp);
                el.removeEventListener("pointercancel", onUp);
                clip.textX = +lastX.toFixed(3);
                clip.textY = +lastY.toFixed(3);
                saveProject();
                requestServerPreviewFrame();
            };
            el.addEventListener("pointermove", onMove);
            el.addEventListener("pointerup", onUp);
            el.addEventListener("pointercancel", onUp);
        });
    }

    function updateTvPreview() {
        if (state.isPlaying) hideServerPreviewFrame();
        const tvp = document.getElementById("tvPreview");
        if (!tvp) return;
        // §16 P0: the canvas monitor owns the Shorts preview — the DOM
        // composite (#tvPreview) stays hidden while it is active.
        if (window.__canvasMonitor && window.__canvasMonitor.enabled()) {
            tvp.classList.add("hidden");
            if (videoEl) videoEl.style.visibility = "";
            if (overlayVideoEl) overlayVideoEl.style.visibility = "";
            return;
        }
        const want = tvPreviewWanted();
        const hideMain = !!want;
        if (videoEl) videoEl.style.visibility = hideMain ? "hidden" : "";
        if (overlayVideoEl) overlayVideoEl.style.visibility = hideMain ? "hidden" : "";
        if (!want) {
            tvp.classList.add("hidden");
            ["tvpTop", "tvpBottom", "tvpSubs"].forEach(id => {
                const el = document.getElementById(id);
                if (el && el.closest(".tvp-dyn")) tvp.appendChild(el);
            });
            tvp.querySelectorAll("video").forEach(v => { if (v.id !== "tvpTopVideo" && v.id !== "tvpBottomVideo" && !v.paused) { try { v.pause(); } catch (e) {} } });
            tvp.querySelectorAll(".tvp-dyn").forEach(el => el.remove());
            return;
        }
        tvp.classList.remove("hidden");
        if (monitorOverlay) monitorOverlay.style.display = "none";
        if (noClipPlaceholder) noClipPlaceholder.classList.add("hidden");
        // rescue the persistent band containers from a previously removed stage
        ["tvpTop", "tvpBottom", "tvpSubs"].forEach(id => {
            const el = document.getElementById(id);
            if (el && el.closest(".tvp-dyn")) tvp.appendChild(el);
        });
        // remove previous dynamic layer/fx nodes — сцена персистентна (не пересоздаётся),
        // иначе переподвес живых видео-элементов мигает на каждом обновлении
        tvp.querySelectorAll(".tvp-dyn:not(.tvp-stage)").forEach(el => el.remove());
        // 9:16 stage fit into the monitor
        const tvpW = tvp.clientWidth || 1, tvpH = tvp.clientHeight || 1;
        let stageW = Math.min(tvpW, tvpH * 9 / 16);
        let stageH = stageW * 16 / 9;
        if (stageH > tvpH) { stageH = tvpH; stageW = stageH * 9 / 16; }
        const stageL = (tvpW - stageW) / 2, stageT = (tvpH - stageH) / 2;
        const layers = want.layers, t = want.t;
        const fmt = state.clipper.format;
        const topC = document.getElementById("tvpTop");
        const botC = document.getElementById("tvpBottom");
        const topV = document.getElementById("tvpTopVideo");
        const botV = document.getElementById("tvpBottomVideo");
        const subsEl = document.getElementById("tvpSubs");
        const base = layers[0].clip;
        const vidAR = (base.media.width && base.media.height) ? base.media.width / base.media.height : 16 / 9;
        const FACE_AR = 1080 / 864, BG_AR = 1080 / 1056;
        const faceBox = state.clipper.cropBox || null;
        const bgBox = state.clipper.bgBox || null;
        const gradeOn = (state.clipper.colorGrade || "none") === "tv";
        // warm grade approximation matching the export chain (no blue cast)
        const gradeCss = gradeOn ? "contrast(1.12) saturate(1.28) brightness(1.01)" : "";
        const px = (v) => `${Math.round(v)}px`;

        // container for everything, so the shake transform moves the whole frame.
        // Сцена персистентна: переиспользуем существующую, чтобы живые видео-
        // элементы внутри не пересоздавались (иначе мигание на каждом апдейте)
        let stage = tvp.querySelector(".tvp-stage");
        if (!stage) {
            stage = document.createElement("div");
            stage.className = "tvp-dyn tvp-stage";
            tvp.appendChild(stage);
        }
        stage.style.cssText = "position:absolute;left:" + px(stageL) + ";top:" + px(stageT) + ";width:" + px(stageW) + ";height:" + px(stageH) + ";overflow:hidden;";

        const fxAll = allFxElements();
        const textTopZ = trackOrder().findIndex(tid => (getTrack(tid) || {}).kind === "text");
        const shakeEls = [];
        for (const fx of fxAll) {
            if (fx.fxKind === "shake" && t >= fx.startTime && t < fx.startTime + fx.duration) {
                shakeEls.push({ z: fx.z, amp: (fx.fxAmp || 12) / 1080 * stageW, freq: fx.fxFreq || 7 });
            }
        }
        const shakeOffset = () => {
            let dx = 0, dy = 0;
            for (const sh of shakeEls) {
                dx += sh.amp * Math.sin(2 * Math.PI * sh.freq * t);
                dy += sh.amp * Math.cos(2 * Math.PI * (sh.freq * 9 / 7) * t);
            }
            return { dx, dy };
        };

        // ── base layer: split bands or fullscreen, exactly like the export ──
        if (fmt === "split_adhd") {
            const topH = stageH * 0.45, botH = stageH - topH;
            if (topC) {
                topC.style.display = "";
                topC.style.left = "0px"; topC.style.top = "0px";
                topC.style.width = px(stageW); topC.style.height = px(topH);
                stage.appendChild(topC);
            }
            if (botC) {
                botC.style.display = "";
                botC.style.left = "0px"; botC.style.top = px(topH);
                botC.style.width = px(stageW); botC.style.height = px(botH);
                stage.appendChild(botC);
            }
            tvpSetVideo(topV, base, t);
            tvpSetVideo(botV, base, t);
            if (topV) topV.style.filter = gradeCss;
            if (botV) botV.style.filter = gradeCss;
            tvpLayoutVideo(topV, topC, faceBox || defaultAspectBox(vidAR, FACE_AR), vidAR);
            tvpLayoutVideo(botV, botC, bgBox, vidAR);
        } else {
            if (topC) topC.style.display = "none";
            if (botC) {
                botC.style.display = "";
                botC.style.left = "0px"; botC.style.top = "0px";
                botC.style.width = px(stageW); botC.style.height = px(stageH);
                stage.appendChild(botC);
            }
            tvpSetVideo(botV, base, t);
            if (botV) botV.style.filter = gradeCss;
            tvpLayoutVideo(botV, botC, faceBox, vidAR);
        }

        // FX + upper layers interleaved strictly by z level (an FX on a track
        // with no active clip still burns at its depth — same as the export):
        // bottom→top = base(z max) → fx(z max) → layer(z-1) → fx(z-1) → …
        const layerByZ = new Map(layers.map(L => [L.z, L]));
        const renderPip = (entry) => {
            const L = entry.clip;
            const pipC = document.createElement("div");
            pipC.className = "tvp-dyn tvp-pip2";
            const pipBox = pipForClip(L);
            const pw = Math.max(0.05, Math.min(0.95, pipBox.w || 0.30)) * stageW;
            const ph = pw * 16 / 9;
            const pos = trackPosAt(L, t);
            let pl, pt;
            if (pos) {
                pl = Math.max(0, Math.min(stageW - pw, pos.x * stageW));
                pt = Math.max(0, Math.min(stageH - ph, pos.y * stageH));
            } else {
                pl = (pipBox.x != null ? pipBox.x : 0.688) * stageW;
                pt = (pipBox.y != null ? pipBox.y : 0.018) * stageH;
                pl = Math.max(0, Math.min(stageW - pw, pl));
                pt = Math.max(0, Math.min(stageH - ph, pt));
            }
            pipC.style.cssText = "position:absolute;left:" + px(pl) + ";top:" + px(pt) + ";width:" + px(pw) + ";height:" + px(ph) + ";overflow:hidden;border:1px solid rgba(255,255,255,0.35);border-radius:8px;box-shadow:0 8px 24px rgba(0,0,0,0.55);background:#000;z-index:5;";
            const vid = document.createElement("video");
            vid.muted = true; vid.playsInline = true; vid.preload = "auto";
            vid.className = "tvp-dyn-video";
            pipC.appendChild(vid);
            stage.appendChild(pipC);
            tvpSetVideo(vid, L, t);
            vid.style.filter = gradeCss;
            // cover-fit the layer video inside its PiP window
            const lar = (L.media.width && L.media.height) ? L.media.width / L.media.height : 16 / 9;
            const css = coverBoxToCss(pw, ph, lar, null);
            vid.style.position = "absolute";
            vid.style.width = px(css.w); vid.style.height = px(css.h);
            vid.style.left = px(css.left); vid.style.top = px(css.top);
            vid.style.maxWidth = "none"; vid.style.maxHeight = "none";
            pipC.style.opacity = String(L.opacity != null ? L.opacity : 1);
        };
        for (let z = layers[0].z; z >= 0; z--) {
            if (z !== layers[0].z) {
                const up = layerByZ.get(z);
                if (up && pipForClip(up.clip)) renderPip(up);
            }
            if (z > textTopZ) appendFxDivs(stage, t, z, stageW, stageH);
        }
        // levels above the topmost track (z = -1 placeholders)
        if (textTopZ < 0) appendFxDivs(stage, t, -1, stageW, stageH);

        // shake: move the whole frame (full video shake feel, as in the export)
        if (shakeEls.length) {
            const off = shakeOffset();
            stage.style.transform = "translate(" + off.dx.toFixed(2) + "px," + off.dy.toFixed(2) + "px)";
        }

        // ── static cinematic frames (рамки сверху/снизу) ──
        const bt = (parseInt(state.clipper.barTop, 10) || 0) / 1920 * stageH;
        const bb = (parseInt(state.clipper.barBottom, 10) || 0) / 1920 * stageH;
        if (bt > 0) {
            const b = document.createElement("div");
            b.className = "tvp-dyn";
            b.style.cssText = "position:absolute;left:0;top:0;width:100%;height:" + bt + "px;background:#000;z-index:14;";
            stage.appendChild(b);
        }
        if (bb > 0) {
            const b = document.createElement("div");
            b.className = "tvp-dyn";
            b.style.cssText = "position:absolute;left:0;bottom:0;width:100%;height:" + bb + "px;background:#000;z-index:14;";
            stage.appendChild(b);
        }

        // ── subtitles & text overlays: same font/glow/anim as the export ──
        if (subsEl) {
            subsEl.innerHTML = "";
            subsEl.className = "tvp-subs";
            // tvpSubs живёт внутри сцены (stage) — координаты относительно сцены.
            // Смещение субтитров ранее давал translateY(-50%) из CSS — убран.
            subsEl.style.left = "0px";
            subsEl.style.width = "100%";
            subsEl.style.height = "100%";
            subsEl.style.position = "absolute";
            subsEl.style.top = "0px";
            subsEl.style.pointerEvents = "none";
            subsEl.style.zIndex = "20";

            // Find all active text clips across all tracks
            const activeTexts = [];
            for (const tid of trackOrder()) {
                const track = getTrack(tid);
                if (!track || track.kind === "audio" || track.hidden) continue;
                for (const c of (state.tracks[tid] || [])) {
                    if (c.isFx || c.media || !c.title) continue;
                    if (t >= c.startTime && t < c.startTime + c.duration) {
                        activeTexts.push(c);
                    }
                }
            }

            if (activeTexts.length > 0) {
                activeTexts.forEach(c => {
                    const isFree = !!c.freeText;
                    let anim = isFree ? (c.textAnimIn || "pop") : (c.textAnimIn || state.clipper.subAnim || "pop");
                    if (c.textShake) anim = "tremble";
                    const fontFam = tvFontCssFamily(c.textFont || state.clipper.subFont);
                    const sizeFrac = isFree && c.textSize ? (c.textSize / 100) : (0.057 * ((c.textSize || 6.0) / 6.0));
                    const sizePx = Math.max(18, stageH * sizeFrac);
                    const d = document.createElement("div");
                    const stId = c.subtitleStyle || state.clipper.subtitleTemplate || "acid";
                    d.className = "subtitle-cue-active sub-style-" + stId + " tvp-sub-anim anim-" + anim;
                    const glow = c.textGlow != null ? c.textGlow : (state.clipper.subGlow != null ? state.clipper.subGlow : 65);
                    d.style.setProperty("--sub-glow", String(glow));
                    d.style.fontFamily = fontFam;
                    d.style.fontSize = Math.round(sizePx) + "px";

                    if (isFree) {
                        d.style.color = c.textColor || "#ffffff";
                        d.style.left = ((c.textX != null ? c.textX : 0.5) * 100) + "%";
                        d.style.top = ((c.textY != null ? c.textY : 0.72) * 100) + "%";
                        d.style.position = "absolute";
                        d.style.transform = "translate(-50%,-50%)";
                        // свободный текст: ширина по содержимому (иначе сжимается
                        // до половины сцены и сворачивается в вертикальный столбик)
                        d.style.width = "max-content";
                        d.style.maxWidth = "92%";
                        if (c.textStroke) d.style.webkitTextStroke = Math.min(6, c.textStroke / 4) + "px #000";
                        if (c.textSpacing) d.style.letterSpacing = (c.textSpacing * sizePx / 100) + "px";
                    } else {
                        d.style.position = "absolute";
                        d.style.left = "50%";
                        const subTop = fmt === "split_adhd" ? (stageH * 0.45 - sizePx * 0.1) : (stageH * 0.62);
                        d.style.top = subTop + "px";
                        d.style.transform = "translate(-50%, -50%)";
                        const isBox = ["hormozi", "clean_editorial", "typewriter_terminal"].includes(stId);
                        d.style.width = isBox ? "auto" : "90%";
                        d.style.maxWidth = "90%";
                        d.style.textAlign = "center";
                        // Non-free clips also honor per-clip color/stroke/spacing/X/Y so inspector edits show up
                        if (c.textColor) d.style.color = c.textColor;
                        if (c.textStroke) d.style.webkitTextStroke = Math.min(6, c.textStroke / 4) + "px #000";
                        if (c.textSpacing) d.style.letterSpacing = (c.textSpacing * sizePx / 100) + "px";
                        if (c.textX != null || c.textY != null) {
                            d.style.left = ((c.textX != null ? c.textX : 0.5) * 100) + "%";
                            d.style.top = ((c.textY != null ? c.textY : 0.72) * 100) + "%";
                        }
                    }

                    const rawWords = (Array.isArray(c.words) && c.words.length) ? c.words : String(c.title).split(" ").map(w => ({ word: w }));
                    const hotOn = c.textHotWords !== false && state.clipper.hotWords !== false && !isFree;
                    const lettersAnim = ["wave", "shimmer", "type", "tremble"].includes(anim);

                    if (stId === "mrbeast") {
                        // MrBeast 3D: dynamic tilt, color cycling across words (Yellow, Cyan, White)
                        const mrColors = ["#ffe600", "#00f2ff", "#ffffff"];
                        rawWords.forEach((wObj, wi) => {
                            const w = (wObj.word || "").trim();
                            if (!w) return;
                            const sp = document.createElement("span");
                            sp.textContent = w;
                            sp.style.color = mrColors[wi % mrColors.length];
                            sp.style.display = "inline-block";
                            sp.style.margin = "0 " + Math.round(sizePx * 0.08) + "px";
                            d.appendChild(sp);
                            if (wi < rawWords.length - 1) {
                                d.appendChild(document.createTextNode(" "));
                            }
                        });
                    } else if (stId === "karaoke_spotlight") {
                        // Spotlight: active word glowing electric cyan with scale pop, other words dimmed silver
                        rawWords.forEach((wObj, wi) => {
                            const w = (wObj.word || "").trim();
                            if (!w) return;
                            const sp = document.createElement("span");
                            sp.textContent = w;
                            const ws = wObj.abs_start !== undefined ? wObj.abs_start : c.startTime;
                            const we = wObj.abs_end !== undefined ? wObj.abs_end : (c.startTime + c.duration);
                            const isActive = (t >= ws && t <= we) || rawWords.length === 1;
                            sp.className = isActive ? "spotlight-active" : "spotlight-muted";
                            sp.style.display = "inline-block";
                            sp.style.margin = "0 " + Math.round(sizePx * 0.08) + "px";
                            d.appendChild(sp);
                            if (wi < rawWords.length - 1) {
                                d.appendChild(document.createTextNode(" "));
                            }
                        });
                    } else if (lettersAnim && String(c.title).length <= 24) {
                        const letters = String(c.title).split("");
                        letters.forEach((ch, i) => {
                            const sp = document.createElement("span");
                            sp.textContent = ch;
                            sp.className = "tvp-letter";
                            sp.style.animationDelay = (i * 0.07) + "s";
                            d.appendChild(sp);
                        });
                    } else if (hotOn && rawWords.length > 1) {
                        rawWords.forEach((wObj, wi) => {
                            const w = (wObj.word || "").trim();
                            if (!w) return;
                            const sp = document.createElement("span");
                            const clean = w.replace(/[^\u0400-\u04FF\w]/g, "");
                            if (clean.length >= 5) sp.className = "tvp-hot";
                            sp.textContent = w;
                            sp.style.display = "inline-block";
                            sp.style.margin = "0 " + Math.round(sizePx * 0.06) + "px";
                            d.appendChild(sp);
                            if (wi < rawWords.length - 1) {
                                d.appendChild(document.createTextNode(" "));
                            }
                        });
                    } else {
                        d.textContent = c.title;
                    }
                    // перетаскивание текста прямо по превью (как в AE):
                    // позиция пишется в клип и попадает в экспорт через \pos
                    makePreviewDraggable(d, c, stage);
                    subsEl.appendChild(d);
                });
                stage.appendChild(subsEl);
            }
        }
        // FX from layers ABOVE the text layer burn over the subtitles
        if (textTopZ >= 0) {
            for (let z = textTopZ; z >= -1; z--) appendFxDivs(stage, t, z, stageW, stageH, true);
        }
        const badgeEl = tvp.querySelector(".tvp-badge");
        if (badgeEl) badgeEl.classList.add("hidden");
    }
    function allFxElements() {
        const out = [];
        const order = trackOrder();
        for (let zi = 0; zi < order.length; zi++) {
            const track = getTrack(order[zi]);
            if (!track || (track.kind !== "video" && track.kind !== "effect" && !isFxTrack(track))) continue;
            for (const c of (state.tracks[order[zi]] || [])) {
                if (!c.isFx) continue;
                out.push(Object.assign({}, c, { z: zi }));
            }
        }
        return out;
    }
    // FX overlays for one z level: flashes (colored div) / squeeze bars (two divs).
    // Bars couple with overlapping shake elements — borders ride the video shake.
    function appendFxDivs(stage, t, z, stageW, stageH, overText) {
        for (const fx of allFxElements()) {
            if (fx.z !== z) continue;
            const s = fx.startTime, e = fx.startTime + fx.duration;
            if (!(t >= s && t < e)) continue;
            const d = e - s;
            const fd = Math.min(d / 2.0, 0.3);
            let a = 0;
            if (t < s + fd) a = (t - s) / fd;
            else if (t > e - fd) a = (e - t) / fd;
            else a = 1;
            if (fx.fxKind === "flash") {
                const peak = fx.fxPeak != null ? fx.fxPeak : 0.75;
                const colors = { white: "#ffffff", green: "#39ff00", red: "#ff2222" };
                const el = document.createElement("div");
                el.className = "tvp-dyn tvp-fx";
                const zi = overText ? 22 : 12;
                if ((fx.fxColor || "white") === "bw") {
                    el.style.cssText = "position:absolute;inset:0;z-index:" + zi + ";backdrop-filter:grayscale(1);-webkit-backdrop-filter:grayscale(1);opacity:" + (a * peak).toFixed(3) + ";";
                } else {
                    el.style.cssText = "position:absolute;inset:0;z-index:" + zi + ";background:" + (colors[fx.fxColor] || "#fff") + ";opacity:" + (a * peak).toFixed(3) + ";";
                }
                stage.appendChild(el);
            } else if (fx.fxKind === "bars") {
                const bhPx = (fx.fxBarH || 120) / 1920 * stageH;
                const prog = Math.max(0, Math.min(1, Math.min(t - s, e - t) / 0.35));
                let shAmp = 0, shF = 7;
                for (const sx of allFxElements()) {
                    if (sx.fxKind !== "shake") continue;
                    const ss = sx.startTime, se = sx.startTime + sx.duration;
                    if (ss < e && se > s) { shAmp = Math.max(shAmp, sx.fxAmp || 12); shF = sx.fxFreq || 7; }
                }
                const sh = shAmp ? (shAmp / 1080 * stageW) * Math.cos(2 * Math.PI * (shF * 9 / 7) * t) : 0;
                const top = document.createElement("div");
                top.className = "tvp-dyn tvp-fx";
                top.style.cssText = "position:absolute;left:0;top:" + (-bhPx + bhPx * prog + sh).toFixed(2) + "px;width:100%;height:" + bhPx.toFixed(1) + "px;background:#000;z-index:" + (overText ? 23 : 13) + ";";
                const bot = document.createElement("div");
                bot.className = "tvp-dyn tvp-fx";
                bot.style.cssText = "position:absolute;left:0;bottom:" + (-bhPx + bhPx * prog + sh).toFixed(2) + "px;width:100%;height:" + bhPx.toFixed(1) + "px;background:#000;z-index:" + (overText ? 23 : 13) + ";";
                stage.appendChild(top); stage.appendChild(bot);
            }
        }
    }
    function tvFontCssFamily(f) {
        const known = [
            "Anton", "Bebas Neue", "Russo One", "Oswald", "Oswald SemiBold", "Oswald Bold",
            "Montserrat", "Montserrat ExtraBold", "Unbounded", "Unbounded ExtraBold",
            "Lobster", "Rubik Mono One", "Play", "Press Start 2P", "Dela Gothic One",
            "Prosto One", "Pacifico", "Marck Script", "Amatic SC", "Yeseva One",
            "M PLUS Rounded 1c", "Fira Sans Extra Bold", "Caveat Bold", "Exo 2 Black",
            "Sofia Sans Extra Condensed Black", "Rubik Black", "Nunito Black",
            "Golos Text Black", "Yanone Kaffeesatz Bold", "Alumni Sans Black",
            "Onest Black", "Wix Madefor Display ExtraBold"
        ];
        return (known.includes(f) ? "'" + f + "'" : "'Russo One'") + ", 'Arial Black', sans-serif";
    }

    function selectClipperSource(filename) {
        // Источник нарезок — файл из библиотеки/таймлайна (без дропдауна в панели Shorts)
        state.clipper.sourceFile = filename;
    }

    function updateBadgeOverlay() {
        // Бейджи платформ убраны из интерфейса — всегда скрыт
        if (!badgeMonitorOverlay) return;
        badgeMonitorOverlay.classList.add("hidden");
    }

    function updateClipperUI() {
        // фон отдельным файлом больше не используется в TV-шаблонах (нижняя половина — область фона)
        const bgSection = document.getElementById("clipperBgSection");
        if (bgSection) bgSection.style.display = "none";
    }
    function initSubSettings() {
        const root = document.getElementById("tabContentClipper");
        if (root && root.dataset.subBound === "1") { reflectSubSettings(); return; }
        if (root) root.dataset.subBound = "1";
        const fontSel = document.getElementById("subFontSelect");
        const animSel = document.getElementById("subAnimSelect");
        const sizeSlider = document.getElementById("subSizeSlider");
        const sizeVal = document.getElementById("subSizeVal");
        const glowSlider = document.getElementById("subGlowSlider");
        const glowVal = document.getElementById("subGlowVal");
        const barTopSlider = document.getElementById("barTopSlider");
        const barBottomSlider = document.getElementById("barBottomSlider");
        const hotWordsCheck = document.getElementById("hotWordsCheck");
        const srcProcCheck = document.getElementById("srcProcessedCheck");
        const wordsSel = document.getElementById("wordsPerCueSelect");
        const langSel = document.getElementById("subLangSelect");
        const sepCheck = document.getElementById("exportSeparateCheck");
        const syncAll = () => {
            if (fontSel) state.clipper.subFont = fontSel.value;
            if (animSel) state.clipper.subAnim = animSel.value;
            if (sizeSlider) {
                state.clipper.subSize = (parseInt(sizeSlider.value, 10) || 100) / 100;
                if (sizeVal) sizeVal.textContent = `${sizeSlider.value}%`;
            }
            if (glowSlider) {
                state.clipper.subGlow = parseInt(glowSlider.value, 10) || 0;
                if (glowVal) glowVal.textContent = `${glowSlider.value}`;
            }
            if (barTopSlider) {
                state.clipper.barTop = parseInt(barTopSlider.value, 10) || 0;
                const v = document.getElementById("barTopVal");
                if (v) v.textContent = `${state.clipper.barTop}px`;
            }
            if (barBottomSlider) {
                state.clipper.barBottom = parseInt(barBottomSlider.value, 10) || 0;
                const v = document.getElementById("barBottomVal");
                if (v) v.textContent = `${state.clipper.barBottom}px`;
            }
            if (hotWordsCheck) state.clipper.hotWords = !!hotWordsCheck.checked;
            if (srcProcCheck) state.clipper.srcProcessed = !!srcProcCheck.checked;
            if (wordsSel) state.clipper.wordsPerCue = parseInt(wordsSel.value, 10) || 3;
            if (langSel) state.clipper.subLang = langSel.value;
            if (sepCheck) state.clipper.exportSeparate = !!sepCheck.checked;
            updateLiveSubtitleOverlay();
            updateTvPreview();
            saveProject();
        };
        [fontSel, animSel, wordsSel, langSel, sepCheck, hotWordsCheck, srcProcCheck].forEach(el => {
            if (el) el.addEventListener("change", syncAll);
        });
        [sizeSlider, glowSlider, barTopSlider, barBottomSlider].forEach(el => {
            if (el) el.addEventListener("input", syncAll);
        });
        reflectSubSettings();
    }
    function reflectSubSettings() {
        const fontSel = document.getElementById("subFontSelect");
        const animSel = document.getElementById("subAnimSelect");
        const sizeSlider = document.getElementById("subSizeSlider");
        const sizeVal = document.getElementById("subSizeVal");
        const glowSlider = document.getElementById("subGlowSlider");
        const glowVal = document.getElementById("subGlowVal");
        const hotWordsCheck = document.getElementById("hotWordsCheck");
        const srcProcCheck = document.getElementById("srcProcessedCheck");
        const barTopSlider = document.getElementById("barTopSlider");
        const barBottomSlider = document.getElementById("barBottomSlider");
        const wordsSel = document.getElementById("wordsPerCueSelect");
        const langSel = document.getElementById("subLangSelect");
        const sepCheck = document.getElementById("exportSeparateCheck");
        // reflect state on load
        if (fontSel) fontSel.value = TV_FONT_OK(state.clipper.subFont) ? state.clipper.subFont : "Russo One";
        if (animSel) animSel.value = state.clipper.subAnim || "pop";
        if (sizeSlider) {
            sizeSlider.value = Math.round((state.clipper.subSize || 1) * 100);
            if (sizeVal) sizeVal.textContent = `${sizeSlider.value}%`;
        }
        if (glowSlider) {
            glowSlider.value = state.clipper.subGlow != null ? state.clipper.subGlow : 55;
            if (glowVal) glowVal.textContent = `${glowSlider.value}`;
        }
        if (barTopSlider) {
            barTopSlider.value = parseInt(state.clipper.barTop, 10) || 0;
            const v = document.getElementById("barTopVal");
            if (v) v.textContent = `${barTopSlider.value}px`;
        }
        if (barBottomSlider) {
            barBottomSlider.value = parseInt(state.clipper.barBottom, 10) || 0;
            const v = document.getElementById("barBottomVal");
            if (v) v.textContent = `${barBottomSlider.value}px`;
        }
        if (hotWordsCheck) hotWordsCheck.checked = state.clipper.hotWords === true;
        if (srcProcCheck) srcProcCheck.checked = !!state.clipper.srcProcessed;
        if (wordsSel) wordsSel.value = String(state.clipper.wordsPerCue || 3);
        if (langSel) langSel.value = state.clipper.subLang || "ru";
        if (sepCheck) sepCheck.checked = !!state.clipper.exportSeparate;
    }

    function renderSubtitlesCues(segments) {
        const container = document.getElementById("subtitlesCuesContainer");
        const cuesList = document.getElementById("cuesList");
        const cuesCountLabel = document.getElementById("cuesCountLabel");

        if (!container || !cuesList) return;
        container.classList.remove("hidden");
        cuesList.innerHTML = "";
        if (cuesCountLabel) cuesCountLabel.textContent = `Распознано: ${segments.length} сегментов`;

        segments.forEach(seg => {
            const item = document.createElement("div");
            item.className = "cue-item";

            const timeSpan = document.createElement("span");
            timeSpan.className = "cue-time";
            timeSpan.textContent = `[${formatDurationShort(seg.abs_start)} - ${formatDurationShort(seg.abs_end)}]`;

            const textSpan = document.createElement("span");
            textSpan.className = "cue-text";
            textSpan.textContent = seg.text;

            item.appendChild(timeSpan);
            item.appendChild(textSpan);

            item.addEventListener("click", () => {
                seekTo(seg.abs_start);
            });

            cuesList.appendChild(item);
        });
    }

    function isHotWord(w) {
        const clean = (w || "").replace(/[^A-Za-zА-Яа-яЁё0-9]/g, "");
        // сервер считает hot-word слово из ≥5 символов (server.py _is_hot_word) — держим порог тем же
        return clean.length >= 5;
    }
    // Live Subtitles Monitor Overlay: prefers timeline text-track clips, falls back to clipper cues
    function updateLiveSubtitleOverlay() {
        if (!subtitlesMonitorOverlay) return;
        // TV composite preview renders subtitles itself — keep the raw overlay empty
        if ((typeof tvPreviewWanted === "function" && tvPreviewWanted()) ||
            (window.__canvasMonitor && window.__canvasMonitor.enabled())) {
            subtitlesMonitorOverlay.innerHTML = "";
            return;
        }
        const currentSec = state.currentTime;
        // hide only when the text layer that owns the cue is hidden
        const cue = currentCueClip();
        if (cue && cue.clip) {
            const tr = getTrack(cue.clip.trackId);
            if (tr && tr.hidden) { subtitlesMonitorOverlay.innerHTML = ""; return; }
        }
        let template = state.clipper.subtitleTemplate || "acid";
        let text = null, words = null, activeSubClip = null;
        if (cue) {
            template = cue.template || template;
            text = cue.text;
            activeSubClip = cue.clip || null;
            words = (cue.clip && Array.isArray(cue.clip.words)) ? cue.clip.words : null;
        } else {
            const cues = state.clipper.subtitles || [];
            const activeCue = cues.find(c => currentSec >= c.abs_start && currentSec <= c.abs_end);
            if (!activeCue) { subtitlesMonitorOverlay.innerHTML = ""; return; }
            text = activeCue.text; words = activeCue.words;
        }
        if (!text) { subtitlesMonitorOverlay.innerHTML = ""; return; }

        const anim = state.clipper.subAnim || "pop";
        const wrapper = document.createElement("div");
        wrapper.className = `subtitle-cue-active sub-style-${template} anim-${anim}`;
        wrapper.style.fontFamily = tvFontCssFamily(activeSubClip && activeSubClip.textFont ? activeSubClip.textFont : state.clipper.subFont);
        // Per-clip params with global fallbacks, so inspector edits are always visible here
        const glow = (activeSubClip && activeSubClip.textGlow != null) ? activeSubClip.textGlow
            : (state.clipper.subGlow != null ? state.clipper.subGlow : 55);
        wrapper.style.setProperty("--sub-glow", String(glow));
        let ovlSizePx = 0;
        if (activeSubClip && activeSubClip.textSize) {
            // % of the monitor height (container-query units need a container — use px)
            const mh = videoMonitor ? videoMonitor.clientHeight : 600;
            ovlSizePx = Math.max(14, Math.round(mh * activeSubClip.textSize / 100));
            wrapper.style.fontSize = `${ovlSizePx}px`;
        }
        if (activeSubClip && activeSubClip.textColor) wrapper.style.color = activeSubClip.textColor;
        if (activeSubClip && activeSubClip.textStroke) wrapper.style.webkitTextStroke = Math.min(6, activeSubClip.textStroke / 4) + "px #000";
        if (activeSubClip && activeSubClip.textSpacing && ovlSizePx) wrapper.style.letterSpacing = (activeSubClip.textSpacing * ovlSizePx / 100) + "px";

        const isBox = ["hormozi", "clean_editorial", "typewriter_terminal"].includes(template);
        if (isBox) {
            wrapper.style.width = "auto";
            wrapper.style.maxWidth = "90%";
        }

        const rawWords = (Array.isArray(words) && words.length) ? words : String(text).split(/\s+/).filter(Boolean).map(w => ({ word: w }));
        const hotOn = state.clipper.hotWords !== false && (!activeSubClip || !activeSubClip.freeText);
        const lettersAnim = ["wave", "shimmer", "type", "tremble"].includes(anim);

        if (template === "mrbeast") {
            const mrColors = ["#ffe600", "#00f2ff", "#ffffff"];
            rawWords.forEach((wObj, wi) => {
                const w = (wObj.word || "").trim();
                if (!w) return;
                const sp = document.createElement("span");
                sp.textContent = w;
                sp.style.color = mrColors[wi % mrColors.length];
                sp.style.display = "inline-block";
                sp.style.margin = "0 4px";
                wrapper.appendChild(sp);
                if (wi < rawWords.length - 1) wrapper.appendChild(document.createTextNode(" "));
            });
        } else if (template === "karaoke_spotlight" || template === "karaoke") {
            rawWords.forEach((wObj, wi) => {
                const w = (wObj.word || "").trim();
                if (!w) return;
                const sp = document.createElement("span");
                sp.textContent = w;
                const ws = wObj.abs_start !== undefined ? wObj.abs_start : 0;
                const we = wObj.abs_end !== undefined ? wObj.abs_end : 999999;
                const isActive = (currentSec >= ws && currentSec <= we) || rawWords.length === 1;
                sp.className = isActive ? "spotlight-active" : "spotlight-muted";
                sp.style.display = "inline-block";
                sp.style.margin = "0 4px";
                wrapper.appendChild(sp);
                if (wi < rawWords.length - 1) wrapper.appendChild(document.createTextNode(" "));
            });
        } else if (lettersAnim && String(text).length <= 24) {
            const letters = String(text).split("");
            letters.forEach((ch, i) => {
                const sp = document.createElement("span");
                sp.textContent = ch;
                sp.className = "tvp-letter";
                sp.style.animationDelay = `${i * 0.07}s`;
                wrapper.appendChild(sp);
            });
        } else if (hotOn && rawWords.length > 1) {
            rawWords.forEach((wObj, wi) => {
                const w = (wObj.word || "").trim();
                if (!w) return;
                const sp = document.createElement("span");
                const clean = w.replace(/[^\u0400-\u04FF\w]/g, "");
                if (clean.length >= 5) sp.className = "tvp-hot";
                sp.textContent = w;
                sp.style.display = "inline-block";
                sp.style.margin = "0 3px";
                wrapper.appendChild(sp);
                if (wi < rawWords.length - 1) wrapper.appendChild(document.createTextNode(" "));
            });
        } else {
            wrapper.textContent = text;
        }

        // Free text: honor its own position on the monitor
        if (activeSubClip && activeSubClip.freeText) {
            wrapper.style.position = "absolute";
            wrapper.style.left = `${(activeSubClip.textX != null ? activeSubClip.textX : 0.5) * 100}%`;
            wrapper.style.top = `${(activeSubClip.textY != null ? activeSubClip.textY : 0.72) * 100}%`;
            wrapper.style.transform = "translate(-50%, -50%)";
        } else if (activeSubClip && (activeSubClip.textX != null || activeSubClip.textY != null)) {
            // Subtitle cues with explicitly moved X/Y also follow the inspector sliders
            wrapper.style.position = "absolute";
            wrapper.style.left = `${(activeSubClip.textX != null ? activeSubClip.textX : 0.5) * 100}%`;
            wrapper.style.top = `${(activeSubClip.textY != null ? activeSubClip.textY : 0.72) * 100}%`;
            wrapper.style.transform = "translate(-50%, -50%)";
        } else if (activeSubClip && activeSubClip.trackPath && activeSubClip.trackPath.length) {
            const pos = trackPosAt(activeSubClip, currentSec);
            if (pos) {
                wrapper.style.position = "absolute";
                wrapper.style.left = `${Math.max(0, Math.min(100, pos.x * 100))}%`;
                wrapper.style.top = `${Math.max(0, Math.min(100, pos.y * 100))}%`;
                wrapper.style.transform = "translate(-50%, -50%)";
            }
        } else {
            wrapper.style.position = "";
            wrapper.style.left = "";
            wrapper.style.top = "";
            wrapper.style.transform = "";
        }

        subtitlesMonitorOverlay.innerHTML = "";
        subtitlesMonitorOverlay.appendChild(wrapper);
    }

    // Apply generated subtitles as timeline clips on the text track
    // Переразбить последнюю транскрибацию на слой титров (с текущими настройками)
    function applySubtitlesToTrackV3() {
        const last = state._lastTranscribe;
        if (!last || !last.words || !last.words.length) {
            showToast("Сначала сгенерируйте субтитры для выбранной нарезки.", "info");
            return;
        }
        const tidText = textTrackId();
        if (tidText && last.tg) {
            const batch = "w_" + last.batchId;
            state.tracks[tidText] = (state.tracks[tidText] || []).filter(c => c.batch !== batch);
        }
        const made = wordsToTimelineClips(last.words, last.tg, last.batchId);
        recalcTotalDuration();
        renderTimeline();
        renderCutsTree();
        saveProject();
        showToast(`На слой титров добавлено фрагментов: ${made} (слов на фрагмент: ${state.clipper.wordsPerCue}).`, "ok");
    }

    // ── Cutting Templates Library (save once, apply to any video) ──
    // Встроенные шаблоны = разные ВИДЫ нарезок. TV-шаблоны (первые два) повторяют
    // референсы: AE-цветокор, фирменные субтитры, сплит и белые вспышки на склейках.
    const BUILTIN_TEMPLATES = [
        {
            id: "builtin_tv_split", builtin: true,
            name: "TV Сплит 45/55 · цветокор + вспышки",
            format: "split_adhd", crop_preset: "top_right",
            platform: "KICK", streamer_handle: "@tv",
            subtitle_template: "lime", color_grade: "tv", flash_cuts: true, noBg: false
        },
        {
            id: "builtin_tv_full", builtin: true,
            name: "TV Full 9:16 · цветокор + вспышки",
            format: "talking_head_9_16", crop_preset: "center",
            platform: "KICK", streamer_handle: "@tv",
            subtitle_template: "acid", color_grade: "tv", flash_cuts: true, noBg: true
        },
        {
            id: "builtin_split_adhd", builtin: true,
            name: "Сплит 50/50 (example.mp4)",
            format: "split_adhd", crop_preset: "top_right",
            platform: "TWITCH", streamer_handle: "@jesusavgn",
            subtitle_template: "meme", noBg: false
        },
        {
            id: "builtin_talking_head", builtin: true,
            name: "Стрим вертикально 9:16",
            format: "talking_head_9_16", crop_preset: "center",
            platform: "KICK", streamer_handle: "@streamer",
            subtitle_template: "karaoke", noBg: true
        },
        {
            id: "builtin_cinematic", builtin: true,
            name: "YouTube 16:9 широкий",
            format: "cinematic_16_9", crop_preset: "center",
            platform: "YOUTUBE", streamer_handle: "@streamer",
            subtitle_template: "news", noBg: true
        },
        {
            // Тип нарезки для съёмок с камеры телефона (горизонт 1920x1080 ~25fps,
            // как 3 последних видео из галереи) — вертикальный кроп из центра кадра
            id: "builtin_phone_vertical", builtin: true,
            name: "Камера телефона → 9:16 центр",
            format: "talking_head_9_16", crop_preset: "center",
            platform: "YOUTUBE", streamer_handle: "@shorts",
            subtitle_template: "accent", noBg: true
        },
        {
            // Горизонтальное видео с камеры без кропа — как снято
            id: "builtin_phone_native", builtin: true,
            name: "Камера телефона 16:9 как есть",
            format: "cinematic_16_9", crop_preset: "center",
            platform: "YOUTUBE", streamer_handle: "@shorts",
            subtitle_template: "clean", noBg: true
        },
        {
            // Крупный план лица из кадра камеры телефона (вебка-стиль)
            id: "builtin_phone_face", builtin: true,
            name: "Камера телефона крупный план",
            format: "talking_head_9_16", crop_preset: "face",
            platform: "TWITCH", streamer_handle: "@clip",
            subtitle_template: "meme", noBg: true
        }
    ];
    const TEMPLATE_KEY = "kick_studio_templates_v1";
    function loadTemplates() {
        let custom = [];
        try { custom = JSON.parse(localStorage.getItem(TEMPLATE_KEY) || "[]"); }
        catch (e) { custom = []; }
        return [...BUILTIN_TEMPLATES, ...custom];
    }
    function storeTemplates(list) {
        try { localStorage.setItem(TEMPLATE_KEY, JSON.stringify(list.filter(t => !t.builtin))); } catch (e) {}
    }
    function currentSettingsAsTemplate(name) {
        return {
            id: "tpl_" + Date.now().toString(36),
            name: name || `Шаблон ${loadTemplates().length + 1}`,
            format: state.clipper.format,
            crop_preset: state.clipper.cropPreset,
            platform: state.clipper.platform,
            streamer_handle: state.clipper.streamerHandle,
            subtitle_template: state.clipper.subtitleTemplate,
            sub_font: state.clipper.subFont || "Anton",
            sub_size: state.clipper.subSize || 1.0,
            sub_glow: state.clipper.subGlow != null ? state.clipper.subGlow : 45,
            sub_anim: state.clipper.subAnim || "pop",
            words_per_cue: state.clipper.wordsPerCue || 3,
            color_grade: state.clipper.colorGrade || "none",
            flash_cuts: !!state.clipper.flashCuts,
            crop_box: state.clipper.cropBox || null,
            bg_box: state.clipper.bgBox || null,
            noBg: !!state.clipper.noBg
        };
    }
    function applyTemplateToClipper(tpl) {
        if (!tpl) return;
        state.clipper.format = tpl.format || "split_adhd";
        state.clipper.cropPreset = tpl.crop_preset || "top_right";
        state.clipper.platform = tpl.platform || "TWITCH";
        state.clipper.streamerHandle = tpl.streamer_handle || "@streamer";
        state.clipper.subtitleTemplate = tpl.subtitle_template || "meme";
        state.clipper.subFont = tpl.sub_font || "Anton";
        state.clipper.subSize = tpl.sub_size || 1.0;
        state.clipper.subGlow = tpl.sub_glow != null ? tpl.sub_glow : 45;
        state.clipper.subAnim = tpl.sub_anim || "pop";
        if (tpl.words_per_cue) state.clipper.wordsPerCue = tpl.words_per_cue;
        state.clipper.colorGrade = tpl.color_grade || "none";
        state.clipper.flashCuts = !!tpl.flash_cuts;
        // шаблон задаёт область вебки, только если она в нём сохранена;
        // иначе оставляем нарисованную пользователем (она зависит от раскладки стрима)
        if (tpl.crop_box) state.clipper.cropBox = tpl.crop_box;
        if (tpl.bg_box) state.clipper.bgBox = tpl.bg_box;
        state.clipper.noBg = !!tpl.noBg;
        state.clipper.templateName = tpl.name || null;
        updateCropBoxUI();
        reflectSubSettings();
        // Sync UI actives
        document.querySelectorAll(".format-card").forEach(c => c.classList.toggle("active", c.dataset.format === state.clipper.format));
        document.querySelectorAll(".crop-btn").forEach(b => b.classList.toggle("active", b.dataset.crop === state.clipper.cropPreset));
        document.querySelectorAll(".plat-btn").forEach(b => b.classList.toggle("active", b.dataset.platform === state.clipper.platform));
        document.querySelectorAll(".style-card").forEach(c => c.classList.toggle("active", c.dataset.style === state.clipper.subtitleTemplate));
        document.querySelectorAll("#inspectorSubtitleSection .mini-style-btn, #inspectorTranscribeSection .mini-style-btn, #regionInspector .mini-style-btn").forEach(b => {
            b.classList.toggle("active", b.dataset.style === state.clipper.subtitleTemplate);
        });
        document.querySelectorAll(".grade-btn").forEach(b => b.classList.toggle("active", b.dataset.grade === (state.clipper.colorGrade || "none")));
        document.querySelectorAll(".flash-btn").forEach(b => b.classList.toggle("active", (b.dataset.flash === "on") === !!state.clipper.flashCuts));
        const hi = document.getElementById("clipperHandleInput");
        if (hi) hi.value = state.clipper.streamerHandle;
        updateClipperUI();
        applyPreviewLook();
        updateBadgeOverlay();
        updateLiveSubtitleOverlay();
        updateTvPreview();
        renderTemplates();
    }
    // Живое превью цветокора на мониторе (экспорт рендерит полный град)
    function applyPreviewLook() {
        if (!videoMonitor) return;
        if (state.clipper.colorGrade === "tv") {
            // приближение нового TV-града: панч, сочность, тёплые света
            videoMonitor.style.filter = "brightness(1.04) contrast(1.22) saturate(1.6)";
        } else {
            videoMonitor.style.filter = "";
        }
    }
    function formatHuman(f) {
        if (f === "split_adhd") return "Сплит 50/50";
        if (f === "talking_head_9_16") return "9:16";
        if (f === "cinematic_16_9") return "16:9";
        return f;
    }
    function renderTemplates() {
        const listEl = document.getElementById("templateList");
        if (!listEl) return;
        const templates = loadTemplates();
        listEl.innerHTML = "";
        templates.forEach(tpl => {
            const row = document.createElement("div");
            row.className = "template-row" + (state.clipper.templateName === tpl.name ? " active" : "");
            const name = document.createElement("span");
            name.className = "template-row-name";
            name.textContent = (tpl.builtin ? "★ " : "") + tpl.name;
            name.title = `${formatHuman(tpl.format)} · ${tpl.crop_preset} · ${tpl.platform} · ${tpl.subtitle_template}`;
            const meta = document.createElement("span");
            meta.className = "template-row-meta";
            const flags = [];
            if (tpl.color_grade === "tv") flags.push("TV");
            if (tpl.flash_cuts) flags.push("вспышки");
            meta.textContent = `${formatHuman(tpl.format)} · ${tpl.subtitle_template}` + (flags.length ? ` · ${flags.join(" · ")}` : "");
            const applyBtn = document.createElement("button");
            applyBtn.className = "mini-action-btn";
            applyBtn.textContent = "Применить";
            applyBtn.addEventListener("click", () => applyTemplateToClipper(tpl));
            const left = document.createElement("div");
            left.className = "template-row-left";
            left.appendChild(name);
            left.appendChild(meta);
            row.appendChild(left);
            row.appendChild(applyBtn);
            if (!tpl.builtin) {
                const delBtn = document.createElement("button");
                delBtn.className = "pack-clip-del";
                delBtn.textContent = "✕";
                delBtn.title = "Удалить шаблон";
                delBtn.addEventListener("click", () => {
                    storeTemplates(loadTemplates().filter(t => t.id !== tpl.id));
                    renderTemplates();
                });
                row.appendChild(delBtn);
            }
            listEl.appendChild(row);
        });
    }
    function initTemplates() {
        renderTemplates();
        const saveBtn = document.getElementById("saveTemplateBtn");
        const nameInput = document.getElementById("templateNameInput");
        if (saveBtn) saveBtn.addEventListener("click", () => {
            const name = (nameInput && nameInput.value.trim()) || `Шаблон ${loadTemplates().length + 1}`;
            const list = loadTemplates();
            const existing = list.findIndex(t => t.name === name && !t.builtin);
            const tpl = currentSettingsAsTemplate(name);
            if (existing >= 0) list[existing] = { ...tpl, id: list[existing].id };
            else list.push(tpl);
            storeTemplates(list);
            state.clipper.templateName = name;
            if (nameInput) nameInput.value = "";
            renderTemplates();
        });
    }
    // Render Batch Pack Clips
    // ── Regions list (= очередь экспорта): то же, что полосы на таймлайне ──
    function renderRegionsList() {
        renderPackClips();
    }
    function renderPackClips() {
        const packList = document.getElementById("packClipsList");
        const emptyHint = document.getElementById("packEmptyHint");
        const exportBtn = document.getElementById("exportPackBtn");

        if (!packList) return;
        packList.innerHTML = "";

        const regs = sortedRegions();
        if (regs.length === 0) {
            if (emptyHint) packList.appendChild(emptyHint);
            if (exportBtn) exportBtn.disabled = true;
            updateRegionToolbarUI();
            return;
        }

        if (exportBtn) exportBtn.disabled = false;

        regs.forEach((r, idx) => {
            const card = document.createElement("div");
            card.className = "pack-clip-card" + (r.id === state.selectedRegionId ? " selected" : "");

            const info = document.createElement("div");
            const title = document.createElement("div");
            title.className = "pack-clip-title";
            title.textContent = `${idx + 1} · ${r.name}`;

            const meta = document.createElement("div");
            meta.className = "pack-clip-meta";
            const srcClip = resolvePackSource(r.startTime);
            const srcShort = srcClip && srcClip.media ? String(srcClip.media.filename).split(/[/\\]/).pop() : "—";
            meta.textContent = `${srcShort} · ${formatDurationShort(r.startTime)} → ${formatDurationShort(r.startTime + r.duration)} (${r.duration.toFixed(1)}с) → отдельный файл`;

            info.appendChild(title);
            info.appendChild(meta);

            card.style.cursor = "pointer";
            card.title = "Клик — выбрать и перейти к нарезке";
            card.addEventListener("click", (ev) => {
                if (ev.target.closest("button")) return;
                selectRegion(r.id);
                seekTo(r.startTime);
            });
            const btnWrap = document.createElement("div");
            btnWrap.className = "pack-clip-actions";
            const delBtn = document.createElement("button");
            delBtn.className = "pack-clip-del";
            delBtn.textContent = "✕";
            delBtn.title = "Удалить нарезку";
            delBtn.addEventListener("click", () => {
                state.regions = (state.regions || []).filter(x => x.id !== r.id);
                if (state.selectedRegionId === r.id) state.selectedRegionId = null;
                renderRegionsLane();
                renderRegionsList();
                updateRegionToolbarUI();
                saveProject();
            });
            btnWrap.appendChild(delBtn);

            card.appendChild(info);
            card.appendChild(btnWrap);
            packList.appendChild(card);
        });
        updateRegionToolbarUI();
    }

    function renderReadyClips(clips) {
        const readyGrid = document.getElementById("readyClipsGrid");
        if (!readyGrid) return;
        readyGrid.innerHTML = "";

        clips.forEach(clip => {
            const row = document.createElement("div");
            row.className = "ready-clip-item";

            const name = document.createElement("span");
            name.className = "ready-clip-name";
            name.textContent = `${clip.filename} (${clip.size_formatted})`;

            const path = document.createElement("div");
            path.className = "ready-clip-path";
            path.textContent = clip.path || "";
            path.title = "Полный путь к файлу — клик: скопировать";
            path.addEventListener("click", async () => {
                try {
                    await navigator.clipboard.writeText(clip.path || clip.filename);
                    path.title = "Скопировано!";
                    setTimeout(() => { path.title = "Полный путь к файлу — клик: скопировать"; }, 1500);
                } catch (e) {}
            });

            const actions = document.createElement("div");
            actions.className = "ready-clip-actions";

            const playBtn = document.createElement("button");
            playBtn.className = "mini-action-btn";
            playBtn.textContent = "Смотреть";
            playBtn.addEventListener("click", () => {
                if (videoEl) {
                    // Просто стримим результат, не ломая текущий аспект/раскладку монитора
                    videoEl.src = clip.stream_url;
                    videoEl.play().catch(() => {});
                }
            });

            const link = document.createElement("a");
            link.className = "mini-action-btn";
            link.href = clip.download_url;
            link.download = clip.filename;
            link.textContent = "Скачать";

            const folderBtn = document.createElement("button");
            folderBtn.className = "mini-action-btn";
            folderBtn.textContent = "Папка";
            folderBtn.title = "Открыть папку экспортов в Проводнике";
            folderBtn.addEventListener("click", async () => {
                try {
                    // экспорты лежат в downloads/exported_packs — открываем именно её
                    await fetch("/api/open-folder", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ sub: "exported_packs" })
                    });
                } catch (e) {}
            });

            actions.appendChild(playBtn);
            actions.appendChild(link);
            actions.appendChild(folderBtn);

            row.appendChild(name);
            row.appendChild(path);
            row.appendChild(actions);
            readyGrid.appendChild(row);
        });
    }

    // ── Layers panel buttons: add tracks / text / FX ──
    function initCutsTree() {
        const addVideoBtn = document.getElementById("addVideoTrackBtn");
        const addAudioBtn = document.getElementById("addAudioTrackBtn");
        const addTextBtn = document.getElementById("addTextClipBtn");
        const addFxBtn = document.getElementById("addFxBtn");
        const addFxTrackBtn = document.getElementById("addFxTrackBtn");
        const addTextTrackBtn = document.getElementById("addTextTrackBtn");
        if (addVideoBtn) addVideoBtn.addEventListener("click", () => addTrack("video"));
        if (addAudioBtn) addAudioBtn.addEventListener("click", () => addTrack("audio"));
        if (addTextBtn) addTextBtn.addEventListener("click", addTextClip);
        if (addTextTrackBtn) addTextTrackBtn.addEventListener("click", () => addTrack("text"));
        if (addFxBtn) addFxBtn.addEventListener("click", () => addFxClip("flash", "white"));
        if (addFxTrackBtn) addFxTrackBtn.addEventListener("click", addFxTrack);
        // studio:stickers - hidden file input + button wiring (added dynamically if missing)
        (function(){
            let inp = document.getElementById("stickerFileInput");
            if (!inp) {
                inp = document.createElement("input");
                inp.type = "file"; inp.id = "stickerFileInput";
                inp.accept = "image/png,image/jpeg,image/webp,image/gif";
                inp.style.display = "none";
                document.body.appendChild(inp);
                inp.addEventListener("change", function(){ if (inp.files && inp.files[0]) addStickerClip(inp.files[0]); inp.value = ""; });
            }
            let btn = document.getElementById("addStickerBtn");
            if (!btn) {
                const bar = document.querySelector(".layers-add-btns") || document.getElementById("trackHeadersList");
                if (bar) {
                    btn = document.createElement("button");
                    btn.className = "layer-add-btn"; btn.id = "addStickerBtn";
                    btn.title = "Добавить стикер-картинку (PNG/WebP) на таймлайн";
                    btn.textContent = "+Стикер";
                    btn.addEventListener("click", function(){ inp.click(); });
                    // insert after +Текст
                    const ref = document.getElementById("addTextClipBtn");
                    if (ref && ref.parentElement === bar) ref.insertAdjacentElement("afterend", btn);
                    else bar.appendChild(btn);
                }
            }
        })();
    }
    // ── FX clips (вспышки / сужение границ / тряска): элементы на видеослоях ──
    const FX_DEFAULT_SOUND = { white: "camera_click", green: "approve", red: "cancel", bw: "whoosh_fast" };
    const FX_LABEL = {
        flash_white: "Вспышка белая", flash_green: "Вспышка зелёная",
        flash_red: "Вспышка красная", flash_bw: "Вспышка ч/б",
        bars: "Сужение границ", shake: "Тряска"
    };
    function fxLabel(c) {
        if (!c || !c.isFx) return "";
        if (c.fxKind === "flash") return FX_LABEL["flash_" + (c.fxColor || "white")] || "⚡ Вспышка";
        return FX_LABEL[c.fxKind] || "FX";
    }
    function isFxTrack(t) {
        return t && t.kind === "video" && /fx|эффект/i.test(t.name || "");
    }
    function ensureFxTrack() {
        ensureTracksInitialized();
        let fx = state.trackList.find(isFxTrack);
        if (!fx) {
            fx = {
                id: "tfx" + Date.now().toString(36),
                kind: "video", name: "Эффекты",
                hidden: false, locked: false, muted: true
            };
            // новый слой эффектов появляется НАД верхним слоем текста
            let idx = state.trackList.findIndex(t => t.kind === "text");
            if (idx < 0) idx = 0;
            state.trackList.splice(idx, 0, fx);
            state.tracks[fx.id] = [];
            renderTracksDOM();
        }
        return fx.id;
    }
    // отдельный слой эффектов над текстом (кнопка "+Слой FX")
    function addFxTrack() {
        ensureTracksInitialized();
        const n = state.trackList.filter(isFxTrack).length + 1;
        const tr = {
            id: "tfx" + Date.now().toString(36) + Math.random().toString(36).slice(2, 5),
            kind: "video", name: `Эффекты ${n}`,
            hidden: false, locked: false, muted: true
        };
        let idx = state.trackList.findIndex(t => t.kind === "text");
        if (idx < 0) idx = 0;
        state.trackList.splice(idx, 0, tr);
        state.tracks[tr.id] = [];
        renderTracksDOM();
        renderTimeline();
        saveProject();
        return tr.id;
    }
    // ── §7.1: ручные маркеры во время просмотра VOD (M / Shift+M / Enter) ──
    function addMarkerAtPlayhead(withNote) {
        ensureTracksInitialized();
        const t = Math.round(state.currentTime * 100) / 100;
        const list = state.clipper.markers = state.clipper.markers || [];
        const existing = list.find(m => Math.abs(m.t - t) < 0.25);
        if (existing) {
            showToast(`Маркер на ${t.toFixed(2)}с уже стоит.`, "info");
            return;
        }
        const marker = { t, note: "" };
        list.push(marker);
        list.sort((a, b) => a.t - b.t);
        const finish = () => {
            renderRegionsLane();
            saveProject();
            showToast(`Маркер ${list.length} @ ${t.toFixed(2)}с поставлен (Enter — нарезка от ближайшего маркера).`, "ok");
        };
        if (withNote) {
            showPrompt("Заметка к маркеру:", "").then(note => {
                marker.note = (note || "").trim();
                finish();
            });
        } else finish();
    }
    function addRegionFromNearestMarker() {
        const list = state.clipper.markers || [];
        if (!list.length) {
            addRegionFromPlayhead();
            return;
        }
        const before = [...list].reverse().find(m => m.t <= state.currentTime + 0.01);
        const after = list.find(m => m.t > state.currentTime);
        const m = before || after;
        if (!m) { addRegionFromPlayhead(); return; }
        seekTo(Math.max(0, m.t));
        addRegionFromPlayhead();
        showToast(`Нарезка от маркера @ ${m.t.toFixed(2)}с${m.note ? " — " + m.note : ""}.`, "ok");
    }
    // §7.3: «эффект в точке плейхеда» одной клавишей, с дефолтными параметрами
    // и дефолтным SFX. Переходный путь поддерживает flash / bars / shake (§15).
    function addEffectAtPlayhead(kind, color, overrides) {
        // studio:fx-add-identity - the new clip is found by identity on the SAME
        // track addFxClip() writes to; returns the clip (or null).
        // §7.3 (W): whip ставится на ближайший рез (граница нарезки/клипа)
        if (overrides && overrides.snapToCut) {
            const cut = nearestCutTo(state.currentTime);
            if (cut != null) seekTo(cut);
        }
        const tid = (overrides && overrides.trackId) ? overrides.trackId : ensureFxTrack();
        const before = new Set(state.tracks[tid] || []);
        addFxClip(kind, color, tid);
        const c = (state.tracks[tid] || []).find(x => !before.has(x));
        if (!c) return null;
        if (c.isFx && overrides) {
            const ov = Object.assign({}, overrides);
            delete ov.snapToCut;
            Object.assign(c, ov);
            c.sourceDuration = c.duration;
            c.title = fxLabel(c);
        }
        renderTimeline();
        saveProject();
        return c;
    }
    function nearestCutTo(t) {
        const cuts = [];
        for (const r of sortedRegions()) {
            cuts.push(r.startTime, r.startTime + r.duration);
        }
        for (const tid of videoTrackIds()) {
            for (const c of (state.tracks[tid] || [])) {
                if (!c.media || c.isFx) continue;
                cuts.push(c.startTime, c.startTime + c.duration);
            }
        }
        let best = null, bestD = 1.5;
        for (const c of cuts) {
            const d = Math.abs(c - t);
            if (d < bestD) { bestD = d; best = c; }
        }
        return best;
    }
    // tidOfFx() removed: unused since PR #7 (studio:drop-tidOfFx)
    // ── §9.4: пресет канала — рамки/раскладка/стиль/словарь одним нажатием (P) ──
    async function applyChannelPreset() {
        const handle = (state.clipper.streamerHandle || "").replace("@", "").trim();
        if (!handle) {
            showToast("Укажи ник стримера в поле хэндла — пресеты хранятся по нику.", "info");
            return;
        }
        try {
            const res = await fetch(`/api/presets/channel/${encodeURIComponent(handle)}`);
            if (!res.ok) {
                showToast(`Пресет канала «${handle}» не найден — настрой рамки и сохрани (Alt+P).`, "info");
                return;
            }
            const data = await res.json();
            const p = data.preset || {};
            if (p.crop_box) state.clipper.cropBox = p.crop_box;
            if (p.bg_box) state.clipper.bgBox = p.bg_box;
            if (p.format) state.clipper.format = p.format;
            if (p.style_pack) {
                if (p.style_pack.subtitle_template) state.clipper.subtitleTemplate = p.style_pack.subtitle_template;
                if (p.style_pack.sub_font) state.clipper.subFont = p.style_pack.sub_font;
                if (p.style_pack.sub_size) state.clipper.subSize = p.style_pack.sub_size;
                if (p.style_pack.sub_glow != null) state.clipper.subGlow = p.style_pack.sub_glow;
                if (p.style_pack.sub_anim) state.clipper.subAnim = p.style_pack.sub_anim;
                if (p.style_pack.color_grade) state.clipper.colorGrade = p.style_pack.color_grade;
            }
            if (p.asr_prompt) state.clipper.asrPrompt = p.asr_prompt;
            if (p.layout === "fullscreen" && !p.crop_box) state.clipper.cropBox = null;
            updateClipperUI();
            updateTvPreview();
            updateLiveSubtitleOverlay();
            syncVideoToCurrentTime();
            saveProject();
            showToast(`Пресет канала «${handle}» применён.`, "ok");
        } catch (e) {
            showToast("Ошибка загрузки пресета: " + e.message, "err");
        }
    }
    async function saveChannelPreset() {
        const handle = (state.clipper.streamerHandle || "").replace("@", "").trim();
        if (!handle) {
            showToast("Укажи ник стримера, под которым сохранить пресет.", "info");
            return;
        }
        const preset = {
            cam_box: state.clipper.cropBox || null,
            content_box: state.clipper.bgBox || null,
            format: state.clipper.format,
            layout: state.clipper.cropBox ? "split" : "fullscreen",
            style_pack: {
                subtitle_template: state.clipper.subtitleTemplate,
                sub_font: state.clipper.subFont,
                sub_size: state.clipper.subSize,
                sub_glow: state.clipper.subGlow,
                sub_anim: state.clipper.subAnim,
                color_grade: state.clipper.colorGrade
            },
            asr_prompt: state.clipper.asrPrompt || null
        };
        try {
            const res = await fetch("/api/presets/channel", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ channel: handle, preset })
            });
            if (!res.ok) throw new Error(await res.text());
            showToast(`Пресет канала «${handle}» сохранён (Alt+P применяет к новым нарезкам).`, "ok");
        } catch (e) {
            showToast("Ошибка сохранения пресета: " + e.message, "err");
        }
    }
    function addFxClip(kind, color, targetTid) {
        const tid = targetTid || ensureFxTrack();
        ensureTracksInitialized();
        const fxKind = kind || "flash";
        const fxColor = fxKind === "flash" ? (color || "white") : (color || "white");
        const dur = fxKind === "flash" ? 0.6 : (fxKind === "bars" ? 1.8 : 1.2);
        const c = {
            id: "fx_" + Date.now().toString(36) + Math.random().toString(36).slice(2, 7),  // studio:fx-unique-id
            trackId: tid,
            startTime: Math.max(0, state.currentTime),
            duration: dur,
            sourceOffset: 0,
            sourceDuration: dur,
            title: "",
            isFx: true,
            fxKind,
            fxColor,
            fxPeak: 0.75,
            fxSound: fxKind === "flash" ? (FX_DEFAULT_SOUND[fxColor] || "click") : "whoosh",
            fxGain: 1.0,
            fxBarH: 160,
            fxAmp: 12,
            fxFreq: 7,
            media: null,
            volume: 1.0,
            opacity: 1.0
        };
        c.title = fxLabel(c);
        (state.tracks[tid] = state.tracks[tid] || []).push(c);
        state.tracks[tid].sort((a, b) => a.startTime - b.startTime);
        selectClip(c.id);
        recalcTotalDuration();
        renderTimeline();
        saveProject();
        switchTab("inspector");
    }
    // studio:stickers - image sticker clip (PNG/WebP) with optional tracking path.
    // Backend supports overlay_file + track_path in export; this wires the UI.
    async function addStickerClip(file) {
        if (!file) return;
        const isImage = /\.(png|jpe?g|webp|gif|bmp)$/i.test(file.name || "");
        if (!isImage) { showToast("Стикер — только картинка (PNG/WebP/JPG с прозрачностью)", "info"); return; }
        try {
            const fd = new FormData(); fd.append("file", file, file.name);
            const r = await fetch("/api/media/upload", { method: "POST", body: fd });
            if (!r.ok) throw new Error(await r.text());
            const media = await r.json();
            // place as overlay PiP on the topmost video track
            const vids = videoTrackIds();
            const tid = vids.length ? vids[0] : (ensureTracksInitialized(), videoTrackIds()[0]);
            const clip = {
                id: "sticker_" + Date.now().toString(36) + Math.random().toString(36).slice(2, 4),
                trackId: tid,
                startTime: Math.max(0, state.currentTime),
                duration: 3.0,
                sourceOffset: 0, sourceDuration: 3.0,
                title: "🖼 " + (file.name || "стикер"),
                media: media,
                isPip: true,
                pipBox: { x: 0.62, y: 0.62, w: 0.32 },
                trackPath: null,
                volume: 1.0, opacity: 1.0
            };
            (state.tracks[tid] = state.tracks[tid] || []).push(clip);
            state.tracks[tid].sort(function(a,b){ return a.startTime - b.startTime; });
            selectClip(clip.id);
            recalcTotalDuration(); renderTimeline(); syncVideoToCurrentTime(); saveProject();
            showToast("Стикер добавлен — тяни на мониторе, трекай в инспекторе", "ok");
            // enable drag on monitor for stickers
            setTimeout(function(){
                const mon = document.getElementById("videoMonitor");
                if (mon) mon.dispatchEvent(new Event("sticker-added"));
            }, 60);
        } catch(e) { showToast("Стикер: " + e.message, "err"); }
    }
    // «+Текст»: свободный текстовый элемент (не субтитры) с полными параметрами;
    // живёт на текстовом слое, но его можно перетащить на любой другой слой
    function addTextClip() {
        ensureTracksInitialized();
        let tid = textTrackId();
        if (!tid) {
            // no text layer: create one on the fly above the video layers
            addTrack("text");
            tid = textTrackId();
        }
        let start = state.currentTime;
        // Overlap resolution: place after any text clip under the playhead
        const existing = state.tracks[tid] || [];
        const under = existing.find(c => start >= c.startTime && start < c.startTime + c.duration);
        if (under) start = under.startTime + under.duration;
        const newClip = {
            id: "text_" + Date.now(),
            trackId: tid,
            startTime: start,
            duration: 3.0,
            sourceOffset: 0,
            sourceDuration: 3.0,
            title: "Новый текст",
            isText: true,
            freeText: true,
            textFont: state.clipper.subFont && TV_FONT_OK(state.clipper.subFont) ? state.clipper.subFont : "Russo One",
            textSize: 6.0,
            textGlow: 55,
            textColor: "#ffffff",
            textAnimIn: "pop",
            textAnimOut: "fade",
            textX: 0.5,
            textY: 0.72,
            textShake: false,
            media: null,
            volume: 1.0,
            opacity: 1.0,
            subtitleStyle: state.clipper.subtitleTemplate || "acid"
        };
        existing.push(newClip);
        existing.sort((a, b) => a.startTime - b.startTime);
        state.tracks[tid] = existing;
        selectClip(newClip.id);
        recalcTotalDuration();
        renderTimeline();
        seekTo(start);
        saveProject();
        switchTab("inspector");
    }
    // ── Real SFX library (files on the server) + preview trigger ──
    const sfxLibrary = {}; // kind -> {id, name, file}
    function initSfxLibrary() {
        fetch("/api/sfx/list").then(r => r.json()).then(list => {
            (list || []).forEach(x => { sfxLibrary[x.id] = x; });
        }).catch(() => {});
    }
    function triggerFxSounds(prevT, t) {
        if (!state.isPlaying) return;
        for (const fx of allFxElements()) {
            if (!fx.fxSound || fx.fxSound === "none") continue;
            const st = fx.startTime;
            if (st > prevT && st <= t) {
                const lib = sfxLibrary[fx.fxSound];
                if (!lib) continue;
                try {
                    const el = new Audio("/api/sfx/" + lib.file);
                    el.volume = Math.max(0, Math.min(1, (fx.fxGain != null ? fx.fxGain : 1) * (masterGain || 1)));
                    el.play().catch(() => {});
                    setTimeout(() => { try { el.remove(); } catch (e) {} }, 10000);
                } catch (e) {}
            }
        }
    }
    function TV_FONT_OK(f) {
        return ["Anton", "Russo One", "Oswald SemiBold", "Oswald Bold", "Montserrat ExtraBold",
                "Unbounded ExtraBold", "Rubik Mono One", "Play", "Press Start 2P", "Lobster",
                "Bebas Neue", "Oswald", "Montserrat"].includes(f);
    }
    function pluralCuts(n) {
        const m10 = n % 10, m100 = n % 100;
        if (m10 === 1 && m100 !== 11) return "нарезка";
        if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return "нарезки";
        return "нарезок";
    }
    function renderCutsTree() {
        const listEl = document.getElementById("cutsTreeList");
        if (!listEl || document.getElementById("cutsTreePanel")?.classList.contains("hidden")) return;

        const groups = new Map(); // filename -> {media, clips:[]}
        trackOrder().forEach(tid => {
            (state.tracks[tid] || []).forEach(clip => {
                if (!clip.media) return;
                const key = clip.media.filename;
                if (!groups.has(key)) groups.set(key, { media: clip.media, clips: [] });
                groups.get(key).clips.push(clip);
            });
        });

        listEl.innerHTML = "";
        if (groups.size === 0) {
            const empty = document.createElement("div");
            empty.className = "pack-empty-hint";
            empty.textContent = "Нет клипов на таймлайне. Перетащи видео из библиотеки на слои.";
            listEl.appendChild(empty);
            return;
        }

        groups.forEach(({ media, clips }) => {
            clips.sort((a, b) => (a.sourceOffset || 0) - (b.sourceOffset || 0));
            const groupEl = document.createElement("div");
            groupEl.className = "cuts-group";

            const head = document.createElement("div");
            head.className = "cuts-group-head";
            const icon = document.createElement("span");
            icon.className = "cuts-group-icon";
            icon.textContent = "🎬";
            const name = document.createElement("span");
            name.className = "cuts-group-name";
            name.textContent = media.title || media.filename;
            name.title = media.filename;
            const count = document.createElement("span");
            count.className = "cuts-group-count";
            count.textContent = `${clips.length} ${pluralCuts(clips.length)}`;
            head.appendChild(icon);
            head.appendChild(name);
            head.appendChild(count);
            groupEl.appendChild(head);

            const items = document.createElement("div");
            items.className = "cuts-group-items";
            clips.forEach((clip, i) => {
                const row = document.createElement("div");
                row.className = "cuts-item" + (clip.id === state.selectedClipId ? " selected" : "");
                const idx = document.createElement("span");
                idx.className = "cuts-item-idx";
                idx.textContent = `#${i + 1}`;
                const range = document.createElement("span");
                range.className = "cuts-item-range mono";
                range.textContent = `${formatDurationShort(clip.sourceOffset || 0)} → ${formatDurationShort((clip.sourceOffset || 0) + clip.duration)}`;
                const place = document.createElement("span");
                place.className = "cuts-item-place";
                place.textContent = `${trackTagLabel(clip.trackId)} @ ${formatDurationShort(clip.startTime)}`;
                row.appendChild(idx);
                row.appendChild(range);
                row.appendChild(place);
                row.title = "Клик — выбрать и перейти к нарезке";
                row.addEventListener("click", () => {
                    selectClip(clip.id);
                    seekTo(clip.startTime + 0.01);
                    renderCutsTree();
                });
                items.appendChild(row);
            });
            groupEl.appendChild(items);
            listEl.appendChild(groupEl);
        });
    }

    // ── Object Tracking UI (Inspector): рамка на мониторе → серверный трек ──
    let trackDrawMode = false;
    let cropDrawMode = false;   // рисование области вебки для TV-шаблонов
    let trackingBox = null; // {x,y,w,h} normalized
    // §10.5: ручной ключ = жёсткое ограничение; сервер перетрекает только участок
    // между соседними ключами, остальные ключи не трогает.
    function addTrackingManualKey() {
        const clip = findClipById(state.selectedClipId);
        if (!clip || !trackingBox) {
            showToast("Выбери клип и нарисуй рамку цели в нужном кадре.", "info");
            return;
        }
        const base = findTrackingBaseClip(clip);
        if (!base || !base.media) return;
        const srcT = (base.sourceOffset || 0) + Math.max(0, state.currentTime - base.startTime);
        const list = clip.trackingManualKeys = clip.trackingManualKeys || [];
        const mk = { t: Math.round(srcT * 1000) / 1000, x: trackingBox.x, y: trackingBox.y, w: trackingBox.w, h: trackingBox.h };
        const i = list.findIndex(k => Math.abs(k.t - srcT) < 0.2);
        if (i >= 0) list[i] = mk; else { list.push(mk); list.sort((a, b) => a.t - b.t); }
        showToast(`Ручной ключ @ ${srcT.toFixed(2)}с добавлен — перетрекиваю участок.`, "ok");
        runObjectTracking();
    }
    function initTrackingUI() {
        const selectBtn = document.getElementById("trackSelectBtn");
        const runBtn = document.getElementById("trackRunBtn");
        const clearBtn = document.getElementById("trackClearBtn");
        if (selectBtn) selectBtn.addEventListener("click", () => {
            trackDrawMode = !trackDrawMode;
            selectBtn.classList.toggle("active", trackDrawMode);
            if (videoMonitor) videoMonitor.classList.toggle("track-draw-mode", trackDrawMode);
        });
        if (runBtn) runBtn.addEventListener("click", runObjectTracking);
        if (clearBtn) clearBtn.addEventListener("click", () => {
            const clip = findClipById(state.selectedClipId);
            if (clip) {
                delete clip.trackPath;
                delete clip.trackingManualKeys;
                trackingBox = null;
                renderTimeline();
                syncVideoToCurrentTime();
                updateTrackingUI(clip);
                saveProject();
            }
        });
        // §10.5: ручной корректирующий ключ в текущем кадре + перетрекинг участка
        if (runBtn && runBtn.parentElement) {
            const mkBtn = document.createElement("button");
            mkBtn.id = "trackManualKeyBtn";
            mkBtn.className = runBtn.className || "btn";
            mkBtn.title = "Ручной ключ ◆: подвинь рамку в нужном кадре и нажми — участок до соседнего ключа перетрекится";
            mkBtn.textContent = "◆ Ручной ключ";
            mkBtn.addEventListener("click", addTrackingManualKey);
            runBtn.parentElement.insertBefore(mkBtn, clearBtn || runBtn.nextSibling);
        }

        // Rubber-band drawing on the monitor
        if (videoMonitor) {
            let drawing = false, sx = 0, sy = 0;
            const boxEl = ensureTrackBoxEl();
            videoMonitor.addEventListener("mousedown", (e) => {
                if (!trackDrawMode && !cropDrawMode) return;
                if (e.target.closest("button")) return;
                drawing = true;
                const r = videoMonitor.getBoundingClientRect();
                sx = (e.clientX - r.left) / r.width;
                sy = (e.clientY - r.top) / r.height;
                boxEl.classList.add("drawing");
                boxEl.style.display = "block";
                boxEl.style.left = `${sx * 100}%`;
                boxEl.style.top = `${sy * 100}%`;
                boxEl.style.width = "0%";
                boxEl.style.height = "0%";
                e.preventDefault();
            });
            videoMonitor.addEventListener("mousemove", (e) => {
                if (!drawing) return;
                const r = videoMonitor.getBoundingClientRect();
                const cx = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
                const cy = Math.min(1, Math.max(0, (e.clientY - r.top) / r.height));
                boxEl.style.left = `${Math.min(sx, cx) * 100}%`;
                boxEl.style.top = `${Math.min(sy, cy) * 100}%`;
                boxEl.style.width = `${Math.abs(cx - sx) * 100}%`;
                boxEl.style.height = `${Math.abs(cy - sy) * 100}%`;
            });
            window.addEventListener("mouseup", (e) => {
                if (!drawing) return;
                drawing = false;
                const r = videoMonitor.getBoundingClientRect();
                const cx = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
                const cy = Math.min(1, Math.max(0, (e.clientY - r.top) / r.height));
                const bx = Math.min(sx, cx), by = Math.min(sy, cy);
                const bw = Math.abs(cx - sx), bh = Math.abs(cy - sy);
                if (bw < 0.02 || bh < 0.02) {
                    boxEl.style.display = "none";
                    return; // too small — ignore click
                }
                if (cropDrawMode) {
                    state.clipper.cropBox = { x: bx, y: by, w: bw, h: bh };
                    updateCropBoxUI();
                    saveProject();
                    return;
                }
                trackingBox = { x: bx, y: by, w: bw, h: bh };
                const clip = findClipById(state.selectedClipId);
                updateTrackingUI(clip);
            });
        }
    }
    function ensureTrackBoxEl() {
        let el = document.getElementById("trackBoxVisual");
        if (!el && videoMonitor) {
            el = document.createElement("div");
            el.id = "trackBoxVisual";
            el.className = "track-box-visual";
            videoMonitor.appendChild(el);
        }
        return el;
    }
    function fmtBox(b) {
        return b ? `${Math.round(b.x*100)}:${Math.round(b.y*100)} ${Math.round(b.w*100)}×${Math.round(b.h*100)}%` : null;
    }
    function updateCropBoxUI() {
        const status = document.getElementById("cropBoxStatus");
        if (status) {
            const f = fmtBox(state.clipper.cropBox);
            const g = fmtBox(state.clipper.bgBox);
            status.textContent = `Вебка: ${f || "весь верх"} · Фон: ${g || "весь низ"}`;
        }
    }
    // ── Solo area picker: слой на весь экран, рамка с пропорциями ──
    // Верх сплита 1080×864 (1.25), низ 1080×1056 (~1.0227), фулл 1080×1920 (0.5625)
    function pickTargetAspect(which) {
        if (which === "bg") return 1080 / 1056;
        if (state.clipper.format === "talking_head_9_16") return 1080 / 1920;
        return 1080 / 864;
    }
    let pickMode = null; // {which, box:{x,y,w,h}, vw, vh}
    function pickSourceMedia() {
        const t = state.currentTime;
        const layers = activeVideoLayers(t);
        const clip = layers.length ? layers[layers.length - 1] : resolvePackSource(t);
        return clip && clip.media ? clip.media : null;
    }
    function enterPickMode(which) {
        const media = pickSourceMedia();
        if (!media) { showToast("Положи видео на таймлайн и поставь плейхед на него.", "info"); return; }
        pausePlayback();
        pickMode = { which, box: null, vw: 0, vh: 0 };
        const solo = document.getElementById("pickSolo");
        const sv = document.getElementById("pickSoloVideo");
        const label = document.getElementById("pickLabel");
        if (label) label.textContent = which === "bg" ? "фон / низ" : "вебка / верх";
        if (sv) {
            sv.src = media.stream_url;
            sv.setAttribute("data-file", media.filename);
            const layers = activeVideoLayers(state.currentTime);
            const base = layers.length ? layers[layers.length - 1] : null;
            try { sv.currentTime = base ? clipTargetTime(base, state.currentTime) : 0; } catch (e) {}
            sv.pause();
        }
        if (solo) solo.classList.remove("hidden");
        if (videoEl) videoEl.style.display = "none";
        const tvp = document.getElementById("tvPreview");
        if (tvp) tvp.classList.add("hidden");
        if (monitorOverlay) monitorOverlay.style.display = "none";
        const show = () => {
            if (!sv || !sv.videoWidth) { setTimeout(show, 120); return; }
            pickMode.vw = sv.videoWidth; pickMode.vh = sv.videoHeight;
            const cur = which === "bg" ? state.clipper.bgBox : state.clipper.cropBox;
            pickMode.box = cur ? { ...cur } : defaultPickBox(pickMode.vw, pickMode.vh, pickTargetAspect(which));
            layoutPickBox();
        };
        show();
    }
    function defaultPickBox(vw, vh, targetAspect) {
        const w = 0.5;
        const h = Math.min(0.95, (w * vw) / (vh * targetAspect));
        return { x: (1 - w) / 2, y: (1 - h) / 2, w, h };
    }
    function pickContentRect() {
        const sv = document.getElementById("pickSoloVideo");
        const solo = document.getElementById("pickSolo");
        if (!sv || !solo || !pickMode.vw) return null;
        const R = sv.getBoundingClientRect();
        const S = solo.getBoundingClientRect();
        const vw = pickMode.vw, vh = pickMode.vh;
        const scale = Math.min(R.width / vw, R.height / vh);
        const cw = vw * scale, ch = vh * scale;
        return {
            x: R.left - S.left + (R.width - cw) / 2,
            y: R.top - S.top + (R.height - ch) / 2,
            w: cw, h: ch
        };
    }
    function layoutPickBox() {
        const boxEl = document.getElementById("pickBox");
        const cr = pickContentRect();
        if (!boxEl || !cr || !pickMode) return;
        const b = pickMode.box;
        boxEl.style.left = `${cr.x + b.x * cr.w}px`;
        boxEl.style.top = `${cr.y + b.y * cr.h}px`;
        boxEl.style.width = `${b.w * cr.w}px`;
        boxEl.style.height = `${b.h * cr.h}px`;
    }
    function exitPickMode(save) {
        if (save && pickMode && pickMode.box) {
            const b = pickMode.box;
            if (pickMode.which === "bg") state.clipper.bgBox = { ...b };
            else state.clipper.cropBox = { ...b };
            saveProject();
        }
        pickMode = null;
        const solo = document.getElementById("pickSolo");
        const sv = document.getElementById("pickSoloVideo");
        if (solo) solo.classList.add("hidden");
        if (sv) { try { sv.pause(); } catch (e) {} sv.removeAttribute("src"); sv.load(); }
        updateCropBoxUI();
        syncVideoToCurrentTime();
        updateTvPreview();
    }
    function initPickMode() {
        const boxEl = document.getElementById("pickBox");
        const handle = document.getElementById("pickHandle");
        const solo = document.getElementById("pickSolo");
        const okBtn = document.getElementById("pickConfirmBtn");
        const noBtn = document.getElementById("pickCancelBtn");
        if (okBtn) okBtn.addEventListener("click", () => exitPickMode(true));
        if (noBtn) noBtn.addEventListener("click", () => exitPickMode(false));
        window.addEventListener("resize", () => { if (pickMode) layoutPickBox(); });
        if (!solo || !boxEl) return;
        let drag = null; // {mode:'move'|'size', dx, dy, orig}
        boxEl.addEventListener("pointerdown", (e) => {
            if (!pickMode) return;
            e.preventDefault();
            const cr = pickContentRect();
            if (!cr) return;
            // страховка: натуральные размеры видео могли обновиться после загрузки метаданных —
            // иначе аспект-лок ресайза считает по устаревшим/неправильным vw/vh
            const svEl = document.getElementById("pickSoloVideo");
            if (svEl && svEl.videoWidth && svEl.videoHeight && (svEl.videoWidth !== pickMode.vw || svEl.videoHeight !== pickMode.vh)) {
                pickMode.vw = svEl.videoWidth;
                pickMode.vh = svEl.videoHeight;
            }
            const mode = (e.target === handle) ? "size" : "move";
            drag = { mode, x0: e.clientX, y0: e.clientY, orig: { ...pickMode.box }, cr };
            try { boxEl.setPointerCapture(e.pointerId); } catch (err) {}
        });
        boxEl.addEventListener("pointermove", (e) => {
            if (!drag || !pickMode) return;
            const { cr, orig } = drag;
            const dx = (e.clientX - drag.x0) / cr.w;
            const dy = (e.clientY - drag.y0) / cr.h;
            const targetAspect = pickTargetAspect(pickMode.which);
            const vidAspect = pickMode.vw / pickMode.vh;
            if (drag.mode === "move") {
                pickMode.box.x = Math.max(0, Math.min(1 - orig.w, orig.x + dx));
                pickMode.box.y = Math.max(0, Math.min(1 - orig.h, orig.y + dy));
            } else {
                // resize by width, height follows locked aspect (in video-pixel terms)
                let w = Math.max(0.05, Math.min(1 - orig.x, orig.w + dx));
                let h = (w * vidAspect) / targetAspect;
                if (orig.y + h > 1) {
                    h = 1 - orig.y;
                    w = (h * targetAspect) / vidAspect;
                }
                pickMode.box.w = w; pickMode.box.h = h;
            }
            layoutPickBox();
        });
        const endDrag = () => { drag = null; };
        boxEl.addEventListener("pointerup", endDrag);
        boxEl.addEventListener("pointercancel", endDrag);
    }
    function updateTrackingUI(clip) {
        const status = document.getElementById("trackingStatus");
        const boxEl = ensureTrackBoxEl();
        if (!status) return;
        if (!clip || !clip.media && !clip.title) {
            status.textContent = "Выбери клип на панели слоёв";
            if (boxEl) boxEl.style.display = "none";
            return;
        }
        const pathLen = clip.trackPath ? clip.trackPath.length : 0;
        if (trackingBox) {
            status.textContent = pathLen
                ? `Рамка задана · трек: ${pathLen} ключей ✓`
                : "Рамка задана — нажми «Трекать»";
            if (boxEl) {
                boxEl.style.display = "block";
                boxEl.style.left = `${trackingBox.x * 100}%`;
                boxEl.style.top = `${trackingBox.y * 100}%`;
                boxEl.style.width = `${trackingBox.w * 100}%`;
                boxEl.style.height = `${trackingBox.h * 100}%`;
                boxEl.classList.remove("drawing");
            }
        } else if (pathLen) {
            status.textContent = `Трек активен: ${pathLen} ключей (клип следует за объектом)`;
            if (boxEl) boxEl.style.display = "none";
        } else {
            status.textContent = "Рамка не задана — нажми «Выделить объект» и обведи объект на мониторе";
            if (boxEl) boxEl.style.display = "none";
        }
    }
    // Base (bottom video track) clip that the selected clip's window maps into
    function findTrackingBaseClip(sel) {
        if (!sel) return null;
        const mid = sel.startTime + sel.duration / 2;
        const vids = videoTrackIds();
        for (let i = vids.length - 1; i >= 0; i--) {
            const clip = (state.tracks[vids[i]] || []).find(c =>
                c.media && mid >= c.startTime && mid <= c.startTime + c.duration);
            if (clip) return clip;
        }
        return null;
    }
    async function runObjectTracking() {
        const clip = findClipById(state.selectedClipId);
        if (!clip) {
            showToast("Выбери клип на панели слоёв.", "info");
            return;
        }
        if (!trackingBox) {
            showToast("Сначала выдели объект рамкой: «Выделить объект», затем обведи объект на мониторе.", "info");
            return;
        }
        const base = findTrackingBaseClip(clip);
        if (!base || !base.media) {
            showToast("Не найдено основное видео под этим клипом — трекать не по чему.", "err");
            return;
        }
        // Source window inside the base media for the selected clip's span
        const srcStart = (base.sourceOffset || 0) + Math.max(0, clip.startTime - base.startTime);
        const srcEnd = (base.sourceOffset || 0) + Math.min(base.duration, clip.startTime + clip.duration - base.startTime);
        const dur = Math.max(0.2, srcEnd - srcStart);

        const status = document.getElementById("trackingStatus");
        const runBtn = document.getElementById("trackRunBtn");
        if (status) status.textContent = "Трекинг выполняется…";
        if (runBtn) runBtn.disabled = true;
        // §10: раздельные цель и зона. Зона по умолчанию = цель ×3, клипп к кадру;
        // ручные ключи клиента передаются как жёсткие ограничения.
        const zone = clip.trackingZone || (() => {
            const zw = Math.min(1, trackingBox.w * 3), zh = Math.min(1, trackingBox.h * 3);
            return {
                x: Math.max(0, Math.min(1 - zw, trackingBox.x + trackingBox.w / 2 - zw / 2)),
                y: Math.max(0, Math.min(1 - zh, trackingBox.y + trackingBox.h / 2 - zh / 2)),
                w: zw, h: zh
            };
        })();
        try {
            const res = await fetch("/api/track-object", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    filename: base.media.filename,
                    t_from: srcStart,
                    t_to: srcEnd,
                    t_anchor: srcStart,
                    target: { x: trackingBox.x, y: trackingBox.y, w: trackingBox.w, h: trackingBox.h },
                    zone: zone,
                    manual_keys: clip.trackingManualKeys || [],
                    mode: "ncc",
                    fps: 12,
                    analysis_width: 960,
                    scale_search: false,
                    min_conf: 0.55
                })
            });
            if (!res.ok) {
                const err = await res.text();
                showToast("Ошибка трекинга: " + err, "err");
                if (status) status.textContent = "Ошибка трекинга";
                return;
            }
            const data = await res.json();
            // §10.4: ключи в абсолютном времени источника; для превью используем
            // legacy-ключи (t относительно клипа), conf/lost — для полосы уверенности.
            const keys = data.keys || [];
            clip.trackPath = (data.keyframes || []).map(k => ({
                t: k.t, x: k.x, y: k.y, w: k.w, h: k.h
            }));
            clip.trackConf = keys.map(k => ({ t: k.t - srcStart, conf: k.conf, lost: !!k.lost, manual: !!k.manual }));
            clip.trackingZone = zone;
            const lostN = keys.filter(k => k.lost).length;
            if (status) status.textContent = lostN
                ? `Трек готов: ${keys.length} ключей, потерян ${lostN} кадров — подвинь рамку там и добавь ручной ключ.`
                : `Трек готов: ${keys.length} ключей, потерь нет.`;
            trackingBox = { ...trackingBox };
            renderTimeline();
            syncVideoToCurrentTime();
            updateTrackingUI(clip);
            saveProject();
        } catch (e) {
            console.error("Tracking error:", e);
            showToast("Сетевая ошибка трекинга: " + e.message, "err");
            if (status) status.textContent = "Ошибка трекинга";
        } finally {
            if (runBtn) runBtn.disabled = false;
        }
    }

    // ── Project persistence (timeline + pack + clipper settings survive reload) ──
    const PROJECT_KEY = "kick_studio_project_v1";
    let saveTimer = null;
    function saveProject() {
        clearTimeout(saveTimer);
        saveTimer = setTimeout(() => {
            try {
                ensureTracksInitialized();
                const slimTracks = {};
                trackOrder().forEach(tid => {
                    slimTracks[tid] = (state.tracks[tid] || []).map(c => ({
                        ...c, media: c.media ? {
                            filename: c.media.filename, title: c.media.title,
                            stream_url: c.media.stream_url, thumb_url: c.media.thumb_url,
                            duration: c.media.duration
                        } : c.media
                    }));
                });
                localStorage.setItem(PROJECT_KEY, JSON.stringify({
                    tracks: slimTracks,
                    trackList: state.trackList,
                    zoom: state.zoom,
                    aspectRatio: state.aspectRatio || "16:9",
                    regions: state.regions || [],
                    selectedRegionId: state.selectedRegionId || null,
                    clipper: {
                        format: state.clipper.format, sourceFile: state.clipper.sourceFile,
                        bgFile: state.clipper.bgFile, noBg: state.clipper.noBg,
                        cropPreset: state.clipper.cropPreset, platform: state.clipper.platform,
                        streamerHandle: state.clipper.streamerHandle,
                        subtitleTemplate: state.clipper.subtitleTemplate,
                        subFont: state.clipper.subFont || "Russo One",
                        subSize: state.clipper.subSize || 1.0,
                        subGlow: state.clipper.subGlow != null ? state.clipper.subGlow : 55,
                        subAnim: state.clipper.subAnim || "pop",
                        wordsPerCue: state.clipper.wordsPerCue || 3,
                        subLang: state.clipper.subLang || "ru",
                        exportSeparate: !!state.clipper.exportSeparate,
                        colorGrade: state.clipper.colorGrade || "none",
                        flashCuts: !!state.clipper.flashCuts,
                        cropBox: state.clipper.cropBox || null,
                        bgBox: state.clipper.bgBox || null,
                        barTop: parseInt(state.clipper.barTop, 10) || 0,
                        barBottom: parseInt(state.clipper.barBottom, 10) || 0,
                        srcProcessed: !!state.clipper.srcProcessed,
                        hotWords: state.clipper.hotWords !== false,
                        templateName: state.clipper.templateName || null,
                        inTime: state.clipper.inTime, outTime: state.clipper.outTime
                    }
                }));
            } catch (e) {}
        }, 400);
    }
    function migrateClipsToTracks() {
        // Move any clip that references a missing track into a track of matching kind;
        // rescue media clips stuck on text tracks (old bug) back to video lanes
        ensureTracksInitialized();
        const vids = videoTrackIds();
        trackOrder().forEach(tid => {
            const track = getTrack(tid);
            (state.tracks[tid] || []).forEach(clip => {
                if (!track) return;
                if (track.kind === "audio" && !isAudioFile(clip.media) && clip.media) {
                    if (vids.length) {
                        (state.tracks[vids[vids.length - 1]] = state.tracks[vids[vids.length - 1]] || []).push(clip);
                        state.tracks[tid] = (state.tracks[tid] || []).filter(c => c.id !== clip.id);
                        clip.trackId = vids[vids.length - 1];
                    }
                }
                if (track.kind === "text" && clip.media && !clip.isFx) {
                    const dst = isAudioFile(clip.media) ? audioTrackIds()[0] : (vids.length ? vids[vids.length - 1] : null);
                    if (dst) {
                        (state.tracks[dst] = state.tracks[dst] || []).push(clip);
                        state.tracks[tid] = (state.tracks[tid] || []).filter(c => c.id !== clip.id);
                        clip.trackId = dst;
                    }
                }
            });
        });
    }
    function restoreProject() {
        let saved = null;
        try { saved = JSON.parse(localStorage.getItem(PROJECT_KEY) || "null"); } catch (e) {}
        if (!saved) return;
        try {
            ensureTracksInitialized();
            if (Array.isArray(saved.trackList) && saved.trackList.length) {
                // Restore custom layers; fall back to defaults for anything missing
                state.trackList = saved.trackList.filter(t => t && t.id && t.kind).map(t => ({
                    kind: "video", hidden: false, locked: false, muted: false, name: t.id,
                    ...t
                }));
            }
            if (saved.tracks) {
                state.tracks = {};
                for (const tid of trackOrder()) {
                    if (Array.isArray(saved.tracks[tid])) state.tracks[tid] = saved.tracks[tid];
                }
            }
            migrateClipsToTracks();
            if (saved.zoom) state.zoom = Math.max(8, Math.min(400, saved.zoom));
            if (saved.clipper) Object.assign(state.clipper, saved.clipper);
            // restore monitor aspect (TV presets work in 9:16)
            const wantVert = saved.aspectRatio === "9:16" ||
                (!saved.aspectRatio && ["split_adhd", "talking_head_9_16"].includes(state.clipper.format));
            if (wantVert) {
                state.aspectRatio = "9:16";
                if (aspectRatioToggleBtn) {
                    aspectRatioToggleBtn.textContent = "9:16";
                    aspectRatioToggleBtn.classList.add("active-9-16");
                }
                if (videoMonitor) videoMonitor.classList.add("vertical-9-16");
            }
            if (Array.isArray(saved.regions)) {
                state.regions = saved.regions.filter(r => r && isFinite(r.startTime) && isFinite(r.duration) && r.duration > 0);
            }
            state.selectedRegionId = saved.selectedRegionId || null;
            const zs = document.getElementById("timelineZoomSlider");
            if (zs) zs.value = Math.max(8, Math.min(400, state.zoom));
            renderTracksDOM();
            recalcTotalDuration();
            renderTimeline();
            renderCutsTree();
            renderPackClips();
            renderRegionsList();
            reflectSubSettings();
            updateMarkerRangeUI();
            updateBadgeOverlay();
            syncVideoToCurrentTime();
            updateLiveSubtitleOverlay();
            seekTo(state.currentTime);
            applyTemplateToClipper({
                format: state.clipper.format, crop_preset: state.clipper.cropPreset,
                platform: state.clipper.platform, streamer_handle: state.clipper.streamerHandle,
                subtitle_template: state.clipper.subtitleTemplate,
                color_grade: state.clipper.colorGrade || "none",
                flash_cuts: !!state.clipper.flashCuts,
                noBg: state.clipper.noBg,
                name: state.clipper.templateName || undefined
            });
        } catch (e) { console.warn("restore failed", e); }
    }
    // Hook persistence into mutations
    const _origRenderTimeline = renderTimeline;
    renderTimeline = function() { _origRenderTimeline(); saveProject(); updateEmptyTimelineHint(); };
    function updateEmptyTimelineHint() {
        const total = totalClipCount();
        if (monitorOverlay && total === 0) monitorOverlay.style.display = "flex";
    }

    // Public Studio API for Kick Downloader integration
    window.Studio = {
        addMediaToTimeline,
        fetchLibrary,
        switchTab,
        seekTo,
        onKickDownloadCompleted: (filePath, title) => {
            console.log("Kick download completed:", filePath, title);
            fetchLibrary().then(() => {
                const fname = filePath.split(/[\/\\]/).pop();
                const newMedia = state.mediaLibrary.find(m => m.filename === fname) || state.mediaLibrary[0];

                const notifyBox = document.getElementById("autoLibraryNotify");
                const addToTimelineBtn = document.getElementById("addToTimelineFromKickBtn");

                if (notifyBox) notifyBox.classList.remove("hidden");

                if (addToTimelineBtn && newMedia) {
                    addToTimelineBtn.onclick = () => {
                        addMediaToTimeline(newMedia, "v1");
                        switchTab("library");
                    };
                }

                setTimeout(() => {
                    switchTab("library");
                }, 1200);
            });
        }
    };

    // ── Studio Integrations (§2 & §6 Moments / Templates / Seek / Transcript) ──
    window.studioSeek = seekTo;

    Object.defineProperty(window, "studioTranscriptWords", {
        get() {
            if (state._lastTranscribe && Array.isArray(state._lastTranscribe.words) && state._lastTranscribe.words.length) {
                return state._lastTranscribe.words;
            }
            const tId = textTrackId();
            const clips = state.tracks[tId] || [];
            const words = [];
            for (const c of clips) {
                if (Array.isArray(c.words)) words.push(...c.words);
            }
            return words.length ? words : null;
        },
        configurable: true
    });

    // studio:addfx-v2 - template/moment fx go through the SAME builder as the
    // hotkeys (addEffectAtPlayhead): per-kind fields (zoom/lens/threshold/flash
    // -> fxPeak, shake -> fxAmp/fxFreq), anchor for the face zoom, and the
    // moment's SOURCE time is mapped onto the timeline via the clip showing it.
    function studioSourceToTimeline(srcT) {
        let best = null;
        const ids = (typeof videoTrackIds === "function") ? videoTrackIds() : [];
        for (const tid of ids) {
            for (const c of (state.tracks[tid] || [])) {
                if (!c || !c.media || c.isFx) continue;
                const off = Number(c.sourceOffset) || 0;
                const rate = Number(c.speed) > 0 ? Number(c.speed) : 1;
                const srcLen = (Number(c.duration) || 0) * rate;
                if (srcT >= off && srcT < off + srcLen) {
                    const t = c.startTime + (srcT - off) / rate;
                    if (best === null || t < best) best = t;
                }
            }
        }
        return best;
    }
    window.studioSourceToTimeline = studioSourceToTimeline;

    window.studioAddFx = function (fxList, baseTime, opts) {
        if (!Array.isArray(fxList) || !fxList.length) return 0;
        const o = opts || {};
        let base = Number(baseTime) || 0;
        if (o.timeBase === "source") {
            const mapped = studioSourceToTimeline(base);
            if (mapped === null) {
                showToast("Момент не попадает ни в один клип на таймлайне: эффекты не добавлены", "info");
                return 0;
            }
            base = mapped;
        }
        const savedTime = state.currentTime;
        let added = 0;
        try {
            for (const f of fxList) {
                if (!f || !f.kind) continue;
                const kind = String(f.kind);
                const s = Number(f.start) || 0;
                const dur = Math.max(0.05, f.end != null ? (Number(f.end) - s) : (Number(f.duration) || 0.35));
                const ov = { duration: dur, fxSound: f.sfx || f.fxSound || "none" };
                if (kind === "zoom") ov.fxPeak = f.amp != null ? Number(f.amp) : 0.15;
                else if (kind === "lens") ov.fxPeak = f.amp != null ? Number(f.amp) : 0.18;
                else if (kind === "threshold") ov.fxPeak = f.amp != null ? Number(f.amp) : 0.45;
                else if (kind === "flash") ov.fxPeak = f.peak != null ? Number(f.peak) : 0.75;
                else if (kind === "shake") {
                    ov.fxAmp = f.amp != null ? Number(f.amp) : 12;
                    if (f.freq != null) ov.fxFreq = Number(f.freq);
                }
                if (f.anchor) ov.anchor = f.anchor;
                if (kind === "push") ov.fxPeak = f.amp != null ? Number(f.amp) : (f.peak != null ? Number(f.peak) : 0.08);
                if (f.mode) ov.fxMode = f.mode;
                if (f.trackId) ov.trackId = f.trackId;
                state.currentTime = Math.max(0, base + s);
                if (addEffectAtPlayhead(kind, f.color || "white", ov)) added++;  // studio:addfx-count
            }
        } finally {
            state.currentTime = savedTime;
        }
        const fxTid = ensureFxTrack();  // studio:addfx-fxtrack
        if (state.tracks[fxTid]) state.tracks[fxTid].sort((a, b) => a.startTime - b.startTime);
        recalcTotalDuration();
        renderTimeline();
        syncVideoToCurrentTime();
        saveProject();
        return added;
    };

    // ── Discipline edits: apply a server plan as a timeline project ──
    // plan: {clips:[{filename,src_in,duration,out_start}], cards:[...],
    //        fx:[{kind,start,end,...,track:"video"|"cards"}], sounds:[...],
    //        music:{filename,offset,duration}, duration, format}
    window.Studio.applyDisciplinePlan = function (plan, opts) {
        if (!plan) return 0;
        const o = opts || {};
        ensureTracksInitialized();
        if (o.clear) {
            for (const tid of trackOrder()) state.tracks[tid] = [];
            state.regions = [];
            state.selectedRegionId = null;
            state.selectedClipId = null;
        }
        const lib = state.mediaLibrary || [];
        const byName = (n) => lib.find(m => m && m.filename === n) || null;
        const vtid = firstVideoTrackId() || trackOrder()[0];
        // cards live on their OWN track above the video so they can overlap
        // the playing video (takeover) and carry their own FX z-level
        let cardsTid = (videoTrackIds() || []).find(tid => /карточк/i.test((getTrack(tid) || {}).name || ""));
        if (!cardsTid || cardsTid === vtid) {
            cardsTid = addTrack("video");
            const t = getTrack(cardsTid);
            if (t) t.name = "Дисциплина · карточки";
            renderTracksDOM();
        }
        const putClip = (media, tid, start, dur, extra) => {
            if (!media) return null;
            const arr = trackClips(tid);
            const c = {
                id: "clip_" + Date.now().toString(36) + "_" + Math.floor(Math.random() * 1e6),
                trackId: tid, startTime: start, duration: dur,
                sourceOffset: (extra && extra.srcIn) || 0, sourceDuration: dur,
                media: media, volume: (extra && extra.volume != null) ? extra.volume : 1.0,
                opacity: 1.0, musicDuck: !!(extra && extra.musicDuck)
            };
            if (extra) {
                if (extra.scaleFrom) c.discScaleFrom = extra.scaleFrom;
                if (extra.scaleIn) c.discScaleIn = extra.scaleIn;
                if (extra.tint && extra.tint !== "none") c.discTint = extra.tint;
            }
            arr.push(c);
            arr.sort((a, b) => a.startTime - b.startTime);
            state.tracks[tid] = arr;
            return c;
        };
        for (const c of (plan.clips || [])) {
            const m = byName(c.filename);
            if (!m) continue;
            putClip(m, vtid, Number(c.out_start) || 0, Number(c.duration) || 2, { srcIn: Number(c.src_in) || 0, volume: 0 });
        }
        for (const c of (plan.cards || [])) {
            const name = c.kind === "pic" ? (c.file || c.filename) : c.filename;
            const m = byName(name);
            if (!m) continue;
            putClip(m, cardsTid, Number(c.out_start) || 0, Number(c.duration) || 2, {
                srcIn: Number(c.src_in) || 0, volume: 0,
                scaleFrom: Number(c.scale_from) || 0,
                scaleIn: Number(c.scale_in) || 0,
                tint: c.tint || "none"
            });
        }
        if (plan.music && plan.music.filename) {
            const m = byName(plan.music.filename);
            if (m) {
                const auds = (typeof audioTrackIds === "function") ? audioTrackIds() : [];
                const atid = auds.length ? auds[auds.length - 1] : trackOrder()[0];
                const ac = putClip(m, atid, 0, Number(plan.duration) || 20, { srcIn: Number(plan.music.offset) || 0, volume: 1.0 });
                if (ac) ac.musicDuck = false;
            }
        }
        // FX: built directly on the plan's target track (video/cards) so the
        // exporter burns each effect at its own z level only.
        const fxClip = (f) => {
            const tid = f.track === "cards" ? cardsTid : vtid;
            const dur = Math.max(0.05, (Number(f.end) || 0) - (Number(f.start) || 0));
            const c = {
                id: "fx_" + Date.now().toString(36) + Math.random().toString(36).slice(2, 7),
                trackId: tid, startTime: Math.max(0, Number(f.start) || 0),
                duration: dur, sourceOffset: 0, sourceDuration: dur,
                title: "", isFx: true, fxKind: f.kind || "flash",
                fxColor: f.color || "white",
                fxPeak: (f.peak != null) ? Number(f.peak) : ((f.amp != null) ? Number(f.amp) : 0.75),
                fxSound: "none", fxGain: 1.0, fxBarH: 160,
                fxAmp: (f.amp != null) ? Number(f.amp) : 12,
                fxFreq: (f.freq != null) ? Number(f.freq) : 7,
                fxMode: f.mode || null,
                media: null, volume: 1.0, opacity: 1.0
            };
            c.title = fxLabel(c);
            (state.tracks[tid] = state.tracks[tid] || []).push(c);
            return c;
        };
        let fxAdded = 0;
        if (Array.isArray(plan.fx)) {
            for (const f of plan.fx) { if (f && f.kind) { fxClip(f); fxAdded++; } }
            for (const tid of new Set([vtid, cardsTid])) {
                if (state.tracks[tid]) state.tracks[tid].sort((a, b) => a.startTime - b.startTime);
            }
        }
        if (Array.isArray(plan.sounds)) {
            for (const s of plan.sounds) {
                const at = Number(s.at) || 0;
                let best = null, bestD = 0.6;
                for (const c of allFxElements()) {
                    const d = Math.abs((c.startTime || 0) - at);
                    if (d < bestD) { bestD = d; best = c; }
                }
                if (best && s.kind && s.kind !== "none") {
                    best.fxSound = s.kind;
                    best.fxGain = (s.gain != null ? s.gain : 1.0);
                    best.title = fxLabel(best);
                }
            }
        }
        // end-card text (planner v2 keeps text empty — slides carry the hook)
        const ttid = (typeof textTrackId === "function") ? textTrackId() : null;
        if (ttid && Array.isArray(plan.text)) {
            for (const t of plan.text) {
                const arr = trackClips(ttid);
                arr.push({
                    id: "text_" + Date.now().toString(36) + Math.floor(Math.random() * 1e3),
                    trackId: ttid, startTime: Number(t.start) || 0,
                    duration: Math.max(0.5, (Number(t.end) || 2) - (Number(t.start) || 0)),
                    sourceOffset: 0, sourceDuration: 2, title: t.text || "",
                    isText: true, freeText: true,
                    textFont: "Montserrat ExtraBold", textSize: 6.0,
                    textGlow: 60, textColor: "#ffffff",
                    textAnimIn: t.anim_in || "pop", textAnimOut: t.anim_out || "fade",
                    textX: t.x != null ? t.x : 0.5, textY: t.y != null ? t.y : 0.5,
                    textShake: false, media: null, volume: 1.0, opacity: 1.0,
                    subtitleStyle: "acid"
                });
                arr.sort((a, b) => a.startTime - b.startTime);
                state.tracks[ttid] = arr;
            }
        }
        // clipper preset for discipline look
        state.clipper.format = plan.format || "fullscreen";
        state.clipper.colorGrade = "tv";
        state.clipper.flashCuts = false;
        state.clipper.hotWords = false;
        state.clipper.subtitleTemplate = "acid";
        // one region over the whole edit
        const r = {
            id: "rg_disc_" + Date.now().toString(36),
            name: "Дисциплина " + (Number(plan.duration) || 0).toFixed(0) + "с",
            startTime: 0, duration: Number(plan.duration) || 20, noFlashAfter: true
        };
        state.regions = [...(state.regions || []), r];
        state.selectedRegionId = r.id;
        state.selectedClipId = null;
        pausePlayback();
        recalcTotalDuration();
        renderTimeline();
        if (typeof renderCutsTree === "function") renderCutsTree();
        renderRegionsLane();
        renderRegionsList();
        updateRegionToolbarUI();
        if (typeof updateClipperUI === "function") updateClipperUI();
        seekTo(0);
        saveProject();
        const placedCount = (plan.clips || []).length + (plan.cards || []).length;
        showToast(`Дисциплина: клипов ${placedCount}, эффектов ${fxAdded}`, "ok");
        return placedCount;
    };

    document.addEventListener("studio:template-plan", (e) => {
        const plan = e.detail;
        if (plan && Array.isArray(plan.fx) && plan.fx.length) {
            const base = (plan.moment && typeof plan.moment.start === "number") ? plan.moment.start : state.currentTime;
            const added = window.studioAddFx(plan.fx, base, { timeBase: "source" });  // studio:addfx-source
            if (added) showToast(`Шаблон «${plan.template || ""}»: добавлено ${added} эффектов на таймлайн`, "ok");
        }
    });

})();

