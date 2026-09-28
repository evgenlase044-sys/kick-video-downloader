# Smoke Test Log (PR #7 / PR #8 / PR #9)

Дата: 2026-09-28
Окружение: Windows 11, Python 3.12, ffmpeg, Chrome / Electron Browser Subagent, Local Server (`127.0.0.1:8765`).

---

## 1. Скриншоты интерфейса и сценариев пользователя
1. **Общий вид приложения:** [`docs/ui_current_state.png`](ui_current_state.png)
   - Вкладка монтажа («Kick Video Studio — монтаж и нарезки»)
   - Превью раскладки «TV Сплит» 9:16 с караоке-субтитрами «ЭТОТ ДОНАТ СЛОМАЛ СТРИМ»
   - Таймлайн: нарезки (`2-Нарезка-150с`), эффекты (`FX 0.5s` zoom punch, shake), субтитры/текст, вебка/оверлей, видео и звук стрима
   - Серверный кадр превью (`#serverFrameImg`), загруженный без `ReferenceError`

2. **Пользовательский выбор шаблона TV Сплит:** [`docs/smoke_user_tv_split.png`](smoke_user_tv_split.png)
   - Клик по кнопке «TV СПЛИТ» в левой панели шаблонов
   - Автоматическая перестройка монитора под вертикальный формат 9:16 с разделением экрана (вебка сверху, геймплей снизу)

3. **Создание нарезки и эффектов:** [`docs/smoke_user_region_effects.png`](smoke_user_region_effects.png)
   - Создание сегмента по кнопке `+ Нарезка`
   - Добавление эффектов по горячим клавишам: Zoom punch (`z`) и Lens punch (`l`)
   - Позиционирование плейхеда и отрисовка кадра серверного превью в реальном времени

---

## 2. Лог запуска сервера (studio_server / server.py)
```text
[studio] server.py patches: {'already': 36, 'skipped': 1}
[studio] export pipeline: {'grade': True, 'encoder_shim': True, 'export_route': True, 'loudness_gate': True}
[studio] web/index.html patches: {'skipped': 2, 'already': 3}
[studio] UI: http://127.0.0.1:8765/index.html?token=NIiWhNB6Ybt-0vQwDd1Uh3uno1EmShto1MEZvTUd_FM
INFO:     Started server process [20168]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8765 (Press CTRL+C to quit)
INFO:     127.0.0.1:63906 - "GET /index.html?token=NIiWhNB6Ybt-0vQwDd1Uh3uno1EmShto1MEZvTUd_FM HTTP/1.1" 200 OK
[studio] web/editor.js patches: {'already': 17}
INFO:     127.0.0.1:63906 - "GET /core/text/canvasText.js?v=1 HTTP/1.1" 304 Not Modified
INFO:     127.0.0.1:61504 - "GET /editor.js?v=12 HTTP/1.1" 200 OK
INFO:     127.0.0.1:53930 - "GET /core/timeRemap.js HTTP/1.1" 304 Not Modified
INFO:     127.0.0.1:57417 - "GET /core/canvasMonitor.js?v=1 HTTP/1.1" 304 Not Modified
INFO:     127.0.0.1:55982 - "GET /core/render/yuv.js?v=1 HTTP/1.1" 304 Not Modified
INFO:     127.0.0.1:64452 - "GET /app.js?v=12 HTTP/1.1" 304 Not Modified
INFO:     127.0.0.1:63906 - "GET /studio/moments.js HTTP/1.1" 304 Not Modified
INFO:     127.0.0.1:61504 - "GET /studio/overlay_export.js HTTP/1.1" 304 Not Modified
INFO:     127.0.0.1:61504 - "GET /api/export-queue/status HTTP/1.1" 200 OK
INFO:     127.0.0.1:61504 - "GET /core/styles.json HTTP/1.1" 304 Not Modified
INFO:     127.0.0.1:63906 - "GET /api/sfx/list HTTP/1.1" 200 OK
INFO:     127.0.0.1:61504 - "GET /api/disk-info HTTP/1.1" 200 OK
INFO:     127.0.0.1:63906 - "GET /api/media/library HTTP/1.1" 200 OK
INFO:     127.0.0.1:61504 - "POST /api/preview-frame HTTP/1.1" 200 OK
INFO:     127.0.0.1:52562 - "POST /api/preview-frame HTTP/1.1" 200 OK
```

