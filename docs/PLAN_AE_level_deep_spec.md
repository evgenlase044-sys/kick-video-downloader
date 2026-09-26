# Kick Video Studio → AE‑уровень: глубокая спецификация реализации (дополнение к `docs/PLAN_viral_quality.md`)

Репозиторий: `evgenlase044-sys/kick-video-downloader`, HEAD `6b62dbb` (5 коммитов, все от 26.09.2026).
Разобрано: `server.py` (включая хвост ~2k строк, присланный вручную), `web/editor.js`, `web/index.html`, `web/style.css`, `web/app.js`, `main.js`, `package.json`, `engine/src/*.rs`, `engine/templates/*`, `tv_grade.cube`, `downloader.py`, `kick_extractor.py`, `verify_all.py`, `docs/PLAN_viral_quality.md`, `docs/PLAN_verification.md`.

> Картинки из сообщения до меня не дошли (вложений нет), поэтому эталон стиля взят из описания референса «Bro turned into iShowSplash» в существующем плане и из шаблона `engine/templates/ishowsplash_style.json`.

---

## 0. Вердикт

1. **Существующий план в целом верен по направлению** (единая сцена + один GPU‑рендерер для превью и экспорта), но в нём нет трёх вещей, без которых он не взлетит: (а) **транспорт кадров из Electron в x264** без IPC/preload, (б) **точная математика** текста/пружин/грейда/цвета, (в) **конкретный путь миграции превью**, где приложение работает на каждом шаге.
2. **Первопричина плохого качества одна: анимация и типографика делаются языком разметки субтитров (ASS), а превью — третьим, несвязанным рендерером (DOM+CSS).** Всё остальное — следствия. ASS не умеет: пружины с непрерывной скоростью, motion blur, свечение от маски, раскладку слова внутри фразы, рендер в 4:4:4. Это потолок, а не баг.
3. В хвосте `server.py` нашлись **ещё 10 конкретных багов**, которых нет в плане (раздел 1): «тень» без смещения, обрыв fade‑out у поздних букв, вечный `\blur0.8` у zoom, пульсация glow, «дышащий» трекинг при shake, наложение текста на уже субдискретизированный `yuv420p`, зум‑скачок shake и др. Часть из них чинится за день и заметно поднимает картинку ещё до переписывания.
4. **Рекомендуемая архитектура экспорта:** WebGL2 рендерит кадр → шейдер упаковывает его в `yuv420p BT.709 limited` с дизерингом → асинхронный `readPixels` через PBO → **WebSocket на `server.py`** → `ffmpeg -f rawvideo -i pipe:0` → **x264 slow CRF 16**. Это 3.1 МБ/кадр (93 МБ/с при рендере 30 fps) — localhost тянет с запасом, не нужен preload/IPC, качество x264 выше, чем у аппаратного WebCodecs‑энкодера. WebCodecs `VideoEncoder` оставить как «быстрый» режим.
5. **Превью чинится в два шага**: P0 (2–4 дня) — один `<canvas>`‑монитор, куда рисуются скрытые `<video>` (по одному на уникальный файл), синхронизация через `requestVideoFrameCallback`, текст рисуется тем же JS‑движком по `mediaTime`; P1 — WebCodecs‑декод и общий с экспортом WebGL2‑рендерер.

---

## 1. Новые первопричины (нет в плане), с привязкой к коду

Нумерация N1…N18. «Хвост» = присланный фрагмент `build_text_elements_ass` / `_tv_grade_parts` / `_apply_fx_chain` / `_export_layered_clip`.

