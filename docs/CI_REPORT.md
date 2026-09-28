## Fold log
```

server.py: {'already': 25, 'skipped': 1}
  already  hooks-import                 marker present
  already  progress-nameerror           marker present
  already  cookies-range                marker present
  already  cookies-full                 marker present
  already  cookies-download             marker present
  already  ssrf-guard                   marker present
  already  ssrf-remember                marker present
  already  disk-peak                    marker present
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

web/editor.js: {'already': 3}
  already  tdz-declare-early            marker present
  already  tdz-drop-late                marker present
  already  queue-sse-reconnect          marker present

web/index.html: {'skipped': 2, 'already': 3}
  skipped  drop-dead-exporter           guard declined
  already  timeremap-script             marker present
  skipped  effects-script               guard declined
  already  moments-panel                marker present
  already  overlay-export               marker present
```

# CI report (2026-09-28T05:19:58Z, e75770c)

### ✅ python compile
```

```

### ✅ anchored patches (server.py / editor.js / index.html)
```

server.py: {'already': 25, 'skipped': 1}
  already  hooks-import                 marker present
  already  progress-nameerror           marker present
  already  cookies-range                marker present
  already  cookies-full                 marker present
  already  cookies-download             marker present
  already  ssrf-guard                   marker present
  already  ssrf-remember                marker present
  already  disk-peak                    marker present
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

web/editor.js: {'already': 3}
  already  tdz-declare-early            marker present
  already  tdz-drop-late                marker present
  already  queue-sse-reconnect          marker present

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
test_fallback_to_ass_when_overlay_fails (studio.tests.test_export_pipeline.ExportWrapperTest.test_fallback_to_ass_when_overlay_fails) ... [studio] canvas text layer failed (overlay ffmpeg rc=254: [concat @ 0x5609ae8ac680] Impossible to open '/tmp/tmpmzdsycdh/ovjob/000000.png'
[in#1 @ 0x5609ae8a1dc0] Error opening input: No such file or directory
Error opening input file /tmp/tmpmzdsycdh/ovjob/list.ffconcat.
Error opening input files: No such file or directory
), falling back to ASS
ok
test_multi_clip_split (studio.tests.test_export_pipeline.ExportWrapperTest.test_multi_clip_split) ... ok
test_passthrough_without_options (studio.tests.test_export_pipeline.ExportWrapperTest.test_passthrough_without_options) ... ok
test_grade_chain_runs (studio.tests.test_export_pipeline.GradeAndOverlayTest.test_grade_chain_runs) ... ok
test_header_validation (studio.tests.test_export_pipeline.GradeAndOverlayTest.test_header_validation) ... ok
test_overlay_lands_on_exact_frame (studio.tests.test_export_pipeline.GradeAndOverlayTest.test_overlay_lands_on_exact_frame) ... ok

----------------------------------------------------------------------
Ran 27 tests in 1.569s

OK
```

### ✅ server imports with fixes (studio.loader)
```
[studio] server.py patches: {'already': 25, 'skipped': 1}
26 patches
```

