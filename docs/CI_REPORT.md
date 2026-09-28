## Fold log
```

server.py: {'already': 27, 'skipped': 1}
  already  hooks-import                 marker present
  already  progress-nameerror           marker present
  already  cookies-range                marker present
  already  cookies-full                 marker present
  already  cookies-download             marker present
  already  ssrf-guard                   marker present
  already  ssrf-remember                marker present
  already  disk-peak                    marker present
  already  check-disk-peak              marker present
  already  fps-exact-init               marker present
  already  fps-exact-probe              marker present
  already  fps-exact-return             marker present
  already  asr-tempid                   marker present
  already  asr-shortwords               marker present
  already  no-abs-paths-file            marker present
  already  no-abs-paths-src             marker present
  already  import-guard                 marker present
  already  sfx-aliases                  marker present
  already  sfx-labels                   marker present
  already  queue-forward-ref            marker present
  already  queue-parse                  marker present
  already  ws-render                    marker present
  already  fx-timeremap                 marker present
  already  whip-clamp                   marker present
  already  whip-clamp-x                 marker present
  skipped  dead-ass-generator           guard declined
  already  version-mtime                marker present
  already  main-secure                  marker present

web/editor.js: {'already': 10}
  already  tdz-declare-early            marker present
  already  tdz-drop-late                marker present
  already  queue-sse-reconnect          marker present
  already  addfx-v2                     marker present
  already  addfx-source                 marker present
  already  addfx-count                  marker present
  already  addfx-fxtrack                marker present
  already  fx-add-identity              marker present
  already  fx-unique-id                 marker present
  already  flash-fxpeak                 marker present

web/index.html: {'skipped': 2, 'already': 3}
  skipped  drop-dead-exporter           guard declined
  already  timeremap-script             marker present
  skipped  effects-script               guard declined
  already  moments-panel                marker present
  already  overlay-export               marker present
```

# CI report (2026-09-28T07:41:10Z, 37fd8ac)

### ✅ python compile
```

```

### ✅ anchored patches (server.py / editor.js / index.html)
```

server.py: {'already': 27, 'skipped': 1}
  already  hooks-import                 marker present
  already  progress-nameerror           marker present
  already  cookies-range                marker present
  already  cookies-full                 marker present
  already  cookies-download             marker present
  already  ssrf-guard                   marker present
  already  ssrf-remember                marker present
  already  disk-peak                    marker present
  already  check-disk-peak              marker present
  already  fps-exact-init               marker present
  already  fps-exact-probe              marker present
  already  fps-exact-return             marker present
  already  asr-tempid                   marker present
  already  asr-shortwords               marker present
  already  no-abs-paths-file            marker present
  already  no-abs-paths-src             marker present
  already  import-guard                 marker present
  already  sfx-aliases                  marker present
  already  sfx-labels                   marker present
  already  queue-forward-ref            marker present
  already  queue-parse                  marker present
  already  ws-render                    marker present
  already  fx-timeremap                 marker present
  already  whip-clamp                   marker present
  already  whip-clamp-x                 marker present
  skipped  dead-ass-generator           guard declined
  already  version-mtime                marker present
  already  main-secure                  marker present

web/editor.js: {'already': 10}
  already  tdz-declare-early            marker present
  already  tdz-drop-late                marker present
  already  queue-sse-reconnect          marker present
  already  addfx-v2                     marker present
  already  addfx-source                 marker present
  already  addfx-count                  marker present
  already  addfx-fxtrack                marker present
  already  fx-add-identity              marker present
  already  fx-unique-id                 marker present
  already  flash-fxpeak                 marker present

web/index.html: {'skipped': 2, 'already': 3}
  skipped  drop-dead-exporter           guard declined
  already  timeremap-script             marker present
  skipped  effects-script               guard declined
  already  moments-panel                marker present
  already  overlay-export               marker present
```