| # | Что не так | Где | Эффект на картинке | Фикс в текущем коде (Фаза 0) |
|---|---|---|---|---|
| **N1** | «Тень» (Dialogue слой 3) в не‑type ветке использует **тот же** `pos_tag`/`\move`, что и текст — смещения `sh_off` нет. Для `rise/slide/bounce` тоже. | хвост, `else:` ветка, `lines.append(f"Dialogue: 3,...{{\\an5{pos_tag}{in_tag}...")` | Вместо drop shadow — вторая чёрная обводка, текст выглядит «жирно‑грязно», без объёма | Использовать `\shad`/`\xshad\yshad` на основном слое **или** дать слою 3 `\pos(px+sh_off, py+sh_off)` и сдвинутый `\move` |
| **N2** | Слой тени **не получает `sway`**, а текст и glow — получают (`\frz±1`). | там же | Текст качается, чёрная копия нет → по краю букв мерцает чёрная кайма | Одинаковый набор трансформ для всех слоёв одного элемента (генерировать из одной строки) |
| **N3** | В type‑ветке `out_tag` посчитан для всего элемента (`o0 = dur_ms-out_ms`), но применяется к каждой букве, чей Dialogue стартует позже (`ls`). Время в `\t` — относительно начала события. | хвост, type‑ветка | Поздние буквы **не успевают** затухнуть и обрываются на `te`; плюс `\fad(15,out_ms)` даёт второй fade поверх | Для буквы i: `o0_i = (te-ls_i)*1000 - out_ms`; убрать дубль `\fad` |
| **N4** | `per = (dur_ms-200)//len(text)` и `ls = ts + i*per` считают `\` и `N` как символы; `xs` строится по строке, где `\N`→1 пробел, а цикл пропускает только `\` → индекс `xi` съезжает на 1 после каждого переноса. | хвост | Буква «N» в тексте, позиции после переноса сдвинуты, многострочная печать в одну строку по `py` | Токенизировать текст на графемы + маркеры переноса до любых расчётов |
| **N5** | `zoom` in: основной слой заканчивает анимацию на `\blur0.8` и **остаётся размытым** до конца; у glow‑слоёв `\t(...\blur0.8)` из `in_tag` конфликтует с `\blur{gb1}` и `gb_osc` (несколько `\t` на один тег). | хвост, `in_map["zoom"]` | Текст мягкий весь кадр; свечение «схлопывается» во время интро и прыгает | `\blur0` в конце; анимацию blur для glow строить отдельно |
| **N6** | `gb_osc` («дыхание» glow ±20%) и `sway` (треугольная волна `\frz±1` каждые ~350 мс, **линейная**, со сменой направления рывком). | хвост | Дешёвая пульсация свечения и дёрганое покачивание (разрыв скорости каждые 350 мс). В вирусных эдитах glow статичен | Удалить `gb_osc`; `sway` — только как опция, синус с `\t(t0,t1,accel,...)` или вообще нет |
| **N7** | `shake_tag` анимирует `\fsp` (межбуквенный интервал). | хвост | Ширина строки «дышит», центрирование плывёт — не похоже на шейк | Шейк = смещение/поворот всего элемента, не трекинг |
| **N8** | Грейд заканчивается `format=yuv420p`, **после** него накладываются субтитры/текст (порядок из докстринга `_export_layered_clip`: «…then grade, static frames, subtitles and free text on top»). libass рисует в 4:2:0. | `_tv_grade_parts` + порядок в `_export_layered_clip` | Цвет текста и свечения хранится в половинном разрешении: красные/жёлтые края «грязные», ореол цветной каши вокруг обводки | Перед `subtitles=` → `format=gbrp`, после всего текста один `scale=out_color_matrix=bt709:out_range=tv:flags=accurate_rnd+full_chroma_int,format=yuv420p` |
| **N9** | Неявные конверсии YUV↔RGB вокруг `lut3d`/`eq`/`blend`/`overlay` без указания матрицы. Если поток не помечен BT.709, swscale по умолчанию берёт BT.601. | весь граф | Сдвиг оттенков (кожа/зелень), разный цвет превью и экспорта | На входе `setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv`; при скачивании проставлять теги bitstream‑фильтром (см. §6.1) |
| **N10** | `flash` = `blend=all_mode=addition` цветного RGBA‑источника на кадр. Если граф согласуется в YUV, складываются и плоскости U/V. Плюс генерируется **полнокадровый** `color` на всю длину ролика на каждую вспышку. | `_apply_fx_chain` | Клиппинг светов (в RGB) или цветной сдвиг (в YUV); медленно | Screen/exposure‑вспышка в RGB, источник длиной `d`, `setpts` как у `bars` |
| **N11** | Shake: `crop=iw-2a:ih-2a` + `scale` обратно → внутри окна `enable` кадр увеличен на `(1+2a/W)`, снаружи — нет. | `_apply_fx_chain` | **Скачок зума** в начале и конце шейка, двойной ресэмплинг | Постоянный overscan на всём клипе или плавный вход/выход зума; в новом рендерере — трансформ камеры |
| **N12** | В `build_tv_subtitles_ass` все слова фразы получают один `\pos(cx, base_y)` — раскладки фразы нет. | `build_tv_subtitles_ass` | Слова рисуются друг поверх друга при перекрытии по времени | Раскладка всей фразы → x‑диапазон каждого слова (§3.3) |
| **N13** | Пружина движка `engine/src/render.rs::pop_scale`: ζ=0.74 → перелёт **всего 3.2%** (`exp(-ζπ/√(1-ζ²))`). В ASS pop — ломаная линейная кривая 68→112→100% с разрывом скорости на 90 мс. | `render.rs` L31–49; ASS `\t` без `accel` | Движковый pop «ватный», ASS‑pop «тикает». У вирусных эдитов перелёт 15–25% | ζ≈0.45–0.5 (§3.5) |
| **N14** | Нет канонического отображения времени: `_remap_subtitles_for_segments` дублирует cue на все пересекающиеся сегменты, не обрезает по границе, special‑case для 1 сегмента смешивает source/output время. | хвост | Дубли и «вылезающие» слова на склейках | `mapTime()` (§2.3) |
| **N15** | Превью декодирует **один и тот же файл до 5 раз** (`studioVideoPlayer`, `studioOverlayPlayer`, `tvpTopVideo`, `tvpBottomVideo`, `tvpPipVideo`) и держит 2 часовые системы: rAF‑часы `state.currentTime` и собственные часы каждого `<video>`, коррекция только при дрейфе > 120 мс (`setElTime`). | `editor.js` | Рассинхрон половин сплита, текст опережает/отстаёт от речи до 7 кадров | Один декод на файл + один мастер‑клок (§5) |
| **N16** | `main.js` переиспользует уже запущенный `server.py` без проверки версии. `PLAN_verification.md` прямо зафиксировал: проблемный экспорт сделан **старой копией** сервера. | `main.js` | Правки «не работают», тестируется старый код | `/api/version` (git sha + mtime `server.py`); при несовпадении — убить и перезапустить |
| **N17** | `kick_extractor.py`: `fps = int(float(...))` → 59.94→59; флаг `is_source` не ставится, если максимум битрейта — первый элемент (обычный случай). | `kick_extractor.py` | Неверный FPS в расчётах, UI может не предложить source‑качество | `float`, `is_source` = argmax битрейта |
| **N18** | Пользовательский текст в ASS не экранируется; `_source_has_audio` → `True` при ошибке ffprobe. | хвост / выше | Инъекция тегов, падение графа на `[0:a]` | Экранирование `{}\`; `False` + `anullsrc` |

**Поправки к существующему плану**
- `fmt_ass_time`: «короткие слова схлопываются» — преувеличено; реальная проблема — двойное квантование (1/60, затем 1/100) → дрожание границ ±10 мс.
- «Нет loudnorm» — по `PLAN_verification.md` однопроходный `loudnorm` и x264 `film CRF 15` уже есть. Нужен двухпроходный.
- «SSIM превью/экспорт ≥ 0.99» после H.264 недостижимо на зернистом материале. При общем рендерере правильный тест другой (§8).
- PixiJS не рекомендую: нужны float‑FBO, свой порядок пассов, детерминизм и асинхронный readback. Тонкий свой слой на WebGL2 (или `twgl.js`) проще контролировать.
- Пружина движка задокументирована как «stiffness=180, damping=20», но реально считается только `w0=12, z=0.74` в нормированном времени `t/pop_dur`: при `pop_dur=0.26` это ω₀≈46 рад/с.

---

## 2. Модель сцены: что добавить к `Composition JSON` из плана

### 2.1. Единицы и пространства
- **Канва** — эталонные единицы 1080×1920 (или 1920×1080). Все размеры текста, радиусы blur/glow, амплитуды shake — в эталонных px или в `em` (доля кегля). Превью рендерит в `scale = monitorPx/1080`, **радиусы всех фильтров умножаются на `scale`** → превью выглядит как уменьшенный экспорт, а не «другой» кадр.
- **Кропы** — в `space:"source"` (доли кадра исходника), **позиции** — в `space:"canvas"`. Пикер кропа переводит указатель из экрана в source с учётом реального прямоугольника видео внутри `object-fit: contain`:
  ```js
  function contentRect(el, vw, vh) {            // куда реально легло видео
    const r = el.getBoundingClientRect(), s = Math.min(r.width / vw, r.height / vh);
    const w = vw * s, h = vh * s;
    return { x: r.left + (r.width - w) / 2, y: r.top + (r.height - h) / 2, w, h };
  }
  const toSource = (px, py, cr) => ({ x: (px - cr.x) / cr.w, y: (py - cr.y) / cr.h }); // clamp 0..1
  ```
- **Время** — целые кадры композиции (`frame = round(t*fps)`), секунды только на границах (ASR, UI).

### 2.2. Анимируемое свойство
```ts
type Anim<T> = T | { k: Array<[t: number, v: T, ease?: Ease]> } | { spring: SpringSpec, from: T, to: T, at: number };
type Ease = "linear" | "hold" | ["bezier", x1, y1, x2, y2] | ["spring", overshoot, settleMs];
```
Оценка — чистая функция `evalAnim(a, tLocal)`. Никакого `Math.random()` и wall‑clock: весь шум — `hash(seed, frame)` (§3.8). Это то, что делает превью и экспорт бит‑в‑бит одинаковыми и повторный экспорт воспроизводимым.

### 2.3. Одна функция времени
```ts
// timeline t → время внутри слоя → время исходника (спидрамп = интеграл скорости)
function mapTime(layer, t) {
  const local = t - layer.time.in;
  const src = layer.time.speed ? layer.time.srcIn + integrateSpeed(layer.time.speed, local)
                               : layer.time.srcIn + local;
  return { local, src };
}
// integrateSpeed по кусочно‑линейной кривой скорости: сумма трапеций, O(число ключей)
```
Её используют: декодер (какой кадр брать), текст (время слова `word.s` хранится в **исходном** времени и проецируется через обратную `mapTime` при компиляции), аудио (растяжение/`atempo`), экспорт. Удаляются `subs_in_output_time` и `_remap_subtitles_for_segments`. Правило для слова на склейке: слово принадлежит сегменту, где лежит его **середина**; концы обрезаются по границе сегмента; слово короче 2 кадров после обрезки выкидывается.

### 2.4. Инвариант текста
`subtitle_mode: "timeline" | "generated" | "none"`. Сервер **отклоняет** (422) payload, где одновременно есть ASR‑клипы с `words` в `text_items` и непустой `subtitles`. Это закрывает двойной текст на уровне контракта, а не надежды на UI.

---

## 3. Текстовый движок уровня After Effects

### 3.1. Загрузка шрифтов (иначе первые кадры — fallback)
```js
const face = new FontFace("Montserrat", "url(/api/fonts/Montserrat-BlackItalic.ttf)", { weight: "900", style: "italic" });
await face.load(); document.fonts.add(face);            // в воркере: self.fonts.add(face)
if (!document.fonts.check('italic 900 100px "Montserrat"', "ЁЖЯ")) throw new Error("font not ready");
```
Экспорт **не стартует**, пока все шрифты сцены не загружены. При старте сервер проверяет cmap каждого шрифта на U+0410–U+044F, U+0401, U+0451 (fontTools) и отдаёт в UI только прошедшие. Для вирусного стиля нужны настоящие курсивные начертания (Montserrat Black Italic, Inter Tight Black Italic): синтетический наклон через shear увеличивает bbox и ломает кернинг.

### 3.2. Сегментация
`Intl.Segmenter("ru", {granularity:"grapheme"})` для букв (эмодзи с ZWJ, «й»/«ё» из двух кодпоинтов — одна единица), `granularity:"word"` для слов. Переносы строк — явные токены, никогда не символы.

### 3.3. Раскладка с кернингом без HarfBuzz‑API
Canvas не отдаёт позиции глифов, но их можно получить префиксными замерами — это **сохраняет кернинг и лигатуры** (именно то, что ломает N12/RC2):
```js
ctx.font = 'italic 900 120px "Montserrat"'; ctx.fontKerning = "normal"; ctx.letterSpacing = `${tracking}px`;
const g = [...seg.segment(line)].map(s => s.segment);
let acc = "", xs = [];
for (const ch of g) { xs.push(ctx.measureText(acc).width); acc += ch; }   // x начала каждой графемы
const lineW = ctx.measureText(acc).width;
```
O(n²) по длине строки — для 2 строк по 20 символов это ~400 замеров, кешируется по `(font,size,text)`.

Перенос/баланс строк: максимум 2 строки, ширина ≤ `0.86·W`; перебрать все точки разрыва между словами, выбрать минимум `max(w1,w2)` (а не жадный перенос) — строки получаются одинаковой длины, как у моушн‑дизайнеров. Если не влезает — уменьшать кегль шагом 4% до `minSize`, затем разбивать экран на два cue.

Safe‑area Shorts/TikTok (эталон 1080×1920): верх 0–220 px, низ 1520–1920 px (описание/кнопки), правый край 950–1080 px в нижней половине. Субтитры по умолчанию центр строки на `y=0.64–0.70·H`.

### 3.4. Растеризация и порядок пассов (как в AE)
- Растр строки делается **один раз** на уникальное состояние в `OffscreenCanvas` в масштабе `S = maxAnimatedScale · renderScale · 2` (например pop до 1.25× и zoom‑punch 1.15× → растр в 2.9× эталона при экспорте). Иначе при pop‑е буквы мылятся — самая частая причина «не как в AE». Текстура с mipmaps, `LINEAR_MIPMAP_LINEAR`.
- Паддинг растра: `stroke + glowRadius + |shadowOffset| + shear·ascent`.
- Каждая графема — **отдельный квад**, сэмплирующий свой подпрямоугольник того же растра (кернинг из общей раскладки сохраняется). Инстансинг: атрибуты `translate, scale, rot, opacity, blur, colorMix, glowBoost` на глиф, считаются аниматорами на CPU (≤200 глифов на экран — копейки).
- Пассы слоя текста:
  1. глифы (fill + stroke) → FBO слоя, premultiplied RGBA16F;
  2. **stroke через SDF**: из маски 2× строится distance field jump‑flood'ом (`⌈log2(maxDist)⌉` пассов, ~7 для 128 px), обводка `a = smoothstep(r+0.5, r-0.5, d)`. Ровная круглая обводка любой толщины, анимируемая без перерастра (заменяет `\bord` и `dilate` движка);
  3. **glow от цветного слоя**, а не от альфы одним цветом: dual‑Kawase blur premultiplied RGBA (4–5 итераций, на ½ и ¼ разрешения) → пословные цвета свечения получаются сами. Два радиуса (0.15em и 0.45em, веса 0.85 и 0.45 — это константы из `engine/src/text.rs`), режим add в линейном свете;
  4. drop shadow: blur альфы (σ = 0.08em), смещение (0, 0.06em), чёрный 60–70%;
  5. extrude (MrBeast): 6–12 копий по диагонали с затемнением, до glow.
- **Связь свечения и появления** (лечит RC3/D3 по построению): `glowAlpha_i = opacity_i^1.5 · glowAmount · glowBoost_i`. Glow физически не может появиться раньше буквы.

### 3.5. Пружина: точная формула и параметры
Затухающий осциллятор от 0 к 1 с начальной скоростью `v0` (аналитика, без интегрирования — детерминировано и даёт скорость для motion blur):
```js
// ζ и ω0 из «перелёт O» и «время успокоения Ts (2%)»
function springParams(O, Ts) { const L = Math.log(O); const z = -L / Math.sqrt(Math.PI**2 + L*L); return { z, w0: 4 / (z * Ts) }; }
function spring(t, { z, w0, v0 = 0 }) {             // возвращает [x, dx/dt]
  if (t <= 0) return [0, v0];
  const x0 = -1;                                     // смещение от цели
  if (z < 1) {
    const wd = w0 * Math.sqrt(1 - z*z), e = Math.exp(-z*w0*t);
    const A = x0, B = (v0 + z*w0*x0) / wd, c = Math.cos(wd*t), s = Math.sin(wd*t);
    const x = 1 + e * (A*c + B*s);
    const dx = e * ((-z*w0)*(A*c + B*s) + (-A*wd*s + B*wd*c));
    return [x, dx];
  }
  const e = Math.exp(-w0*t), B = v0 + w0*x0;          // критическое демпфирование
  return [1 + e*(x0 + B*t), e*(B - w0*(x0 + B*t))];
}
```
При `v0=0` формула совпадает с `engine/src/render.rs::pop_scale`. Эталонные значения: перелёт 18%, успокоение 300 мс → ζ=0.479, ω₀=27.8 рад/с. Для «slam» 8%/200 мс, для «bounce» 30%/450 мс.

Кубический безье (для кейфреймов AE‑стиля): решать `x(u)=t` Ньютоном 4–6 итераций с fallback на бисекцию, как в Chromium `UnitBezier`. Easy Ease AE = `(0.33,0,0.67,1)`; «вирусный snap» = `(0.16,1,0.3,1)`.

### 3.6. Аниматоры (аналог Text Animator + Range Selector)
Для единицы i (графема/слово/строка) из n:
- порядок `ord_i`: forward `i`, backward `n-1-i`, center‑out `|i-(n-1)/2|`, random — перестановка по `hash(seed)`;
- задержка: для ASR‑слов **`delay_i = word.s - cue.s`** (реальное время речи, не равномерный stagger); иначе `delay_i = ord_i · stagger`;
- локальное время `τ_i = tLocal - delay_i`, значение свойства `p_i = to + (from - to)·(1 - E(τ_i))`, где `E` — пружина или безье.

| Пресет | Параметры (эталон 60 fps) |
|---|---|
| `word_pop_spring` | scale 0.55→1 пружиной (18%/300 мс); opacity 0→1 за 50 мс; blur 6→0 px за 90 мс; y +0.08em→0; rot ±4°·rand(seed,i)→0 той же пружиной |
| `slam` (hot‑слова) | scale 2.2→1 easeIn(quad) 120 мс, motion blur вкл.; в момент касания: shake 6 px 80 мс + glowBoost 2→1 за 120 мс + SFX impact |
| `char_type` (ремарки `*ОРЁТ*`) | 38 мс/графема; каждая: opacity ступенькой, scale 1.3→1 за 90 мс easeOutCubic, glowBoost 2→1 |
| `karaoke_fill` | фраза видна (opacity 0.6, белый); активное слово: scale 1→1.12 пружиной, цвет→акцент за 60 мс, glowBoost 1.6 |
| `bounce_in` | y −0.6em→0 пружиной 30%/450 мс |
| `wave` (idle) | y = 0.04em·sin(2π·1.2·t − 0.6·i) |
| `jitter` (idle, rage) | dx,dy = 1.5 px·noise(seed_i, t·12), rot ±1.2°·noise |
| `glitch_in` | 4 кадра: сдвиг горизонтальных полос по `hash(row,frame)`, RGB‑split 6→0 px |
| `out_blur_fade` | 180 мс: opacity→0, blur→10 px, scale→0.94, easeInCubic |
| `out_burn` | 100 мс fill→белый и glow×3, затем opacity→0 за 120 мс |
| `whip_out` | x→+0.3W easeInExpo 150 мс + направленный blur по скорости |

Idle‑«дыхания» glow нет (см. N6).

### 3.7. Motion blur для текста и камеры
Скорость известна аналитически (производная пружины/безье). Два режима:
- **дёшево (превью)**: направленный blur квада глифа вдоль экранной скорости, длина `|v|·shutter/fps` (shutter 180° → 0.5/fps), 8 сэмплов в шейдере;
- **точно (экспорт)**: N сабсэмплов кадра `t_k = t + (k/(N-1) - 0.5)·0.5/fps`, **только для слоёв с ненулевой скоростью**, накопление в RGBA16F (`EXT_color_buffer_float` обязателен, проверять при старте). N=8 по умолчанию. Видеокадр исходника в сабсэмплах не передекодируется — у него свой родной смаз.

### 3.8. Детерминированный шум
```js
function pcg(n) { n = (n * 747796405 + 2891336453) >>> 0; let w = ((n >>> ((n >>> 28) + 4)) ^ n) * 277803737 >>> 0; return ((w >>> 22) ^ w) >>> 0; }
const rand = (seed, i) => pcg(seed ^ Math.imul(i, 0x9E3779B1)) / 4294967296;             // [0,1)
const noise1 = (seed, x) => { const i = Math.floor(x), f = x - i, u = f*f*(3-2*f); return (rand(seed,i)*(1-u) + rand(seed,i+1)*u) * 2 - 1; };
```
Тот же код портируется в GLSL (`uint`‑арифметика WebGL2) для глитча и зерна.

---

## 4. Цветокор

### 4.1. Где происходит каждая операция
Декод (YUV→RGB, BT.709 limited) → **линеаризация** (`pow(x, 2.4)`, BT.1886; обратная ровно та же функция на выходе → круговой проход без сдвига) → exposure и баланс белого **в линейном** → контраст **в логе** вокруг 0.18 → roll‑off светов → CDL/насыщенность/вторичные/split‑toning **в display‑пространстве** → креативный LUT → пространственные эффекты (clarity, bloom, виньетка) → зерно/дизеринг → квантование.

### 4.2. Шейдер первичного грейда (WebGL2)
```glsl
#version 300 es
precision highp float; precision highp sampler3D;
uniform sampler2D uSrc; uniform sampler3D uLut; uniform float uLutN, uLutMix;
uniform vec3 uWB; uniform float uExpo, uContrast, uKnee, uSat, uVib;
uniform vec3 uSlope, uOffset, uPower; uniform vec4 uShadowTint, uHighTint;
uniform vec4 uHue[4];   // (hueCenter, width, satGain, lumGain) — вторичные
uniform float uSkinProtect;
in vec2 vUv; out vec4 o;
const vec3 K = vec3(0.2126, 0.7152, 0.0722);
vec3 lin(vec3 c){ return pow(max(c,0.), vec3(2.4)); }  vec3 disp(vec3 c){ return pow(max(c,0.), vec3(1./2.4)); }
vec3 rgb2hsv(vec3 c){ vec4 K4=vec4(0.,-1./3.,2./3.,-1.); vec4 p=mix(vec4(c.bg,K4.wz),vec4(c.gb,K4.xy),step(c.b,c.g));
  vec4 q=mix(vec4(p.xyw,c.r),vec4(c.r,p.yzx),step(p.x,c.r)); float d=q.x-min(q.w,q.y); return vec3(abs(q.z+(q.w-q.y)/(6.*d+1e-6)),d/(q.x+1e-6),q.x); }
