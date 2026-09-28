## Fold log
```

server.py: {'already': 30, 'skipped': 1, 'applied': 6}
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
  already  fx-anchor-fields             marker present
  already  zoom-anim                    marker present
  already  lens-anim                    marker present
  applied  zoom-mblur                   1x
  applied  lens-v2                      replaced 1205 chars
  applied  whip-mblur                   1x
  applied  grade-bands-layered          1x
  applied  grade-bands-pack             1x
  applied  grade-bands-preview          1x
  -> written server.py

web/editor.js: {'already': 17}
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
  already  hoist-collectors-subs        replacement present
  already  hoist-collectors-text        replacement present
  already  hoist-collectors-fx          replacement present
  already  hoist-collectors-define      marker present
  already  preview-frame-v2             marker present
  already  face-anchor-norm             marker present
  already  drop-tidOfFx                 marker present

web/index.html: {'skipped': 2, 'already': 3}
  skipped  drop-dead-exporter           guard declined
  already  timeremap-script             marker present
  skipped  effects-script               guard declined
  already  moments-panel                marker present
  already  overlay-export               marker present
```

# CI report (2026-09-28T08:47:20Z, 56f444d)

### ✅ python compile
```

```

### ✅ anchored patches (server.py / editor.js / index.html)
```
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
  already  fx-anchor-fields             marker present
  already  zoom-anim                    marker present
  already  lens-anim                    marker present
  already  zoom-mblur                   marker present
  already  lens-v2                      marker present
  already  whip-mblur                   marker present
  already  grade-bands-layered          marker present
  already  grade-bands-pack             marker present
  already  grade-bands-preview          marker present

web/editor.js: {'already': 17}
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
  already  hoist-collectors-subs        replacement present
  already  hoist-collectors-text        replacement present
  already  hoist-collectors-fx          replacement present
  already  hoist-collectors-define      marker present
  already  preview-frame-v2             marker present
  already  face-anchor-norm             marker present
  already  drop-tidOfFx                 marker present

web/index.html: {'skipped': 2, 'already': 3}
  skipped  drop-dead-exporter           guard declined
  already  timeremap-script             marker present
  skipped  effects-script               guard declined
  already  moments-panel                marker present
  already  overlay-export               marker present
```

### ✅ python regression tests
```
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
test_fallback_to_ass_when_overlay_fails (studio.tests.test_export_pipeline.ExportWrapperTest.test_fallback_to_ass_when_overlay_fails) ... [studio] canvas text layer failed (overlay ffmpeg rc=254: [concat @ 0x55cda149d680] Impossible to open '/tmp/tmp2mmtizui/ovjob/000000.png'
[in#1 @ 0x55cda1492dc0] Error opening input: No such file or directory
Error opening input file /tmp/tmp2mmtizui/ovjob/list.ffconcat.
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
test_collectors_live_outside_initClipperPanel (studio.tests.test_pr8.Pr8EditorTest.test_collectors_live_outside_initClipperPanel) ... ok
test_face_anchor_is_normalized_object (studio.tests.test_pr8.Pr8EditorTest.test_face_anchor_is_normalized_object) ... ok
test_fx_anchor_exported (studio.tests.test_pr8.Pr8EditorTest.test_fx_anchor_exported) ... ok
test_patched_editor_parses (studio.tests.test_pr8.Pr8EditorTest.test_patched_editor_parses) ... ok
test_patches_applied (studio.tests.test_pr8.Pr8EditorTest.test_patches_applied) ... ok
test_preview_frame_has_no_undefined_token (studio.tests.test_pr8.Pr8EditorTest.test_preview_frame_has_no_undefined_token) ... ok
[studio] server.py patches: {'already': 36, 'skipped': 1}
test_lens_punch_is_animated (studio.tests.test_pr8.Pr8ExportFxTest.test_lens_punch_is_animated) ... ok
test_mixed_chain_renders (studio.tests.test_pr8.Pr8ExportFxTest.test_mixed_chain_renders) ... ok
test_zoom_anchor_moves_the_punch (studio.tests.test_pr8.Pr8ExportFxTest.test_zoom_anchor_moves_the_punch) ... ok
test_zoom_really_zooms_only_inside_its_window (studio.tests.test_pr8.Pr8ExportFxTest.test_zoom_really_zooms_only_inside_its_window) ... ok
test_grade_bands_renders (studio.tests.test_pr9.Pr9FxTest.test_grade_bands_renders) ... ok
test_lens_and_blur_only_touch_their_window (studio.tests.test_pr9.Pr9FxTest.test_lens_and_blur_only_touch_their_window) ... ok
test_lens_params_match_lens_js (studio.tests.test_pr9.Pr9FxTest.test_lens_params_match_lens_js) ... ok
test_lens_parts_have_overscan_and_no_rgbashift (studio.tests.test_pr9.Pr9FxTest.test_lens_parts_have_overscan_and_no_rgbashift) ... ok
test_split_top_h (studio.tests.test_pr9.Pr9FxTest.test_split_top_h) ... ok

----------------------------------------------------------------------
Ran 50 tests in 12.132s

OK
```

### ✅ server imports with fixes (studio.loader)
```
[studio] server.py patches: {'already': 30, 'skipped': 1}
31 patches
```

### ✅ export pipeline installs into the real server
```
[studio] server.py patches: {'already': 30, 'skipped': 1}
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