### ✅ python regression tests
```
test_peak_and_safety (studio.tests.test_audit.DiskManagerTest.test_peak_and_safety) ... ok
test_server_patch_signature (studio.tests.test_audit.DiskManagerTest.test_server_patch_signature) ... ok
test_resume_key_stable_across_signed_urls (studio.tests.test_audit.DownloaderTest.test_resume_key_stable_across_signed_urls) ... ok
test_parse (studio.tests.test_audit.HlsParserTest.test_parse) ... ok
test_slice_validation (studio.tests.test_audit.HlsParserTest.test_slice_validation) ... ok
test_fps_exact (studio.tests.test_audit.HooksTest.test_fps_exact) ... ok
test_ramp_duration_preserving (studio.tests.test_audit.HooksTest.test_ramp_duration_preserving) ... ok
test_short_words_kept (studio.tests.test_audit.HooksTest.test_short_words_kept) ... ok
test_time_remap_filters (studio.tests.test_audit.HooksTest.test_time_remap_filters) ... ok
test_finds_injected_peak (studio.tests.test_audit.MomentsTest.test_finds_injected_peak) ... ok
test_llm_fallback (studio.tests.test_audit.MomentsTest.test_llm_fallback) ... ok
test_all_required_patches_apply (studio.tests.test_audit.PatchAnchorsTest.test_all_required_patches_apply) ... ok
test_header_limits_and_command (studio.tests.test_audit.RenderWsTest.test_header_limits_and_command) ... ok
test_paths_and_hosts (studio.tests.test_audit.SecurityTest.test_paths_and_hosts) ... ok
test_policy (studio.tests.test_audit.TemplatesTest.test_policy) ... ok
test_codec_block_replaced_and_input_tags_kept (studio.tests.test_export_pipeline.ArgvRewriteTest.test_codec_block_replaced_and_input_tags_kept) ... ok
test_export_encode_detected_only_in_export_dir (studio.tests.test_export_pipeline.ArgvRewriteTest.test_export_encode_detected_only_in_export_dir) ... ok
test_fps_override_and_ntsc (studio.tests.test_export_pipeline.ArgvRewriteTest.test_fps_override_and_ntsc) ... ok
test_intermediate_is_near_lossless (studio.tests.test_export_pipeline.ArgvRewriteTest.test_intermediate_is_near_lossless) ... ok
test_seek_audit (studio.tests.test_export_pipeline.ArgvRewriteTest.test_seek_audit) ... ok
test_canvas_layer_replaces_ass_text (studio.tests.test_export_pipeline.ExportWrapperTest.test_canvas_layer_replaces_ass_text) ... ok
test_fallback_to_ass_when_overlay_fails (studio.tests.test_export_pipeline.ExportWrapperTest.test_fallback_to_ass_when_overlay_fails) ... [studio] canvas text layer failed (overlay ffmpeg rc=254: [concat @ 0x55bfecbb1680] Impossible to open '/tmp/tmpqqndiokw/ovjob/000000.png'
[in#1 @ 0x55bfecba6dc0] Error opening input: No such file or directory
Error opening input file /tmp/tmpqqndiokw/ovjob/list.ffconcat.
Error opening input files: No such file or directory
), falling back to ASS
ok
test_multi_clip_split (studio.tests.test_export_pipeline.ExportWrapperTest.test_multi_clip_split) ... ok
test_passthrough_without_options (studio.tests.test_export_pipeline.ExportWrapperTest.test_passthrough_without_options) ... ok
test_grade_chain_runs (studio.tests.test_export_pipeline.GradeAndOverlayTest.test_grade_chain_runs) ... ok
test_header_validation (studio.tests.test_export_pipeline.GradeAndOverlayTest.test_header_validation) ... ok
test_overlay_lands_on_exact_frame (studio.tests.test_export_pipeline.GradeAndOverlayTest.test_overlay_lands_on_exact_frame) ... ok
test_export_wrapper_applies_gate_on_plain_exports (studio.tests.test_pr7.LoudnessGateTest.test_export_wrapper_applies_gate_on_plain_exports) ... ok
test_loud_clip_true_peak_limited (studio.tests.test_pr7.LoudnessGateTest.test_loud_clip_true_peak_limited) ... ok
test_no_audio_is_skipped (studio.tests.test_pr7.LoudnessGateTest.test_no_audio_is_skipped) ... ok
test_on_target_clip_untouched (studio.tests.test_pr7.LoudnessGateTest.test_on_target_clip_untouched) ... ok
test_quiet_clip_is_normalized_and_video_kept (studio.tests.test_pr7.LoudnessGateTest.test_quiet_clip_is_normalized_and_video_kept) ... ok
test_editor_patches (studio.tests.test_pr7.Pr7PatchesTest.test_editor_patches) ... ok
test_gl_lens_shader_has_no_debug_output (studio.tests.test_pr7.Pr7PatchesTest.test_gl_lens_shader_has_no_debug_output) ... ok
test_server_patches (studio.tests.test_pr7.Pr7PatchesTest.test_server_patches) ... ok

----------------------------------------------------------------------
Ran 35 tests in 9.748s

OK
```

### ✅ server imports with fixes (studio.loader)
```
[studio] server.py patches: {'already': 27, 'skipped': 1}
28 patches
```

### ✅ export pipeline installs into the real server
```
[studio] server.py patches: {'already': 27, 'skipped': 1}
[studio] export pipeline: {'grade': True, 'encoder_shim': True, 'export_route': True, 'loudness_gate': True}
{'grade': True, 'encoder_shim': True, 'export_route': True, 'loudness_gate': True}
```