void main(){
  vec3 c = lin(texture(uSrc, vUv).rgb) * uWB * exp2(uExpo);
  c = 0.18 * exp2(log2(max(c, 1e-5) / 0.18) * uContrast);                   // контраст в логе
  vec3 k = vec3(uKnee); c = mix(c, k + (1.-k)*(1.-exp(-(c-k)/(1.-k))), step(k, c)); // плечо: C1‑гладкое
  vec3 d = pow(max(disp(c) * uSlope + uOffset, 0.), uPower);               // ASC CDL
  vec3 hsv = rgb2hsv(clamp(d,0.,1.)); float Y = dot(d, K);
  float skin = smoothstep(0.10, 0.02, abs(hsv.x - 0.07)) * smoothstep(0.1, 0.3, hsv.y) * uSkinProtect; // тон кожи ~25°
  float satMul = uSat * (1. + uVib * (1. - hsv.y));
  for (int i = 0; i < 4; i++) { float dh = abs(fract(hsv.x - uHue[i].x + .5) - .5);
    float w = max(0., cos(min(dh / uHue[i].y, 1.) * 1.5708)); satMul *= 1. + (uHue[i].z - 1.) * w; }
  satMul = mix(satMul, 1. + (satMul - 1.) * 0.35, skin);                  // кожу не пересыщаем
  d = Y + (d - Y) * satMul;
  float w = smoothstep(0.05, 0.95, Y);
  d += uShadowTint.rgb * uShadowTint.a * (1. - w) + uHighTint.rgb * uHighTint.a * w;
  vec3 s = (clamp(d,0.,1.) * (uLutN - 1.) + .5) / uLutN;                  // центр ячеек LUT
  d = mix(d, texture(uLut, s).rgb, uLutMix);
  o = vec4(d, 1.);
}
```
Важно: `sampler3D` даёт **трилинейную** интерполяцию, а FFmpeg в текущем коде — `interp=tetrahedral`. Для совпадения переходного периода ставить в FFmpeg `interp=trilinear` (или писать тетраэдральную выборку в шейдере 8 `texelFetch`‑ами).

### 4.3. Авто‑нормализация на клип (без «пульсации»)
При добавлении нарезки сервер берёт 12 кадров равномерно (`ffmpeg -ss … -frames:v 1` по 64×… даунскейлу) и считает:
- перцентили яркости p1/p50/p99 → `expo = clamp(log2(0.40 / p50_lin_display), -1, +1)` EV;
- серый мир по «почти нейтральным» пикселям (HSV S<0.12, 0.15<Y<0.85) → `wb = mean_g / mean_c`, ограничение ±15% на канал;
- чёрная точка по p1 → `offset`.
Параметры **константны на весь клип** (никакого покадрового автоэкспозиционирования — именно оно даёт пульсацию). Если внутри региона свет резко меняется (>1 EV между сэмплами) — нормализация по под‑сегментам с кроссфейдом параметров 0.5 с.

### 4.4. Пространственные операции
- **Clarity** (локальный контраст): `L' = L + k·(L − guided(L, r=24px@1080, ε=0.01))` с маской средних тонов `4·L·(1−L)`. Guided filter вместо гаусса — без ореолов вокруг вебки и текста чата. k=0.2–0.3.
- **Bloom**: soft‑knee порог в линейном (`knee=0.85`), пирамида 6 уровней dual‑filter вниз/вверх, add с весом 0.05–0.12. **Halation**: тот же bloom, взвешенный `(1, 0.35, 0.1)` — красноватый ореол светов, «плёночный» вид.
- **Виньетка**: `1 − 0.18·r^1.6` (формула движка), в линейном.
- **Резкость**: RCAS (AMD FSR1, MIT) по яркости **на выходном разрешении** после всех ресэмплингов, 0.25–0.4. Никакого `hqdn3d` перед грейдом.
- **Зерно**: blue‑noise 64×64 с офсетом `hash(frame)` (детерминизм), амплитуда `0.025·(4·Y·(1−Y))^0.5`, добавляется до квантования — работает и как дизеринг от бандинга. На x264 держать зерно ≤3%, иначе съест битрейт.

