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

# CI report (2026-09-28T07:38:24Z, 694bb53)

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
test_fallback_to_ass_when_overlay_fails (studio.tests.test_export_pipeline.ExportWrapperTest.test_fallback_to_ass_when_overlay_fails) ... [studio] canvas text layer failed (overlay ffmpeg rc=254: [concat @ 0x564cb2ef3680] Impossible to open '/tmp/tmprfh_z58s/ovjob/000000.png'
[in#1 @ 0x564cb2ee8dc0] Error opening input: No such file or directory
Error opening input file /tmp/tmprfh_z58s/ovjob/list.ffconcat.
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
Ran 35 tests in 10.205s

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

# PROBE
FILE web/editor.js bytes=311483 crlf=false lines=6226

#### def collectRegionSubtitles (1)
```js  // line 3327
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
```

#### def collectRegionTextItems (1)
```js  // line 3377
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
```

#### def collectRegionFx (1)
```js  // line 3422
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
                    overlays.push({
                        start: Math.max(0, cs - r.startTime),
                        end: Math.min(r.duration, ce - r.startTime),
                        kind: c.fxKind || "flash",
                        color: c.fxColor || "white",
                        peak: c.fxPeak != null ? c.fxPeak : 0.75,
                        bar_h: c.fxBarH || 120,
                        amp: c.fxAmp || 12,
                        freq: c.fxFreq || 7,
                        z: zi
                    });
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
```

#### def requestServerPreviewFrame (1)
```js  // line 3943
    function requestServerPreviewFrame() {
        const img = document.getElementById("serverFrameImg");
        if (state.isPlaying) { hideServerPreviewFrame(); return; }
        const r = (state.regions || []).find(rg => state.currentTime >= rg.startTime && state.currentTime < rg.startTime + rg.duration);
        if (!r) { hideServerPreviewFrame(); return; }
        const mc = resolvePackSource(r.startTime);
        if (!mc || !mc.media) { hideServerPreviewFrame(); return; }
        if (pvTimer) clearTimeout(pvTimer);
        pvTimer = setTimeout(async () => {
            if (state.isPlaying) return;
            const subs = collectRegionSubtitles([r], [0]);
            const tis = collectRegionTextItems([r], [0]);
            const fx = collectRegionFx(r);
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
                if (!res.ok) return;
                const blob = await res.blob();
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
                    if (img.dataset.token === token) { img.src = url; img.style.display = "block"; }
                };
                img.dataset.token = url;
                probe.src = url;
            } catch (e) { /* превью не критично */ }
        }, 380);
    }
```

#### def tidOfFx (1)
```js  // line 5272
    function tidOfFx() {
        const order = trackOrder();
        for (const tid of order) {
            const tr = getTrack(tid);
            if (tr && tr.kind === "video") return tid;
        }
        return ensureFxTrack();
    }
```
#### initClipperPanel head
```
3069:    function initClipperPanel() {
    function initClipperPanel() {$
        // One-click TV presets (M-PM-:M-PM-0M-PM-: M-PM-2 M-PM-?M-QM-^@M-PM-8M-PM-<M-PM-5M-QM-^@M-PM-0M-QM-^E): M-PM-2M-QM-^KM-QM-^AM-QM-^BM-PM-0M-PM-2M-PM-;M-QM-^OM-QM-^NM-QM-^B M-QM-^DM-PM->M-QM-^@
        // + M-PM-1M-PM-5M-PM-;M-QM-^KM-PM-5 M-PM-2M-QM-^AM-PM-?M-QM-^KM-QM-^HM-PM-:M-PM-8 + M-PM-7M-PM-5M-PM-;M-QM-^QM-PM-=M-QM-^KM-PM-5 M-QM-^AM-QM-^CM-PM-1M-QM-^BM-PM-8M-QM-^BM-QM-^@M-QM-^K M-PM->M
        function syncTvPresetUI() {$
            const isSplit = state.clipper.format === "split_adhd"$
                && state.clipper.colorGrade === "tv" && !!state.clipper.flashCuts;$
            const isFull = state.clipper.format === "talking_head_9_16"$
                && state.clipper.colorGrade === "tv" && !!state.clipper.flashCuts;$
            const ps = document.getElementById("presetTvSplit");$
            const pf = document.getElementById("presetTvFull");$
            if (ps) ps.classList.toggle("active", isSplit);$
            if (pf) pf.classList.toggle("active", isFull);$
        }$
```
#### grep collectRegionSubtitles
```
3327:        function collectRegionSubtitles(regs, outBases) {
3563:                    subtitles: collectRegionSubtitles([r], outBases),
3953:            const subs = collectRegionSubtitles([r], [0]);
```
#### grep collectRegionTextItems
```
3377:        function collectRegionTextItems(regs, outBases) {
3564:                    text_items: collectRegionTextItems([r], outBases),
3954:            const tis = collectRegionTextItems([r], [0]);
```
#### grep collectRegionFx
```
3422:        function collectRegionFx(r) {
3552:                const fx = collectRegionFx(r);
3955:            const fx = collectRegionFx(r);
```
#### grep requestServerPreviewFrame
```
1748:        requestServerPreviewFrame();
3943:    function requestServerPreviewFrame() {
4024:                requestServerPreviewFrame();
```
#### grep tidOfFx
```
5272:    function tidOfFx() {
```
#### grep CoreTimeMap
```
```
#### grep faceAnchor
```
1842:            faceAnchor(baseClip, t) {
```
#### grep studioSourceToTimeline
```
6151:    function studioSourceToTimeline(srcT) {
6168:    window.studioSourceToTimeline = studioSourceToTimeline;
6175:            const mapped = studioSourceToTimeline(base);
```
#### grep anchor
```
2432:        const anchorSec = state.currentTime;
2433:        // Keep playhead anchored: measure before, restore after layout
2434:        const beforeLeft = anchorSec * state.zoom;
2441:            const target = Math.max(0, anchorSec * state.zoom - visW * 0.4);
3774:    // default aspect-matched region, anchored RIGHT (talking-head streams keep
5903:                    t_anchor: srcStart,
6149:    // -> fxPeak, shake -> fxAmp/fxFreq), anchor for the face zoom, and the
6199:                if (f.anchor) ov.anchor = f.anchor;
```
#### core files
```
web/core:
total 132
drwxr-xr-x 5 runner runner  4096 Sep 28 07:37 .
drwxr-xr-x 4 runner runner  4096 Sep 28 07:37 ..
-rw-r--r-- 1 runner runner 22400 Sep 28 07:37 canvasMonitor.js
-rw-r--r-- 1 runner runner  9037 Sep 28 07:37 composition.js
-rw-r--r-- 1 runner runner  5110 Sep 28 07:37 geometry.js
-rw-r--r-- 1 runner runner  3504 Sep 28 07:37 lut3d.js
drwxr-xr-x 2 runner runner  4096 Sep 28 07:37 mp4
drwxr-xr-x 2 runner runner  4096 Sep 28 07:37 render
-rw-r--r-- 1 runner runner 30406 Sep 28 07:37 selftest.js
-rw-r--r-- 1 runner runner  4228 Sep 28 07:37 selftest_audit.js
-rw-r--r-- 1 runner runner  2952 Sep 28 07:37 styles.json
drwxr-xr-x 2 runner runner  4096 Sep 28 07:37 text
-rw-r--r-- 1 runner runner  4100 Sep 28 07:37 timeMap.js
-rw-r--r-- 1 runner runner  1614 Sep 28 07:37 timeRemap.js
-rw-r--r-- 1 runner runner  6430 Sep 28 07:37 webcodecs.js

web/core/render:
total 112
drwxr-xr-x 2 runner runner  4096 Sep 28 07:37 .
drwxr-xr-x 5 runner runner  4096 Sep 28 07:37 ..
-rw-r--r-- 1 runner runner 16823 Sep 28 07:37 composer.js
-rw-r--r-- 1 runner runner  9472 Sep 28 07:37 effects.js
-rw-r--r-- 1 runner runner  9787 Sep 28 07:37 exporter.js
-rw-r--r-- 1 runner runner 16998 Sep 28 07:37 glPasses.js
-rw-r--r-- 1 runner runner  4246 Sep 28 07:37 gltest.html
-rw-r--r-- 1 runner runner   925 Sep 28 07:37 golden.json
-rw-r--r-- 1 runner runner 10764 Sep 28 07:37 grade.js
-rw-r--r-- 1 runner runner 10387 Sep 28 07:37 lens.js
-rw-r--r-- 1 runner runner  2231 Sep 28 07:37 yuv.js

web/studio:
total 44
drwxr-xr-x 2 runner runner  4096 Sep 28 07:37 .
drwxr-xr-x 4 runner runner  4096 Sep 28 07:37 ..
-rw-r--r-- 1 runner runner  6936 Sep 28 07:37 moments.js
-rw-r--r-- 1 runner runner 21737 Sep 28 07:37 overlay_export.js
-rw-r--r-- 1 runner runner  3692 Sep 28 07:37 selftest_overlay.js
```
#### grep CoreTimeMap / faceAnchor in web/core
```
web/core/canvasMonitor.js:17:    const TM = root.CoreTimeMap;
web/core/canvasMonitor.js:300:                else if (this.hooks.faceAnchor) {
web/core/canvasMonitor.js:301:                    const fa = this.hooks.faceAnchor(base, t);
web/core/render/effects.js:16:    const TM = (typeof CoreTimeMap !== "undefined") ? CoreTimeMap : require("../timeMap.js");
web/core/render/composer.js:14:    const TM = (typeof CoreTimeMap !== "undefined") ? CoreTimeMap : require("../timeMap.js");
web/core/render/lens.js:16:    const TM = (typeof CoreTimeMap !== "undefined") ? CoreTimeMap : require("../timeMap.js");
web/core/timeMap.js:7:    root.CoreTimeMap = mod;
web/core/composition.js:12:    const TM = (typeof CoreTimeMap !== "undefined") ? CoreTimeMap : require("./timeMap.js");
web/core/text/canvasText.js:22:    const TM = (typeof CoreTimeMap !== "undefined") ? CoreTimeMap : require("../timeMap.js");
```
#### grep glPasses/exporter.js
```
web/index.html:1348:    <script src="core/timeMap.js?v=1"></script>
web/core/render/exporter.js:1:/* Kick Clip Studio — web/core/render/exporter.js
web/core/render/effects.js:16:    const TM = (typeof CoreTimeMap !== "undefined") ? CoreTimeMap : require("../timeMap.js");
web/core/render/glPasses.js:1:/* Kick Clip Studio — web/core/render/glPasses.js
web/core/render/gltest.html:6:<script src="../timeMap.js"></script>
web/core/render/gltest.html:9:<script src="glPasses.js"></script>
web/core/render/composer.js:14:    const TM = (typeof CoreTimeMap !== "undefined") ? CoreTimeMap : require("../timeMap.js");
web/core/render/lens.js:16:    const TM = (typeof CoreTimeMap !== "undefined") ? CoreTimeMap : require("../timeMap.js");
web/core/timeMap.js:1:/* Kick Clip Studio — web/core/timeMap.js
web/core/composition.js:12:    const TM = (typeof CoreTimeMap !== "undefined") ? CoreTimeMap : require("./timeMap.js");
web/core/selftest.js:12:const TM = require("./timeMap.js");
web/core/text/canvasText.js:22:    const TM = (typeof CoreTimeMap !== "undefined") ? CoreTimeMap : require("../timeMap.js");
```
#### server.py _apply_fx_chain
```py
# line 3050
def _apply_fx_chain(filter_parts: List[str], curr_v: str, fx_list: List[FxOverlay],
                    out_w: int, out_h: int, total_dur: float, tag_prefix: str) -> str:
    """Burn FX overlay elements (flash / bars / shake) onto curr_v in order.
    Returns the new current video label. Shake uses lanczos to avoid blur;
    flash uses rapid attack and additive blend for authentic viral impact."""
    for fi, fx in enumerate(fx_list):
        try:
            s0 = max(0.0, float(fx.start))
            e0 = min(total_dur, float(fx.end))
        except (TypeError, ValueError):
            continue
        if not (e0 > s0 + 0.05):
            continue
        d = e0 - s0
        en = f"'between(t,{s0:.3f},{e0:.3f})'"
        if fx.kind == "shake":
            # N11: crop/scale geometry is applied CONSTANTLY (no enable) with an
            # amplitude envelope — output size never changes, so there is no
            # zoom pop at the enable boundaries.
            a = max(2, min(40, int(fx.amp or 10)))
            fq = max(2.0, min(15.0, float(fx.freq or 7.0)))
            env = f"min(1\\,max(0\\,min(t-{s0:.3f}\\,{e0:.3f}-t)/0.1))"
            filter_parts.append(
                f"{curr_v}split=2[{tag_prefix}v{fi}a][{tag_prefix}v{fi}b]"
            )
            filter_parts.append(
                f"[{tag_prefix}v{fi}b]crop=iw-{2*a}:ih-{2*a}:"
                f"x='{a}+{a}*sin(2*PI*{fq:.1f}*t)*{env}':y='{a}+{a}*cos(2*PI*{fq*9/7:.1f}*t)*{env}',"
                f"scale={out_w}:{out_h}:flags=lanczos+accurate_rnd[{tag_prefix}v{fi}s]"
            )
            filter_parts.append(f"[{tag_prefix}v{fi}a][{tag_prefix}v{fi}s]overlay=x=0:y=0[{tag_prefix}v{fi}]")
            curr_v = f"[{tag_prefix}v{fi}]"
        elif fx.kind == "zoom":
            # §15 zoom punch, transition path: constant overscan (N11) then an
            # animated crop window whose size follows the punch envelope.
            a = max(0.02, min(0.5, float(fx.peak if fx.peak and fx.peak < 1 else 0.15)))
            ov = 1 + 2 * a                       # constant overscan (no geometry pop)
            env = f"(1+{a:.4f}*(0.12+0.88*exp(-3*max(t-{s0:.3f}\\,0)/{max(1e-3, d):.3f}))*between(t,{s0:.3f},{e0:.3f}))"
            filter_parts.append(
                f"{curr_v}scale=ceil(iw*{ov:.4f}/2)*2:ceil(ih*{ov:.4f}/2)*2[{tag_prefix}v{fi}o]")
            filter_parts.append(
                f"[{tag_prefix}v{fi}o]crop=w='iw/{env}':h='ih/{env}':"
                f"x='(iw-iw/{env})/2':y='(ih-ih/{env})/2',"
                f"scale={out_w}:{out_h}:flags=lanczos+accurate_rnd[{tag_prefix}v{fi}]")
            curr_v = f"[{tag_prefix}v{fi}]"
        elif fx.kind == "lens":
            # §13.4: static barrel + CA on the interval (animation = new renderer)
            k1 = max(-0.45, min(0.45, float(fx.peak or 0.12)))
            k1s = str(k1)
            cx = 0.5 if fx.color in (None, "", "white") else 0.5
            filter_parts.append(
                f"{curr_v}lenscorrection=k1={k1s}:k2=0:cx=0.5:cy=0.5:enable={en}[{tag_prefix}v{fi}lc]")
            shift = max(1, int(round(abs(k1) * 12)))
            filter_parts.append(
                f"[{tag_prefix}v{fi}lc]rgbashift=rh={shift}:bh=-{shift}:enable={en}[{tag_prefix}v{fi}]")
            curr_v = f"[{tag_prefix}v{fi}]"
        elif fx.kind == "threshold":
            # §15 threshold hit: hard luma gate + noise dither, 1-2 frames
            th = int(16 + (fx.peak if fx.peak is not None else 0.45) * 219)
            filter_parts.append(
                f"{curr_v}lutyuv=y='if(gt(val,{th}),235,16)':u=128:v=128:"
                f"enable={en}[{tag_prefix}v{fi}]")
            curr_v = f"[{tag_prefix}v{fi}]"
        elif fx.kind == "whip":
            # §15 whip: horizontal displacement with a smoothstep ease via
            # animated crop-x (directional blur is new-renderer territory).
            dirn = 1 if (fx.color or "white") != "left" else -1
            BS = chr(92)
            prg = f"((t-{s0:.3f})/{max(1e-3, d):.3f})"
            pc = f"max(0{BS},min(1{BS},{prg}))"
            ease = f"({pc}*{pc}*(3-2*{pc}))"
            shift = f"{dirn}*0.25*iw*{ease}"  # studio:whip-clamp
            filter_parts.append(
                f"{curr_v}split=2[{tag_prefix}v{fi}a][{tag_prefix}v{fi}b]")
            filter_parts.append(
                f"[{tag_prefix}v{fi}b]scale=iw*2:ih,"
                f"crop=w=iw/2:h=ih:x='max(0{BS},min(iw/2{BS},(iw-iw/2)/2+({shift})))':y=0,"  # studio:whip-clamp-x
                f"scale={out_w}:{out_h}:flags=lanczos+accurate_rnd[{tag_prefix}v{fi}s]")
            filter_parts.append(
                f"[{tag_prefix}v{fi}a][{tag_prefix}v{fi}s]overlay=x=0:y=0:enable={en}[{tag_prefix}v{fi}]")
            curr_v = f"[{tag_prefix}v{fi}]"
        elif fx.kind in ("ramp", "freeze"):
            # time-remap lives in the new renderer (Composition §8.3); the
            # transition path logs and skips instead of producing garbage.
            # studio:fx-timeremap - rendered in the filtergraph (video only)
            _tr_parts, curr_v = _studio.fx_time_remap(fx.kind, curr_v, f"{tag_prefix}v{fi}", s0, e0)
            filter_parts.extend(_tr_parts)
        elif fx.kind == "bars":
            bh = max(20, min(out_h // 3, int(fx.bar_h or 120)))
            prog = f"min(1,min(t-{s0:.3f},{e0:.3f}-t)/0.35)"
            sh_amp, sh_f = 0, 7.0
            for sx in fx_list:
                if sx.kind != "shake":
                    continue
                try:
                    ss = max(0.0, float(sx.start)); se = min(total_dur, float(sx.end))
                except (TypeError, ValueError):
                    continue
                if ss < e0 and se > s0:
                    sh_amp = max(sh_amp, max(2, min(40, int(sx.amp or 10))))
                    sh_f = max(2.0, min(15.0, float(sx.freq or 7.0)))
            sh_y = (f"{sh_amp}*cos(2*PI*{sh_f*9/7:.1f}*t)*between(t,{s0:.3f},{e0:.3f})") if sh_amp else "0"
            filter_parts.append(f"color=c=black:s={out_w}x{bh}:d={d:.3f},format=rgba,setpts=PTS+{s0:.3f}/TB[{tag_prefix}c{fi}t]")
            filter_parts.append(f"color=c=black:s={out_w}x{bh}:d={d:.3f},format=rgba,setpts=PTS+{s0:.3f}/TB[{tag_prefix}c{fi}b]")
            filter_parts.append(
                f"{curr_v}[{tag_prefix}c{fi}t]overlay=x=0:y='-{bh}+{bh}*{prog}+{sh_y}':enable={en}[{tag_prefix}m{fi}]"
            )
            filter_parts.append(
                f"[{tag_prefix}m{fi}][{tag_prefix}c{fi}b]overlay=x=0:y='{out_h}-{bh}*{prog}+{sh_y}':enable={en}[{tag_prefix}v{fi}]"
            )
            curr_v = f"[{tag_prefix}v{fi}]"
        else:  # flash
            peak = max(0.2, min(1.0, float(fx.peak or 0.85)))
            f_in = min(0.04, d * 0.15)
            f_out = max(0.08, d - f_in)
            if (fx.color or "white") == "bw":
                filter_parts.append(f"{curr_v}split=2[{tag_prefix}v{fi}a][{tag_prefix}v{fi}b]")
                filter_parts.append(
                    f"[{tag_prefix}v{fi}b]hue=s=0,format=rgba,"
                    f"fade=t=in:st={s0:.3f}:d={f_in:.3f}:alpha=1,"
                    f"fade=t=out:st={s0+f_in:.3f}:d={f_out:.3f}:alpha=1,"
                    f"colorchannelmixer=aa={peak:g}[{tag_prefix}v{fi}g]"
                )
                filter_parts.append(f"[{tag_prefix}v{fi}a][{tag_prefix}v{fi}g]overlay=x=0:y=0:enable={en}[{tag_prefix}v{fi}]")
            else:
                # N10: screen blend in RGB against a clip-length source (no
                # full-length addition of U/V — no clipping, no colour shift).
                cmap = {"white": "white", "green": "0x39FF00", "red": "0xFF2222"}.get(fx.color or "white", "white")
                filter_parts.append(
                    f"color=c={cmap}:s={out_w}x{out_h}:d={d:.3f},format=rgba,"
                    f"fade=t=in:st=0:d={f_in:.3f}:alpha=1,"
                    f"fade=t=out:st={f_in:.3f}:d={f_out:.3f}:alpha=1,"
                    f"colorchannelmixer=aa={peak:g},"
                    f"setpts=PTS+{s0:.3f}/TB[{tag_prefix}c{fi}]"
                )
                filter_parts.append(f"{curr_v}format=gbrp[{tag_prefix}v{fi}rgb]")
                filter_parts.append(
                    f"[{tag_prefix}v{fi}rgb][{tag_prefix}c{fi}]blend=all_mode=screen:all_opacity=1:enable={en}[{tag_prefix}v{fi}]"
                )
            curr_v = f"[{tag_prefix}v{fi}]"
    return curr_v



```
#### grep server anchor / _tv_grade_parts / text_z
```
1226:    t_anchor: float                       # frame carrying the target box
1378:    """NCC template matching with subpixel peak, anchored template, lost state (§10.3).
1383:    template_t0 = None          # anchor template against drift
1465:                # template update anchored to the original (anti-drift).
1466:                # High gate (>0.92): a 0.5px anchor rounding offset makes
1475:                        anchor_ncc = float(cv2.matchTemplate(
1477:                        if anchor_ncc > 0.5:
1562:    """Plan §10.2/10.3: split [t_from, t_to] by anchor+manual keys, track each run."""
1566:        hard_keys.append((max(req.t_from, min(req.t_to, req.t_anchor)), req.target))
1587:        # for px/s velocity); manual/anchor keys are not smoothed.
1605:                    continue  # hard key wins over the run's re-anchored first frame
1640:        req.t_anchor = req.t_from
1651:    if req.t_anchor < req.t_from or req.t_anchor > req.t_to:
1652:        req.t_anchor = max(req.t_from, min(req.t_to, req.t_anchor))
2023:    text_z: Optional[int] = None
3029:def _tv_grade_parts(src: str, dst: str, is_vertical: bool = True) -> List[str]:
3307:def _export_layered_clip(clip, out_path: str, out_filename: str, timestamp_str: str, idx: int) -> Optional[Dict[str, Any]]:
3371:    text_z = clip.text_z if clip.text_z is not None else -1
3372:    fx_over_text = sorted([fx for fx in (clip.overlays or []) if (fx.z or 0) <= text_z],
3374:    fx_normal = [fx for fx in (clip.overlays or []) if (fx.z or 0) > text_z]
3387:                """Aspect-fill into tw_ x th_ using configured crop anchor."""
3466:                # vertical crop: right-anchored for top presets, centered otherwise
3569:        filter_parts.extend(_tv_grade_parts(comp, "[graded]", is_vertical=(out_w < out_h)))
3926:        # Default anchor: RIGHT-TOP (talking-head streams keep the face on the
4094:            filter_parts.extend(_tv_grade_parts(curr_v, "[graded]", is_vertical=(out_w < out_h)))
4446:            fp.extend(_tv_grade_parts(comp, "[graded]", is_vertical=(W < H)))
```