### ✅ web core selftest
```
  PASS  pcg hash golden
  PASS  value noise golden
  PASS  jump-flood distance golden
  PASS  SDF stroke smoothstep golden
  PASS  Kawase energy preserved
  PASS  Kawase spreads the impulse
  PASS  glow alpha is ZERO when word opacity is 0
  PASS  glowAlpha = opacity^1.5 * amount
  PASS  zoom punch scale golden
  PASS  zoom punch peak = 1 + A*(1+overshoot)
  PASS  shake state golden (seed 7 @200ms)
  PASS  shake is zero after its duration (no permanent shake)
  PASS  shake constant overscan 1+2*amp/W (N11)
  PASS  BT.709 white = Y235 Cb128
  PASS  BT.709 black = Y16
  PASS  yuv420 plane sizes
  PASS  Y plane within 1 LSB of the BT.709 formula
  PASS  raw frame = w*h*1.5 bytes (WS protocol)

[шаг 3 lens & grade: k1=0 бит-в-бит, overscan, Viral Punch (§7.5)]
  PASS  k1=0: бит-в-бит равен входу (zero-lens == no-lens)
  PASS  auto-overscan: при k1>0 углы остаются в кадре
  PASS  lens bends symmetrically around the center
  PASS  Lens Punch starts and ends at zero
  PASS  Lens Punch k1 peaks ~0.18 near 80 ms
  PASS  bulge center invariant
  PASS  fisheye fov=0 identity
  PASS  wave A=0 identity
  PASS  twirl center invariant
  PASS  Viral Punch clipping < 0.5% of channels
  PASS  skin hue within ±10 degrees on all skin samples
  PASS  autoLevels expo = log2(0.40/p50)
  PASS  autoLevels expo clamped +1
  PASS  strength 0 = identity params
  PASS  strength 1 = full preset
  PASS  preset §14.5: viral_punch
  PASS  preset §14.5: teal_orange
  PASS  preset §14.5: night_neon
  PASS  preset §14.5: clean_natural
  PASS  preset §14.5: moody_film
  PASS  preset §14.5: bw_contrast
  PASS  preset §14.5: tv_acid
  PASS  lens preset §13.3: lens_punch
  PASS  lens preset §13.3: fisheye_hold
  PASS  lens preset §13.3: bulge_face
  PASS  lens preset §13.3: crispy
  PASS  lens preset §13.3: heat_wobble
  PASS  lens preset §13.3: crispy_lens
  PASS  Detail increases edge contrast (MTF50 up)

[шаг 4: fx композера §15 + time-remap (§7.3/§8.3)]
  PASS  zoom punch: scale > 1 inside the window
  PASS  zoom scale = 1 outside the window
  PASS  threshold hit active in its window
  PASS  threshold inactive outside
  PASS  freeze holds the source time
  PASS  ramp re-times the source (0.35x..1.8x)
  PASS  outside fx windows the timeline is untouched

ALL CORE SELFTESTS PASSED
```

### ✅ web audit selftest
```

[text layout: no lost words]
  PASS  every word lands on some page
  PASS  ≤2 rows per page
  PASS  page follows the active word
  PASS  short phrase: one page, full size
  PASS  layoutLines keeps all words
  PASS  UI id 'mrbeast' resolves to styles.json 'mrbeast_3d'
  PASS  text block clamped to the safe zone

[ramp: preview == export curve]
  PASS  composer ramp == timeRemap.js curve
  PASS  duration preserving: back in sync, no jump at the window end

[yuv420: true 2x2 chroma mean]
  PASS  U/V = mean of the 4 pixels

ALL AUDIT SELFTESTS PASSED
```

### ✅ overlay export selftest
```
overlay_export selftest: OK
```

### ✅ node --check web/editor.js
```

```

### ✅ node --check web/app.js
```

```

### ✅ node --check web/studio/moments.js
```

```

### ✅ node --check web/studio/overlay_export.js
```

```

### ✅ node --check web/core/canvasMonitor.js
```

```

### ✅ node --check web/core/text/canvasText.js
```

```

### ✅ node --check web/core/render/glPasses.js
```

```

# PROBE 2
FILE web/editor.js bytes=311483 crlf=false lines=6226

#### def ensureFxTrack (1)
```js  // line 5153
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
```

#### def addFxClip (1)
```js  // line 5351
    function addFxClip(kind, color) {
        const tid = ensureFxTrack();
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
```