### 4.5. Пресет `Viral Punch` (стартовые значения, подбирать A/B‑шторкой)
exposure = авто; contrast 1.18; knee 0.80; CDL slope (1.02, 1.00, 0.97), offset (−0.010, −0.004, +0.012), power 1.0; saturation 1.15; vibrance 0.25; вторичные: красные (h 0.0, w 0.06) sat ×1.18, пурпур (0.85, 0.07) ×1.12, зелень (0.33, 0.08) ×0.92; skinProtect 0.6; тени teal (0.00, 0.03, 0.05)·0.6, света warm (0.05, 0.02, −0.02)·0.5; clarity 0.25; bloom 0.08; halation 0.04; vignette 0.18; RCAS 0.35; grain 0.025.

### 4.6. Мост на переходный период: грейд, одинаковый в FFmpeg и превью
Пока экспорт видео идёт через FFmpeg: весь попиксельный грейд (§4.2 без пространственных частей) **запекается в LUT 65³** той же JS‑функцией (порт шейдера на CPU, 274 625 точек ≈ 50 мс) → пишется `.cube` в `downloads/.cache/grade_<hash>.cube` → FFmpeg `lut3d=interp=trilinear` в `gbrpf32le`, превью берёт тот же массив как `sampler3D`. Совпадение по построению. `tv_grade.cube` (17³) остаётся как пресет «TV Acid (legacy)».