---

## 3. Проверка тестов регрессии (50 тестов, 0 ошибок)
```text
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
test_fallback_to_ass_when_overlay_fails (studio.tests.test_export_pipeline.ExportWrapperTest.test_fallback_to_ass_when_overlay_fails) ... ok
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
Ran 50 tests in 23.969s

OK
```

---

## 4. Результаты проверок PR #8 / PR #9
1. **Hoisting коллекторов региона (PR #8):**
   `collectRegionSubtitles`, `collectRegionTextItems`, `collectRegionFx` доступны из `requestServerPreviewFrame` без `ReferenceError`.
2. **Серверный кадр превью (PR #8):**
   Вызов `/api/preview-frame` возвращает HTTP 200, кадр отрисовывается в `<img>`, утечки blob-URL устранены.
3. **Хук `faceAnchor` (PR #8):**
   Возвращает нормализованный `{ x, y }` в пределах 0.15..0.85 (предотвращает появление `NaN` в матрице трансформации `canvasMonitor`).
4. **Удаление `tidOfFx` (PR #8):**
   Мёртвый код удален, глобальная область чистая.
5. **Lens Punch v2 (PR #9):**
   Экспортная линза теперь использует формулу из `lens.js`, auto-overscan (без затемненных углов) и `chromashift` вместо `rgbashift`.
6. **Motion blur (PR #9):**
   Динамическое субкадровое накопление на зумах и whip-переходах, действующее строго в интервале движения.
7. **Раздельный грейд полос (PR #9):**
   Полосы вебки и геймплея в `split_adhd` грейдятся независимо с защитой оттенков кожи на лице.

---

## 5. Результаты проверок PR #10 и модульной декомпозиции
1. **Декомпозиция монолитного `server.py`:**
   - Вынесен `studio/tracking_engine.py` (460 строк): `Box`, `ZoneKey`, `TrackRequest`, `_LowPass`, `_OneEuro`, `_iter_gray_frames`, `_probe_video_size`, `track_object_handler`.
   - Вынесен `studio/asr_engine.py` (400 строк): `TranscribeRequest`, `build_segments_from_words`, `_extract_asr_audio`, `_groq_post`, `_groq_words_and_filter`, `transcribe_media_handler`.
   - Вынесен `studio/media_tools.py` (130 строк): `ProxyRequest`, `make_proxy_handler`, `WaveformRequest`, `waveform_handler`, `format_export_name`, `_downsample_track_path`, `_build_track_expr`.
   - Все 36 якорных патчей `server.py` сохранены без единой поломки (`python -m studio.patching` -> 36 already, 1 skipped).
2. **Прогон регрессионного набора unit-тестов (71 тест):**
   ```text
   Ran 71 tests in 35.086s
   OK
   ```
   Включая 21 новый тест `test_pr10.py` (fMP4, BYTERANGE, AES-128, Kick JSON API, точный расчет размера, реконнект чат-рекордера).
3. **Прогон полного оффлайн-сьюта `verify_all.py`:**
   - Исправлена кодировка UTF-8 в вызовах subprocess Node для Windows.
   - Добавлен `riser.mp3` в `sfx/CREDITS.md`.
   - Результат: **ALL VERIFICATION CHECKS PASSED in 102.3s**.
4. **Сквозное пользовательское тестирование в браузере (User Smoke Test):**
   - Проверена загрузка приложения с защитным токеном (`http://127.0.0.1:8765/index.html?token=...`).
   - Проверено переключение вкладок: медиабиблиотека, инспектор, нарезка, таймлайн.
   - Проверена панель «🔥 Моменты»: вызов по плавающей кнопке, выбор шаблона (Hype/Story/Clean), поддержка чат-лога.
   - Зафиксированы скриншоты интерфейса:
     - Обзор интерфейса: `docs/ui_overview_pr10.png`
     - Панель автопоиска моментов: `docs/moments_panel_pr10.png`
     - Раскладка редактора: `docs/editor_layout_pr10.png`

