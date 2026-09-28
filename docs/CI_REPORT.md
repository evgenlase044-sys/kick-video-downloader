## Fold log
```

server.py: {'already': 30, 'skipped': 1}
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

# CI report (2026-09-28T08:34:09Z, 3b4e3ac)

# PROBE PR9 #2
#### web/editor.js lines 1808-1915
```
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
1846|                // studio:face-anchor-norm - canvasMonitor reads anchor.x / anchor.y
1847|                // as 0..1 of the frame; an array gave NaN (broken zoom transform).
1848|                let fx_ = box.x + box.w / 2, fy_ = box.y + box.h / 2;
1849|                if (!isFinite(fx_) || !isFinite(fy_)) return null;
1850|                if (fx_ > 1.001 || fy_ > 1.001) {       // track box in source pixels
1851|                    const m = baseClip.media || {};
1852|                    const mw = Number(m.width || m.w || (videoEl && videoEl.videoWidth)) || 1920;
1853|                    const mh = Number(m.height || m.h || (videoEl && videoEl.videoHeight)) || 1080;
1854|                    fx_ /= mw; fy_ /= mh;
1855|                }
1856|                // keep the punch inside the frame even for a face at the very edge
1857|                return { x: Math.max(0.15, Math.min(0.85, fx_)), y: Math.max(0.15, Math.min(0.85, fy_)) };
1858|            },
1859|            cueAt(t) {
1860|                const clip = currentCueClip(t);
1861|                if (!clip) return null;
1862|                const raw = Array.isArray(clip.words) && clip.words.length
1863|                    ? clip.words
1864|                    : [{ word: clip.title || "", abs_start: clip.startTime, abs_end: clip.startTime + clip.duration }];
1865|                const first = raw.length ? (raw[0].abs_start != null ? raw[0].abs_start : 0) : 0;
1866|                const words = raw.map(w => ({
1867|                    word: w.word || "",
1868|                    s: Math.max(0, (w.abs_start != null ? w.abs_start : first) - first),
1869|                    e: Math.max(0.05, (w.abs_end != null ? w.abs_end : (w.abs_start || first) + 0.3) - first),
1870|                    hot: !!w.hot,
1871|                    color: w.color || null
1872|                }));
1873|                const isSplit = state.clipper.format === "split_adhd";
1874|                return {
1875|                    words: words,
1876|                    end: Math.max(0.2, clip.duration),
1877|                    styleName: clip.subtitleStyle || state.clipper.subtitleTemplate || "acid",
1878|                    x: clip.textX != null ? clip.textX : 0.5,
1879|                    y: clip.textY != null ? clip.textY : (isSplit ? 0.225 : 0.68),
1880|                    localT: Math.max(0, t - clip.startTime),
1881|                    sizeRatio: 0.058 * (state.clipper.subSize || 1.0) * (isSplit ? 0.9 : 1.0)
1882|                };
1883|            },
1884|            fxAt(t) {
1885|                const out = [];
1886|                for (const tid of videoTrackIds()) {
1887|                    for (const c of (state.tracks[tid] || [])) {
1888|                        if (!c.isFx) continue;
1889|                        out.push({
1890|                            kind: c.fxKind || "flash", color: c.fxColor || "white",
1891|                            peak: c.fxPeak != null ? c.fxPeak : 0.75,
1892|                            amp: c.fxAmp || 12, freq: c.fxFreq || 7,
1893|                            start: c.startTime, end: c.startTime + c.duration
1894|                        });
1895|                    }
1896|                }
1897|                return out;
1898|            },
1899|            now() { return state.currentTime; },
1900|            // §16 P1: WebCodecs exact frames with per-asset worker + proxy scrub
1901|            decoderFor(clip) {
1902|                if (!window.CoreWebCodecs || !window.CoreWebCodecs.supported()) return null;
1903|                const media = clip.media || {};
1904|                if (!media.filename) return null;
1905|                const proxyUrl = __proxyUrlCached(media.filename);
1906|                return window.CoreWebCodecs.decoderFor(media.filename, media.stream_url,
1907|                    proxyUrl, state.previewFps || 60);
1908|            }
1909|        };
1910|        const mon = new window.CoreCanvasMonitor(canvas, hooks);
1911|        window.__canvasMonitor = mon;
1912|        mon.loadLut("/api/grade/lut").catch(() => {});
1913|    }
1914|
1915|    function clipTargetTime(clip, t) {
```
#### web/editor.js lines 2235-2306
```
2235|    async function startPlayback() {
2236|        if (state.isPlaying) return;
2237|        state.isPlaying = true;
2238|        if (playIcon) playIcon.classList.add("hidden");
2239|        if (pauseIcon) pauseIcon.classList.remove("hidden");
2240|
2241|        if (state.currentTime >= state.totalDuration) {
2242|            state.currentTime = 0;
2243|        }
2244|
2245|        syncVideoToCurrentTime();
2246|        // Ensure every visible active element is actually playing before starting the clock
2247|        [videoEl, overlayVideoEl, ...Object.values(audioEls)].forEach(el => {
2248|            if (el && el.src && el.paused && el.style.display !== "none") {
2249|                if (el === overlayVideoEl && el.classList.contains("hidden")) return;
2250|                el.play().catch(() => {});
2251|            }
2252|        });
2253|        await waitSeeked([videoEl, overlayVideoEl, ...Object.values(audioEls)]);
2254|
2255|        state.lastFrameTime = performance.now();
2256|        requestAnimationFrame(playbackLoop);
2257|    }
2258|
2259|    function pausePlayback() {
2260|        state.isPlaying = false;
2261|        if (playIcon) playIcon.classList.remove("hidden");
2262|        if (pauseIcon) pauseIcon.classList.add("hidden");
2263|        [videoEl, overlayVideoEl, ...Object.values(audioEls)].forEach(el => {
2264|            if (el && !el.paused) { try { el.pause(); } catch (e) {} }
2265|        });
2266|        const tvp = document.getElementById("tvPreview");
2267|        if (tvp) tvp.querySelectorAll("video").forEach(v => {
2268|            if (!v.paused) { try { v.pause(); } catch (e) {} }
2269|        });
2270|    }
2271|
2272|    function playbackLoop(timestamp) {
2273|        if (!state.isPlaying) return;
2274|
2275|        const deltaSec = (timestamp - state.lastFrameTime) / 1000;
2276|        state.lastFrameTime = timestamp;
2277|
2278|        state.currentTime += deltaSec;
2279|
2280|        if (state.currentTime >= state.totalDuration) {
2281|            seekTo(state.totalDuration);
2282|            pausePlayback();
2283|            return;
2284|        }
2285|
2286|        // Moment preview: stop exactly at OUT marker
2287|        if (state.previewStopAt !== null && state.currentTime >= state.previewStopAt) {
2288|            const stop = state.previewStopAt;
2289|            state.previewStopAt = null;
2290|            pausePlayback();
2291|            seekTo(stop);
2292|            return;
2293|        }
2294|
2295|        updatePlayheadPosition();
2296|        updateTimecodeDisplays();
2297|        triggerFxSounds(state.currentTime - Math.min(deltaSec, 0.25), state.currentTime);
2298|        // Drift correction every frame keeps multi-layer A/V in sync;
2299|        // syncVideoToCurrentTime also resumes any element that went silent/stale.
2300|        syncVideoToCurrentTime();
2301|        updateLiveSubtitleOverlay();
2302|        autoScrollFollowPlayhead();
2303|
2304|        requestAnimationFrame(playbackLoop);
2305|    }
2306|    function autoScrollFollowPlayhead() {
```
#### web/editor.js lines 2019-2060
```
2019|    function syncVideoToCurrentTime() {
2020|        if (!videoEl) return;
2021|        ensureTracksInitialized();
2022|        // Empty project: clear stale frames, show placeholder
2023|        if (totalClipCount() === 0) {
2024|            const hadSrc = !!(videoEl.currentSrc || videoEl.src);
2025|            if (hadSrc) resetMonitorMedia();
2026|            if (monitorOverlay) monitorOverlay.style.display = "flex";
2027|            setPlaceholderText("Монитор предпросмотра", "Перетащите видео из Библиотеки ресурсов на панель слоёв внизу");
2028|            if (noClipPlaceholder) noClipPlaceholder.classList.remove("hidden");
2029|            return;
2030|        }
2031|        const t = state.currentTime;
2032|        const layers = activeVideoLayers(t); // [topmost, ...] max 2
2033|        const over = layers.length >= 2 ? layers[0] : null;   // PiP layer
2034|        const base = layers.length >= 1 ? layers[layers.length - 1] : null; // fullscreen base
2035|
2036|        // GAP under playhead: hide video completely — no stale frame in empty space
2037|        const hasLoadedVideo = !!(videoEl.currentSrc || videoEl.src);
2038|        if (monitorOverlay) {
2039|            if (base) monitorOverlay.style.display = "none";
2040|            else monitorOverlay.style.display = "flex";
2041|        }
2042|        if (noClipPlaceholder) {
2043|            if (base) noClipPlaceholder.classList.add("hidden");
2044|            else noClipPlaceholder.classList.remove("hidden");
2045|        }
2046|
2047|        // Base layer (bottom-most visible video track with an active clip)
2048|        if (base && base.media) {
2049|            ensureElMedia(videoEl, base);
2050|            setElTime(videoEl, clipTargetTime(base, t));
2051|            videoEl.style.opacity = String(base.opacity ?? 1);
2052|            const baseTrack = getTrack(base.trackId);
2053|            videoEl.muted = !!(baseTrack && baseTrack.muted);
2054|            videoEl.volume = Math.max(0, Math.min(1, (base.volume ?? 1) * masterGain));
2055|            videoEl.style.display = "block";
2056|            if (state.isPlaying && videoEl.paused && videoEl.src) videoEl.play().catch(() => {});
2057|        } else {
2058|            if (!videoEl.paused) { try { videoEl.pause(); } catch (e) {} }
2059|            videoEl.style.display = "none"; // hide stale frame in the gap
2060|            setPlaceholderText("Нет клипа под плейхедом", "Промежуток таймлайна пуст — переместите клип или плейхед");
```
#### server.py lines 3353-3400
```
3353|        return None
3354|    # clamp in-points against the real source length: a layer beyond EOF
3355|    # would silently render as an empty input
3356|    for L in layers:
3357|        d = _probe_duration(L.source_file)
3358|        if d and L.src_offset > d - 0.2:
3359|            L.src_offset = max(0.0, d - max(0.2, float(L.duration or 1.0)))
3360|    layers.sort(key=lambda L: -L.z)          # deepest (highest z) first
3361|    base = layers[0]
3362|
3363|    tv = clip.color_grade == "tv" and not clip.src_processed
3364|    fmt = "talking_head_9_16" if clip.src_processed else clip.format
3365|    if clip.format == "cinematic_16_9":
3366|        out_w, out_h = (1920, 1080)
3367|    else:
3368|        out_w, out_h = (1080, 1920)
3369|    top_h = int(round(out_h * 0.45 / 2) * 2)
3370|    bot_h = out_h - top_h
3371|
3372|    total_dur = max(0.5, float(base.duration or 0.0) or max((L.duration for L in layers), default=1.0))
3373|    total_dur = max(0.5, min(total_dur, 600.0))
3374|
3375|    inputs: List[str] = []
3376|    filter_parts: List[str] = []
3377|    audio_parts: List[str] = []   # audio-only chain -> separate WAV pre-pass
3378|    n_inputs = 0
3379|    layer_audio: List[str] = []
3380|
3381|    # crop preset for the base layer template geometry
3382|    crop_x = "(iw-ow)/2"
3383|    crop_y = "0"
3384|    if clip.crop_preset == "top_left":
3385|        crop_x = "0"
3386|    elif clip.crop_preset == "top_right":
3387|        crop_x = "iw-ow"
3388|    elif clip.crop_preset == "center":
3389|        crop_x = "(iw-ow)/2"
3390|    elif clip.crop_preset == "face":
3391|        crop_x = "(iw-ow)/2"
3392|        crop_y = "(ih-oh)/3"
3393|
3394|    bg_path = None
3395|    if clip.background_file:
3396|        bg_candidate = os.path.join(DOWNLOADS_DIR, os.path.basename(clip.background_file))
3397|        if os.path.exists(bg_candidate):
3398|            bg_path = bg_candidate
3399|
3400|    # FX on tracks ABOVE the topmost text layer burn OVER the text
```
#### server.py lines 3605-3700
```
3605|    if bt > 0 or bb > 0:
3606|        parts = []
3607|        if bt > 0:
3608|            parts.append(f"drawbox=x=0:y=0:w={out_w}:h={bt}:color=black:t=fill")
3609|        if bb > 0:
3610|            parts.append(f"drawbox=x=0:y={out_h - bb}:w={out_w}:h={bb}:color=black:t=fill")
3611|        filter_parts.append(f"{comp}{','.join(parts)}[barred]")
3612|        comp = "[barred]"
3613|
3614|    # ── subtitles (output-local) — skipped for already-processed sources ──
3615|    ass_path = None
3616|    if clip.subtitles and not clip.src_processed:
3617|        subs = clip.subtitles
3618|        if clip.subs_in_output_time:
3619|            remapped = subs
3620|        else:
3621|            remapped = _remap_subtitles_for_segments(subs, [(0.0, total_dur)], [0], [total_dur])
3622|        if remapped:
3623|            margin_v = int(out_h * 0.55) if clip.format == "split_adhd" else (int(out_h * 0.38) if clip.format == "talking_head_9_16" else int(out_h * 0.12))
3624|            opts = _tv_sub_opts(clip.subtitle_template, clip, remapped)
3625|            if clip.subtitle_template in TV_TEMPLATES_CONFIG or clip.subtitle_template in TV_SUB_COLORS:
3626|                ass_content = build_tv_subtitles_ass(remapped, opts["default_style"], out_w, out_h, margin_v,
3627|                                                     font=opts["font"], size_mul=opts["size_mul"],
3628|                                                     glow=opts["glow"], anim=opts["anim"],
3629|                                                     hot_words=bool(getattr(clip, "hot_words", True)))
3630|            else:
3631|                ass_content = generate_ass_subtitle_content(remapped, clip.subtitle_template)
3632|            ass_path = os.path.join(DOWNLOADS_DIR, f"temp_sub_{idx}_{timestamp_str}.ass")
3633|            with open(ass_path, "w", encoding="utf-8") as f:
3634|                f.write(ass_content)
3635|
3636|    # ── free text elements (skipped in passthrough too) ──
3637|    text_ass_path = None
3638|    if clip.text_items and not clip.src_processed:
3639|        tass = build_text_elements_ass(clip.text_items, out_w, out_h)
3640|        if tass.strip():
3641|            text_ass_path = os.path.join(DOWNLOADS_DIR, f"temp_txt_{idx}_{timestamp_str}.ass")
3642|            with open(text_ass_path, "w", encoding="utf-8") as f:
3643|                f.write(tass)
3644|
3645|    def burn_ass(curr, path):
3646|        escaped = path.replace("\\", "/").replace(":", "\\:")
3647|        fontsdir = FONTS_DIR.replace("\\", "/").replace(":", "\\:")
3648|        filter_parts.append(f"{curr}subtitles=filename='{escaped}':fontsdir='{fontsdir}'[assout]")
3649|        return "[assout]"
3650|
3651|    if ass_path and os.path.exists(ass_path):
3652|        comp = burn_ass(comp, ass_path)
3653|    if text_ass_path and os.path.exists(text_ass_path):
3654|        comp = burn_ass(comp, text_ass_path)
3655|
3656|    # FX from layers ABOVE the text layer burn over the subtitles/text
3657|    if fx_over_text:
3658|        comp = _apply_fx_chain(filter_parts, comp, fx_over_text, out_w, out_h, total_dur, "otx_")
3659|
3660|    # N8/N9: exactly ONE final RGB->YUV quantization, with explicit BT.709
3661|    # matrix/range so text edges stay clean and preview == export.
3662|    filter_parts.append(
3663|        f"{comp}scale=out_color_matrix=bt709:out_range=tv:flags=accurate_rnd+full_chroma_int,format=yuv420p,setparams=range=tv:colorspace=bt709:color_primaries=bt709:color_trc=bt709[vfinal]"
3664|    )
3665|    comp = "[vfinal]"
3666|
3667|    # ── audio: layers' own audio + real SFX + synth fallback + timeline music ──
3668|    def _sfx_chain(kind: str, gain: float, at_ms: int, tag: str) -> str:
3669|        g = max(0.0, min(3.0, gain))
3670|        dl = f"adelay={at_ms}|{at_ms}"
3671|        if kind == "approve":
3672|            return (f"sine=frequency=700:duration=0.12,adelay={at_ms}|{at_ms}[{tag}a];"
3673|                    f"sine=frequency=1050:duration=0.22,adelay={at_ms + 110}|{at_ms + 110}[{tag}b];"
3674|                    f"[{tag}a][{tag}b]amix=inputs=2:normalize=0,volume={g}[{tag}]")
3675|        if kind == "cancel":
3676|            return (f"sine=frequency=420:duration=0.15,adelay={at_ms}|{at_ms}[{tag}a];"
3677|                    f"sine=frequency=250:duration=0.30,adelay={at_ms + 150}|{at_ms + 150}[{tag}b];"
3678|                    f"[{tag}a][{tag}b]amix=inputs=2:normalize=0,volume={g}[{tag}]")
3679|        if kind == "pop":
3680|            return f"sine=frequency=520:duration=0.07,afade=t=out:st=0.02:d=0.05,{dl},volume={g}[{tag}]"
3681|        if kind == "whoosh":
3682|            return (f"anoisesrc=d=0.45:c=white:r=48000:a=0.5,lowpass=f=900,"
3683|                    f"afade=t=in:st=0:d=0.15,afade=t=out:st=0.25:d=0.2,{dl},volume={g}[{tag}]")
3684|        if kind == "boom":
3685|            return (f"sine=frequency=110:duration=0.5,afade=t=in:st=0:d=0.02,afade=t=out:st=0.12:d=0.38,"
3686|                    f"{dl},volume={g * 1.2:.2f}[{tag}]")
3687|        if kind == "cheer":
3688|            return (f"anoisesrc=d=1.1:c=pink:r=48000:a=0.55,bandpass=f=1600:w=900,"
3689|                    f"tremolo=f=9:d=0.6,afade=t=in:st=0:d=0.15,afade=t=out:st=0.7:d=0.4,{dl},volume={g}[{tag}]")
3690|        if kind == "riser":
3691|            return (f"sine=frequency=300:duration=0.8,volume=0.6,"
3692|                    f"afade=t=in:st=0:d=0.6,afade=t=out:st=0.65:d=0.15,{dl},volume={g}[{tag}]")
3693|        return (f"anoisesrc=d=0.16:c=white:r=48000:a=0.9,highpass=f=1500,"
3694|                f"afade=t=out:st=0.06:d=0.1,{dl},volume={g}[{tag}]")
3695|
3696|    # ── audio: built in a SEPARATE pass into WAV, then two-pass loudnorm (0b) ──
3697|    mix_labels = list(layer_audio)
3698|    for qi, snd in enumerate(clip.sounds or []):
3699|        try:
3700|            kind = (snd.kind or "click").lower()
```
#### server.py lines 4411-4440
```
4411|@app.post("/api/preview-frame")
4412|def preview_frame(req: dict):
4413|    """Рендерит ОДИН кадр тем же фильтр-графом, что и финальный экспорт
4414|    (кроп/сплит, FX, TV-грейд+bloom, субтитры, свободный текст) → PNG.
4415|    Гарантирует превью == экспорт."""
4416|    try:
4417|        base_src = os.path.join(DOWNLOADS_DIR, os.path.basename(req.get("source_file", "")))
4418|        if not os.path.exists(base_src):
4419|            base_src = req.get("source_file")
4420|        src_time = float(req.get("src_time", 0.0))
4421|        fmt = req.get("format", "talking_head_9_16")
4422|        W = int(req.get("width", 1080)); H = int(req.get("height", 1920))
4423|        top_h = int(round(H * 0.45 / 2) * 2); bot_h = H - top_h
4424|        crop_box = req.get("crop_box"); bg_box = req.get("bg_box")
4425|        use_tv = req.get("color_grade") == "tv"
4426|        subs = req.get("subtitles") or []
4427|        text_items = req.get("text_items") or []
4428|        overlays = req.get("overlays") or []
4429|        t_rel = float(req.get("region_time", 0.0))
4430|
4431|        ass_path = None; text_ass_path = None
4432|        inputs: List[str] = ["-ss", f"{max(0.0, src_time):.3f}", "-i", base_src]
4433|        n_inputs = 1
4434|        fp: List[str] = []
4435|        bx = crop_box
4436|        if fmt == "split_adhd" and bx:
4437|            bw = f"{max(0.02, min(1.0, bx.get('w', 0.5))):g}*iw"
4438|            bh_ = f"{max(0.02, min(1.0, bx.get('h', 0.5))):g}*ih"
4439|            bxx = f"{max(0.0, min(0.98, bx.get('x', 0.0))):g}*iw"
4440|            byy = f"{max(0.0, min(0.98, bx.get('y', 0.0))):g}*ih"
```
#### grep top_h
```
server.py:3369:    top_h = int(round(out_h * 0.45 / 2) * 2)
server.py:3370:    bot_h = out_h - top_h
server.py:3958:        top_h = int(round(out_h * 0.45 / 2) * 2)
server.py:3959:        bot_h = out_h - top_h
server.py:4423:        top_h = int(round(H * 0.45 / 2) * 2); bot_h = H - top_h
```
#### grep splitTop/topFrac
```
web/editor.js:22:            format: "split_adhd",       // split_adhd, talking_head_9_16, cinematic_16_9
web/editor.js:1873:                const isSplit = state.clipper.format === "split_adhd";
web/editor.js:3084:            const isSplit = state.clipper.format === "split_adhd"
web/editor.js:3095:                state.clipper.format = "split_adhd";
web/editor.js:3138:                const shortsFmt = state.clipper.format === "split_adhd" || state.clipper.format === "talking_head_9_16";
web/editor.js:3643:        if (fmt !== "split_adhd" && fmt !== "talking_head_9_16") return null;
web/editor.js:4169:        if (fmt === "split_adhd") {
web/editor.js:4331:                        const subTop = fmt === "split_adhd" ? (stageH * 0.45 - sizePx * 0.1) : (stageH * 0.62);
web/editor.js:4824:            format: "split_adhd", crop_preset: "top_right",
web/editor.js:4836:            id: "builtin_split_adhd", builtin: true,
web/editor.js:4838:            format: "split_adhd", crop_preset: "top_right",
web/editor.js:4915:        state.clipper.format = tpl.format || "split_adhd";
web/editor.js:4965:        if (f === "split_adhd") return "Сплит 50/50";
web/editor.js:6092:                (!saved.aspectRatio && ["split_adhd", "talking_head_9_16"].includes(state.clipper.format));
web/core/geometry.js:80:        if (fmt === "split_adhd") {
```
#### grep lens in canvasMonitor
```
11: * lens punch, threshold hit, whip, freeze and speed ramp are now VISIBLE in
286:        // camera fx: shake + whip offsets, zoom/lens scale with anchor
304:            } else if (f.kind === "lens") {
```
#### ffmpeg filters
```
 TSC chromashift       V->V       Shift chroma.
 TSC colorkey          V->V       Turns a certain color into transparency. Operates on RGB colors.
 TSC hsvkey            V->V       Turns a certain HSV range into transparency. Operates on YUV colors.
 TSC lenscorrection    V->V       Rectify the image by correcting for lens distortion.
 TSC maskedmerge       VVV->V     Merge first stream with second stream using third stream as mask.
 .S. remap             VVV->V     Remap pixels.
 TSC tmix              V->V       Mix successive video frames.
ffmpeg version 6.1.1-3ubuntu5 Copyright (c) 2000-2023 the FFmpeg developers
```
### ✅ python compile
```

```

### ✅ anchored patches (server.py / editor.js / index.html)
```

server.py: {'already': 30, 'skipped': 1}
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
test_fallback_to_ass_when_overlay_fails (studio.tests.test_export_pipeline.ExportWrapperTest.test_fallback_to_ass_when_overlay_fails) ... [studio] canvas text layer failed (overlay ffmpeg rc=254: [concat @ 0x55d4e638e680] Impossible to open '/tmp/tmp53hoosp7/ovjob/000000.png'
[in#1 @ 0x55d4e6383dc0] Error opening input: No such file or directory
Error opening input file /tmp/tmp53hoosp7/ovjob/list.ffconcat.
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
[studio] server.py patches: {'already': 30, 'skipped': 1}
test_lens_punch_is_animated (studio.tests.test_pr8.Pr8ExportFxTest.test_lens_punch_is_animated) ... ok
test_mixed_chain_renders (studio.tests.test_pr8.Pr8ExportFxTest.test_mixed_chain_renders) ... ok
test_zoom_anchor_moves_the_punch (studio.tests.test_pr8.Pr8ExportFxTest.test_zoom_anchor_moves_the_punch) ... ok
test_zoom_really_zooms_only_inside_its_window (studio.tests.test_pr8.Pr8ExportFxTest.test_zoom_really_zooms_only_inside_its_window) ... ok

----------------------------------------------------------------------
Ran 45 tests in 10.078s

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