---

## 5. Превью: как чинить, по шагам

### P0 (2–4 дня) — один canvas поверх существующих `<video>`
1. `#studioVideoPlayer`, `#tvPreview`, `#subtitlesMonitorOverlay`, `.overlay-pip` визуально скрываются; монитор = один `<canvas>` с размером канвы композиции (9:16 или 16:9) — формат берётся из `state.clipper.format`, `state.aspectRatio` становится производным (исправляет RC8/H7).
2. **Один скрытый `<video>` на уникальный файл** (а не на слой): сплит «верх/низ» и PiP из одного источника рисуются `drawImage(video, sx,sy,sw,sh, dx,dy,dw,dh)` из **одного** декодированного кадра → половины больше не рассинхронизируются, нагрузка на декодер падает в 3–5 раз.
3. Мастер‑клок при воспроизведении — **аудио**: `t = t0 + (audioCtx.currentTime − ctx0) − audioCtx.outputLatency`. Видео‑элементы только догоняют его: при |дрейф| > 1 кадра — `playbackRate` 0.97/1.03 на 250 мс, при > 150 мс — seek. Стоп‑кадр/скраб: `video.requestVideoFrameCallback((now, meta) => draw(meta.mediaTime))` — текст и эффекты рисуются для **фактически показанного** кадра (`meta.mediaTime`), а не для желаемого `t`. Это даёт кадровую синхронизацию текста с картинкой без WebCodecs.
4. Все CSS‑`@keyframes` текста (`tvWave`, `tvShimmer`, `tvType`, `tvTremble`) удаляются; текст рисуется в тот же canvas модулем `web/core/text/*` (§3) — **тем же кодом, который позже будет рендерить экспорт**. Уже на P0 текст превью совпадает с будущим экспортом.
5. Шаг кадра `±1/fps` композиции с привязкой к сетке `round(t·fps)/fps`; `activeVideoLayers()` без лимита 2; PiP/кропы/трекинг — из `pipBox`/`cropBox`/`trackPath` в пространствах §2.1.
6. Грейд в превью — WebGL2‑пасс поверх canvas с LUT из §4.6 (тот же, что уходит в FFmpeg).

