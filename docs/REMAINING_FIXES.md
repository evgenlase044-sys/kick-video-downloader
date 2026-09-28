# Оставшиеся правки после PR #1–#6

Состояние `main` после мерджа PR #6. Отсортировано по влиянию на итоговый ролик.
Сделанное в PR #6 вычеркнуто и описано в `docs/AUDIT_FIXES_SUMMARY.md`.

## 0. Сделать один раз руками (5–10 минут) — без этого часть фиксов не проверена
1. **Прогнать проверки:** `pip install -r requirements.txt` и `bash tools/ci_check.sh`. Строка
   «export pipeline installs into the real server» проверяет, что PR #6 встал в настоящий `server.py`
   (подмена грейда, кодека и маршрута `/api/export-pack`). В среде правок не было FastAPI и полного
   `server.py`, поэтому там эта проверка не запускалась.
2. **Вшить якорные патчи:** `python -m studio.patching --write`, проверить `git diff`, закоммитить.
   Не сделано автоматически: GitHub-инструменты автоматизации отдают только первую половину
   `server.py` (217 КБ) и `editor.js` (305 КБ) и не умеют править файл частично.
3. **Включить CI:** перенести `tools/github-workflows/ci.yml` в `.github/workflows/` (у токена нет права `workflow`).
4. **Живой смоук экспорта:** добавить текст, в «🎬 Экспорт» выбрать шаблон, «В очередь». В логе
   `[studio] export pipeline: {...}`, в `GET /api/studio/export-report` запись с `codec` без `slow_seek`,
   у клипа `text_layer: "canvas"`. Если `ass_fallback` — причина в логе. Нужен ffmpeg ≥ 5.0.

## 1. Экспорт (`server.py`) — P0/P1
* ~~NVENC/битрейты платформ в основном экспорте~~ ✅ PR #6.
* ~~30 fps для разговорных клипов~~ ✅ PR #6 (шаблоны «История»/«Чистый»).
* ~~8-бит грейд, `setparams` вместо конвертации, LUT на 100%~~ ✅ PR #6 (`studio/grade.py`).
* Два аудиопути: ✅ частично — у легаси те же цели (−14 LUFS, TP −1.0, LRA 11) и лимитер, **но loudnorm
  там однопроходный**. Нужен вызов `_two_pass_loudnorm()` внутри легаси-функции `server.py`.
* **`-ss` перед `-i` в `_export_layered_clip()`** глазами не проверен. PR #6 пишет в
  `/api/studio/export-report` поле `seek.slow_seek`; если `true`, перенести `-ss` перед `-i` и сдвинуть `trim`.
* **Отдельный грейд facecam/геймплей и skin protect:** сейчас один грейд на кадр. Нужно вызывать
  `_tv_grade_parts` отдельно для полос в `server.py`. Skin protect в ffmpeg честно не делается.
* Motion blur на зумах/тексте (суб-кадровое накопление 4–8 сэмплов на интервалах движения).
* Lens в экспорте статичный — анимировать k1 через `sendcmd`.
* FX «над текстом» (`text_z`): при canvas-слое текст всегда поверх всех FX.

## 2. Фронтенд (`web/editor.js`) — P1
Все пункты требуют правки второй половины `editor.js`.
* `removeTrack()` сохраняет проект **до** подтверждения; `initClipDrag` → `onMouseUp` не вызывает `saveProject()`.
* SSE `/api/progress` без переподключения.
* Аудио-мастер-клок не подключён.
* При удалении медиа вызывать `window.__canvasMonitor.dropMedia(filename)`.
* Хуки `hooks.faceAnchor`, `window.studioSeek`, `window.studioTranscriptWords`.
* `studio:template-plan`: план эффектов не ставится на таймлайн — нужен API вроде `window.studioAddFx(fx[])`.
* ~~`hot_words` «самое длинное слово», выключено~~ ✅ PR #6.
* Emoji ✅ частично PR #6 (в тексте + авто-emoji); стикеров-картинок нет.
* ~~Backspace без `preventDefault()`~~ ✅ PR #6.
* `core/render/exporter.js` заморожен: удалить или перевести на WebCodecs.

## 3. Скачивание — P1/P2
* fMP4 / BYTERANGE / зашифрованные плейлисты — понятная ошибка, но не скачиваются.
* Kick через regex по HTML → `api/v2/video/{uuid}` и `api/v1/channels/{slug}` с фолбэком.
* Размер — оценка по 15 HEAD-запросам.
* `/api/check-disk` считает без пика 2×, `/api/start-download` — с пиком: UI может сказать «хватает», а скачивание откажет.
* Запись чата во время эфира → JSONL `{t, user, text}` (формат уже принимает `/api/studio/moments`).

## 4. Безопасность — P1
* `python server.py` напрямую = старый сервер без токена. После п.0.2 заменить тело `if __name__ == "__main__":`
  в `server.py` на `import studio_server; sys.exit(studio_server.main())`.
* `/api/media/import` допускает любой медиафайл с диска (так задумано).

## 5. Проверки качества — P1
* 3–5 реальных фрагментов Kick в `tests/fixtures`.
* e2e на реальном `server.py`: 10 кадров → «не чёрный», текст в зоне, эффект изменил кадр, A/V-синхрон.
  Каркас: `OverlayBurnTest`/`ExportWrapperTest` в `studio/tests/test_export_pipeline.py`.
* Playwright-смоук: открыть файл, Z/R/E, «В очередь», файл с `text_layer: canvas`.
* Переписать grep-проверки в `verify_all.py`.

## 6. Продукт — P2
* Автопоиск v2: визуальные сигналы, обучение весов на удачных клипах.
* Экспорт 2 версий (20–30 с и 45–60 с) одной кнопкой.
* Политики платформ (reused content, музыка, фермы).
