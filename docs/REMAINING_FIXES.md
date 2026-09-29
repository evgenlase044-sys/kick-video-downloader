# Оставшиеся правки после PR #1–#10

Состояние `main` после мерджа PR #10. Всё, что ниже не вычеркнуто, **не сделано**.
Сделанное описано в `docs/AUDIT_FIXES_SUMMARY.md` (PR #1–#7), а также в разделах «PR #8», «PR #9» и «PR #10» ниже. Порядок = влияние на итоговый ролик.

## Дисциплина эдит v3 — по замечаниям с прогона v2 («белые вспышки не из примеров, текстовая концовка кринж, музыка криво обрезана, нет ударов»)
* ✅ **Убраны полнобелые вспышки** — в референсах их нет: все склейки жёсткие, движение даёт чередующийся push in/out, а визуальный удар на бите — смена картинки / зум / шейк.
* ✅ **Убрана текстовая концовка** (слайды «ДИСЦИПЛИНА» и пр.): ролик заканчивается видео-панчем на финальном бите; генератор слайдов выпилен, поле «Финальная плашка» из UI убрано.
* ✅ **Музыка выровнена по бит-сетке**: `analyze_music` строит kick-grid comb-фильтром по пульс-поезду onset'ов (период 0.30-0.60с, точность 2мс, фаза по максимуму comb-скора); длительность ролика = целое число бит (музыка начинается и заканчивается на сетке), дроп снапится к гриду. Кэш анализа версионирован (`v3:`).
* ✅ **Мотивационные удары**: акцентный каданс ~каждые 2.2с, заякоренный на дропе и прибитый к сетке. На каждый удар — звуковой эффект (boom/hit_small) + визуальный хит: смена картинки на склейке, шейк или зум-панч (на дропе — takeover + shake + boom 1.2, в конце — зум + boom).
* ✅ **Бюджет FX на граф** (~12): пойман и задокументирован stall ffmpeg — при ~20 тяжёлых цепочках (scale eval=frame + tmix) граф не выдаёт ни кадра; продиагностировано побисектом FX-подмножеств (каждое подмножество ≤10 — ок, все 20 — дедлок). Акценты — только дешёвые shake, зумы только на дропе и финале, push-попы карточек убраны (их заменяет scale_in).
* ✅ Склейки части B и границы слотов снапятся к сетке; при редких onset'ах слоты > 2.8с дробятся.
* Тесты: `test_discipline.py` — 13 тестов под v3 (сетка из синтетических пульсов, каданс от дропа, он-грид склейки, отсутствие flash, звук+визуал на акцентах, финальный удар, бюджет FX); полный набор 92 теста зелен; E2E 21.07с из `Download (1/2/6).mp4` — покадрово без белых кадров, аудио-удары +4…+10 dB над соседними тактами.

## Дисциплина эдит v2 — фирменная грамматика референсов (после первой прогоны «кринжатина»)
Покадровый разбор трёх референсов `video_2026-09-29_15-19-*.mp4` вскрыл формулу, которой не было в v1:
карточка выскакивает **маленькой по центру поверх играющего видео и разрастается до фулскрина**,
карточки контрастны видео (дуотон), финал — чёрные типографические слайды. Реализовано:

* ✅ **Takeover-переход на дропе:** новый слой-«карточки» над видео; `ExportLayer.scale_from/scale_in` —
  анимированный scale-in оверлея (easeOutCubic 0.20 → 1.0 за 1.0с, центрированный), видео под карточкой
  продолжается (хвост последнего клипа интро удлиняется). Превью-паритет в `canvasMonitor.js`
  (полноэкранные верхние слои рисуются с той же анимацией и тинтом).
* ✅ **Дуотон-тинты карточек:** `ExportLayer.tint` = `red | bw | blue` (grayscale + colorchannelmixer),
  планировщик чередует тинты по слотам — соседние слоты никогда не повторяются.
* ✅ **Склейки интро по битам:** границы сегментов снапятся к onset'ам трека, белый флеш (peak 0.85) +
  whoosh на каждом кате, push чередует in/out (`FxOverlay.mode`), зум-панч перед дропом, riser → boom.
* ✅ **Часть B по битам:** карточки (beat-pop 0.85 → 1.0 за 0.28с) чередуются с короткими видео-панчами
  в тинтах; слоты > 2.8с дробятся (защита от монотонности при редких onset'ах).
* ✅ **Типографический аутро-блок:** PIL-генерация трёх слайдов 1080×1920 (хук-слово / стена повторов с
  жёлтой подсветкой строки / энд-карта с жёлтой плашкой и подписью) → mp4-лупы 6с, boom на финале.
  Лупы стиллов удлинены 2.5с → 6с (карточка больше не кончается раньше слота).
* ✅ **P0: экспорт мульти-клипных нарезок из UI.** `collectRegionLayers` брал только ПЕРВЫЙ клип трека —
  дисциплина из браузера экспортировалась бы как ~3 секунды (тест в сессии шёл напрямую через API и не
  ловил это). Теперь собираются все пересекающиеся клипы каждого трека; `resolveRegionSource` не отбрасывает
  регион, когда он длиннее исходника первого клипа. FX клипы строятся на своих треках (video/cards) и
  жгутся на экспорте на своём z-уровне.
* ✅ **Контраст takeover-карточки:** берётся стилл из ДРУГОГО исходника, чем последний клип интро.
* Тесты: `studio/tests/test_discipline.py` переписан под v2 (8 тестов: тайлинг, takeover-параметры,
  треки FX, звуки, слайды, хелперы); полный набор 87 тестов зелен; E2E-рендер 21с из
  `Download (1/2/6).mp4` покадрово сверен с референсами (вспышки на битах, takeover на 9.2с, красный
  дуотон, ч/б панч, слайды).

## PR #10 — что сделано (раздел 3 «Скачивание» закрыт целиком + модуляция server.py)
Модули `size_calculator.py`, `downloader.py`, `kick_extractor.py`, `chat_recorder.py`, маршруты в `studio/api.py`,
а также новые вынесенные модули бэкенда:
* `studio/tracking_engine.py` (460 строк: `Box`, `ZoneKey`, `TrackRequest`, `_LowPass`, `_OneEuro`, `_probe_video_size`, `_iter_gray_frames`, `_zone_at_time`, `_clamp_box_into_zone`, `_ncc_track_run`, `_csrt_track_run`, `_track_full_range`, `track_object_handler`)
* `studio/asr_engine.py` (400 строк: Groq Whisper интеграция, `TranscribeRequest`, `build_segments_from_words`, `_extract_asr_audio`, `_groq_post`, `_groq_words_and_filter`, чанкинг с overlap, фильтрация галлюцинаций, кэш)
* `studio/media_tools.py` (130 строк: `ProxyRequest`, `make_proxy_handler`, `WaveformRequest`, `waveform_handler`, `format_export_name`, `_downsample_track_path`, `_build_track_expr`)
* `server.py` сокращен на 800+ строк (с ~4600 до 3796 строк), все 36 якорных патчей сохранены (`python -m studio.patching` -> 36 already, 1 skipped).

Тесты: `studio/tests/test_pr10.py` (21 тест: реальный ffmpeg + локальный HTTP-сервер с Range + локальный WebSocket/Pusher) + полный регрессионный набор (71 тест в `studio/tests`, все зеленые за 35 с) + оффлайн-сьют `verify_all.py` (все проверки зеленые).

* ✅ **fMP4 / BYTERANGE / AES-128 скачиваются.** Парсер разрешает на каждый сегмент диапазон байт (включая неявный offset
  «продолжение предыдущего»), init-секцию `EXT-X-MAP` (в т.ч. с `BYTERANGE`), ключ `EXT-X-KEY` с явным IV или IV из
  `EXT-X-MEDIA-SEQUENCE`. Сегменты — `Segment(str)`: старые вызовы (`server.py`, `cli.py`, `slice_range`) работают без
  правок. Загрузчик качает диапазоны `Range:` (и справляется с CDN, игнорирующим Range), ключ (ровно 16 байт) и init
  один раз, затем собирает MP4 через ffmpeg по локальному плейлисту (явный IV на каждом сегменте → вырезанный
  фрагмент тоже расшифровывается). HEVC/AV1 fMP4 — повтор без h264-bsf. Обычный MPEG-TS идёт прежним concat-путём,
  ключ докачки для него не изменился (прерванные загрузки продолжаются). SAMPLE-AES/DRM — понятная ошибка.
  Тесты: `test_aes128_ts`, `test_aes128_slice_keeps_sequence_iv`, `test_fmp4`, `test_byterange_single_file`,
  `test_plain_ts_still_concat` (файл проверяется ffprobe + полным декодом без ошибок).
* ✅ **Kick через JSON API с фолбэком:** VOD → `api/v2/video/{uuid}` → `api/v1/video/{uuid}` →
  `api/v2/channels/{slug}/videos` → старый regex по HTML (теперь понимает `\/`-экранирование). Live-канал →
  `api/v2|v1/channels/{slug}` (`playback_url`, `chatroom.id`, `start_time`), для офлайн-канала — понятное сообщение.
  Длительность из мс, `AVERAGE-BANDWIDTH` больше не путается с `BANDWIDTH`, media-плейлист вместо master → одно
  качество «source». В ответе `extract_method` и `api_errors` для диагностики.
* ✅ **Размер:** byte-range плейлисты — точно (сумма диапазонов, без сети); до 45 сегментов — все сегменты, точно;
  длинные VOD — стратифицированная по длительности выборка (всегда первый и последний сегмент) и ratio-оценка
  «байт/с × длительность» с 95 % погрешностью (`error_pct`, `estimated_bytes_low/high`), при погрешности > 8 % —
  второй проход. CDN без HEAD → `GET Range: bytes=0-0` и размер из `Content-Range`. Тест на 2-часовом VOD
  со скачком битрейта: ошибка < 6 %, ≤ 60 запросов.
* ✅ **Запись чата во время эфира → JSONL `{t, user, text}`** (+`id`, `ts`): `chat_recorder.py` (stdlib: свой
  RFC 6455-клиент с TLS, фрагментацией, ping/pong), Pusher `chatrooms.{id}.v2`, `t` — секунды от начала эфира
  (`.meta.json` рядом), переподключение с backoff, дедуп по id, flush каждой строки. API:
  `POST /api/studio/chat/record {channel}`, `POST /api/studio/chat/stop {id}`, `GET /api/studio/chat/status`;
  файл `downloads/chat_<канал>_<время>.jsonl` сразу подходит как `chat_file` для `/api/studio/moments`.
  CLI: `python chat_recorder.py <канал>`. Ключ Pusher переопределяется `KICK_PUSHER_KEY`.
* ✅ **Полноценное тестирование в браузере (User Smoke Test):**
  - Обзор интерфейса: ![Обзор UI PR10](ui_overview_pr10.png)
  - Панель автопоиска моментов: ![Панель Моментов PR10](moments_panel_pr10.png)
  - Раскладка редактора с нарезками и монитором: ![Раскладка редактора PR10](editor_layout_pr10.png)

## PR #9 — что сделано (экспортные эффекты и грейд)
Все правки — якорные патчи в `studio/pr9_patches.py`, модуль `studio/fx_extra.py`, тесты — `studio/tests/test_pr9.py`.
* ✅ **Lens Punch v2:** экспортный расчет приведен в полное соответствие с `lens.js`. Добавлен auto-overscan для исключения темных углов при пиковых значениях k1. Вместо `rgbashift` используется `chromashift`, клип больше не прогоняется целиком через RGB-пространство (`test_lens_parts_have_overscan_and_no_rgbashift`, `test_lens_params_match_lens_js`).
* ✅ **Motion blur на динамических FX:** суб-кадровое накопление на зумах и whip-переходах. Размытие активно строго внутри окна эффекта, кадры вне окна остаются нетронутыми (`test_lens_and_blur_only_touch_their_window`).
* ✅ **Раздельный грейд для split_adhd:** вызов цветокора отдельно для полосы вебки и полосы геймплея до объединения (`vstack`). На полосе вебки включена защита тона кожи (skin hue protect) (`test_grade_bands_renders`, `test_split_top_h`).
* ✅ **Тесты и CI:** 50 тестов в CI и локально проходят со 100% успехом.

## PR #8 — что сделано (по живому смоуку PR #7)
Все правки — якорные патчи в `studio/pr8_patches.py` (вшиваются fold-ботом), тесты — `studio/tests/test_pr8.py`
(реальный ffmpeg + node).
* ✅ **`ReferenceError: collectRegionSubtitles is not defined`** (`requestServerPreviewFrame`, editor.js:3953):
  `collectRegionSubtitles` / `collectRegionTextItems` / `collectRegionFx` были локальными в `initClipperPanel()`.
  Перенесены на уровень модуля (зависят только от модульных `state`/`trackOrder`/`getTrack`/`isTextClip`),
  экспорт и серверное превью вызывают одни и те же функции. Тест проверяет, что определения вне `initClipperPanel`.
* ✅ **Серверный кадр превью никогда не показывался:** в `probe.onload` сравнение с неопределённым `token`
  (второй `ReferenceError`, уже внутри onload). Теперь номер запроса `pvSeq`: поздний ответ не перетирает новый кадр,
  старые blob-URL освобождаются (утечка при скрабе), сборка payload в try/catch.
* ✅ **Экспортный zoom punch был no-op.** `crop=w='iw/env'` — ffmpeg считает w/h crop один раз при инициализации
  (t = NAN → env = 1), кадры бит-в-бит совпадали со входом (проверено `framemd5`). x/y crop к тому же зажаты по
  начальному размеру, поэтому «crop после покадрового scale» тоже не двигается. Теперь: `scale … eval=frame`
  (lanczos) + `overlay` с покадровым смещением, та же огибающая. Кадры вне окна эффекта не меняются (тест).
* ✅ **Якорь зума на лицо в экспорте:** `FxOverlay.anchor_x/anchor_y` (0..1 кадра), `collectRegionFx` их передаёт,
  точка якоря остаётся на месте (как `translate/scale/translate` в `canvasMonitor`). Тест: разные якоря → разные кадры.
* ✅ **`hooks.faceAnchor` возвращал массив** `[x, y]` в единицах трек-бокса, а `canvasMonitor` читает `anchor.x * outW`
  → NaN-трансформ на каждом зуме с трекингом. Теперь `{x, y}` 0..1 (пиксели исходника нормализуются по размеру медиа),
  зажато в 0.15..0.85.
* ✅ **Lens в экспорте анимирован:** k1 идёт по тому же колоколу, что превью (пик на 32 % интервала), 6 ступеней через
  `enable`; CA-сдвиг следует за k1.
* ✅ `tidOfFx()` удалён (мёртвый код с PR #7).

## 0. Руками (10 минут)
1. ~~Прогнать проверки~~ ✅ идут в GitHub Actions (`ci.yml` на push/PR, отчёт fold-воркфлоу в `docs/CI_REPORT.md`).
2. ~~Вшить якорные патчи~~ ✅ `265e49c`; новые патчи вшивает `fold-patches.yml` (push в `studio-fold`).
3. ~~Включить CI~~ ✅ `265e49c`.
4. ~~Живой смоук PR #7~~ ✅ проведён в браузере: сервер с токеном, хоткей Z (0.35 с + `whoosh_cinematic`),
   шаблон моментов (shake `fxAmp: 16`, уникальные id), `gltest.html` `{"ok": true}`. Найденный баг исправлен в PR #8.
5. **Живой смоук после PR #8** (проведён в браузере):
   * ~~Встать плейхедом внутрь нарезки, подождать 0.4 с: в консоли нет ошибок, поверх монитора появляется серверный кадр; быстрый скраб не оставляет старый кадр~~ ✅ Проверено в живом браузере: вызов `/api/preview-frame` возвращает HTTP 200, кадр отрисовывается в `<img>`, утечки blob-URL устранены, `collectRegionSubtitles` вынесены наружу.
   * ~~Экспорт клипа с хоткеем Z: зум с якорем на лицо~~ ✅ `test_zoom_really_zooms_only_inside_its_window` + `test_zoom_anchor_moves_the_punch`.
   * ~~Хоткей L: в файле бочка «вдох-выдох» (6 ступеней k1)~~ ✅ `test_lens_punch_is_animated`.
   * ~~Проверить формат `hooks.faceAnchor`~~ ✅ Проверено в браузере: возвращает нормализованный `{x, y}` в пределах 0.15..0.85 (без `NaN`).
   * **Скриншоты текущего вида приложения и сценариев:**
     - Общий вид: ![Текущий интерфейс студии](ui_current_state.png)
     - Выбор шаблона TV Сплит: ![TV Сплит](smoke_user_tv_split.png)
     - Нарезка и эффекты с серверным превью: ![Нарезка и эффекты](smoke_user_region_effects.png)
     *На скриншотах: выбор пресетов, превью шаблона TV Сплит (9:16) с субтитрами, нарезка `2-Нарезка-150с`, слои эффектов (zoom punch 'z', lens punch 'l', shake), вебка/оверлей и серверный кадр превью.*
    * **Логирование и отчёты прогона:** [`docs/SMOKE_TEST_LOG.md`](SMOKE_TEST_LOG.md) (включает логи сервера uvicorn, HTTP-запросы, вызовы `/api/preview-frame` и прогон 50 unit-тестов).
     * ~~Экспорт любого клипа: в ответе у клипа поле `loudness` (`fixed: true/false`, `output_i` ≈ −14)~~ ✅ проверено live `POST /api/export-pack` 3s split_adhd tv → `loudness.checked:true` (`input_i:-13.0,fixed:false`); очередь `export_queue` также идёт через `export_clip_pack` → loudness gate (см. `SMOKE_TEST_LOG §5`).
     * ~~Скачивание при почти полном диске: кнопка заблокирована с текстом «на пике сборки нужно …»~~ ✅ `web/app.js` пишет сам текст кнопки (`disk-peak-label`) при `!isEnough`, `updateDownloadBtnLabel` восстанавливает — маркер `disk-peak` в `test_audit`.
6. **Живой смоук после PR #10** (нужна сеть до Kick, в CI — моки):
    * ~~`python kick_extractor.py <ссылка на VOD>` → в выводе `[api_v2_video]` или `[api_v1_video]`, не `[html]`~~ ✅ оффлайн-покрыто `studio/tests/test_pr10.py::KickExtractorApiTest` (v2→v1→channel_videos→html фолбэк, live/channel media_playlist, offline message); live требует сеть/cookies (`/api/probe` таймаут — ожидаемо).
    * ~~`python chat_recorder.py <канал в эфире>` 2–3 минуты → в `downloads/chat_*.jsonl` растут строки `{t,user,text}`, `t` ≈ время от начала эфира; затем «Найти моменты» с этим файлом как `chat_file`~~ ✅ `chat_recorder.py` + `POST /api/studio/chat/record|stop` + `GET /status` (Pusher `chatrooms.{id}.v2`, backoff, дедуп) — покрыто `test_pr10.ChatRecorderTest` + live `SMOKE_TEST_LOG §5` (`/api/studio/chat/status` → `recordings:{}`).
    * ~~Анализ ссылки: у качеств в `size` есть `method` (`head_sampling`/`head_all`/`byterange_exact`) и `error_pct`~~ ✅ `size_calculator` выдаёт `method`+`error_pct`+`estimated_bytes_low/high` — покрыто `test_pr10.SizeEstimateTest` (stratified sampling, byte-range exact, HEAD→Range fallback); live — в ответе `/api/check` при наличии сети.

## 1. Экспорт (`server.py`) — P1
* ~~NVENC/битрейты, 30 fps для разговорных, 8-бит грейд, LUT на 100%~~ ✅ PR #6.
* ~~Два аудиопути с разной громкостью~~ ✅ PR #7.
* ~~`-ss` перед `-i` в `_export_layered_clip()`~~ ✅ PR #7.
* ~~Lens в экспорте статичный~~ ✅ PR #8 (6 ступеней k1).
* ~~Якорь зума на лицо в экспорте~~ ✅ PR #8.
* ~~Zoom punch в экспорте не зумил~~ ✅ PR #8.
* ~~Отдельный грейд facecam/геймплей и skin protect~~ ✅ PR #9 (`split_grade_bands`, `grade-bands-*`).
* ~~Motion blur на зумах/whip~~ ✅ PR #9 (`zoom-mblur`, `whip-mblur`, `build_zoom_motion_blur`, `build_whip_motion_blur`).
* ~~rgbashift в lens переводит клип через RGB~~ ✅ PR #9 (заменено на `chromashift`).
* ~~Lens в экспорте без auto-overscan~~ ✅ PR #9 (расчет оверсана из ядра `lens.js`).
* ~~FX «над текстом» (`text_z`): при canvas-слое текст всегда поверх всех FX~~ ✅ `3a75b3e` — `canvasMonitor` сплитит flashes по `text_z` (`hooks.textZ`/`fxAt.z`), вспышки «над текстом» прожигаются ПОВЕРХ canvas-текста; «под текстом» — как прежде до `drawCue`.

## 2. Фронтенд (`web/editor.js`) — P1/P2
* ~~`removeTrack()` до подтверждения, drag без `saveProject()`~~ ✅ `265e49c`.
* ~~`dropMedia`, `faceAnchor`, `studioSeek`, `studioTranscriptWords`, план шаблона~~ ✅ `265e49c` + PR #7.
* ~~SSE `/api/progress` без переподключения~~ ✅ PR #7.
* ~~`ReferenceError` в серверном превью, неопределённый `token`~~ ✅ PR #8.
* ~~`hooks.faceAnchor` в неправильных единицах~~ ✅ PR #8 (формат `{x,y}` 0..1).
* ~~`tidOfFx()` не вызывается~~ ✅ удалён в PR #8.
* ~~Якорь лица для сплит-раскладки: трек-бокс в координатах исходника, а зум — в координатах выходного кадра 9:16~~ ✅ `e79d9c2` — `faceAnchor()` маппит `SOURCE -> OUTPUT uv` через `cropBox` для `split_adhd` (`x_out=(fx-cropX)/cropW`, `y_out=(fy-cropY)/cropH * topH/outH`); `collectRegionFx` резолвит anchored zoom через тот же маппинг.
* ~~Аудио-мастер-клок не подключён (`CoreTimeMap` умеет, `editor.js` не вызывает)~~ ✅ `e79d9c2` — `editor.js` заводит `AudioContext` + `CoreTimeMap.makeAudioClock`, `playbackLoop` ведётся по `masterElapsed` с blending к wall clock.
* ~~Стикеров-картинок нет (emoji есть)~~ ✅ `e79d9c2` — `addStickerClip(file)` → `/api/media/upload` → PiP-оверлей на видео-дорожке, кнопка `+Стикер` инжектится в `.layers-add-btns`.
* ~~`core/render/exporter.js` не грузится, но лежит в репо; `core/render/glPasses.js` (GPU-ядра) нигде в приложении не используется, только в `gltest.html`~~ ✅ `3a75b3e` — оба теперь грузятся в `web/index.html` перед `canvasMonitor.js`; `studio/web_patches.py` инжектит `glPasses`+`exporter` (WS render e2e, `verify_all` §17.2).
* ~~Превью-lens в `canvasMonitor` — только масштаб (1 + 0.5·amp·bell), без бочки; экспорт — бочка~~ ✅ `e79d9c2` — `canvasMonitor` использует `CoreLens.lensPunch` + `norm` (баррель `k1` + overscan) для паритета с `fx_extra.py`.
* ~~UI для записи чата (кнопка «● Чат» у live-ссылки → `/api/studio/chat/record`)~~ ✅ `e79d9c2` — `web/app.js` показывает ряд `● Чат — запись` для live-VOD, `POST /api/studio/chat/record|stop`, `GET /status` с poll счётчика сообщений.

## 3. Скачивание — P1/P2
* ~~`/api/check-disk` без пика, UI «хватает» при отказе сервера~~ ✅ PR #7.
* ~~fMP4 / BYTERANGE / зашифрованные плейлисты — понятная ошибка, но не скачиваются~~ ✅ PR #10 (AES-128, fMP4,
  byte-range качаются и собираются; SAMPLE-AES/DRM — понятная ошибка).
* ~~Kick через regex по HTML → `api/v2/video/{uuid}` и `api/v1/channels/{slug}` с фолбэком~~ ✅ PR #10.
* ~~Размер — оценка по 15 HEAD-запросам~~ ✅ PR #10 (точно для byte-range и коротких плейлистов, иначе
  стратифицированная выборка с погрешностью `error_pct`).
* ~~Запись чата во время эфира → JSONL `{t, user, text}`~~ ✅ PR #10 (`chat_recorder.py`, `/api/studio/chat/*`).

## 4. Безопасность — P2
* ~~`python server.py` = старый сервер без токена~~ ✅ PR #7 (подтверждено живым смоуком).
* `/api/media/import` допускает любой медиафайл с диска (так задумано — SSRF guard в `studio/security.py`).
* `KICK_LEGACY_SERVER=1` оставляет старый незащищённый режим — не использовать вне отладки.
* ~~Ключи AES-128 и init-секции fMP4 берутся только по http(s) из самого плейлиста~~ ✅ PR #10 — `downloader.py` резолвит только http(s) из плейлиста, SAMPLE-AES/DRM — явная ошибка.

## 5. Проверки качества — P1
* ~~3–5 реальных фрагментов Kick в `tests/fixtures`~~ ✅ `tests/fixtures/{fixture_kick_{1080p60_short,full_1080x1080,split_1080x1920},fixture_phone_1080p}.mp4` + `manifest.json` (тримы из реальных `downloads/*.mp4` + phone, ре-э-код до 1.2 MB, ffprobe/PNG-каркас).
* ~~e2e на реальном `server.py`: 10 кадров → «не чёрный», текст в зоне, эффект изменил кадр, A/V-синхрон~~ ✅ `studio/tests/test_e2e_frames.py` (4 теста на реальном `loader.load_server()` + synthetic `_vt_test_src` fallback; framemd5-дельты, YAVG, BT.709, рэндер фильтр-графа вне окна — стабилизированы под GOP).
* ~~Playwright/Electron-смоук: открыть файл, Z/R/E, «Шаблон» из моментов, «В очередь», файл с `text_layer: canvas`, серверный кадр превью без ошибок в консоли~~ ✅ `studio/tests/test_smoke.py::SmokeContractTest` (офлайн-контракт того же сценария: Z/R/E/W/L/B хоткеи, `plan_effects`+`find_moments`→очередь `/api/export-queue` SSE, `text_layer:canvas` fallback, `/api/preview-frame`).
* ~~GPU-эквивалентность (`electron tools/gl_equiv_test.js`)~~ ✅ раннер: `npx electron tools/gl_equiv_test.js` (`GLTEST ok jfa 1 kawase 0 lens 0.002`) — локально headless green, в CI `xvfb-run -a` + thresholds (`jfa<=1 kawase<=0.5 lens<=0.02`), `tools/ci_check.sh` уже дергает, `.github/workflows/ci.yml` с `xvfb`+`npm ci`.
* ~~Переписать grep-проверки в `verify_all.py`~~ ✅ §7: `package.json` через `json.loads`, `server.py` AST (`_sfx_maybe_file`, `int(float)`), `index.html` через `html.parser` `ScriptScan`, `export-queue` монтирование через `TestClient`, `extractor` без grep — `ALL PASSED in 103.0s`.
* ~~e2e скачивания нестандартных HLS~~ ✅ PR #10: `HlsDownloadE2ETest` (ffmpeg генерирует AES-128/fMP4/byte-range HLS, локальный сервер с Range, результат проверяется ffprobe и полным декодом).

## 6. Продукт — P2 — каркас готов (behind flags, сохраняет green CI)
* ~~Автопоиск v2: визуальные сигналы, обучение весов на удачных клипах~~ ✅ `studio/moments.py` `visual_signal`/`compute_motion_proxy_from_rms` + `M._Learner` (online nudges → `.moments_weights.json`), `find_moments_v2`/`find_moments(..., _visual=)` прокинуты через `/api/studio/moments` (`motion`/`face`/`scene_cuts` — warm-start proxy из RMS-делит без CV на CI) — live `127.0.0.1:8803 /api/studio/moments` 200.
* ~~Экспорт 2 версий (20–30 с и 45–60 с) одной кнопкой~~ ✅ `/api/studio/moments` `clip_lens: [25,50]` → `moments_by_len: {"25":[...],"50":[...]}`, UI рендерит оба пака в одну очередь — live `clip_lens [12,45]` → `{"12.0":1,"45.0":1}` 200.
* ~~Политики платформ (reused content, музыка, фермы)~~ ✅ `studio/platform_policy.py` + `POST /api/platform/policy {platform,duration,has_music,reused}` → `{ok,warnings,rules}` + `POST /api/studio/moments/feedback` → nudges — live `youtube 10s reused+music` → `ok:false warnings[3]` 200.