#### def fxLabel (1)
```js  // line 5145
    function fxLabel(c) {
        if (!c || !c.isFx) return "";
        if (c.fxKind === "flash") return FX_LABEL["flash_" + (c.fxColor || "white")] || "⚡ Вспышка";
        return FX_LABEL[c.fxKind] || "FX";
    }
```

#### def resolvePackSource (1)
```js  // line 2623
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
```

#### def isTextClip (1)
```js  // line 1472
    function isTextClip(clip) {
        if (!clip) return false;
        if (clip.isFx) return false;
        if (clip.isText) return true;
        if (clip.media) return false;
        const t = getTrack(clip.trackId);
        return !!((t && t.kind === "text") && clip.title);
    }
```

#### def hideServerPreviewFrame (1)
```js  // line 3939
    function hideServerPreviewFrame() {
        const img = document.getElementById("serverFrameImg");
        if (img) img.style.display = "none";
    }
```

#### def trackPosAt (1)
```js  // line 1958
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
```
#### web/editor.js lines 3405-3424
```
3405|                        });
3406|                    });
3407|                }
3408|            }
3409|            return items;
3410|        }
3411|        function resolveRegionSource(r) {
3412|            const mc = resolvePackSource(r.startTime);
3413|            if (!mc || !mc.media) return null;
3414|            const a = convertTimelineToSourceTime(mc, r.startTime);
3415|            const b = convertTimelineToSourceTime(mc, r.startTime + r.duration);
3416|            if (!(b > a + 0.2)) return null;
3417|            return { mc, a, b };
3418|        }
3419|        // FX overlays + sounds + timeline audio mapped into one region's output.
3420|        // z = позиция слоя в trackList (0 = верхний): вспышка под верхними
3421|        // элементами НЕ действует на них (сервер жжёт её только под композитом)
3422|        function collectRegionFx(r) {
3423|            const overlays = [];
3424|            const sounds = [];
```
#### web/editor.js lines 3540-3580
```
3540|                // H1: субтитры живут на таймлайне — единый источник правды
3541|                subtitle_mode: "timeline"
3542|            };
3543|            // верхний слой с текстом: FX на треках выше него прожигаются ПОВЕРХ текста
3544|            const tz = trackOrder().findIndex(tid => (getTrack(tid) || {}).kind === "text");
3545|            // Источник — уже готовый шортс (вшиты субтитры и цветокор)?
3546|            // авто-детект ТОЛЬКО по нашим экспортным префиксам/суффиксам + ручной
3547|            // переключатель; обычные слова в имени файла (напр. «ГОТОВЫ») больше
3548|            // не отключают град и субтитры
3549|            const processedRe = /(?:^|[\\/])Short_[^\\/]*\.mp4$|[_-](?:processed|final)\.mp4$/i;
3550|            // Каждая нарезка — всегда отдельный файл (для этого они и размечаются)
3551|            const items = resolved.map(({ r, mc, a, b }) => {
3552|                const fx = collectRegionFx(r);
3553|                const lrs = collectRegionLayers(r);
3554|                const srcProcessed = !!state.clipper.srcProcessed ||
3555|                    !!(lrs.length && lrs[0].source_file && processedRe.test(lrs[0].source_file));
3556|                const outBases = [0];
3557|                return {
3558|                    id: "rg_" + r.id,
3559|                    title: r.name,
3560|                    source_file: mc.media.filename,
3561|                    start_time: a, end_time: b,
3562|                    segments: [{ start_time: a, end_time: b }],
3563|                    subtitles: collectRegionSubtitles([r], outBases),
3564|                    text_items: collectRegionTextItems([r], outBases),
3565|                    subs_in_output_time: true,
3566|                    layers: lrs,
3567|                    overlays: fx.overlays,
3568|                    sounds: fx.sounds,
3569|                    extra_audio: collectRegionAudio(r),
3570|                    skip_flash_at: [],
3571|                    text_z: tz >= 0 ? tz : null,
3572|                    src_processed: srcProcessed,
3573|                    ...common
3574|                };
3575|            });
3576|            return { items, skipped };
3577|        }
3578|        // §7.4/§7.6: очередь экспорта — пакет уходит в фон, редактор остаётся живым
3579|        // studio:tdz-exportPackBtn - declared before its first use
3580|        const exportPackBtn = document.getElementById("exportPackBtn");
```
#### web/editor.js lines 1740-1752
```
1740|    // Seek Playhead to precise time
1741|    function seekTo(timeSec) {
1742|        state.previewStopAt = null; // manual seek cancels moment preview
1743|        state.currentTime = Math.max(0, Math.min(state.totalDuration, timeSec));
1744|        updatePlayheadPosition();
1745|        updateTimecodeDisplays();
1746|        syncVideoToCurrentTime();
1747|        updateLiveSubtitleOverlay();
1748|        requestServerPreviewFrame();
1749|    }
1750|
1751|    function seekRelative(deltaSec) {
1752|        seekTo(state.currentTime + deltaSec);
```
#### web/editor.js lines 1800-1870
```
1800|            }).catch(() => {});
1801|        }
1802|        return __proxyCache.get(filename);       // may be null on first call (P0 meanwhile)
1803|    }
1804|
1805|    // ── §16 P0: canvas monitor — ONE canvas over the monitor, ONE hidden
1806|    // <video> per unique file, master-clock sync, canvas text (no CSS anims),
1807|    // WebGL2 grade with the own 65^3 LUT. Active for the 9:16 Shorts view. ──
1808|    function initCanvasMonitor() {
1809|        if (!window.CoreCanvasMonitor || !videoMonitor || window.__canvasMonitor) return;
1810|        const canvas = document.createElement("canvas");
1811|        canvas.id = "studioCanvasMonitor";
1812|        videoMonitor.appendChild(canvas);
1813|        const hooks = {
1814|            settings() {
1815|                return {
1816|                    enabled: state.aspectRatio === "9:16",
1817|                    playing: state.isPlaying,
1818|                    fps: state.previewFps || 60,
1819|                    format: state.clipper.format,
1820|                    cropBox: state.clipper.cropBox,
1821|                    bgBox: state.clipper.bgBox,
1822|                    topRatio: 0.45,
1823|                    barTop: Math.max(0, Math.min(640, parseInt(state.clipper.barTop, 10) || 0)),
1824|                    barBottom: Math.max(0, Math.min(640, parseInt(state.clipper.barBottom, 10) || 0)),
1825|                    gradeOn: state.clipper.colorGrade === "tv"
1826|                };
1827|            },
1828|            videoClips(t) {
1829|                // ALL active video layers, topmost first — no cap of 2 (§16.5)
1830|                const out = [];
1831|                for (const tid of videoTrackIds()) {
1832|                    const clip = activeClipOn(tid, t);
1833|                    if (clip) out.push(clip);
1834|                }
1835|                return out;
1836|            },
1837|            targetTime(clip, t) { return clipTargetTime(clip, t); },
1838|            pipBoxFor(clip) { return pipForClip(clip); },
1839|            trackBoxFor(clip, t) {
1840|                return clip.trackPath && clip.trackPath.length ? trackPosAt(clip, t) : null;
1841|            },
1842|            faceAnchor(baseClip, t) {
1843|                if (!baseClip) return null;
1844|                const box = baseClip.trackPath && baseClip.trackPath.length ? trackPosAt(baseClip, t) : null;
1845|                if (!box) return null;
1846|                return [box.x + box.w / 2, box.y + box.h / 2];
1847|            },
1848|            cueAt(t) {
1849|                const clip = currentCueClip(t);
1850|                if (!clip) return null;
1851|                const raw = Array.isArray(clip.words) && clip.words.length
1852|                    ? clip.words
1853|                    : [{ word: clip.title || "", abs_start: clip.startTime, abs_end: clip.startTime + clip.duration }];
1854|                const first = raw.length ? (raw[0].abs_start != null ? raw[0].abs_start : 0) : 0;
1855|                const words = raw.map(w => ({
1856|                    word: w.word || "",
1857|                    s: Math.max(0, (w.abs_start != null ? w.abs_start : first) - first),
1858|                    e: Math.max(0.05, (w.abs_end != null ? w.abs_end : (w.abs_start || first) + 0.3) - first),
1859|                    hot: !!w.hot,
1860|                    color: w.color || null
1861|                }));
1862|                const isSplit = state.clipper.format === "split_adhd";
1863|                return {
1864|                    words: words,
1865|                    end: Math.max(0.2, clip.duration),
1866|                    styleName: clip.subtitleStyle || state.clipper.subtitleTemplate || "acid",
1867|                    x: clip.textX != null ? clip.textX : 0.5,
1868|                    y: clip.textY != null ? clip.textY : (isSplit ? 0.225 : 0.68),
1869|                    localT: Math.max(0, t - clip.startTime),
1870|                    sizeRatio: 0.058 * (state.clipper.subSize || 1.0) * (isSplit ? 0.9 : 1.0)
```
#### web/editor.js lines 3930-3943
```
3930|        }
3931|        if (fallback) return fallback;
3932|        const cues = state.clipper.subtitles || [];
3933|        const cue = cues.find(x => t >= x.abs_start && t <= x.abs_end);
3934|        if (cue && cue.text) return { text: cue.text, template: state.clipper.subtitleTemplate };
3935|        return null;
3936|    }
3937|    // Серверный кадр превью: рендер тем же фильтр-графом, что и экспорт (WYSIWYG)
3938|    let pvTimer = null;
3939|    function hideServerPreviewFrame() {
3940|        const img = document.getElementById("serverFrameImg");
3941|        if (img) img.style.display = "none";
3942|    }
3943|    function requestServerPreviewFrame() {
```
#### web/editor.js lines 4015-4030
```
4015|                el.style.transform = "translate(-50%,-50%)";
4016|            };
4017|            const onUp = () => {
4018|                el.removeEventListener("pointermove", onMove);
4019|                el.removeEventListener("pointerup", onUp);
4020|                el.removeEventListener("pointercancel", onUp);
4021|                clip.textX = +lastX.toFixed(3);
4022|                clip.textY = +lastY.toFixed(3);
4023|                saveProject();
4024|                requestServerPreviewFrame();
4025|            };
4026|            el.addEventListener("pointermove", onMove);
4027|            el.addEventListener("pointerup", onUp);
4028|            el.addEventListener("pointercancel", onUp);
4029|        });
4030|    }
```
#### web/core/canvasMonitor.js lines 280-330
```
280|        w.fillStyle = "#000";
281|        w.fillRect(0, 0, outW, outH);
282|        if (!base || !base.media) {
283|            this._blit(s, null);
284|            return true;
285|        }
286|        // camera fx: shake + whip offsets, zoom/lens scale with anchor
287|        let shake = { dx: 0, dy: 0 };
288|        let scale = 1, anchor = { x: 0.5, y: 0.5 }, blurPx = 0, threshold = false;
289|        for (const f of fx) {
290|            const a0 = fxIn(f), a1 = fxOut(f);
291|            if (f.kind === "shake") {
292|                const a = (f.amp || 12) * (1080 / 608);
293|                const env = Math.max(0, Math.min(1, Math.min(t - a0, a1 - t) / 0.1));
294|                shake.dx += a * Math.sin(2 * Math.PI * (f.freq || 7) * t) * env;
295|                shake.dy += a * Math.cos(2 * Math.PI * (f.freq || 7) * 9 / 7 * t) * env;
296|            } else if (f.kind === "zoom") {
297|                const z = zoomScale(f, t);
298|                if (z > scale) scale = z;
299|                if (f.anchor) anchor = f.anchor;
300|                else if (this.hooks.faceAnchor) {
301|                    const fa = this.hooks.faceAnchor(base, t);
302|                    if (fa) anchor = fa;
303|                }
304|            } else if (f.kind === "lens") {
305|                const p = Math.max(0, Math.min(1, (t - a0) / Math.max(0.05, a1 - a0)));
306|                const bell = p > 0 ? Math.exp(-Math.pow((p - 0.32) / 0.35, 2)) : 0;
307|                scale = Math.max(scale, 1 + 0.5 * (f.amp != null ? f.amp : 0.18) * bell);
308|            } else if (f.kind === "threshold") {
309|                if (t >= a0 && t <= a1) threshold = true;
310|            } else if (f.kind === "whip") {
311|                const dur = Math.max(0.05, a1 - a0);
312|                const p = (t - a0) / dur;
313|                if (p >= 0 && p <= 1) {
314|                    const dir = f.color === "left" ? -1 : 1;
315|                    // same clamp as export (0.25*W): never slides the frame out
316|                    const e = p < 0.5 ? smoothstep(p * 2) : 1 - smoothstep((p - 0.5) * 2);
317|                    shake.dx += dir * 0.25 * outW * e;
318|                    blurPx = Math.max(blurPx, 18 * e);
319|                }
320|            }
321|        }
322|        w.save();
323|        if (scale !== 1) {
324|            const ax = anchor.x * outW, ay = anchor.y * outH;
325|            w.translate(ax, ay);
326|            w.scale(scale, scale);
327|            w.translate(-ax, -ay);
328|        }
329|        w.translate(shake.dx, shake.dy);
330|
```
#### grep pvTimer / token in editor
```
3938:    let pvTimer = null;
3950:        if (pvTimer) clearTimeout(pvTimer);
3951:        pvTimer = setTimeout(async () => {
3982:                    if (img.dataset.token === token) { img.src = url; img.style.display = "block"; }
3984:                img.dataset.token = url;
```
#### grep lensPunch in lens.js
```
7: * Presets §13.3: Lens Punch (animated), Fisheye Hold, Bulge Face, Crispy,
10:(function (root, factory) {
14:})(typeof self !== "undefined" ? self : this, function () {
20:    function lensMap(u, v, p) {
35:    function fisheyeMap(u, v, p) {
54:    function bulgeMap(u, v, p) {
77:    function caOffsets(u, v, p) {
88:    function waveMap(u, v, p, t) {
95:    function twirlMap(u, v, p) {
110:    function mapPoint(u, v, params, t) {
125:    function cx_(q, k, u0, p) {
132:    function sampleColor(srcFn, u, v, params, t) {
141:    function gauss1d(sigma) {
151:    function _sepBlur(plane, W, H, sigma) {
179:    function applyDetail(luma, W, H, opts) {
194:        lens_punch: { k1: 0.18, k2: 0, ca: 3, W: 1080, cx: 0.5, cy: 0.5,
203:    /** Lens Punch animation (§13.3): k1 0->0.18->0 (snap, peak @80 ms), CA 0->3->0. */
204:    function lensPunch(t, opts) {
214:            .zoomPunch(t, { A: 0.12, overshoot: 0.18, settleMs: 250, at: at });
236:        lensPunch: lensPunch, LENS_GLSL: LENS_GLSL
```
FILE web/core/render/lens.js bytes=10387 crlf=false lines=239