Ограничения P0: `drawImage(video)` не гарантирует кадр при seek во время воспроизведения (решено rVFC), YUV→RGB делает браузер (решено тегами BT.709 при скачивании, §6.1).

### P1 (2–3 недели) — WebCodecs + общий рендерер
- **Демукс**: mp4box.js; для H.264 `description` = сериализованный `avcC` из `stsd.entries[0]` (без 8 байт заголовка бокса). Индекс сэмплов (`pts`, `is_sync`) строится один раз.
- **Декод**: воркер на ассет, `VideoDecoder` с `hardwareAcceleration:"prefer-hardware"`, держать `decodeQueueSize ≤ 4`; выходные кадры идут **в порядке pts** (B‑кадры переупорядочены декодером), кольцевой кэш ≤ 12 `VideoFrame` на ассет, **каждый кадр `close()` после загрузки в текстуру** — иначе через 1–2 с GPU‑память кончается и декодер встаёт.
- **Seek**: ближайший sync‑сэмпл ≤ цели → скормить сэмплы до цели → выбросить кадры с `pts < target`. Для скраба — прокси 960×540, GOP 10 (≤9 лишних декодов); во время перетаскивания показывать ближайший кэшированный кадр, уточнять по отпусканию (debounce 60 мс).
- **Выбор кадра**: для исходника с `fps_src` и времени `src` — кадр `floor(src·fps_src + 1e-6)` (удержание, как FFmpeg `fps`‑фильтр round=down). 30→60 fps = каждый кадр дважды, одинаково в превью и экспорте.
- **Загрузка в GPU**: `gl.texImage2D(..., videoFrame)` (VideoFrame — валидный TexImageSource в Chromium; Electron 44 ⇒ WebGL2/WebCodecs/OffscreenCanvas есть, но проверять фичи при старте и иметь fallback на P0‑путь).
- **Планирование рендера**: rAF на частоте дисплея, перерисовка только если сменился `frameIndex` или «грязное» свойство; превью рендерится в `monitorPx·dpr` (например 405×720 ×2), экспорт — 1080×1920 тем же `renderFrame(comp, frame, target, scale)`.
- **Аудио превью**: WebAudio‑граф с теми же гейнами/дакингом, что у экспорта; огибающая дакинга считается сервером один раз (RMS голоса) и применяется `GainNode.setValueCurveAtTime` в превью и `volume='…':eval=frame` / предрендер WAV в экспорте.

---

## 6. Экспорт

### 6.1. Нормализация исходника при скачивании (ingest)
- Точный трим: вместо `-ss … -c copy` (режет по ключевым кадрам) — либо скачать с запасом ±2 с и хранить смещение, либо перекодировать мезонин.
- Проверка: `ffprobe -show_entries stream=r_frame_rate,avg_frame_rate` + поиск разрывов pts. Если VFR/разрывы — мезонин `libx264 -crf 12 -preset veryfast -g 60 -fflags +genpts -vsync cfr -r <fps>`; иначе ремукс.
- Теги цвета без перекодирования: `-bsf:v h264_metadata=colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1:video_full_range_flag=0` — после этого браузер и FFmpeg гарантированно конвертируют YUV→RGB одной матрицей (закрывает N9).
- По умолчанию — **source/1080p60** (для 9:16 из 16:9 это кроп 608×1080 вместо 405×720; апскейл ×1.78 вместо ×2.67).
- Прокси 960×540 GOP 10 для скраба.

### 6.2. Рендер кадров в Electron → x264 (основной «качественный» путь)
**Почему не WebCodecs `VideoEncoder` по умолчанию**: на Windows он идёт в аппаратный MF‑энкодер, который при равном битрейте заметно уступает x264 `slow`; а платформы всё равно перекодируют — входное качество решает. **Почему не сырые RGBA через IPC**: 1080×1920×4×60 ≈ 498 МБ/с, у окна нет preload/`nodeIntegration`.

