# Audit fixes: что реально сделано (сверено с кодом)

Аудит: коммит `d91ca83`. Исправления: PR #1–#5. Эта версия заменяет прошлую сводку, где часть пунктов
была заявлена, но в коде не существовала (например `/api/moments`, «шаблоны готовы»).

## Как применяются фиксы в `server.py` / `web/editor.js` / `web/index.html`
Файлы огромные (217 / 305 / 103 КБ), поэтому фиксы для них — **якорные патчи**
(`studio/server_patches.py`, `studio/web_patches.py`, движок `studio/patching.py`).

**Важно:** сейчас патчи применяются при запуске через `studio_server.py` (так запускают `main.js` и `start_web.bat`).
`python server.py` напрямую = старый код с багами. Чтобы вшить навсегда: `python -m studio.patching --write`
(локально, одна команда) или workflow из `tools/github-workflows/fold-patches.yml`.
Тест `PatchAnchorsTest` падает, если хоть один обязательный патч перестал находить свой якорь.

## §1 Баги
| Баг | Статус | Где |
|---|---|---|
| `**snap` → NameError в `/api/progress` | ✅ | патч `progress-nameerror` |
| TDZ `exportPackBtn` | ✅ | патч `tdz-*` |
| Недостижимый браузерный экспортёр | ✅ заморожен, не грузится | патч `drop-dead-exporter` |
| Демуксер: всё keyframe | ✅ | `web/core/mp4/demux.js` |
| Скачивание без cookies | ✅ сервер (`cookies-*`) + CLI (PR #5) | |
| YUV хрома не 2×2 | ✅ + тест | `yuv.js`, `selftest_audit.js` |
| Ramp 0.35× дважды | ✅ одна кривая для превью, композера и ffmpeg | `timeRemap.js` ↔ `studio/timeremap.py` |
| SFX `riser` | ✅ генерится при старте; `whoosh_magic`/`hit_small` подключены | `studio/sfx.py` |
| CLI KeyError | ✅ поле возвращает `DiskManager` | `disk_manager.py` |
| **Новый баг из PR #1:** патч `disk-peak` передавал `peak_factor` в `check_space()`, который его не принимал → TypeError на КАЖДОМ скачивании | ✅ PR #5 | `disk_manager.py` |
| **Регресс PR #2:** композер считал ramp своей кривой со скачком времени в конце окна, превью ≠ экспорт | ✅ PR #5 | `composer.js` |
| **Регресс PR #2:** «3 строки» противоречили правилу ≤2 строк и всё равно теряли слова на 4-й | ✅ PR #5 | `canvasText.js` |

## Рендер, экспорт, превью
* ✅ WS-рендер: stderr в файл, `-t` = длина видео, рациональный FPS, цветовые теги до `-i`, лимиты заголовка, аудио только из `downloads/`/`exported_packs/`, NVENC при наличии.
* ✅ Ramp/freeze попадают в файл (setpts/select), whip клампится.
* ✅ Точный FPS (`fps_exact`, `fps_rational`), короткие слова не выкидываются, temp-файлы ASR с uuid.
* ✅ PR #5 превью: zoom (якорь на лицо через хук `faceAnchor`), lens punch, threshold, whip, freeze, ramp видны.
* ✅ PR #5: `VideoFrame` всегда закрывается, текстура грейда одна, `webglcontextlost/restored`, `dropMedia()`.
* ✅ PR #5 текст: ≤2 строки, автоуменьшение до 72%, дальше страницы (ни одно слово не теряется), караоке активного слова, сила pop по важности, rise/spin/wave/tremble/shimmer/char_type, экструзия/tilt/bob, алиас `mrbeast → mrbeast_3d`, безопасная зона 40–1040 × 150–1650.

## Скачивание (PR #5)
* ✅ HLS-парсер: EXT-X-MAP/KEY/BYTERANGE/DISCONTINUITY, URI без `#EXTINF` не сегмент, понятные отказы.
* ✅ Resume между запусками (`downloads/_resume_<key>/`), атомарный `.part.mp4`, проверка Content-Length.
* ✅ Диск: пик (сегменты + MP4) + 5% минус уже скачанное.
* ✅ Склейка `+genpts`/`make_zero` (разрывы HLS).
* ✅ CLI: cookies, `--start/--end` с точной обрезкой, `-q`, `-y`.

## Безопасность
* ✅ `studio_server.py`: 127.0.0.1, токен (HttpOnly cookie/заголовок), Host/Origin, пути только в `downloads/`, импорт только медиа, allowlist Kick/CDN (SSRF), лимиты WS.

## Новое (PR #5)
* ✅ Автопоиск моментов: `studio/moments.py`, `POST /api/studio/moments` (аудио-всплески, чат, речь, опц. LLM Groq с хук-текстом), панель «🔥 Моменты».
* ✅ Шаблоны Хайп/История/Чистый + политика эффектов с кулдаунами: `studio/templates.py`, `GET /api/studio/templates`, `POST /api/studio/templates/plan`.
* ✅ Реальные тесты: `studio/tests/test_audit.py`, `web/core/selftest_audit.js`, `tools/ci_check.sh`.

Что осталось: `docs/REMAINING_FIXES.md`.