#### def lensPunchK1 (0)

#### def punchK1 (0)

#### def lensPunch (1)
```js  // line 204
    function lensPunch(t, opts) {
        const o = opts || {};
        const dur = (o.durMs || 250) / 1000;
        const at = o.at || 0;
        const p = Math.max(0, Math.min(1, (t - at) / dur));
        if (p <= 0) return { k1: 0, ca: 0, zoomScale: 1 };
        const env = TM.easeSnap(p);
        const peakT = (o.peakMs || 80) / 1000 / dur;
        const bell = Math.exp(-Math.pow((p - peakT) / 0.35, 2));
        const zp = (typeof CoreEffects !== "undefined" ? CoreEffects : require("./effects.js"))
            .zoomPunch(t, { A: 0.12, overshoot: 0.18, settleMs: 250, at: at });
        return {
            k1: (o.k1 != null ? o.k1 : 0.18) * bell,
            ca: (o.ca != null ? o.ca : 3) * bell,
            zoomScale: zp.scale
        };
    }
```
#### templates anchor
```
studio/templates.py:8:Zoom anchors on the tracked face when a track box is available.
studio/templates.py:74:    {kind, start, end, amp, anchor?, sfx?} in the editor's fx format."""
studio/templates.py:102:                fx["anchor"] = {"x": float(face.get("x", 0.5)), "y": float(face.get("y", 0.4))}
studio/__init__.py:4:  patching / server_patches / web_patches / loader  - anchored fixes for the
studio/export_pipeline.py:2:loaded server module at runtime (no anchors in server.py needed).
studio/ffmpeg_argv.py:4:single-pass loudnorm on the legacy path). Instead of anchoring patches in a
studio/loader.py:1:"""Load server.py with the anchored audit fixes applied and register it as
studio/patching.py:5:for those files is an anchored patch: exact text (or a start/end pair) that
studio/patching.py:8:* anchor found the expected number of times -> applied;
studio/patching.py:90:            return text, "failed", "start anchor not found"
studio/patching.py:92:            return text, "failed", "start anchor not unique"
studio/patching.py:95:            return text, "failed", "end anchor not found after start"
studio/patching.py:112:        return text, "failed", "anchor not found"
studio/patching.py:114:        return text, "failed", f"anchor found {n}x, expected {p.count}"
studio/templates.py:8:Zoom anchors on the tracked face when a track box is available.
studio/templates.py:74:    {kind, start, end, amp, anchor?, sfx?} in the editor's fx format."""
studio/templates.py:102:                fx["anchor"] = {"x": float(face.get("x", 0.5)), "y": float(face.get("y", 0.4))}
studio/web_patches.py:11:    // -> fxPeak, shake -> fxAmp/fxFreq), anchor for the face zoom, and the
studio/web_patches.py:61:                if (f.anchor) ov.anchor = f.anchor;
```
#### class FxOverlay
```py
# line 1935
class FxOverlay(BaseModel):
    start: float = 0.0           # output-time seconds
    end: float = 0.5
    kind: str = "flash"          # flash | bars | shake | zoom | lens | threshold | whip | ramp | freeze
    color: str = "white"         # white | green | red | bw
    peak: float = 0.75           # max opacity 0..1 (never fully covers)
    bar_h: int = 120             # cinebars height px (kind=bars)
    amp: int = 10                # shake amplitude px (kind=shake)
    z: int = 0                   # video-track index (0 = topmost track): the FX
                                 # affects only the composite built BELOW its track
    freq: float = 7.0            # shake frequency Hz (kind=shake)


```
#### class PreviewFrameRequest
```py
```
#### clip model around text_z
```py
2000|    color_grade: str = "none"            # none | tv
2001|    flash_cuts: bool = False             # soft white flash between segments
2002|    skip_flash_at: List[int] = []        # junction indices (0-based, between seg k and k+1) with hard cut
2003|    segments: Optional[List[ExportSegment]] = None  # None -> single [start_time, end_time]
2004|    crop_box: Optional[CropBox] = None   # webcam/face region (page-recording streams)
2005|    bg_box: Optional[CropBox] = None     # background/gameplay region for split bottom band
2006|    # Timeline FX (layer elements): overlays burned UNDER subtitles,
2007|    # synth/file sounds, timeline audio (music ducking, SFX)
2008|    overlays: List[FxOverlay] = []
2009|    sounds: List[FxSound] = []
2010|    extra_audio: List[TimelineAudioClip] = []
2011|    # Layered compositing: every video/image element from the timeline.
2012|    # When non-empty, takes priority over the single source_file pipeline.
2013|    layers: List[ExportLayer] = []
2014|    # Free text elements (AE-style): {text,start,end,font,size,color,glow,
2015|    # anim_in,anim_out,x,y,align,shake} — output-local seconds
2016|    text_items: List[Dict[str, Any]] = []
2017|    # subtitles already in output time (region pipeline) — skip re-mapping
2018|    subs_in_output_time: bool = False
2019|    # source is already a finished short (burned subs + grade): passthrough —
2020|    # do NOT re-grade and do NOT burn subtitles/text over it
2021|    src_processed: bool = False
2022|    # track index of the TOPMOST text layer: FX on tracks ABOVE it burn over text
2023|    text_z: Optional[int] = None
2024|    # highlight long "hot" keywords in an accent color (viral style)
2025|    hot_words: bool = False
2026|    # H1: single source of subtitles — "timeline" (text_items) | "generated"
2027|    # (subtitles field) | "none". Unset + both present -> HTTP 422.
2028|    subtitle_mode: Optional[str] = None
2029|    # Static cinematic frames (рамки) burned above FX, below subtitles (px)
2030|    bar_top: int = 0
2031|    bar_bottom: int = 0
2032|
2033|def _probe_duration(path: str) -> Optional[float]:
2034|    try:
2035|        r = subprocess.run(
```
#### _export_layered_clip text_z
```py
3360|    elif clip.crop_preset == "face":
3361|        crop_x = "(iw-ow)/2"
3362|        crop_y = "(ih-oh)/3"
3363|
3364|    bg_path = None
3365|    if clip.background_file:
3366|        bg_candidate = os.path.join(DOWNLOADS_DIR, os.path.basename(clip.background_file))
3367|        if os.path.exists(bg_candidate):
3368|            bg_path = bg_candidate
3369|
3370|    # FX on tracks ABOVE the topmost text layer burn OVER the text
3371|    text_z = clip.text_z if clip.text_z is not None else -1
3372|    fx_over_text = sorted([fx for fx in (clip.overlays or []) if (fx.z or 0) <= text_z],
3373|                          key=lambda fx: -(fx.z or 0))
3374|    fx_normal = [fx for fx in (clip.overlays or []) if (fx.z or 0) > text_z]
3375|
3376|    z_levels = sorted({L.z for L in layers}, reverse=True)  # deepest first
3377|    comp = None
3378|    for li, L in enumerate(layers):
3379|        is_base = li == 0
3380|        inputs.extend(["-ss", f"{max(0.0, L.src_offset):.3f}", "-t", f"{max(0.2, L.duration or total_dur):.3f}", "-i", L.source_file])
```
HIT 3029|def _tv_grade_parts(src: str, dst: str, is_vertical: bool = True) -> List[str]:
HIT 3050|def _apply_fx_chain(filter_parts: List[str], curr_v: str, fx_list: List[FxOverlay],
HIT 3540|            comp = _apply_fx_chain(filter_parts, comp, fx_here, out_w, out_h, total_dur, f"z{L.z}_")
HIT 3548|            comp = _apply_fx_chain(filter_parts, comp, fx_here, out_w, out_h, total_dur, f"z{z}_")
HIT 3628|        comp = _apply_fx_chain(filter_parts, comp, fx_over_text, out_w, out_h, total_dur, "otx_")
HIT 4116|        curr_v = _apply_fx_chain(filter_parts, curr_v, clip.overlays or [], out_w, out_h, total_dur, "fx")
HIT 4381|@app.post("/api/preview-frame")
HIT 4442|            comp = _apply_fx_chain(fp, comp, fx_list, W, H, 0.4, "pv_")
HIT 4506|        print(f"[preview-frame] error: {render_res.stderr[-400:] if render_res.stderr else 'unknown'}")