Решение: упаковка в YUV420 в шейдере и стрим на уже существующий `server.py`.
- Три пасса упаковки, результат читается без конверсии на CPU:
  - Y: цель `(W/4)×H RGBA8`, каждый тексель = 4 соседних отсчёта яркости;
  - U и V: цели `(W/8)×(H/2) RGBA8`.
  ```glsl
  // Y‑пасс. uRGB — финальный кадр (display‑referred, [0..1]); flip по Y, т.к. readPixels снизу вверх
  uniform sampler2D uRGB; uniform highp usampler2D uBlue; uniform int uFrame, uH;
  out vec4 o;
  float Yp(vec3 c){ return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
  void main(){
    ivec2 p = ivec2(gl_FragCoord.xy); int y = uH - 1 - p.y; vec4 r;
    for (int i = 0; i < 4; i++) {
      ivec2 q = ivec2(p.x*4 + i, y);
      float dn = (float(texelFetch(uBlue, (q + uFrame*17) & 63, 0).r) / 255. - .5);   // ±0.5 LSB дизер
      r[i] = (16. + 219. * Yp(texelFetch(uRGB, q, 0).rgb) + dn) / 255.;
    }
    o = r;
  }
  // U/V‑пасс: среднее 2×2 (центральное позиционирование; для точного "left" — веса [1,2,1]/4 по X),
  // Cb = 128 + 224*(B'-Y')/1.8556, Cr = 128 + 224*(R'-Y')/1.5748
  ```
- Асинхронный readback, чтобы не ждать GPU: 3 PBO по кругу.
  ```js
  gl.bindBuffer(gl.PIXEL_PACK_BUFFER, pbo[i]); gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, 0);
  fences[i] = gl.fenceSync(gl.SYNC_GPU_COMMANDS_COMPLETE, 0);
  // через 1–2 кадра:
  if (gl.clientWaitSync(fences[j], 0, 0) !== gl.TIMEOUT_EXPIRED) { gl.getBufferSubData(gl.PIXEL_PACK_BUFFER, 0, view); ws.send(view); }
  ```
- Объём: 1080×1920×1.5 = **3 110 400 байт/кадр**; при скорости рендера 30 fps — 93 МБ/с по localhost WebSocket. Поток с кредитами: клиент держит ≤ 8 неподтверждённых кадров, сервер шлёт `{ack:n}` каждые 4.
- Сервер (FastAPI; нужен пакет `websockets` для uvicorn):
  ```python
  @app.websocket("/ws/render/{job_id}")
  async def ws_render(ws: WebSocket, job_id: str):
      await ws.accept()
      hdr = await ws.receive_json()   # {w,h,fps,frames,audio_wav,out}
      args = ["ffmpeg","-y","-f","rawvideo","-pix_fmt","yuv420p","-s",f"{hdr['w']}x{hdr['h']}","-r",str(hdr['fps']),
              "-color_range","tv","-colorspace","bt709","-color_primaries","bt709","-color_trc","bt709","-i","pipe:0",
              "-i",hdr["audio_wav"],"-map","0:v","-map","1:a",
              "-c:v","libx264","-preset","slow","-crf","16","-tune","film","-profile:v","high","-level","4.2",
              "-x264-params","aq-mode=3:deblock=-1,-1","-g",str(hdr['fps']*2),"-pix_fmt","yuv420p",
              "-colorspace","bt709","-color_primaries","bt709","-color_trc","bt709","-color_range","tv",
              "-c:a","aac","-b:a","320k","-movflags","+faststart","-shortest",hdr["out"]]
      proc = await asyncio.create_subprocess_exec(*args, stdin=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
      n = 0
      try:
          while n < hdr["frames"]:
              proc.stdin.write(await ws.receive_bytes()); await proc.stdin.drain(); n += 1
              if n % 4 == 0: await ws.send_json({"ack": n})
      finally:
          proc.stdin.close(); rc = await proc.wait(); await ws.send_json({"done": rc == 0})
  ```
  На Windows asyncio‑subprocess требует Proactor‑цикла (дефолт Python ≥3.8, но uvicorn с `--reload` может переключить на Selector) — либо проверить, либо писать в `subprocess.Popen` из отдельного потока через `asyncio.Queue(maxsize=8)`.
- Уровень H.264: 1080×1920 = 68×120 = 8160 макроблоков/кадр, ×60 = 489 600 MB/s → укладывается в **High@4.2** (MaxFS 8704, MaxMBPS 522 240). Для WebCodecs это `avc1.64002A`.
- Аудио собирается сервером **до** видео в WAV (существующий граф SFX/`extra_audio`/дакинг) + **двухпроходный** `loudnorm=I=-14:TP=-1:LRA=11` (первый проход `print_format=json`, второй с `measured_*`) + лимитер. Мукс — в той же команде.
- «Быстрый» режим: `VideoEncoder({codec:"avc1.64002A", width:1080, height:1920, bitrate:25e6, framerate:60, latencyMode:"quality", avc:{format:"annexb"}})` → чанки по тому же WebSocket → `ffmpeg -f h264 -i pipe:0 -c:v copy`.
- Отмена/прогресс — через существующий SSE `/api/progress`.

### 6.3. Переходный экспорт (пока рендерер не готов) — чинить ASS‑путь
Фаза 0 из плана + N1–N11: порядок графа `setparams(bt709) → crop → один scale lanczos → grade (LUT §4.6, gbrpf32le) → format=gbrp → subtitles(ASS) → FX → scale(out_color_matrix=bt709) → format=yuv420p`. Удалить `hqdn3d` (или `0.6:0.6:2:2` после скейла только для шумных), `cas` перенести на выходное разрешение.

---

## 7. Эффекты (шейдеры) — точные формулы

