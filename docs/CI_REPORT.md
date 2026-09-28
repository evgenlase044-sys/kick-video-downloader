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

web/editor.js: {'already': 6}
  already  tdz-declare-early            marker present
  already  tdz-drop-late                marker present
  already  queue-sse-reconnect          marker present
  already  addfx-v2                     marker present
  already  addfx-source                 marker present
  already  flash-fxpeak                 marker present

web/index.html: {'skipped': 2, 'already': 3}
  skipped  drop-dead-exporter           guard declined
  already  timeremap-script             marker present
  skipped  effects-script               guard declined
  already  moments-panel                marker present
  already  overlay-export               marker present
```

# CI report (2026-09-28T05:30:01Z, f41e3b1)

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

web/editor.js: {'already': 6}
  already  tdz-declare-early            marker present
  already  tdz-drop-late                marker present
  already  queue-sse-reconnect          marker present
  already  addfx-v2                     marker present
  already  addfx-source                 marker present
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
test_fallback_to_ass_when_overlay_fails (studio.tests.test_export_pipeline.ExportWrapperTest.test_fallback_to_ass_when_overlay_fails) ... [studio] canvas text layer failed (overlay ffmpeg rc=254: [concat @ 0x560401927680] Impossible to open '/tmp/tmp8ejhraht/ovjob/000000.png'
[in#1 @ 0x56040191cdc0] Error opening input: No such file or directory
Error opening input file /tmp/tmp8ejhraht/ovjob/list.ffconcat.
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
Ran 35 tests in 9.262s

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

## Probe

#### editor.js from studio:addfx-v2 to EOF
```
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

    document.addEventListener("studio:template-plan", (e) => {
        const plan = e.detail;
        if (plan && Array.isArray(plan.fx) && plan.fx.length) {
            const base = (plan.moment && typeof plan.moment.start === "number") ? plan.moment.start : state.currentTime;
            const added = window.studioAddFx(plan.fx, base, { timeBase: "source" });  // studio:addfx-source
            if (added) showToast(`Шаблон «${plan.template || ""}»: добавлено ${added} эффектов на таймлайн`, "ok");
        }
    });

})();

```

#### editor.js flash hotkey
```
225:                addEffectAtPlayhead("flash", col, { duration: 0.18, peak: 0.95, fxPeak: 0.95, fxSound: "impact_epic" });  // studio:flash-fxpeak
```

#### editor.js addFxClip head
```
    function addFxClip(kind, color) {
        const tid = ensureFxTrack();
        ensureTracksInitialized();
        const fxKind = kind || "flash";
        const fxColor = fxKind === "flash" ? (color || "white") : (color || "white");
        const dur = fxKind === "flash" ? 0.6 : (fxKind === "bars" ? 1.8 : 1.2);
        const c = {
            id: "fx_" + Date.now().toString(36),
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
    // «+Текст»: свободный текстовый элемент (не субтитры) с полными параметрами;
    // живёт на текстовом слое, но его можно перетащить на любой другой слой
    function addTextClip() {
        ensureTracksInitialized();
        let tid = textTrackId();
```

#### server.py check_disk
```
def check_disk(req: CheckDiskRequest):
    """
    Check if disk has enough free space for the requested size.
    Returns status, shortage, and clear messages if space is insufficient.
    """
    return disk_manager.check_space(req.required_bytes, peak_factor=_studio.DOWNLOAD_PEAK_FACTOR)  # studio:check-disk-peak

@app.post("/api/probe")
```

#### server.py __main__
```
if __name__ == "__main__":
    # studio:main-secure - hardened server (127.0.0.1 + token + Host/Origin checks +
    # export pipeline). The old unprotected server: KICK_LEGACY_SERVER=1 python server.py
    if os.environ.get("KICK_LEGACY_SERVER") == "1":
        run_server()
    else:
        import studio_server
        sys.exit(studio_server.main())
```
