// Kick Downloader UI Logic & Studio Integration
document.addEventListener("DOMContentLoaded", () => {
    // Header & Disk elements
    const pillDrive = document.getElementById("pillDrive");
    const pillFree = document.getElementById("pillFree");
    const pillRefreshBtn = document.getElementById("pillRefreshBtn");
    const openFolderBtn = document.getElementById("openFolderBtn");

    // Input form
    const videoUrlInput = document.getElementById("videoUrlInput");
    const pasteBtn = document.getElementById("pasteBtn");
    const clearBtn = document.getElementById("clearBtn");
    const probeBtn = document.getElementById("probeBtn");
    const probeSpinner = document.getElementById("probeSpinner");

    // Details & Qualities
    const videoDetailsSection = document.getElementById("videoDetailsSection");
    const videoThumb = document.getElementById("videoThumb");
    const videoDuration = document.getElementById("videoDuration");
    const streamerName = document.getElementById("streamerName");
    const videoTitle = document.getElementById("videoTitle");
    const qualitiesGrid = document.getElementById("qualitiesGrid");

    // Disk Meter
    const diskDriveLabel = document.getElementById("diskDriveLabel");
    const freeSpaceText = document.getElementById("freeSpaceText");
    const totalSpaceText = document.getElementById("totalSpaceText");
    const storageUsedSegment = document.getElementById("storageUsedSegment");
    const storageRequiredSegment = document.getElementById("storageRequiredSegment");
    const storageFreeSegment = document.getElementById("storageFreeSegment");
    const legendUsedSize = document.getElementById("legendUsedSize");
    const legendRequiredSize = document.getElementById("legendRequiredSize");
    const legendRemainingSize = document.getElementById("legendRemainingSize");
    const legendRequiredDot = document.getElementById("legendRequiredDot");

    // Insufficient Space Alert
    const spaceAlertBox = document.getElementById("spaceAlertBox");
    const alertReq = document.getElementById("alertReq");
    const alertFree = document.getElementById("alertFree");
    const alertShortage = document.getElementById("alertShortage");
    const alertDrive = document.getElementById("alertDrive");
    const recheckSpaceBtn = document.getElementById("recheckSpaceBtn");

    // Download Actions & Progress
    const startDownloadBtn = document.getElementById("startDownloadBtn");
    const downloadBtnText = document.getElementById("downloadBtnText");
    const btnQualityLabel = document.getElementById("btnQualityLabel");

    const progressSection = document.getElementById("progressSection");
    const statusPill = document.getElementById("statusPill");
    const percentVal = document.getElementById("percentVal");
    const progressFill = document.getElementById("progressFill");
    const speedVal = document.getElementById("speedVal");
    const segmentsVal = document.getElementById("segmentsVal");
    const etaVal = document.getElementById("etaVal");
    const bytesVal = document.getElementById("bytesVal");
    const statusMessage = document.getElementById("statusMessage");
    const cancelDownloadBtn = document.getElementById("cancelDownloadBtn");

    // Same rule as the server (disk_manager.check_space with DOWNLOAD_PEAK_FACTOR):
    // while the HLS VOD is merged, segments AND the MP4 exist at once (x2),
    // plus the 5% safety margin promised in the README. Before PR #7 the UI
    // checked 1x, said "enough", and /api/start-download then refused silently.
    const DOWNLOAD_PEAK_FACTOR = 2.0;
    const DISK_SAFETY_RATIO = 0.05;

    // State
    let currentVideoData = null;
    let selectedQuality = null;
    let currentDiskInfo = null;
    let eventSource = null;
    let progressFinished = false;
    let progressRetryTimer = null;
    let progressRetryDelay = 1000;
    let dlMode = "full"; // "full" | "fragment"

    function parseTimeInput(str) {
        if (!str) return NaN;
        const t = String(str).trim().replace(",", ".");
        if (/^\d+(\.\d+)?$/.test(t)) return parseFloat(t);
        const parts = t.split(":").map(Number);
        if (parts.some(isNaN)) return NaN;
        let sec = 0;
        for (const p of parts) sec = sec * 60 + p;
        return sec;
    }

    function formatMmSs(sec) {
        if (!isFinite(sec) || sec < 0) return "--:--";
        const s = Math.floor(sec);
        const h = Math.floor(s / 3600);
        const m = Math.floor((s % 3600) / 60);
        const r = s % 60;
        const pad = (n) => String(n).padStart(2, "0");
        return h > 0 ? `${h}:${pad(m)}:${pad(r)}` : `${pad(m)}:${pad(r)}`;
    }

    function getFragmentRange() {
        const startInput = document.getElementById("dlStartInput");
        const endInput = document.getElementById("dlEndInput");
        if (!currentVideoData || !startInput || !endInput) return null;
        const total = currentVideoData.duration || 0;
        let start = parseTimeInput(startInput.value);
        let end = parseTimeInput(endInput.value);
        if (!isFinite(start) || !isFinite(end)) return null;
        start = Math.max(0, start);
        end = total > 0 ? Math.min(total, end) : end;
        if (!(end > start)) return null;
        return { start, end, total };
    }

    function getEffectiveRequiredBytes() {
        const full = selectedQuality ? selectedQuality.size.estimated_bytes : 0;
        if (dlMode === "fragment" && currentVideoData && currentVideoData.duration > 0) {
            const r = getFragmentRange();
            if (r) return Math.max(1024, Math.floor(full * ((r.end - r.start) / currentVideoData.duration)));
        }
        return full;
    }

    function peakNeedBytes(reqBytes) {
        return Math.ceil(Math.max(0, reqBytes) * DOWNLOAD_PEAK_FACTOR * (1 + DISK_SAFETY_RATIO));
    }

    function updateDownloadBtnLabel() {
        if (!selectedQuality || !downloadBtnText) return;
        if (dlMode === "fragment") {
            const r = getFragmentRange();
            if (r) {
                downloadBtnText.innerHTML = `Скачать фрагмент ${formatMmSs(r.start)}–${formatMmSs(r.end)} (<span id="btnQualityLabel">${selectedQuality.label}</span>)`;
                return;
            }
        }
        downloadBtnText.innerHTML = `Скачать целиком (<span id="btnQualityLabel">${selectedQuality.label}</span>)`;
    }

    // Load initial disk info
    fetchDiskInfo();

    async function fetchDiskInfo() {
        try {
            const res = await fetch("/api/disk-info");
            if (res.ok) {
                currentDiskInfo = await res.json();
                if (pillDrive) pillDrive.textContent = currentDiskInfo.drive;
                if (pillFree) pillFree.textContent = `${currentDiskInfo.free_formatted} свободно`;
                if (diskDriveLabel) diskDriveLabel.textContent = currentDiskInfo.drive;
                if (freeSpaceText) freeSpaceText.textContent = currentDiskInfo.free_formatted;
                if (totalSpaceText) totalSpaceText.textContent = currentDiskInfo.total_formatted;
            }
        } catch (e) {
            console.error("Ошибка получения данных диска:", e);
        }
    }

    // Paste & Clear
    pasteBtn.addEventListener("click", async () => {
        try {
            const text = await navigator.clipboard.readText();
            if (text) videoUrlInput.value = text.trim();
        } catch (e) {
            console.warn("Буфер обмена недоступен через API");
        }
    });

    clearBtn.addEventListener("click", () => {
        videoUrlInput.value = "";
        videoUrlInput.focus();
    });

    pillRefreshBtn.addEventListener("click", () => {
        fetchDiskInfo();
        if (selectedQuality) {
            checkSelectedQualitySpace();
        }
    });

    recheckSpaceBtn.addEventListener("click", async () => {
        await fetchDiskInfo();
        checkSelectedQualitySpace();
    });

    // Probe Video URL
    probeBtn.addEventListener("click", async () => {
        const url = videoUrlInput.value.trim();
        if (!url) {
            showToast("Пожалуйста, вставьте ссылку на запись стрима Kick.com", "info");
            return;
        }

        probeBtn.disabled = true;
        probeSpinner.classList.add("active");
        videoDetailsSection.classList.add("hidden");
        progressSection.classList.add("hidden");

        try {
            const res = await fetch("/api/probe", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ url })
            });

            if (!res.ok) {
                // detail may be a string, object, array (validation) or the body may not be JSON at all
                let msg = "Ошибка при анализе видео";
                try {
                    const err = await res.json();
                    const d = err.detail !== undefined ? err.detail : err;
                    if (typeof d === "string") msg = d;
                    else if (Array.isArray(d)) msg = d.map(x => (x && x.msg) ? x.msg : String(x)).join("; ");
                    else if (d && typeof d === "object" && d.message) msg = d.message;
                    else msg = JSON.stringify(d);
                } catch (e) {
                    try { msg = (await res.text()).slice(0, 300) || msg; } catch (e2) {}
                }
                throw new Error(msg);
            }

            currentVideoData = await res.json();
            currentDiskInfo = currentVideoData.disk_info;
            displayVideoDetails(currentVideoData);
        } catch (err) {
            showToast("Ошибка получения данных: " + err.message, "err");
        } finally {
            probeBtn.disabled = false;
            probeSpinner.classList.remove("active");
        }
    });

    function displayVideoDetails(data) {
        videoThumb.src = data.thumbnail || "";
        videoDuration.textContent = data.duration_str || "00:00:00";
        streamerName.textContent = data.streamer || "Channel";
        videoTitle.textContent = data.title || "Запись стрима";

        // Render Quality Cards
        qualitiesGrid.innerHTML = "";
        data.qualities.forEach((q, idx) => {
            const card = document.createElement("div");
            card.className = "quality-card";
            if (idx === 0) {
                card.classList.add("selected");
                selectedQuality = q;
            }

            const isSource = q.is_source;
            const badgeHtml = isSource ? `<span class="quality-badge source-badge">⚡ Source</span>` : `<span class="quality-badge">${q.resolution}</span>`;

            card.innerHTML = `
                <div class="quality-card-top">
                    <span class="quality-label">${q.label}</span>
                    ${badgeHtml}
                </div>
                <div class="quality-size-text">${q.size.formatted_size}</div>
                <div class="quality-bitrate-text">${q.size.bitrate_mbps.toFixed(2)} Mbps</div>
            `;

            card.addEventListener("click", () => {
                document.querySelectorAll(".quality-card").forEach(c => c.classList.remove("selected"));
                card.classList.add("selected");
                selectedQuality = q;
                checkSelectedQualitySpace();
            });

            qualitiesGrid.appendChild(card);
        });

        videoDetailsSection.classList.remove("hidden");
        checkSelectedQualitySpace();
        // studio:chat-live-button - show ● Чат for live streams (chat_recorder backend)
        setupChatButton(data);
    }

    // studio:chat-live-button - minimal live chat recorder UI
    let _chatRecId = null, _chatPoll = null;
    function setupChatButton(data) {
        let row = document.getElementById("chatRecRow");
        const isLive = !!(data && (data.is_live || data.slug && !data.uuid));
        // remove old row if not live anymore
        if (!isLive && row) { row.remove(); return; }
        if (!isLive) return;
        // find slug from probe data or url
        const slug = (data.slug || (data.url ? (data.url.match(/kick\.com\/([^\/]+)/i) || [])[1] : "" ) || "").replace(/\/.*/, "");
        if (!slug) return;
        if (!row) {
            row = document.createElement("div");
            row.id = "chatRecRow";
            row.style.cssText = "display:flex;align-items:center;gap:8px;margin:10px 0;padding:8px 10px;background:#0f1419;border:1px solid #1f2a33;border-radius:8px;font:13px system-ui;";
            const anchor = document.getElementById("startDownloadBtn");
            if (anchor && anchor.parentElement) anchor.parentElement.insertBefore(row, anchor);
            else if (videoDetailsSection) videoDetailsSection.appendChild(row);
        }
        if (_chatRecId) {
            row.innerHTML = '<span style="color:#e11">● REC</span> <span id="chatRecInfo">запись чата...</span> <button id="chatStopBtn" style="margin-left:auto" class="btn-sm btn-secondary">Стоп</button>';
            const stopBtn = document.getElementById("chatStopBtn");
            if (stopBtn) stopBtn.onclick = async function() {
                try { await fetch("/api/studio/chat/stop", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({id: _chatRecId})}); } catch(e){}
                _chatRecId = null;
                if (_chatPoll) { clearInterval(_chatPoll); _chatPoll = null; }
                setupChatButton(data);
                showToast("Запись чата остановлена", "info");
            };
            return;
        }
        const chatInfo = data.chatroom_id ? "чат доступен" : "чат канала";
        row.innerHTML = '<button id="chatRecBtn" class="btn-sm btn-accent" title="Запись чата live-эфира в JSONL для автопоиска моментов">● Чат — запись</button> <span style="color:#8a9bb0;font-size:12px">' + chatInfo + '</span> <span id="chatRecStatus" style="margin-left:auto;color:#5a6a7a;font-size:12px"></span>';
        const btn = document.getElementById("chatRecBtn");
        if (btn) btn.onclick = async function() {
            btn.disabled = true; btn.textContent = "● ...";
            try {
                const r = await fetch("/api/studio/chat/record", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({channel: slug})});
                const j = await r.json();
                if (!r.ok) throw new Error(j.detail || r.statusText);
                _chatRecId = j.id;
                showToast("Запись чата: " + (j.file || j.id), "ok");
                setupChatButton(data);
                // poll status for message count
                _chatPoll = setInterval(async function(){
                    try {
                        const rs = await fetch("/api/studio/chat/status"); const js = await rs.json();
                        const rec = (js.recordings || []).find(function(x){ return x.id === _chatRecId; });
                        const el = document.getElementById("chatRecInfo");
                        if (el && rec) el.textContent = (rec.messages || 0) + " сообщ. · " + (rec.file || "");
                        if (!rec) { clearInterval(_chatPoll); _chatPoll = null; _chatRecId = null; setupChatButton(data); }
                    } catch(e){}
                }, 2500);
            } catch(e) { showToast("Чат: " + e.message, "err"); btn.disabled = false; btn.textContent = "● Чат — запись"; }
        };
    }

    // Space check: the SAME rule as the server (peak x2 + 5%), so the button
    // state never contradicts /api/start-download.
    function checkSelectedQualitySpace() {
        if (!selectedQuality || !currentDiskInfo) return;

        updateDownloadBtnLabel();

        const reqBytes = getEffectiveRequiredBytes();
        const needBytes = peakNeedBytes(reqBytes);
        const totalBytes = currentDiskInfo.total_bytes;
        const freeBytes = currentDiskInfo.free_bytes;
        const usedBytes = currentDiskInfo.used_bytes;

        const isEnough = freeBytes >= needBytes;
        const shortage = Math.max(0, needBytes - freeBytes);

        // Update Disk Usage Bar (the bar shows the final file; the peak is in the hint)
        const usedPct = (usedBytes / totalBytes) * 100;
        const reqPct = Math.min((reqBytes / totalBytes) * 100, 100 - usedPct);

        storageUsedSegment.style.width = `${usedPct}%`;
        storageRequiredSegment.style.width = `${reqPct}%`;

        if (!isEnough) {
            storageRequiredSegment.classList.add("overflow");
            legendRequiredDot.classList.add("overflow");
        } else {
            storageRequiredSegment.classList.remove("overflow");
            legendRequiredDot.classList.remove("overflow");
        }

        legendUsedSize.textContent = currentDiskInfo.used_formatted;
        legendRequiredSize.textContent = formatBytesJs(reqBytes);

        if (isEnough) {
            const remaining = freeBytes - reqBytes;
            legendRemainingSize.textContent = formatBytesJs(remaining);
            spaceAlertBox.classList.add("hidden");
            startDownloadBtn.disabled = false;
            startDownloadBtn.style.opacity = "1";
            startDownloadBtn.title = `Начать скачивание (на пике сборки нужно ${formatBytesJs(needBytes)})`;
            // restore normal label when enough space after previous shortage
            updateDownloadBtnLabel();
        } else {
            legendRemainingSize.textContent = "0 B (Недостаточно!)";
            alertReq.textContent = `${formatBytesJs(reqBytes)} (на пике сборки ${formatBytesJs(needBytes)})`;
            alertFree.textContent = currentDiskInfo.free_formatted;
            alertDrive.textContent = currentDiskInfo.drive;
            alertShortage.textContent = formatBytesJs(shortage);
            spaceAlertBox.classList.remove("hidden");

            startDownloadBtn.disabled = true;
            startDownloadBtn.style.opacity = "0.4";
            startDownloadBtn.title = `Необходимо освободить как минимум ${formatBytesJs(shortage)}`;
            // studio:disk-peak-label - the blocked button itself must read "на пике сборки нужно ..."
            if (downloadBtnText) {
                downloadBtnText.textContent = `На пике сборки нужно ${formatBytesJs(needBytes)} — свободно ${currentDiskInfo.free_formatted}`;
            }
        }
    }

    function formatBytesJs(bytes) {
        if (bytes <= 0) return "0 B";
        const units = ["B", "KB", "MB", "GB", "TB"];
        const i = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
        const val = bytes / Math.pow(1024, i);
        return `${val.toFixed(2)} ${units[i]}`;
    }

    function detailMessage(detail, fallback) {
        if (!detail) return fallback;
        if (typeof detail === "string") return detail;
        if (Array.isArray(detail)) return detail.map(x => (x && x.msg) ? x.msg : String(x)).join("; ");
        if (typeof detail === "object" && detail.message) return detail.message;
        try { return JSON.stringify(detail); } catch (e) { return fallback; }
    }

    // Download range mode switcher + fragment inputs
    function initDownloadRange() {
        const seg = document.getElementById("dlModeSeg");
        const fragRow = document.getElementById("dlFragmentRow");
        const fragHint = document.getElementById("dlFragmentHint");
        const startInput = document.getElementById("dlStartInput");
        const endInput = document.getElementById("dlEndInput");
        const previewBtn = document.getElementById("dlPreviewRangeBtn");
        if (!seg) return;

        seg.querySelectorAll(".seg-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                seg.querySelectorAll(".seg-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                dlMode = btn.dataset.mode || "full";
                if (fragRow) fragRow.classList.toggle("hidden", dlMode !== "fragment");
                if (fragHint) fragHint.classList.toggle("hidden", dlMode !== "fragment");
                if (dlMode === "fragment" && currentVideoData && currentVideoData.duration) {
                    if (startInput && !startInput.value) startInput.value = "00:00";
                    if (endInput && !endInput.value) endInput.value = formatMmSs(Math.min(60, currentVideoData.duration));
                }
                checkSelectedQualitySpace();
            });
        });

        [startInput, endInput].forEach(inp => {
            if (inp) inp.addEventListener("input", checkSelectedQualitySpace);
        });

        if (previewBtn) previewBtn.addEventListener("click", () => {
            const r = getFragmentRange();
            if (!r) {
                showToast("Укажите корректный диапазон: начало раньше конца, формат ММ:СС.", "info");
                return;
            }
            const bytes = getEffectiveRequiredBytes();
            if (fragHint) {
                fragHint.textContent = `Фрагмент ${formatMmSs(r.start)}–${formatMmSs(r.end)} (${formatMmSs(r.end - r.start)}) ≈ ${formatBytesJs(bytes)}. Скачается только этот отрезок.`;
                fragHint.classList.remove("hidden");
            }
        });
    }
    initDownloadRange();

    // Start Download
    startDownloadBtn.addEventListener("click", async () => {
        if (!selectedQuality || !currentVideoData) return;

        let range = null;
        if (dlMode === "fragment") {
            range = getFragmentRange();
            if (!range) {
                showToast("Укажите корректный диапазон фрагмента: начало раньше конца.", "info");
                return;
            }
        }

        startDownloadBtn.disabled = true;

        try {
            const payload = {
                url: currentVideoData.url,
                playlist_url: selectedQuality.playlist_url,
                quality_label: selectedQuality.label,
                title: currentVideoData.title,
                streamer: currentVideoData.streamer,
                required_bytes: getEffectiveRequiredBytes()
            };
            if (range) {
                payload.start_time = range.start;
                payload.end_time = range.end;
            }

            const res = await fetch("/api/start-download", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                let err = {};
                try { err = await res.json(); } catch (e) { err = {}; }
                const d = err.detail;
                if (d && typeof d === "object" && (d.error === "INSUFFICIENT_SPACE" || d.status === "INSUFFICIENT_SPACE")) {
                    await fetchDiskInfo();
                    checkSelectedQualitySpace();
                    showToast(d.message || "Недостаточно места на диске для скачивания.", "err");
                    return;
                }
                throw new Error(detailMessage(d, `Не удалось начать скачивание (HTTP ${res.status})`));
            }

            // Show Progress Section
            progressSection.classList.remove("hidden");
            listenToProgress();
        } catch (err) {
            showToast("Ошибка старта: " + err.message, "err");
            startDownloadBtn.disabled = false;
            checkSelectedQualitySpace();
        }
    });

    // Listen to SSE progress (reconnects with backoff when the browser gives up,
    // e.g. after a backend restart; stops once the download reached a final state)
    function listenToProgress() {
        progressFinished = false;
        progressRetryDelay = 1000;
        openProgressStream();
    }

    function openProgressStream() {
        if (progressRetryTimer) { clearTimeout(progressRetryTimer); progressRetryTimer = null; }
        if (eventSource) {
            eventSource.close();
        }

        eventSource = new EventSource("/api/progress");

        eventSource.onopen = () => { progressRetryDelay = 1000; };

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                updateProgressUI(data);
            } catch (e) {
                console.error("SSE parse error:", e);
            }
        };

        eventSource.onerror = () => {
            if (progressFinished) return;
            // CONNECTING = the browser retries by itself; CLOSED = it gave up
            if (eventSource && eventSource.readyState === EventSource.CLOSED) {
                eventSource.close();
                eventSource = null;
                console.warn(`SSE closed, reconnecting in ${progressRetryDelay} ms`);
                progressRetryTimer = setTimeout(openProgressStream, progressRetryDelay);
                progressRetryDelay = Math.min(15000, progressRetryDelay * 2);
            }
        };
    }

    function finishProgress() {
        progressFinished = true;
        if (progressRetryTimer) { clearTimeout(progressRetryTimer); progressRetryTimer = null; }
        if (eventSource) { eventSource.close(); eventSource = null; }
    }

    function updateProgressUI(data) {
        if (!data || data.status === "idle") return;
        if (progressFinished) return;      // a reconnect must not replay the final state

        const pct = data.percent || 0;
        progressFill.style.width = `${pct}%`;
        percentVal.textContent = `${Math.round(pct)}%`;

        speedVal.textContent = data.speed_formatted || "0 MB/s";
        etaVal.textContent = `Осталось: ${data.eta_formatted || "--:--"}`;
        segmentsVal.textContent = `Сегменты: ${data.completed_segments || 0} / ${data.total_segments || 0}`;
        bytesVal.textContent = `${data.downloaded_formatted || "0 B"} / ${data.total_formatted || "0 B"}`;

        if (data.status === "downloading") {
            statusPill.textContent = "Загрузка";
            statusPill.style.background = "var(--kick-green-dim)";
            statusPill.style.color = "var(--kick-green)";
            statusMessage.textContent = data.message || "Скачивание HLS сегментов...";
        } else if (data.status === "merging") {
            statusPill.textContent = "Сборка MP4";
            statusPill.style.background = "rgba(245, 158, 11, 0.2)";
            statusPill.style.color = "var(--warning)";
            statusMessage.textContent = data.message || "Конкатенация и создание MP4 через FFmpeg...";
        } else if (data.status === "completed") {
            statusPill.textContent = "Готово!";
            statusPill.style.background = "rgba(8, 185, 255, 0.3)";
            statusPill.style.color = "var(--kick-green)";
            statusMessage.innerHTML = `<strong>Готово!</strong> ${data.message}`;
            cancelDownloadBtn.style.display = "none";
            startDownloadBtn.disabled = false;
            finishProgress();

            // CRITICAL INTEGRATION: Notify Studio and auto-register in Media Library!
            if (window.Studio && window.Studio.onKickDownloadCompleted) {
                window.Studio.onKickDownloadCompleted(data.output_file, data.title, data.quality_label);
            }
        } else if (data.status === "error") {
            statusPill.textContent = "Ошибка";
            statusPill.style.background = "var(--danger-bg)";
            statusPill.style.color = "var(--danger)";
            statusMessage.textContent = data.message || "Произошла ошибка при загрузке.";
            startDownloadBtn.disabled = false;
            finishProgress();
        } else if (data.status === "cancelled") {
            statusPill.textContent = "Отменено";
            statusPill.style.background = "rgba(255, 255, 255, 0.1)";
            statusPill.style.color = "#fff";
            statusMessage.textContent = "Загрузка была прервана пользователем.";
            startDownloadBtn.disabled = false;
            finishProgress();
        }
    }

    // Cancel Download
    cancelDownloadBtn.addEventListener("click", async () => {
        const ok = await showConfirm("Отменить скачивание видео?", "Отменить");
        if (!ok) return;
        try {
            await fetch("/api/cancel-download", { method: "POST" });
        } catch (e) {
            console.error("Ошибка отмены:", e);
        }
    });

    // Open Downloads Folder
    if (openFolderBtn) {
        openFolderBtn.addEventListener("click", async () => {
            try {
                await fetch("/api/open-folder", { method: "POST" });
            } catch (e) {
                console.error("Ошибка открытия папки:", e);
            }
        });
    }
});