| Эффект | Формула / реализация | Параметры по умолчанию |
|---|---|---|
| Zoom punch | scale камеры = `1 + A·spring(τ)`; радиальный смаз `Σ w_s·tex((uv−c)/(z(1+0.028s))+c)`, `w_s = 1−s/N` (из `img.rs`), **сила = \|ds/dt\|·shutter** (затухает вместе со скоростью пружины) | A=0.15, пружина 12%/220 мс, N=12 |
| Camera shake | `dx = amp·env·(0.7·noise1(s,t·f) + 0.3·noise1(s+1,t·2.3f))`, rot = 0.4°·env·noise; `env` атака 1 кадр, спад `exp(−t/τ)`; **overscan постоянный** `1+2·amp/W` на всём клипе (лечит N11); motion blur по скорости | amp 14 px, f 9 Гц, τ 120 мс |
| Whip | смещение easeInOutCubic на ±0.35W за 6–8 кадров + направленный blur 16 сэмплов длиной `\|v\|·0.5/fps`; стык двух планов на пике скорости | 120 мс |
| Flash | огибающая движка: `p<0.12 ? p/0.12 : exp(−(p−0.12)·4.2)`; **screen** в линейном: `c' = 1−(1−c)(1−F·env·peak)`; «экспозиция»: `c·2^(EV·env)` | белый/красный (0.89,0.086,0.11)/оранжевый, 180 мс |
| Threshold hit | `Y>t ? 1 : 0` + шум `hash(pixel,frame)·0.08`, 1–2 кадра | t=0.45 |
| Overexpose burn | +2 EV·env, bloom ×3, тинт (1, 0.55, 0.2), спад 200 мс | |
| RGB split | радиальный: `R = tex(c+(uv−c)(1+k))`, `B = tex(c+(uv−c)(1−k))`; стат. CA движка 1.4 px, ×1.6–2.0 на ударах | k=0.004 |
| Glitch | полосы высотой 8–48 px, сдвиг `(hash(row,frame)−0.5)·0.08W` с вероятностью 0.3, + RGB split | 3–5 кадров |
| Red silhouette | маска человека **предрасчитывается сервером при импорте** (MediaPipe Selfie Segmentation / RVM ONNX) в серое видео H.264 1:1 по кадрам, декодируется как обычный ассет; `mix(frame, duotone(red), mask·env)` | 3–6 кадров |
| Speed ramp | `srcTime = ∫speed` (§2.3), frame blending между `floor`/`ceil` кадрами с весом дробной части; аудио — `atempo` сегментами | 0.35× перед ударом, рывок 1.8× |
| Freeze + zoom | удержание кадра `src = const`, zoom 1→1.12 easeOutCubic, текст «ЖДИ…» | |
| Blur + darken outro | гаусс σ 5.4 px (из `img.rs`, эталон 1440 → ×1.33 для 1920), −1.5 EV, стикер 💀 со свечением | 0.6 с |

**Ритм**: сервер один раз на регион считает `librosa.onset.onset_detect` + пики RMS голоса (порог +8 дБ к медиане, окно 50 мс) → «магнитные» точки на таймлайне; hot‑слова (громкие/ключевые) по умолчанию получают `slam` + zoom punch + SFX.

---

## 8. Проверка качества и паритета

- Так как превью и экспорт — **один `renderFrame`**, паритет проверяется до кодека: `renderFrame(comp, f, scale=1)` → даунскейл до превью‑размера vs `renderFrame(comp, f, scale=s)`; зерно выключено; критерий SSIM ≥ 0.99. После кодека — отдельный тест качества энкода: PSNR‑Y ≥ 40 дБ на эталонных сценах.
- Golden‑сцены (в `verify_all.py` → Playwright/Electron headless): IRL, Just Chatting со сплитом, игра, тёмная/пересвеченная, кириллица+эмодзи+ё+длинные слова, 3 видеослоя, каждый аниматор и эффект.
- Синхрон: тестовый клип с «хлопком» (белый кадр + клик) — расхождение аудио/видео ≤ 1 кадр; слово ASR появляется в кадре `round(word.s·fps)` ± 1.
- Громкость: −14 LUFS ±1, TP ≤ −1 dBTP.
- `/api/version` сверяется в тестах (N16).

---

## 9. Простота: «один клик → вирусный Short»

«Сделать Short» по выделению = ASR (Groq `whisper-large-v3-turbo` с `word` таймкодами уже есть) → авто‑регионы (YuNet лицо, 1 кадр/с, медиана бокса вебки) → раскладка `cam_top_content_bottom`/`fullscreen_face` → стиль‑пакет → `Viral Punch` + авто‑нормализация → эффекты на пиках/hot‑словах → SFX → loudnorm → экспорт. **Стиль‑пакет** — один JSON (шрифт, палитра по словам, аниматоры in/out/idle, glow/stroke/shadow, грейд, набор эффектов и SFX), общий для карточек UI, превью и рендера. Ручная правка — инспектор слоя с кейфреймами и пресетами easing, без обязательной анимации руками.

---

## 10. Порядок работ

| Шаг | Срок | Что | Готово, когда |
|---|---|---|---|
| **0a** | 1 день | N16 (`/api/version`), N1–N7, N18, экранирование ASS | тень со смещением, нет обрывов и мыла у текста, нет пульсации |
| **0b** | 1–2 дня | H1 `subtitle_mode` (422 на конфликт), N8–N11, порядок графа §6.3, `hqdn3d` прочь, ingest §6.1 (теги, 1080p60, точный трим), N17 | нет двойного текста; чистые цветные края текста; нет скачка зума на шейке |
| **P0** | 2–4 дня | canvas‑монитор, 1 декод на файл, аудио‑клок + rVFC, текстовый модуль §3 в превью, LUT‑грейд §4.6 | превью 9:16 с тем же текстом/грейдом, что в экспорте; половины сплита синхронны |
| **1** | 2–3 нед | Composition + `mapTime`, WebGL2 `renderFrame`, WebCodecs‑провайдер, экспорт §6.2 | экспорт 1080×1920@60 из рендерера; паритет §8 |
| **2** | 2 нед | SDF‑stroke, Kawase‑glow, аниматоры §3.6, motion blur §3.7 | слепое сравнение 10 кадров с референсом |
| **3** | 2 нед | грейд §4 целиком, эффекты §7, маски | `Viral Punch` на 5 разных стримах без клиппинга |
| **4** | 1–2 нед | авто‑регионы, ритм, стиль‑пакеты, «Сделать Short» | ≤ 3 клика от выделения до файла |
| **Уборка** | параллельно | удалить `generate_ass_subtitle_content`, дубль `_sfx_maybe_file`, `#tvPreview`/`#subtitlesMonitorOverlay`, CSS‑анимации текста; `engine/` заморозить (формулы перенесены в §3/§7) | один реестр стилей, один путь рендера |

---

## 11. Что не удалось проверить

- GitHub API отдаёт только верх больших файлов: нижняя половина `editor.js` (сборщик payload экспорта, ~L6000–7600) и финальная команда энкода в `server.py` прочитаны не полностью; выводы по ним опираются на модели pydantic, вызовы и `PLAN_verification.md`. Перед шагом 0b стоит залогировать реальный JSON экспорта, ASS и команду FFmpeg для проблемной нарезки.
- Какой формат согласует FFmpeg для `blend` во вспышке (YUV или RGB) — зависит от графа; N10 описан как риск, проверяется одной строкой `-report`.
- Качество аппаратного H.264 в WebCodecs на конкретной видеокарте пользователя не мерилось; поэтому по умолчанию x264.
