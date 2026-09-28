"""Anchored fixes for web/editor.js and web/index.html."""
from studio.patching import Patch

# PR #7: template/moment fx. The first version built fx clips by hand:
# shake got fxAmp = 16*100 = 1600 and fxPeak = 16, fxFreq was ignored, the
# moment's SOURCE time was used as TIMELINE time, and the clips went to a
# different track than the hotkeys. Now every fx goes through the same
# builder as the hotkeys (addEffectAtPlayhead) with per-kind fields.
ADDFX_V2 = r'''    // studio:addfx-v2 - template/moment fx go through the SAME builder as the
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
                const before = (state.tracks[tidOfFx()] || []).length;
                state.currentTime = Math.max(0, base + s);
                addEffectAtPlayhead(kind, f.color || "white", ov);
                if ((state.tracks[tidOfFx()] || []).length > before) added++;
            }
        } finally {
            state.currentTime = savedTime;
        }
        const fxTid = tidOfFx();
        if (state.tracks[fxTid]) state.tracks[fxTid].sort((a, b) => a.startTime - b.startTime);
        recalcTotalDuration();
        renderTimeline();
        syncVideoToCurrentTime();
        saveProject();
        return added;
    };

'''

EDITOR_PATCHES = [
    # §1 TDZ: exportPackBtn read before `const exportPackBtn` -> export init died
    Patch(id="tdz-declare-early", group="tdz",
          old="        const queueExportBtn = document.createElement(\"button\");\n",
          new=("        // studio:tdz-exportPackBtn - declared before its first use\n"
               "        const exportPackBtn = document.getElementById(\"exportPackBtn\");\n"
               "        const queueExportBtn = document.createElement(\"button\");\n"),
          marker="studio:tdz-exportPackBtn"),
    Patch(id="tdz-drop-late", group="tdz",
          old=("        const addHighlightBtn = document.getElementById(\"addHighlightToPackBtn\");\n"
               "        const exportPackBtn = document.getElementById(\"exportPackBtn\");\n"),
          new=("        const addHighlightBtn = document.getElementById(\"addHighlightToPackBtn\");\n"
               "        // (exportPackBtn is declared above - studio:tdz-late-removed)\n"),
          marker="studio:tdz-late-removed"),
    Patch(id="queue-sse-reconnect", required=False,
          old=("            queueES.onerror = () => {\n"
               "                if (queueES) { queueES.close(); queueES = null; }\n"
               "            };\n"),
          new=("            queueES.onerror = () => {\n"
               "                // studio:queue-sse-reconnect\n"
               "                if (queueES) { queueES.close(); queueES = null; }\n"
               "                setTimeout(() => {\n"
               "                    fetch(\"/api/export-queue/status\").then(r => r.json()).then(st => {\n"
               "                        if (st && st.running && !queueES) listenExportQueue();\n"
               "                    }).catch(() => {});\n"
               "                }, 1500);\n"
               "            };\n"),
          marker="studio:queue-sse-reconnect"),
    # PR #7: template fx builder (see ADDFX_V2)
    Patch(id="addfx-v2", group="addfx",
          start="    window.studioAddFx = function(fxList, baseTime = 0) {\n",
          end="    document.addEventListener(\"studio:template-plan\", (e) => {\n",
          new=ADDFX_V2, marker="studio:addfx-v2"),
    Patch(id="addfx-source", group="addfx",
          old=("            window.studioAddFx(plan.fx, base);\n"
               "            showToast(`Шаблон «${plan.template || \"\"}»: добавлено ${plan.fx.length} эффектов на таймлайн`, \"ok\");\n"),
          new=("            const added = window.studioAddFx(plan.fx, base, { timeBase: \"source\" });  // studio:addfx-source\n"
               "            if (added) showToast(`Шаблон «${plan.template || \"\"}»: добавлено ${added} эффектов на таймлайн`, \"ok\");\n"),
          marker="studio:addfx-source"),
    # PR #7: hotkey F wrote `peak`, every other path reads `fxPeak`
    Patch(id="flash-fxpeak", required=False,
          old="addEffectAtPlayhead(\"flash\", col, { duration: 0.18, peak: 0.95, fxSound: \"impact_epic\" });",
          new=("addEffectAtPlayhead(\"flash\", col, { duration: 0.18, peak: 0.95, fxPeak: 0.95, "
               "fxSound: \"impact_epic\" });  // studio:flash-fxpeak"),
          marker="studio:flash-fxpeak"),
]

INDEX_PATCHES = [
    # §2 unreachable browser exporter: frozen, not loaded
    Patch(id="drop-dead-exporter", required=False, regex=True, count=0,
          guard=lambda src: "core/render/exporter.js" in src,
          old=r"[ \t]*<script[^>]*src=[\"'][^\"']*core/render/exporter\.js[^\"']*[\"'][^>]*>\s*</script>[ \t]*\r?\n?",
          new=""),
    Patch(id="timeremap-script", required=False, regex=True, count=1,
          old=r"(?=<script[^>]*src=[\"'][^\"']*core/canvasMonitor\.js)",
          new="<script src=\"core/timeRemap.js\"></script><!-- studio:timeremap-script -->\n    ",
          marker="studio:timeremap-script"),
    # preview fx use the SAME zoom curve as the export (CoreEffects)
    Patch(id="effects-script", required=False, regex=True, count=1,
          guard=lambda src: "core/render/effects.js" not in src,
          old=r"(?=<script[^>]*src=[\"'][^\"']*core/canvasMonitor\.js)",
          new="<script src=\"core/render/effects.js\"></script><!-- studio:effects-script -->\n    ",
          marker="studio:effects-script"),
    # §6 moment finder + §7 templates panel
    Patch(id="moments-panel", required=False, regex=True, count=1,
          old=r"(?=</body>)",
          new="<script src=\"studio/moments.js\"></script><!-- studio:moments-panel -->\n",
          marker="studio:moments-panel"),
    # §2 one text renderer: canvas text layer for the export, key words, emoji,
    # export templates, Backspace guard (web/studio/overlay_export.js)
    Patch(id="overlay-export", required=False, regex=True, count=1,
          old=r"(?=</body>)",
          new="<script src=\"studio/overlay_export.js\"></script><!-- studio:overlay-export -->\n",
          marker="studio:overlay-export"),
]