### ✅ export pipeline installs into the real server
```
[studio] server.py patches: {'already': 25, 'skipped': 1}
[studio] export pipeline: {'grade': True, 'encoder_shim': True, 'export_route': True}
{'grade': True, 'encoder_shim': True, 'export_route': True}
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

#### editor.js definitions
```
5145:    function fxLabel(c) {
5153:    function ensureFxTrack() {
5230:    function addEffectAtPlayhead(kind, color, overrides) {
5246:    function nearestCutTo(t) {
5942:    function saveProject() {
```

#### editor.js addEffectAtPlayhead body
```
    function addEffectAtPlayhead(kind, color, overrides) {
        // §7.3 (W): whip ставится на ближайший рез (граница нарезки/клипа)
        if (overrides && overrides.snapToCut) {
            const cut = nearestCutTo(state.currentTime);
            if (cut != null) seekTo(cut);
        }
        const before = (state.tracks[tidOfFx()] || []).length;
        addFxClip(kind, color);
        const tid = tidOfFx();
        const clips = state.tracks[tid] || [];
        if (clips.length === before) return;
        const c = clips[clips.length - 1];
        if (c && c.isFx && overrides) Object.assign(c, overrides);
        renderTimeline();
        saveProject();
    }
    function nearestCutTo(t) {
        const cuts = [];
        for (const r of sortedRegions()) {
            cuts.push(r.startTime, r.startTime + r.duration);
        }
        for (const tid of videoTrackIds()) {
            for (const c of (state.tracks[tid] || [])) {
                if (!c.media || c.isFx) continue;
                cuts.push(c.startTime, c.startTime + c.duration);
            }
        }
        let best = null, bestD = 1.5;
        for (const c of cuts) {
            const d = Math.abs(c - t);
            if (d < bestD) { bestD = d; best = c; }
        }
        return best;
    }
    function tidOfFx() {
        const order = trackOrder();
        for (const tid of order) {
            const tr = getTrack(tid);
            if (tr && tr.kind === "video") return tid;
        }
        return ensureFxTrack();
    }
    // ── §9.4: пресет канала — рамки/раскладка/стиль/словарь одним нажатием (P) ──
    async function applyChannelPreset() {
        const handle = (state.clipper.streamerHandle || "").replace("@", "").trim();
        if (!handle) {
            showToast("Укажи ник стримера в поле хэндла — пресеты хранятся по нику.", "info");
            return;
        }
        try {
            const res = await fetch(`/api/presets/channel/${encodeURIComponent(handle)}`);
            if (!res.ok) {
                showToast(`Пресет канала «${handle}» не найден — настрой рамки и сохрани (Alt+P).`, "info");
                return;
            }
            const data = await res.json();
            const p = data.preset || {};
            if (p.crop_box) state.clipper.cropBox = p.crop_box;
            if (p.bg_box) state.clipper.bgBox = p.bg_box;
            if (p.format) state.clipper.format = p.format;
            if (p.style_pack) {
                if (p.style_pack.subtitle_template) state.clipper.subtitleTemplate = p.style_pack.subtitle_template;
                if (p.style_pack.sub_font) state.clipper.subFont = p.style_pack.sub_font;
                if (p.style_pack.sub_size) state.clipper.subSize = p.style_pack.sub_size;
                if (p.style_pack.sub_glow != null) state.clipper.subGlow = p.style_pack.sub_glow;
                if (p.style_pack.sub_anim) state.clipper.subAnim = p.style_pack.sub_anim;
                if (p.style_pack.color_grade) state.clipper.colorGrade = p.style_pack.color_grade;
            }
            if (p.asr_prompt) state.clipper.asrPrompt = p.asr_prompt;
            if (p.layout === "fullscreen" && !p.crop_box) state.clipper.cropBox = null;
            updateClipperUI();
            updateTvPreview();
            updateLiveSubtitleOverlay();
            syncVideoToCurrentTime();
            saveProject();
            showToast(`Пресет канала «${handle}» применён.`, "ok");
```

#### editor.js ensureFxTrack body
```
    function ensureFxTrack() {
        ensureTracksInitialized();
        let fx = state.trackList.find(isFxTrack);
        if (!fx) {
            fx = {
                id: "tfx" + Date.now().toString(36),
                kind: "video", name: "Эффекты",
                hidden: false, locked: false, muted: true
            };
            // новый слой эффектов появляется НАД верхним слоем текста
            let idx = state.trackList.findIndex(t => t.kind === "text");
            if (idx < 0) idx = 0;
            state.trackList.splice(idx, 0, fx);
            state.tracks[fx.id] = [];
            renderTracksDOM();
        }
        return fx.id;
    }
    // отдельный слой эффектов над текстом (кнопка "+Слой FX")
    function addFxTrack() {
        ensureTracksInitialized();
        const n = state.trackList.filter(isFxTrack).length + 1;
        const tr = {
            id: "tfx" + Date.now().toString(36) + Math.random().toString(36).slice(2, 5),
            kind: "video", name: `Эффекты ${n}`,
            hidden: false, locked: false, muted: true
```

#### editor.js fxLabel body
```
    function fxLabel(c) {
        if (!c || !c.isFx) return "";
        if (c.fxKind === "flash") return FX_LABEL["flash_" + (c.fxColor || "white")] || "⚡ Вспышка";
        return FX_LABEL[c.fxKind] || "FX";
    }
    function isFxTrack(t) {
        return t && t.kind === "video" && /fx|эффект/i.test(t.name || "");
    }
    function ensureFxTrack() {
        ensureTracksInitialized();
        let fx = state.trackList.find(isFxTrack);
        if (!fx) {
            fx = {
                id: "tfx" + Date.now().toString(36),
                kind: "video", name: "Эффекты",
                hidden: false, locked: false, muted: true
            };
            // новый слой эффектов появляется НАД верхним слоем текста
            let idx = state.trackList.findIndex(t => t.kind === "text");
            if (idx < 0) idx = 0;
            state.trackList.splice(idx, 0, fx);
```

#### editor.js hotkeys addEffectAtPlayhead calls
```
225:                addEffectAtPlayhead("flash", col, { duration: 0.18, peak: 0.95, fxSound: "impact_epic" });
228:                addEffectAtPlayhead("shake", "white", { duration: 0.35, fxAmp: 14, fxSound: "whoosh_fast" });
231:                addEffectAtPlayhead("zoom", "white", { duration: 0.35, fxPeak: 0.15, fxSound: "whoosh_cinematic" });
234:                addEffectAtPlayhead("lens", "white", { duration: 0.25, fxPeak: 0.18, fxSound: "whoosh_magic" });
237:                addEffectAtPlayhead("threshold", "white", { duration: 0.067, fxPeak: 0.45, fxSound: "hit_small" });
240:                addEffectAtPlayhead("whip", "white", { duration: 0.12, fxSound: "whoosh_fast", snapToCut: true });
243:                addEffectAtPlayhead("ramp", "white", { duration: 0.6, fxSound: "riser" });
246:                addEffectAtPlayhead("freeze", "white", { duration: 0.6, fxSound: "camera_click" });
5230:    function addEffectAtPlayhead(kind, color, overrides) {
```

#### editor.js clock / master
```
```

#### editor.js video base clip helpers (sourceOffset mapping)
```
91:    function firstVideoTrackId() {
```

#### editor.js tail from Studio Integrations
```
    // ── Studio Integrations (§2 & §6 Moments / Templates / Seek / Transcript) ──
    window.studioSeek = seekTo;

    Object.defineProperty(window, "studioTranscriptWords", {
        get() {
            if (state._lastTranscribe && Array.isArray(state._lastTranscribe.words) && state._lastTranscribe.words.length) {
                return state._lastTranscribe.words;
            }
            const tId = textTrackId();
            const clips = state.tracks[tId] || [];
            const words = [];
            for (const c of clips) {
                if (Array.isArray(c.words)) words.push(...c.words);
            }
            return words.length ? words : null;
        },
        configurable: true
    });

    window.studioAddFx = function(fxList, baseTime = 0) {
        if (!Array.isArray(fxList) || !fxList.length) return;
        const tid = ensureFxTrack();
        ensureTracksInitialized();
        for (const f of fxList) {
            const start = baseTime + (f.start || 0);
            const dur = Math.max(0.05, (f.end != null ? (f.end - f.start) : (f.duration || 0.35)));
            const c = {
                id: "fx_" + Math.random().toString(36).slice(2, 9),
                trackId: tid,
                startTime: Math.max(0, start),
                duration: dur,
                sourceOffset: 0,
                sourceDuration: dur,
                title: "",
                isFx: true,
                fxKind: f.kind || "flash",
                fxColor: f.color || "white",
                fxPeak: f.amp != null ? f.amp : (f.peak != null ? f.peak : 0.75),
                fxSound: f.sfx || f.fxSound || "none",
                fxGain: 1.0,
                fxBarH: 160,
                fxAmp: (f.amp ? Math.round(f.amp * 100) : 12),
                fxFreq: 7,
                media: null,
                volume: 1.0,
                opacity: 1.0
            };
            if (f.anchor) c.anchor = f.anchor;
            c.title = fxLabel(c);
            (state.tracks[tid] = state.tracks[tid] || []).push(c);
        }
        state.tracks[tid].sort((a, b) => a.startTime - b.startTime);
        recalcTotalDuration();
        renderTimeline();
        saveProject();
    };

    document.addEventListener("studio:template-plan", (e) => {
        const plan = e.detail;
        if (plan && Array.isArray(plan.fx) && plan.fx.length) {
            const base = (plan.moment && typeof plan.moment.start === "number") ? plan.moment.start : state.currentTime;
            window.studioAddFx(plan.fx, base);
            showToast(`Шаблон «${plan.template || ""}»: добавлено ${plan.fx.length} эффектов на таймлайн`, "ok");
        }
    });

})();

```

#### server.py __main__ to EOF
```
if __name__ == "__main__":
    run_server()
```

#### server.py _two_pass_loudnorm
```
3273:def _two_pass_loudnorm(src_wav: str, dst_wav: str, target_i: float = -14.0,
3742:            if not _two_pass_loudnorm(wav_raw, wav_norm):
def _two_pass_loudnorm(src_wav: str, dst_wav: str, target_i: float = -14.0,
                       target_tp: float = -1.0, target_lra: float = 11.0) -> bool:
    """0b: two-pass loudnorm (measure then apply linearly) + true-peak limiter."""
    try:
        p1 = ["ffmpeg", "-y", "-loglevel", "info", "-i", src_wav,
              "-af", f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}:print_format=json",
              "-f", "null", "-"]
        r1 = subprocess.run(p1, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=600)
        measured = {}
        if r1.stderr:
            start = r1.stderr.rfind("{")
            end = r1.stderr.rfind("}")
            if start >= 0 and end > start:
                try:
                    measured = json.loads(r1.stderr[start:end + 1])
                except Exception:
                    measured = {}
        if {"measured_I", "measured_TP", "measured_LRA", "measured_thresh"}.issubset(measured.keys()):
            af = (f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}"
                  f":measured_I={measured['measured_I']}:measured_TP={measured['measured_TP']}"
                  f":measured_LRA={measured['measured_LRA']}:measured_thresh={measured['measured_thresh']}"
                  f":offset={measured.get('target_offset', 0.0) or 0.0}:linear=true,"
                  "alimiter=limit=0.891:attack=5:release=50")
        else:
            af = (f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra},"
                  "alimiter=limit=0.891:attack=5:release=50")
        p2 = ["ffmpeg", "-y", "-loglevel", "error", "-i", src_wav, "-af", af,
              "-ar", "48000", "-c:a", "pcm_s16le", dst_wav]
        r2 = subprocess.run(p2, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=600)
        return r2.returncode == 0 and os.path.exists(dst_wav) and os.path.getsize(dst_wav) > 44
    except Exception:
        return False


def _export_layered_clip(clip, out_path: str, out_filename: str, timestamp_str: str, idx: int) -> Optional[Dict[str, Any]]:
    """Layered compositing export: every timeline video/image element renders
    in z-order (bottom first), FX elements apply at their track level only
    (an FX under an upper layer never touches it), then grade, static frames,
    subtitles and free text on top. Mirrors the on-canvas preview."""
    layers = [L for L in (clip.layers or []) if L.source_file]
    if not layers:
        return None
    # resolve files
    for L in layers:
        p0 = os.path.join(DOWNLOADS_DIR, os.path.basename(L.source_file))
        if not os.path.exists(p0) and os.path.exists(L.source_file):
```

#### server.py loudnorm occurrences
```
3273:def _two_pass_loudnorm(src_wav: str, dst_wav: str, target_i: float = -14.0,
3275:    """0b: two-pass loudnorm (measure then apply linearly) + true-peak limiter."""
3278:              "-af", f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}:print_format=json",
3291:            af = (f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}"
3297:            af = (f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra},"
3666:    # ── audio: built in a SEPARATE pass into WAV, then two-pass loudnorm (0b) ──
3742:            if not _two_pass_loudnorm(wav_raw, wav_norm):
4306:                "".join(mix_labels) + f"amix=inputs={len(mix_labels)}:duration=longest:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[aout]"
4310:            filter_parts.append("".join(audio_seg_labels) + f"concat=n={n_seg}:v=0:a=1,loudnorm=I=-14:TP=-1.5:LRA=11[aout]")
4314:                filter_parts.append("[0:a]loudnorm=I=-14:TP=-1.0:LRA=11,alimiter=limit=-1.0dB:attack=5:release=50[aout]")
```

#### server.py export_clip_pack audio block
```
                    n_inputs = new_n
                mix_labels.append(f"[sfx{qi}]")
            # timeline audio files (music / SFX from layers)
            for ai, au in enumerate(clip.extra_audio or []):
                try:
                    apath = os.path.join(DOWNLOADS_DIR, os.path.basename(au.filename))
                    if not os.path.exists(apath):
                        continue
                    gain = max(0.0, min(3.0, float(au.gain if au.gain is not None else 1.0)))
                    off = max(0.0, float(au.src_offset or 0.0))
                    dur = max(0.2, float(au.duration or 5.0))
                    place = int(max(0.0, float(au.out_start or 0.0)) * 1000)
                except (TypeError, ValueError):
                    continue
                ain = n_inputs
                in_args = ["-ss", str(off), "-t", str(dur)]
                if au.loop:
                    in_args = ["-stream_loop", "-1", "-ss", str(off), "-t", str(dur)]
                inputs.extend(in_args + ["-i", apath])
                n_inputs += 1
                mtag = f"mx{ai}"
                filter_parts.append(
                    f"[{ain}:a]aresample=48000,aformat=channel_layouts=stereo,"
                    f"volume={gain},adelay={place}|{place}[{mtag}raw]"
                )
                if au.duck:
                    # music ducks under the voice; [amain] is split so the mix
                    # still receives a copy (a stream can only be consumed once)
                    if not _duck_split_done:
                        _duck_split_done = True
                        filter_parts.append("[amain]asplit=2[amaindk]amain")
                        filter_parts.append(
                            f"[{mtag}raw][amaindk]sidechaincompress=threshold=0.02:ratio=9:"
                            f"attack=15:release=450:makeup=1[{mtag}]"
                        )
                    else:
                        filter_parts.append(f"[{mtag}raw]volume=0.55[{mtag}]")
                else:
                    filter_parts.append(f"[{mtag}raw]anull[{mtag}]")
                mix_labels.append(f"[{mtag}]")
            filter_parts.append(
                "".join(mix_labels) + f"amix=inputs={len(mix_labels)}:duration=longest:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[aout]"
            )
            audio_map = "[aout]"
        elif n_seg > 1:
            filter_parts.append("".join(audio_seg_labels) + f"concat=n={n_seg}:v=0:a=1,loudnorm=I=-14:TP=-1.5:LRA=11[aout]")
            audio_map = "[aout]"
        else:
            if _source_has_audio(source_path):
                filter_parts.append("[0:a]loudnorm=I=-14:TP=-1.0:LRA=11,alimiter=limit=-1.0dB:attack=5:release=50[aout]")
            else:
                filter_parts.append(f"anullsrc=r=48000:cl=stereo:d={total_dur:.3f}[aout]")
            audio_map = "[aout]"

        # Construct full FFmpeg command
        filter_complex_str = ";".join(filter_parts)
        ffmpeg_cmd = ["ffmpeg", "-y"] + inputs + [
            "-filter_complex", filter_complex_str,
            "-map", curr_v,
            "-map", audio_map,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "15",
            "-tune", "film",
            "-x264-params", "aq-mode=3:aq-strength=0.9:deblock=-1,-1",
            "-g", "60",
            "-bf", "3",
            "-pix_fmt", "yuv420p",
            "-colorspace", "bt709",
            "-color_primaries", "bt709",
            "-color_trc", "bt709",
            "-color_range", "tv",
            "-c:a", "aac",
            "-b:a", "256k",
            "-ar", "48000",
            "-movflags", "+faststart",
            out_path
        ]

        try:
            ffmpeg_env = os.environ.copy()
            if "FONTCONFIG_PATH" not in ffmpeg_env and sys.platform == "win32":
                ffmpeg_env["FONTCONFIG_PATH"] = FONTS_DIR

            render_res = subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=600, env=ffmpeg_env)
            if render_res.returncode == 0 and os.path.exists(out_path):
```

#### server.py -ss usages
```
287:                "-ss", str(round(req.trim_offset, 3)),
472:            "ffmpeg", "-y", "-ss", "00:00:01", "-i", video_path,
968:    cmd = ["ffmpeg", "-y", "-ss", str(max(0.0, start))]
1138:                cmd = ["ffmpeg", "-y", "-ss", f"{cpos:.3f}", "-t", f"{cdur:.3f}", "-i", temp_audio,
1296:    cmd = ["ffmpeg", "-loglevel", "error", "-ss", f"{max(0.0, t_from):.3f}",
1722:    cmd = ["ffmpeg", "-loglevel", "error", "-ss", str(max(0.0, req.start))]
3380:        inputs.extend(["-ss", f"{max(0.0, L.src_offset):.3f}", "-t", f"{max(0.2, L.duration or total_dur):.3f}", "-i", L.source_file])
3696:        in_args = ["-ss", str(off), "-t", str(dur)]
3698:            in_args = ["-stream_loop", "-1", "-ss", str(off), "-t", str(dur)]
3961:            inputs.extend(["-ss", str(seg_start), "-t", str(seg_lens[si]), "-i", source_path])
4190:                inputs.extend(["-ss", str(clip.start_time), "-t", str(total_dur), "-i", ovl_path])
4280:                in_args = ["-ss", str(off), "-t", str(dur)]
4282:                    in_args = ["-stream_loop", "-1", "-ss", str(off), "-t", str(dur)]
4402:        inputs: List[str] = ["-ss", f"{max(0.0, src_time):.3f}", "-i", base_src]
```

#### server.py _export_layered_clip head
```
def _export_layered_clip(clip, out_path: str, out_filename: str, timestamp_str: str, idx: int) -> Optional[Dict[str, Any]]:
    """Layered compositing export: every timeline video/image element renders
    in z-order (bottom first), FX elements apply at their track level only
    (an FX under an upper layer never touches it), then grade, static frames,
    subtitles and free text on top. Mirrors the on-canvas preview."""
    layers = [L for L in (clip.layers or []) if L.source_file]
    if not layers:
        return None
    # resolve files
    for L in layers:
        p0 = os.path.join(DOWNLOADS_DIR, os.path.basename(L.source_file))
        if not os.path.exists(p0) and os.path.exists(L.source_file):
            p0 = L.source_file
        L.source_file = p0
    layers = [L for L in layers if os.path.exists(L.source_file)]
    if not layers:
        return None
    # clamp in-points against the real source length: a layer beyond EOF
    # would silently render as an empty input
    for L in layers:
        d = _probe_duration(L.source_file)
        if d and L.src_offset > d - 0.2:
            L.src_offset = max(0.0, d - max(0.2, float(L.duration or 1.0)))
    layers.sort(key=lambda L: -L.z)          # deepest (highest z) first
    base = layers[0]

    tv = clip.color_grade == "tv" and not clip.src_processed
    fmt = "talking_head_9_16" if clip.src_processed else clip.format
    if clip.format == "cinematic_16_9":
        out_w, out_h = (1920, 1080)
    else:
```

#### server.py defs
```
156:class CheckDiskRequest(BaseModel):
183:def check_disk(req: CheckDiskRequest):
1977:class ExportClipItem(BaseModel):
3017:def _source_has_audio(path: str) -> bool:
3029:def _tv_grade_parts(src: str, dst: str, is_vertical: bool = True) -> List[str]:
3307:def _export_layered_clip(clip, out_path: str, out_filename: str, timestamp_str: str, idx: int) -> Optional[Dict[str, Any]]:
3848:def export_clip_pack(req: ExportPackRequest):
```

#### server.py export_clip_pack inputs
```
3957:        n_inputs = 0
3961:            inputs.extend(["-ss", str(seg_start), "-t", str(seg_lens[si]), "-i", source_path])
3963:            n_inputs += 1
4053:            inputs.extend(["-stream_loop", "-1", "-t", str(total_dur), "-i", bg_path])
4055:            n_inputs += 1
4188:                inputs.extend(["-loop", "1", "-framerate", "30", "-t", str(total_dur), "-i", ovl_path])
4190:                inputs.extend(["-ss", str(clip.start_time), "-t", str(total_dur), "-i", ovl_path])
4191:            n_inputs += 1
4265:                    n_inputs = new_n
4283:                inputs.extend(in_args + ["-i", apath])
4284:                n_inputs += 1
4403:        n_inputs = 1
```

#### disk_manager.check_space signature
```
79:    def check_space(
80-        self,
81-        required_bytes: int,
82-        path: Optional[str] = None,
83-        peak_factor: float = 1.0,
84-        safety_ratio: float = SAFETY_RATIO,
85-        already_present_bytes: int = 0,
```

#### studio/loader.py
```
"""Load server.py with the anchored audit fixes applied and register it as
the `server` module (so verify_all.py / tests / studio_server.py get the
fixed code). After `python -m studio.patching --write` it is a plain import.
"""
from __future__ import annotations

import importlib.util
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from studio.patching import apply_patches, read_source, summarize  # noqa: E402
from studio.server_patches import SERVER_PATCHES  # noqa: E402

REPORT = []


def load_server():
    mod = sys.modules.get("server")
    if mod is not None and getattr(mod, "_STUDIO_PATCHED", False):
        return mod
    path = os.path.join(BASE_DIR, "server.py")
    src, _bom = read_source(path)
    patched, results = apply_patches(src, SERVER_PATCHES, "server.py")
    REPORT[:] = results
    spec = importlib.util.spec_from_file_location("server", path)
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = path
    mod._STUDIO_PATCH_REPORT = [r.as_dict() for r in results]
    sys.modules["server"] = mod
    try:
        exec(compile(patched, path, "exec"), mod.__dict__)
    except BaseException:
        sys.modules.pop("server", None)
        raise
    mod._STUDIO_PATCHED = True
    failed = [r for r in results if r.status == "failed"]
    msg = f"[studio] server.py patches: {summarize(results)}"
    if failed:
        msg += " FAILED: " + ", ".join(f"{r.id} ({r.detail})" for r in failed)
    print(msg, flush=True)
    return mod


server = load_server()
```
