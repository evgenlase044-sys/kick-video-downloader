# splash_engine — Rust-движок мем-эдитов (iShowSplash-стиль)

Покадровый рендер коротких вертикальных видео (1080×1440@60) по JSON-шаблону.
I/O через ffmpeg-пайпы (декод rawvideo → обработка кадра в чистом Rust → x264),
все эффекты и типографика реализованы внутри движка (rayon-параллелизм по строкам кадра).

## Сборка

```
cd engine
cargo build --release
```

Требуется `ffmpeg`/`ffprobe` в PATH.

## Использование

```
splash_engine render templates/ishowsplash_style.json -o out.mp4 [--crf 18] [--preset medium]
splash_engine frame  templates/ishowsplash_style.json --at 5.0 -o frame.png   # быстрый предпросмотр одного кадра
splash_engine check  templates/ishowsplash_style.json                         # валидация шаблона
```

`SPLASH_DEBUG_FONTS=1` — печать метрик шрифтов и раскладки текста.

## Команды шаблона (templates/ishowsplash_style.json — reproduced demo)

| Секция | Поля | Что делает |
|---|---|---|
| `canvas` | width, height, fps | выходное разрешение/частота |
| `output` | crf, preset, audio_bitrate | качество x264 (CRF 18 + medium ≈ визуально прозрачный) |
| `grade` | contrast, saturation, sharpen, vignette, ca_px, tint | глобальный грейд; `tint`: none / orange / red_dark / bleach |
| `fonts` | marker, sans, emoji | TTF-файлы (переменные шрифты поддерживаются, sans фиксируется на wght=800) |
| `watermark` | text, size, y, color, opacity, outline, shadow | водяной знак (верхний слой) |
| `clips[]` | src, in, dur, zoom_from/to, anchor, tint, ca_mult, burst, blur_darken | планы таймлайна: зум-панч, радиальный смаз (`burst`), финальное «блюр+затемнение» |
| `texts[]` | style: marker/italic/impact; text; colors[]; start/end; x/y; size; tracking; word_starts[] или type_reveal; pop_dur; wobble{amp,freq}; rotate_jitter_deg; stroke; shadow; glow(+color); shear; plate | подписи: пружинный pop-in, печать по словам, дрожание, обводка/тень/свечение, per-word цвета |
| `nametags[]` | text, color, x/y, start/end, arrow, size, bob | ники-теги со стрелкой и качанием |
| `flashes[]` | kind: red/black/white, start, dur, peak | полноэкранные вспышки с атака/спад-огибающей |
| `emojis[]` | char, start/end, x/y, size, glow | эмодзи как белая маска + свечение (Segoe UI Emoji) |
| `audio` | src, offset | дорожка; по умолчанию берётся из первого клипа |

Пути относительные — от файла шаблона. Пропорции x/y — доли кадра; size — px на высоте 1440.

## Как делать «такое же» видео на своём материале

1. Нарезать исходник на планы (см. карту склеек в `../scratch/video_analysis/ANALYSIS.md`).
2. В `clips[]` указать для каждого плана `in/dur` и характер зума; на ударных склейках `burst: 5`.
3. Скопировать текстовую сетку из шаблона, заменить реплики и цвета слов.
4. Оставить `flashes` (красная на дропе, чёрная на акценте) и `grade.ca_px ≈ 1.4`.

## Структура кода

- `src/template.rs` — serde-схема шаблона;
- `src/ffmpeg.rs` — пайпы декодирования/кодирования;
- `src/img.rs` — кадровый буфер: motion-resample, zoom burst, хроматика, unsharp, грейд, виньетка, блюр, слои;
- `src/text.rs` — метрики/растеризация ab_glyph, наклон/поворот букв, обводка (dilate), тень, glow, печать по словам;
- `src/render.rs` — таймлайн, композиция кадра, вспышки, водяной знак;
- `src/main.rs` — CLI.

## Статус/ограничения

- Демо-рендер поверх исходника дублирует уже впечённые в него подписи/водяной знак — это ожидаемо для верификации стиля; на чистом материале дублирования нет.
- Кастомный TTF на отдельный текст задаётся через секцию `fonts` (per-text `font` зарезервирован).
- Bangers более узкий, чем шрифт оригинала — ширина компенсируется `tracking`.
