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

# CI report (2026-09-28T08:31:31Z, c38a7b9)

# PROBE PR9
#### server index
```
89|def server_version() -> dict:
111|@app.get("/api/version")
112|def api_version():
116|@app.post("/api/shutdown")
117|async def api_shutdown():
153|class ProbeRequest(BaseModel):
156|class CheckDiskRequest(BaseModel):
159|class DownloadRequest(BaseModel):
171|def format_range_suffix(start: float, end: float) -> str:
177|@app.get("/api/disk-info")
178|def get_disk_info():
182|@app.post("/api/check-disk")
183|def check_disk(req: CheckDiskRequest):
190|@app.post("/api/probe")
191|def probe_video(req: ProbeRequest):
253|def _run_download_task(req: DownloadRequest, segments: list):
333|@app.post("/api/start-download")
334|def start_download(req: DownloadRequest):
420|@app.post("/api/cancel-download")
421|def cancel_download():
432|@app.get("/api/progress")
433|async def progress_stream():
453|def format_duration_str(seconds: float) -> str:
462|def get_or_generate_thumbnail(video_path: str) -> Optional[str]:
482|def probe_media_file(video_path: str) -> Dict[str, Any]:
519|class ImportMediaRequest(BaseModel):
522|class DeleteMediaRequest(BaseModel):
525|class PrepareImageRequest(BaseModel):
530|@app.post("/api/prepare-image")
531|def prepare_image(req: PrepareImageRequest):
571|@app.get("/api/media/library")
572|def get_media_library():
668|@app.get("/api/sfx/list")
669|def list_sfx():
677|@app.get("/api/sfx/{sfxfile}")
678|def get_sfx_file(sfxfile: str):
686|@app.get("/api/fonts/{fontfile}")
687|def get_font_file(fontfile: str):
696|@app.get("/api/media/thumb")
697|def get_media_thumbnail(file: str):
712|@app.get("/api/media/stream")
713|def stream_media_file(file: str, request: Request):
767|@app.post("/api/media/import")
768|def import_media(req: ImportMediaRequest):
787|@app.post("/api/media/upload")
788|async def upload_media(request: Request):
815|@app.delete("/api/media/delete")
816|def delete_media(req: DeleteMediaRequest):
845|def _load_ghost_phrases() -> List[str]:
861|def _norm_phrase(p: str) -> str:
870|def _asr_cache_key(file_path: str, start: float, end: float, model: str,
880|def _asr_cache_read(key: str) -> Optional[Dict[str, Any]]:
890|def _asr_cache_write(key: str, payload: Dict[str, Any]) -> None:
901|class TranscribeRequest(BaseModel):
909|def build_segments_from_words(words: List[Dict[str, Any]], base_offset: float = 0.0) -> List[Dict[str, Any]]:
966|def _extract_asr_audio(file_path: str, start: float, duration: Optional[float], out_path: str) -> None:
977|def _groq_post(audio_path: str, *, model: str, language: Optional[str], prompt: str) -> Dict[str, Any]:
1030|def _groq_words_and_filter(gj: Dict[str, Any], chunk_offset: float, ghost_set: set) -> tuple:
1069|@app.post("/api/transcribe")
1070|def transcribe_media(req: TranscribeRequest):
1212|class Box(BaseModel):
1219|class ZoneKey(Box):
1222|class TrackRequest(BaseModel):
1245|class _LowPass:
1252|class _OneEuro:
1272|def _probe_video_size(video_path: str) -> tuple:
1288|def _iter_gray_frames(video_path: str, t_from: float, t_to: float, fps: float,
1321|def _zone_at_time(zone: Optional[Box], zone_keys: Optional[List[ZoneKey]], t: float,
1351|def _clamp_box_into_zone(nx: float, ny: float, nw: float, nh: float, zone_px: tuple,
1361|def _track_feature(img):
1372|def _patch_shape_ok(shape, tw, th):
1375|def _ncc_track_run(frames_iter, fps: float, start_box_norm: tuple, start_t: float,
1504|def _csrt_track_run(frames_iter, fps: float, start_box_norm: tuple, start_t: float,
1561|def _track_full_range(file_path: str, req: TrackRequest) -> List[Dict[str, Any]]:
1622|@app.post("/api/track-object")
1623|def track_object(req: TrackRequest):
1674|class ProxyRequest(BaseModel):
1679|@app.post("/api/proxy")
1680|def make_proxy(req: ProxyRequest):
1706|class WaveformRequest(BaseModel):
1712|@app.post("/api/waveform")
1713|def waveform(req: WaveformRequest):
1745|def format_export_name(template: str, ctx: Dict[str, Any]) -> str:
1760|class ExportQueueRequest(BaseModel):
1772|def _export_queue_worker():
1797|@app.post("/api/export-queue")
1798|def export_queue_enqueue(req: ExportQueueRequest):
1818|@app.get("/api/export-queue/status")
1819|def export_queue_status():
1829|@app.get("/api/export-queue/stream")
1830|async def export_queue_stream():
1861|@app.post("/api/export-queue/clear")
1862|def export_queue_clear():
1872|@app.get("/api/grade/lut")
1873|def get_grade_lut():
1882|@app.websocket("/ws/render/{job_id}")
1883|async def ws_render(ws: WebSocket, job_id: str):
1892|class ChannelPresetRequest(BaseModel):
1896|@app.get("/api/presets/channel/{channel}")
1897|def get_channel_preset(channel: str):
1907|@app.post("/api/presets/channel")
1908|def save_channel_preset(req: ChannelPresetRequest):
1918|class ExportSegment(BaseModel):
1922|class CropBox(BaseModel):
1929|class PipBox(BaseModel):
1935|class FxOverlay(BaseModel):
1950|class ExportLayer(BaseModel):
1964|class FxSound(BaseModel):
1970|class TimelineAudioClip(BaseModel):
1980|class ExportClipItem(BaseModel):
2036|def _probe_duration(path: str) -> Optional[float]:
2048|def _downsample_track_path(path: List[Dict[str, Any]], max_points: int = 18) -> List[Dict[str, Any]]:
2055|def _build_track_expr(points: List[Dict[str, Any]], axis: str, out_w: int, out_h: int) -> str:
2082|class ExportPackRequest(BaseModel):
2087|def generate_ass_subtitle_content(subtitles: List[Dict[str, Any]], template_id: str = "meme") -> str:
2345|def _text_has_cyrillic(subtitles: List[Dict[str, Any]]) -> bool:
2353|def _font_cmap_supports_cyrillic(ttf_name: str) -> bool:
2368|def _build_cyr_capable_fonts() -> set:
2378|def _resolve_font(font: str, has_cyr: bool) -> str:
2433|def _letter_widths(font: str, size_px: float, text: str) -> List[float]:
2470|def _letter_positions(font: str, size_px: float, text: str, out_w: int, spacing: float = 0.0) -> List[float]:
2481|def _tv_sub_opts(subtitle_template: str, clip, subtitles=None) -> dict:
2505|def _is_hot_word(word: str) -> bool:
2509|def _ass_escape(s: str) -> str:
2516|def build_tv_subtitles_ass(remapped_subs, style_id: str, out_w: int, out_h: int, margin_v: int,
2785|def build_text_elements_ass(text_items: List[Dict[str, Any]], out_w: int, out_h: int) -> str:
3020|def _source_has_audio(path: str) -> bool:
3032|def _tv_grade_parts(src: str, dst: str, is_vertical: bool = True) -> List[str]:
3053|def _apply_fx_chain(filter_parts: List[str], curr_v: str, fx_list: List[FxOverlay],
3223|def _sfx_maybe_file(inputs: List[str], filter_parts: List[str], n_inputs: int,
3246|def _remap_subtitles_for_segments(subtitles, segments, seg_out_starts, seg_lens):
3303|def _two_pass_loudnorm(src_wav: str, dst_wav: str, target_i: float = -14.0,
3337|def _export_layered_clip(clip, out_path: str, out_filename: str, timestamp_str: str, idx: int) -> Optional[Dict[str, Any]]:
3853|def _normalize_subtitle_mode(clip) -> None:
3877|@app.post("/api/export-pack")
3878|def export_clip_pack(req: ExportPackRequest):
4411|@app.post("/api/preview-frame")
4412|def preview_frame(req: dict):
4544|@app.get("/api/exported-packs")
4545|def list_exported_packs():
4565|@app.post("/api/open-folder")
4566|async def open_folder(request: Request):
4588|def run_server(host: str = "127.0.0.1", port: int = 8765):
```
#### def _apply_fx_chain
```py
3053|def _apply_fx_chain(filter_parts: List[str], curr_v: str, fx_list: List[FxOverlay],
3054|                    out_w: int, out_h: int, total_dur: float, tag_prefix: str) -> str:
3055|    """Burn FX overlay elements (flash / bars / shake) onto curr_v in order.
3056|    Returns the new current video label. Shake uses lanczos to avoid blur;
3057|    flash uses rapid attack and additive blend for authentic viral impact."""
3058|    for fi, fx in enumerate(fx_list):
3059|        try:
3060|            s0 = max(0.0, float(fx.start))
3061|            e0 = min(total_dur, float(fx.end))
3062|        except (TypeError, ValueError):
3063|            continue
3064|        if not (e0 > s0 + 0.05):
3065|            continue
3066|        d = e0 - s0
3067|        en = f"'between(t,{s0:.3f},{e0:.3f})'"
3068|        if fx.kind == "shake":
3069|            # N11: crop/scale geometry is applied CONSTANTLY (no enable) with an
3070|            # amplitude envelope — output size never changes, so there is no
3071|            # zoom pop at the enable boundaries.
3072|            a = max(2, min(40, int(fx.amp or 10)))
3073|            fq = max(2.0, min(15.0, float(fx.freq or 7.0)))
3074|            env = f"min(1\\,max(0\\,min(t-{s0:.3f}\\,{e0:.3f}-t)/0.1))"
3075|            filter_parts.append(
3076|                f"{curr_v}split=2[{tag_prefix}v{fi}a][{tag_prefix}v{fi}b]"
3077|            )
3078|            filter_parts.append(
3079|                f"[{tag_prefix}v{fi}b]crop=iw-{2*a}:ih-{2*a}:"
3080|                f"x='{a}+{a}*sin(2*PI*{fq:.1f}*t)*{env}':y='{a}+{a}*cos(2*PI*{fq*9/7:.1f}*t)*{env}',"
3081|                f"scale={out_w}:{out_h}:flags=lanczos+accurate_rnd[{tag_prefix}v{fi}s]"
3082|            )
3083|            filter_parts.append(f"[{tag_prefix}v{fi}a][{tag_prefix}v{fi}s]overlay=x=0:y=0[{tag_prefix}v{fi}]")
3084|            curr_v = f"[{tag_prefix}v{fi}]"
3085|        elif fx.kind == "zoom":
3086|            # studio:zoom-anim - §15 zoom punch that REALLY animates. The old
3087|            # crop=w='iw/env' was a no-op: crop evaluates w/h once at init
3088|            # (t=NAN -> env=1), so every exported zoom was bit-identical to the
3089|            # input; crop x/y are also clamped to the INIT size, so a crop after
3090|            # a per-frame scale cannot move. Now: the frame is scaled per frame
3091|            # (scale eval=frame, lanczos) and overlaid onto itself at a per-frame
3092|            # offset that keeps the fx anchor (template face anchor, 0..1 of the
3093|            # output; default centre) fixed, clamped so no edge ever shows.
3094|            # Same envelope as before (and as the preview curve).
3095|            a = max(0.02, min(0.5, float(fx.peak if fx.peak and fx.peak < 1 else 0.15)))
3096|            ax = getattr(fx, "anchor_x", None)
3097|            ay = getattr(fx, "anchor_y", None)
3098|            ax = 0.5 if ax is None else max(0.0, min(1.0, float(ax)))
3099|            ay = 0.5 if ay is None else max(0.0, min(1.0, float(ay)))
3100|            zx = (f"(1+{a:.4f}*(0.12+0.88*exp(-3*max(t-{s0:.3f}\\,0)/{max(1e-3, d):.3f}))"
3101|                  f"*between(t\\,{s0:.3f}\\,{e0:.3f}))")
3102|            ox = f"-max(0\\,min({out_w}*{zx}-{out_w}\\,{ax:.4f}*{out_w}*{zx}-{ax:.4f}*{out_w}))"
3103|            oy = f"-max(0\\,min({out_h}*{zx}-{out_h}\\,{ay:.4f}*{out_h}*{zx}-{ay:.4f}*{out_h}))"
3104|            filter_parts.append(
3105|                f"{curr_v}scale={out_w}:{out_h}:flags=lanczos+accurate_rnd,"
3106|                f"split=2[{tag_prefix}v{fi}b][{tag_prefix}v{fi}s]")
3107|            filter_parts.append(
3108|                f"[{tag_prefix}v{fi}s]scale=w='2*trunc(iw*{zx}/2+0.5)':h='2*trunc(ih*{zx}/2+0.5)':"
3109|                f"eval=frame:flags=lanczos+accurate_rnd[{tag_prefix}v{fi}z]")
3110|            filter_parts.append(
3111|                f"[{tag_prefix}v{fi}b][{tag_prefix}v{fi}z]overlay=x='{ox}':y='{oy}':eval=frame,"
3112|                f"setsar=1[{tag_prefix}v{fi}]")
3113|            curr_v = f"[{tag_prefix}v{fi}]"
3114|        elif fx.kind == "lens":
3115|            # studio:lens-anim - animated Lens Punch (§13.3). lenscorrection
3116|            # options are init-only, so the old code held one static barrel for
3117|            # the whole interval. k1 now follows the preview bell (canvasMonitor:
3118|            # peak at 32 % of the interval, width 0.35) in 6 enable-gated steps;
3119|            # the CA shift follows k1.
3120|            k1p = max(-0.45, min(0.45, float(fx.peak or 0.12)))
3121|            steps = 6
3122|            for si in range(steps):
3123|                t0 = s0 + d * si / steps
3124|                t1 = e0 if si == steps - 1 else s0 + d * (si + 1) / steps
3125|                pm = (si + 0.5) / steps
3126|                k = k1p * (2.718281828459045 ** (-((pm - 0.32) / 0.35) ** 2))
3127|                if abs(k) < 0.004:
3128|                    continue
3129|                sen = f"'gte(t,{t0:.3f})*lt(t,{t1:.3f})'"
3130|                shift = max(1, int(round(abs(k) * 12)))
3131|                lbl = f"[{tag_prefix}v{fi}l{si}]"
3132|                filter_parts.append(
3133|                    f"{curr_v}lenscorrection=k1={k:.4f}:k2=0:cx=0.5:cy=0.5:enable={sen},"
3134|                    f"rgbashift=rh={shift}:bh=-{shift}:enable={sen}{lbl}")
3135|                curr_v = lbl
3136|        elif fx.kind == "threshold":
3137|            # §15 threshold hit: hard luma gate + noise dither, 1-2 frames
3138|            th = int(16 + (fx.peak if fx.peak is not None else 0.45) * 219)
3139|            filter_parts.append(
3140|                f"{curr_v}lutyuv=y='if(gt(val,{th}),235,16)':u=128:v=128:"
3141|                f"enable={en}[{tag_prefix}v{fi}]")
3142|            curr_v = f"[{tag_prefix}v{fi}]"
3143|        elif fx.kind == "whip":
3144|            # §15 whip: horizontal displacement with a smoothstep ease via
3145|            # animated crop-x (directional blur is new-renderer territory).
3146|            dirn = 1 if (fx.color or "white") != "left" else -1
3147|            BS = chr(92)
3148|            prg = f"((t-{s0:.3f})/{max(1e-3, d):.3f})"
3149|            pc = f"max(0{BS},min(1{BS},{prg}))"
3150|            ease = f"({pc}*{pc}*(3-2*{pc}))"
3151|            shift = f"{dirn}*0.25*iw*{ease}"  # studio:whip-clamp
3152|            filter_parts.append(
3153|                f"{curr_v}split=2[{tag_prefix}v{fi}a][{tag_prefix}v{fi}b]")
3154|            filter_parts.append(
3155|                f"[{tag_prefix}v{fi}b]scale=iw*2:ih,"
3156|                f"crop=w=iw/2:h=ih:x='max(0{BS},min(iw/2{BS},(iw-iw/2)/2+({shift})))':y=0,"  # studio:whip-clamp-x
3157|                f"scale={out_w}:{out_h}:flags=lanczos+accurate_rnd[{tag_prefix}v{fi}s]")
3158|            filter_parts.append(
3159|                f"[{tag_prefix}v{fi}a][{tag_prefix}v{fi}s]overlay=x=0:y=0:enable={en}[{tag_prefix}v{fi}]")
3160|            curr_v = f"[{tag_prefix}v{fi}]"
3161|        elif fx.kind in ("ramp", "freeze"):
3162|            # time-remap lives in the new renderer (Composition §8.3); the
3163|            # transition path logs and skips instead of producing garbage.
3164|            # studio:fx-timeremap - rendered in the filtergraph (video only)
3165|            _tr_parts, curr_v = _studio.fx_time_remap(fx.kind, curr_v, f"{tag_prefix}v{fi}", s0, e0)
3166|            filter_parts.extend(_tr_parts)
3167|        elif fx.kind == "bars":
3168|            bh = max(20, min(out_h // 3, int(fx.bar_h or 120)))
3169|            prog = f"min(1,min(t-{s0:.3f},{e0:.3f}-t)/0.35)"
3170|            sh_amp, sh_f = 0, 7.0
3171|            for sx in fx_list:
3172|                if sx.kind != "shake":
3173|                    continue
3174|                try:
3175|                    ss = max(0.0, float(sx.start)); se = min(total_dur, float(sx.end))
3176|                except (TypeError, ValueError):
3177|                    continue
3178|                if ss < e0 and se > s0:
3179|                    sh_amp = max(sh_amp, max(2, min(40, int(sx.amp or 10))))
3180|                    sh_f = max(2.0, min(15.0, float(sx.freq or 7.0)))
3181|            sh_y = (f"{sh_amp}*cos(2*PI*{sh_f*9/7:.1f}*t)*between(t,{s0:.3f},{e0:.3f})") if sh_amp else "0"
3182|            filter_parts.append(f"color=c=black:s={out_w}x{bh}:d={d:.3f},format=rgba,setpts=PTS+{s0:.3f}/TB[{tag_prefix}c{fi}t]")
3183|            filter_parts.append(f"color=c=black:s={out_w}x{bh}:d={d:.3f},format=rgba,setpts=PTS+{s0:.3f}/TB[{tag_prefix}c{fi}b]")
3184|            filter_parts.append(
3185|                f"{curr_v}[{tag_prefix}c{fi}t]overlay=x=0:y='-{bh}+{bh}*{prog}+{sh_y}':enable={en}[{tag_prefix}m{fi}]"
3186|            )
3187|            filter_parts.append(
3188|                f"[{tag_prefix}m{fi}][{tag_prefix}c{fi}b]overlay=x=0:y='{out_h}-{bh}*{prog}+{sh_y}':enable={en}[{tag_prefix}v{fi}]"
3189|            )
3190|            curr_v = f"[{tag_prefix}v{fi}]"
3191|        else:  # flash
3192|            peak = max(0.2, min(1.0, float(fx.peak or 0.85)))
3193|            f_in = min(0.04, d * 0.15)
3194|            f_out = max(0.08, d - f_in)
3195|            if (fx.color or "white") == "bw":
3196|                filter_parts.append(f"{curr_v}split=2[{tag_prefix}v{fi}a][{tag_prefix}v{fi}b]")
3197|                filter_parts.append(
3198|                    f"[{tag_prefix}v{fi}b]hue=s=0,format=rgba,"
3199|                    f"fade=t=in:st={s0:.3f}:d={f_in:.3f}:alpha=1,"
3200|                    f"fade=t=out:st={s0+f_in:.3f}:d={f_out:.3f}:alpha=1,"
3201|                    f"colorchannelmixer=aa={peak:g}[{tag_prefix}v{fi}g]"
3202|                )
3203|                filter_parts.append(f"[{tag_prefix}v{fi}a][{tag_prefix}v{fi}g]overlay=x=0:y=0:enable={en}[{tag_prefix}v{fi}]")
3204|            else:
3205|                # N10: screen blend in RGB against a clip-length source (no
3206|                # full-length addition of U/V — no clipping, no colour shift).
3207|                cmap = {"white": "white", "green": "0x39FF00", "red": "0xFF2222"}.get(fx.color or "white", "white")
3208|                filter_parts.append(
3209|                    f"color=c={cmap}:s={out_w}x{out_h}:d={d:.3f},format=rgba,"
3210|                    f"fade=t=in:st=0:d={f_in:.3f}:alpha=1,"
3211|                    f"fade=t=out:st={f_in:.3f}:d={f_out:.3f}:alpha=1,"
3212|                    f"colorchannelmixer=aa={peak:g},"
3213|                    f"setpts=PTS+{s0:.3f}/TB[{tag_prefix}c{fi}]"
3214|                )
3215|                filter_parts.append(f"{curr_v}format=gbrp[{tag_prefix}v{fi}rgb]")
3216|                filter_parts.append(
3217|                    f"[{tag_prefix}v{fi}rgb][{tag_prefix}c{fi}]blend=all_mode=screen:all_opacity=1:enable={en}[{tag_prefix}v{fi}]"
3218|                )
3219|            curr_v = f"[{tag_prefix}v{fi}]"
3220|    return curr_v
3221|
3222|
3223|
```
#### def _tv_grade_parts
```py
3032|def _tv_grade_parts(src: str, dst: str, is_vertical: bool = True) -> List[str]:
3033|    """H6/N8: grade chain ordered for WYSIWYG parity.
3034|    setparams(BT.709) -> own 65^3 LUT (trilinear) -> cas at output res ->
3035|    format=gbrp (text is burned in RGB afterwards; the FINAL yuv420p
3036|    quantization with BT.709 matrix happens once, after all overlays).
3037|    No hqdn3d (smearing source of the old graph), no eq (baked into the LUT)."""
3038|    lut_path = os.path.join(BASE_DIR, "tv_grade.cube")
3039|    if os.path.exists(lut_path):
3040|        esc_lut = lut_path.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
3041|        lut_filter = f"lut3d=file='{esc_lut}':interp=trilinear,"
3042|    else:
3043|        lut_filter = "curves=m='0/0 0.25/0.22 0.5/0.52 0.75/0.78 1/1',"
3044|    chain = (
3045|        "setparams=range=tv:colorspace=bt709:color_primaries=bt709:color_trc=bt709,"
3046|        f"{lut_filter}"
3047|        "cas=0.30,"
3048|        "format=gbrp"
3049|    )
3050|    return [f"{src}{chain}{dst}"]
3051|
3052|
3053|
```
#### def _tv_grade_filter
```py
```
#### hits
```
2026|    text_z: Optional[int] = None
2786|    """Generates an ASS subtitle file for free text overlays placed on the canvas.
3341|    subtitles and free text on top. Mirrors the on-canvas preview."""
3401|    text_z = clip.text_z if clip.text_z is not None else -1
3402|    fx_over_text = sorted([fx for fx in (clip.overlays or []) if (fx.z or 0) <= text_z],
3404|    fx_normal = [fx for fx in (clip.overlays or []) if (fx.z or 0) > text_z]
3456|                        filter_parts.append(f"[topL{li}][botL{li}]vstack=inputs=2[comp0]")
3493|                    filter_parts.append(f"[topL{li}][botL{li}]vstack=inputs=2[comp0]")
3599|        filter_parts.extend(_tv_grade_parts(comp, "[graded]", is_vertical=(out_w < out_h)))
4013|                        filter_parts.append(f"[top{si}][bot{si}]vstack=inputs=2[g{si}]")
4061|                    filter_parts.append(f"[top{si}][bot{si}]vstack=inputs=2[g{si}]")
4093|                filter_parts.append(f"[top{si}][bot{si}]vstack=inputs=2[g{si}]")
4124|            filter_parts.extend(_tv_grade_parts(curr_v, "[graded]", is_vertical=(out_w < out_h)))
4452|            fp.append(f"[topL][botL]vstack=inputs=2[comp0]")
4476|            fp.extend(_tv_grade_parts(comp, "[graded]", is_vertical=(W < H)))
```
#### ctx 2026
```py
2014|    # Layered compositing: every video/image element from the timeline.
2015|    # When non-empty, takes priority over the single source_file pipeline.
2016|    layers: List[ExportLayer] = []
2017|    # Free text elements (AE-style): {text,start,end,font,size,color,glow,
2018|    # anim_in,anim_out,x,y,align,shake} — output-local seconds
2019|    text_items: List[Dict[str, Any]] = []
2020|    # subtitles already in output time (region pipeline) — skip re-mapping
2021|    subs_in_output_time: bool = False
2022|    # source is already a finished short (burned subs + grade): passthrough —
2023|    # do NOT re-grade and do NOT burn subtitles/text over it
2024|    src_processed: bool = False
2025|    # track index of the TOPMOST text layer: FX on tracks ABOVE it burn over text
2026|    text_z: Optional[int] = None
2027|    # highlight long "hot" keywords in an accent color (viral style)
2028|    hot_words: bool = False
2029|    # H1: single source of subtitles — "timeline" (text_items) | "generated"
2030|    # (subtitles field) | "none". Unset + both present -> HTTP 422.
2031|    subtitle_mode: Optional[str] = None
2032|    # Static cinematic frames (рамки) burned above FX, below subtitles (px)
2033|    bar_top: int = 0
2034|    bar_bottom: int = 0
2035|
2036|def _probe_duration(path: str) -> Optional[float]:
2037|    try:
```
#### ctx 2786
```py
2774|                lines.append(
2775|                    f"Dialogue: 1,{ts},{te},Glow_{wsid},,0,0,0,,"
2776|                    f"{{\\an5{pos_tag}\\blur{core_b}\\bord{max(2, core_b//2)}\\1c&H{gcol[-6:]}&\\3c&H{gcol[-6:]}&\\alpha&HFF&\\t(50,140,\\alpha&H60&){pop_tag}}}{_ass_escape(wt)}"
2777|                )
2778|                # Main text with crisp dark outline and shadow (top layer)
2779|                lines.append(
2780|                    f"Dialogue: 2,{ts},{te},Main_{wsid},,0,0,0,,"
2781|                    f"{{\\an5{pos_tag}\\fad(15,{out_fade}){bord_tag}{col_tag}{pop_tag}}}{_ass_escape(wt)}"
2782|                )
2783|
2784|    return "\n".join(lines)
2785|def build_text_elements_ass(text_items: List[Dict[str, Any]], out_w: int, out_h: int) -> str:
2786|    """Generates an ASS subtitle file for free text overlays placed on the canvas.
2787|    B2 = "\\"
2788|    Renders with After Effects-grade 4-layer radiant neon glow, 3D shadow, bold stroke,
2789|    smooth entry/exit animations, and organic shake."""
2790|    B2 = "\\"
2791|    if not text_items:
2792|        return ""
2793|    styles_seen = {}
2794|    for ti in text_items:
2795|        fam = ti.get("font") if ti.get("font") in TV_SUB_FONTS else "Montserrat ExtraBold"
2796|        fam = _resolve_font(fam, _text_has_cyrillic([{"text": ti.get("text", "")}]))
2797|        # размер здесь должен совпадать с итоговым размером в цикле событий ниже
```
#### ctx 3341
```py
3329|        p2 = ["ffmpeg", "-y", "-loglevel", "error", "-i", src_wav, "-af", af,
3330|              "-ar", "48000", "-c:a", "pcm_s16le", dst_wav]
3331|        r2 = subprocess.run(p2, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=600)
3332|        return r2.returncode == 0 and os.path.exists(dst_wav) and os.path.getsize(dst_wav) > 44
3333|    except Exception:
3334|        return False
3335|
3336|
3337|def _export_layered_clip(clip, out_path: str, out_filename: str, timestamp_str: str, idx: int) -> Optional[Dict[str, Any]]:
3338|    """Layered compositing export: every timeline video/image element renders
3339|    in z-order (bottom first), FX elements apply at their track level only
3340|    (an FX under an upper layer never touches it), then grade, static frames,
3341|    subtitles and free text on top. Mirrors the on-canvas preview."""
3342|    layers = [L for L in (clip.layers or []) if L.source_file]
3343|    if not layers:
3344|        return None
3345|    # resolve files
3346|    for L in layers:
3347|        p0 = os.path.join(DOWNLOADS_DIR, os.path.basename(L.source_file))
3348|        if not os.path.exists(p0) and os.path.exists(L.source_file):
3349|            p0 = L.source_file
3350|        L.source_file = p0
3351|    layers = [L for L in layers if os.path.exists(L.source_file)]
3352|    if not layers:
```
#### ctx 3401
```py
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
3401|    text_z = clip.text_z if clip.text_z is not None else -1
3402|    fx_over_text = sorted([fx for fx in (clip.overlays or []) if (fx.z or 0) <= text_z],
3403|                          key=lambda fx: -(fx.z or 0))
3404|    fx_normal = [fx for fx in (clip.overlays or []) if (fx.z or 0) > text_z]
3405|
3406|    z_levels = sorted({L.z for L in layers}, reverse=True)  # deepest first
3407|    comp = None
3408|    for li, L in enumerate(layers):
3409|        is_base = li == 0
3410|        inputs.extend(["-ss", f"{max(0.0, L.src_offset):.3f}", "-t", f"{max(0.2, L.duration or total_dur):.3f}", "-i", L.source_file])
3411|        src_i = n_inputs
3412|        n_inputs += 1
```
#### ctx 3456
```py
3444|                            gbxx = f"{max(0.0, min(0.98, gx.x)):g}*iw"
3445|                            gbyy = f"{max(0.0, min(0.98, gx.y)):g}*ih"
3446|                            filter_parts.append(
3447|                                f"[sbb{li}]crop={gbw}:{gbh}:{gbxx}:{gbyy},"
3448|                                f"scale={out_w}:{bot_h}:force_original_aspect_ratio=increase:flags=lanczos+accurate_rnd,"
3449|                                f"crop={out_w}:{bot_h}[botL{li}]"
3450|                            )
3451|                        else:
3452|                            filter_parts.append(
3453|                                f"[sbb{li}]scale={out_w}:{bot_h}:force_original_aspect_ratio=increase,"
3454|                                f"crop={out_w}:{bot_h}[botL{li}]"
3455|                            )
3456|                        filter_parts.append(f"[topL{li}][botL{li}]vstack=inputs=2[comp0]")
3457|                        comp = "[comp0]"
3458|                elif fmt == "talking_head_9_16":
3459|                    filter_parts.append(
3460|                        f"[{src_i}:v]crop={bw}:{bh_}:{bxx}:{byy},"
3461|                        f"scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
3462|                        f"crop={out_w}:{out_h}[comp0]"
3463|                    )
3464|                    comp = "[comp0]"
3465|                else:
3466|                    filter_parts.append(
3467|                        f"[{src_i}:v]crop={bw}:{bh_}:{bxx}:{byy},"
```
#### ctx 3493
```py
3481|                        gbxx = f"{max(0.0, min(0.98, gx.x)):g}*iw"
3482|                        gbyy = f"{max(0.0, min(0.98, gx.y)):g}*ih"
3483|                        filter_parts.append(
3484|                            f"[sbb{li}]crop={gbw}:{gbh}:{gbxx}:{gbyy},"
3485|                            f"scale={out_w}:{bot_h}:force_original_aspect_ratio=increase:flags=lanczos+accurate_rnd,"
3486|                            f"crop={out_w}:{bot_h}[botL{li}]"
3487|                        )
3488|                    else:
3489|                        filter_parts.append(
3490|                            f"[sbb{li}]scale={out_w}:{bot_h}:force_original_aspect_ratio=increase:flags=lanczos+accurate_rnd,"
3491|                            f"crop={out_w}:{bot_h}[botL{li}]"
3492|                        )
3493|                    filter_parts.append(f"[topL{li}][botL{li}]vstack=inputs=2[comp0]")
3494|                    comp = "[comp0]"
3495|            elif fmt == "talking_head_9_16":
3496|                # vertical crop: right-anchored for top presets, centered otherwise
3497|                if clip.crop_preset in ("top_left", "top_right"):
3498|                    ax = "0" if clip.crop_preset == "top_left" else "iw-ow"
3499|                    ay = "0"
3500|                elif clip.crop_preset == "face":
3501|                    ax = "(iw-ow)/2"
3502|                    ay = "(ih-oh)/3"
3503|                else:
3504|                    ax = "(iw-ow)/2"
```
#### ctx 3599
```py
3587|        filter_parts.append(
3588|            f"[{bg_i}:v]scale={out_w}:{bot_h}:force_original_aspect_ratio=increase,"
3589|            f"crop={out_w}:{bot_h}[bgBot]"
3590|        )
3591|        filter_parts.append(f"{comp}[bgBot]overlay=x=0:y={top_h}[compBG]")
3592|        comp = "[compBG]"
3593|
3594|    if comp is None:
3595|        return None
3596|
3597|    # ── TV color grade on the full composite ──
3598|    if tv:
3599|        filter_parts.extend(_tv_grade_parts(comp, "[graded]", is_vertical=(out_w < out_h)))
3600|        comp = "[graded]"
3601|
3602|    # ── static cinematic frames (рамки сверху/снизу) ──
3603|    bt = max(0, min(out_h // 3, int(clip.bar_top or 0)))
3604|    bb = max(0, min(out_h // 3, int(clip.bar_bottom or 0)))
3605|    if bt > 0 or bb > 0:
3606|        parts = []
3607|        if bt > 0:
3608|            parts.append(f"drawbox=x=0:y=0:w={out_w}:h={bt}:color=black:t=fill")
3609|        if bb > 0:
3610|            parts.append(f"drawbox=x=0:y={out_h - bb}:w={out_w}:h={bb}:color=black:t=fill")
```
#### ctx 4013
```py
4001|                if clip.format == "split_adhd":
4002|                    filter_parts.append(f"[{src_i}:v]split=2[stop{si}][sbot{si}]")
4003|                    filter_parts.append(
4004|                        f"[stop{si}]crop={bw}:{bh}:{bxx}:{byy},"
4005|                        f"scale={out_w}:{top_h}:force_original_aspect_ratio=increase,"
4006|                        f"crop={out_w}:{top_h}[top{si}]"
4007|                    )
4008|                    if not bg_path:
4009|                        filter_parts.append(
4010|                            f"[sbot{si}]scale={out_w}:{bot_h}:force_original_aspect_ratio=increase,"
4011|                            f"crop={out_w}:{bot_h}[bot{si}]"
4012|                        )
4013|                        filter_parts.append(f"[top{si}][bot{si}]vstack=inputs=2[g{si}]")
4014|                elif clip.format == "talking_head_9_16":
4015|                    filter_parts.append(
4016|                        f"[{src_i}:v]crop={bw}:{bh}:{bxx}:{byy},"
4017|                        f"scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
4018|                        f"crop={out_w}:{out_h}[g{si}]"
4019|                    )
4020|                else:
4021|                    filter_parts.append(
4022|                        f"[{src_i}:v]crop={bw}:{bh}:{bxx}:{byy},"
4023|                        f"scale={out_w}:{out_h}:flags=lanczos[g{si}]"
4024|                    )
```
#### ctx 4061
```py
4049|                        gbxx = f"{max(0.0, min(0.98, gx.x)):g}*iw"
4050|                        gbyy = f"{max(0.0, min(0.98, gx.y)):g}*ih"
4051|                        filter_parts.append(
4052|                            f"[sbot{si}]crop={gbw}:{gbh}:{gbxx}:{gbyy},"
4053|                            f"scale={out_w}:{bot_h}:force_original_aspect_ratio=increase:flags=lanczos+accurate_rnd,"
4054|                            f"crop={out_w}:{bot_h}[bot{si}]"
4055|                        )
4056|                    else:
4057|                        filter_parts.append(
4058|                            f"[sbot{si}]scale={out_w}:{bot_h}:force_original_aspect_ratio=increase:flags=lanczos+accurate_rnd,"
4059|                            f"crop={out_w}:{bot_h}[bot{si}]"
4060|                        )
4061|                    filter_parts.append(f"[top{si}][bot{si}]vstack=inputs=2[g{si}]")
4062|            elif clip.format == "talking_head_9_16":
4063|                ar_v = out_w / float(out_h)
4064|                filter_parts.append(
4065|                    f"[{src_i}:v]crop=w='min(iw\\,ih*{ar_v:.5f})':h='min(ih\\,iw/{ar_v:.5f})':"
4066|                    f"x='{crop_x}':y='{crop_y}',"
4067|                    f"scale={out_w}:{out_h}:force_original_aspect_ratio=increase:flags=lanczos+accurate_rnd,"
4068|                    f"crop={out_w}:{out_h}[g{si}]"
4069|                )
4070|            else:  # cinematic_16_9
4071|                filter_parts.append(f"[{src_i}:v]scale={out_w}:{out_h}:flags=lanczos[g{si}]")
4072|            seg_labels.append(f"[g{si}]")
```
#### ctx 4093
```py
4081|        # background input (single, split across segments)
4082|        if clip.format == "split_adhd" and bg_path:
4083|            inputs.extend(["-stream_loop", "-1", "-t", str(total_dur), "-i", bg_path])
4084|            bg_i = n_inputs
4085|            n_inputs += 1
4086|            bg_splits = "".join(f"[bgk{k}]" for k in range(n_seg))
4087|            filter_parts.append(f"[{bg_i}:v]split={n_seg}{bg_splits}")
4088|            for si in range(n_seg):
4089|                filter_parts.append(
4090|                    f"[bgk{si}]scale={out_w}:{bot_h}:force_original_aspect_ratio=increase,"
4091|                    f"crop={out_w}:{bot_h}[bot{si}]"
4092|                )
4093|                filter_parts.append(f"[top{si}][bot{si}]vstack=inputs=2[g{si}]")
4094|
4095|        # ── Join segments: soft white flash (xfade) or hard concat, per junction ──
4096|        if n_seg == 1:
4097|            joined = "g0"
4098|        elif clip.flash_cuts:
4099|            prev = "g0"
4100|            out_dur = seg_lens[0]
4101|            for si in range(1, n_seg):
4102|                out_lbl = f"x{si}"
4103|                if (si - 1) in skip_flash:
4104|                    # hard cut: plain concat keeps both segments full-length
```
#### ctx 4124
```py
4112|                prev = out_lbl
4113|            joined = prev
4114|        else:
4115|            joined = f"cat{idx}"
4116|            filter_parts.append(
4117|                "".join(seg_labels) + f"concat=n={n_seg}:v=1:a=0[{joined}]"
4118|            )
4119|
4120|        curr_v = f"[{joined}]"
4121|
4122|        # ── TV color grade (after join so both halves glow uniformly) ──
4123|        if tv:
4124|            filter_parts.extend(_tv_grade_parts(curr_v, "[graded]", is_vertical=(out_w < out_h)))
4125|            curr_v = "[graded]"
4126|
4127|        # ── Facecam PIP removed: the webcam band already shows the face,
4128|        #     a duplicated PIP only clutters the frame ──
4129|        pip_done = False
4130|
4131|        # ── Platform badge (только legacy; в TV-референсах бейджа нет) ──
4132|        if not tv:
4133|            badge_platform = clip.platform.upper()
4134|            badge_handle = clip.streamer_handle or "@STREAMER"
4135|            badge_text = f"{badge_platform}  {badge_handle}".replace("'", "\\'")
```
#### ctx 4452
```py
4440|            byy = f"{max(0.0, min(0.98, bx.get('y', 0.0))):g}*ih"
4441|            fp.append(f"[0:v]split=2[stb][sbb]")
4442|            fp.append(f"[stb]crop={bw}:{bh_}:{bxx}:{byy},scale={W}:{top_h}:force_original_aspect_ratio=increase,crop={W}:{top_h}[topL]")
4443|            if bg_box:
4444|                gx = bg_box
4445|                gbw = f"{max(0.02, min(1.0, gx.get('w', 0.5))):g}*iw"
4446|                gbh = f"{max(0.02, min(1.0, gx.get('h', 0.5))):g}*ih"
4447|                gbxx = f"{max(0.0, min(0.98, gx.get('x', 0.0))):g}*iw"
4448|                gbyy = f"{max(0.0, min(0.98, gx.get('y', 0.0))):g}*ih"
4449|                fp.append(f"[sbb]crop={gbw}:{gbh}:{gbxx}:{gbyy},scale={W}:{bot_h}:force_original_aspect_ratio=increase,crop={W}:{bot_h}[botL]")
4450|            else:
4451|                fp.append(f"[sbb]scale={W}:{bot_h}:force_original_aspect_ratio=increase,crop={W}:{bot_h}[botL]")
4452|            fp.append(f"[topL][botL]vstack=inputs=2[comp0]")
4453|            comp = "[comp0]"
4454|        else:
4455|            bw = f"min(iw\\,ih*{W / float(H):.5f})"
4456|            bh_ = f"min(ih\\,iw/{W / float(H):.5f})"
4457|            fp.append(f"[0:v]crop={bw}:{bh_},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}[comp0]")
4458|            comp = "[comp0]"
4459|
4460|        # FX (flash/bars) — фазы относительно t_rel
4461|        fx_list = []
4462|        for ov in overlays:
4463|            st = float(ov.get("start", 0)) - t_rel
```
#### ctx 4476
```py
4464|            en = float(ov.get("end", 0)) - t_rel
4465|            if en < 0 or st > 0.25:
4466|                continue
4467|            fx_list.append(FxOverlay(kind=ov.get("kind", "flash"), start=max(0.0, st), end=en,
4468|                                     color=ov.get("color", "white"), peak=float(ov.get("peak", 0.75)),
4469|                                     bar_h=int(ov.get("bar_h", 160)), amp=float(ov.get("amp", 12)),
4470|                                     freq=float(ov.get("freq", 7)), z=int(ov.get("z", 0))))
4471|        if fx_list:
4472|            comp = _apply_fx_chain(fp, comp, fx_list, W, H, 0.4, "pv_")
4473|
4474|        # TV grade + bloom
4475|        if use_tv:
4476|            fp.extend(_tv_grade_parts(comp, "[graded]", is_vertical=(W < H)))
4477|            comp = "[graded]"
4478|
4479|        # субтитры: установившееся состояние (всё допечатано)
4480|        ass_path = None
4481|        if subs:
4482|            settled = []
4483|            for s in subs:
4484|                dur = max(0.4, float(s.get("end", 1)) - float(s.get("start", 0)))
4485|                words = [{"word": w.get("word", ""), "start": 0.0, "end": dur} for w in (s.get("words") or [])]
4486|                settled.append({"text": s.get("text", ""), "start": 0.0, "end": dur,
4487|                                "style": s.get("style"), "words": words,
```
#### editor.js index
```
54:    function defaultTrackList() {
63:    function ensureTracksInitialized() {
72:    function trackOrder() {
76:    function getTrack(tid) {
79:    function isTrackLocked(tid) {
83:    function trackClips(tid) {
87:    function textTrackId() {
91:    function firstVideoTrackId() {
96:    function videoTrackIds() {
99:    function audioTrackIds() {
102:    function trackTagLabel(tid) {
108:    function trackDisplayName(tid) {
112:    function isAudioFile(media) {
131:    function formatTimecode(seconds, fps = 60) {
143:    function formatDurationShort(sec) {
277:    function initDOMElements() {
329:    function initTabs() {
350:    function switchTab(tabId) {
361:    function timelineContentWidth() {
366:    function visibleLanesWidth() {
370:    function initCanvas() {
377:    function resizeCanvas() {
404:    function drawRuler() {
466:    async function fetchLibrary() {
487:    function renderMediaLibrary() {
596:    async function deleteMediaFile(filename) {
615:    function addMediaToTimeline(media, trackId = null, desiredStartTime = null) {
664:    function recalcTotalDuration() {
678:    function renderTimeline() {
791:    function renderTracksDOM() {
926:    function bindLaneInteractions() {
931:    function syncLanesHeight() {
937:    function addTrack(kind) {
965:    function moveTrack(trackId, dir) {
978:    function removeTrack(trackId) {
1005:    function syncTranscribeTrackSelect() {
1029:    function selectClip(clipId) {
1122:    function syncFxInspector(clip) {
1233:    function syncTextInspector(clip) {
1357:    function showRegionInspector(r) {
1380:    async function transcribeRegion(r) {
1463:    function findClipById(clipId) {
1472:    function isTextClip(clip) {
1480:    function canPlaceOnTrack(clip, trackId) {
1492:    function trackFromClientY(clientY) {
1501:    function clearLaneHighlights() {
1507:    function initClipDrag(clipEl, clip, startEvent) {
1568:    function initTrimHandle(handleEl, clip, side) {
1625:    function initTimelineInteraction() {
1690:    async function prepareImageClip(media, targetTid, dropTime) {
1716:    function lanesTimeFromClientX(clientX) {
1722:    function onScrubStart(e) {
1741:    function seekTo(timeSec) {
1751:    function seekRelative(deltaSec) {
1755:    function updatePlayheadPosition() {
1761:    function updateTimecodeDisplays() {
1771:    function activeClipOn(trackId, t) {
1779:    function activeVideoLayers(t) {
1789:    function __proxyUrlCached(filename) {
1808:    function initCanvasMonitor() {
1915:    function clipTargetTime(clip, t) {
1918:    function ensureElMedia(el, clip) {
1927:    function initMultiPreview() {
1943:    function getAudioEl(trackId) {
1954:    function setElTime(el, target) {
1961:    function setPlaceholderText(title, sub) {
1969:    function trackPosAt(clip, t) {
1992:    function applyTrackingTransform(el, clip, t) {
2019:    function syncVideoToCurrentTime() {
2110:    function totalClipCount() {
2114:    function resetMonitorMedia() {
2126:    function syncAudioEl(el, clip, trackMuted) {
2139:    function updateOverlayBadge() {
2146:    function initTransport() {
2211:    function togglePlay() {
2221:    function waitSeeked(elements, timeoutMs = 450) {
2235:    async function startPlayback() {
2259:    function pausePlayback() {
2272:    function playbackLoop(timestamp) {
2306:    function autoScrollFollowPlayhead() {
2317:    function initTools() {
2429:    function setTool(toolName) {
2437:    function setZoom(newZoom) {
2462:    function initResizers() {
2512:    function initDockToggle() {
2524:    function sortedRegions() {
2527:    function findRegionById(id) {
2530:    function selectRegion(id) {
2546:    function addRegionFromPlayhead() {
2570:    function deleteSelectedRegion() {
2580:    function splitSelectedRegion() {
2603:    function previewSelectedRegion() {
2611:    function updateRegionToolbarUI() {
2621:    function initTimelineMarkers() {
2630:    function setMarker() {}
2631:    function nudgeMarker() {}
2632:    function updateMarkerRangeUI() { updateRegionToolbarUI(); }
2634:    function resolvePackSource(timelineT) {
2647:    function convertTimelineToSourceTime(clip, timelineT) {
2654:    function ensureRegionLane() {
2666:    function renderRegionsLane() {
2711:    function regionPointerDown(e, r, el) {
2758:    function splitClipAtPlayhead() {
2785:    function splitClipAtTimestamp(clipToSplit, splitTime) {
2828:    function deleteSelectedClip() {
2844:    function initInspector() {
3080:    function initClipperPanel() {
3623:    function pipForClip(c) {
3639:    function tvPreviewWanted() {
3659:    function coverBoxToCss(cW, cH, vidAR, box) {
3673:    function defaultAspectBox(vidAR, targetAspect) {
3684:    function tvpSetVideo(vid, clip, targetTime) {
3696:    function tvpLayoutVideo(vid, cont, box, vidAR) {
3710:    function chunkWordsForCues(words, maxN) {
3733:    function wordsToTimelineClips(words, tg, batchId, opts = {}) {
3813:    function currentCueClip() {
3838:    function collectRegionSubtitles(regs, outBases) {
3887:    function collectRegionTextItems(regs, outBases) {
3924:    function collectRegionFx(r) {
3968:    function hideServerPreviewFrame() {
3979:    function requestServerPreviewFrame() {
4040:    function makePreviewDraggable(el, clip, stage) {
4080:    function updateTvPreview() {
4428:    function allFxElements() {
4443:    function appendFxDivs(stage, t, z, stageW, stageH, overText) {
4486:    function tvFontCssFamily(f) {
4500:    function selectClipperSource(filename) {
4505:    function updateBadgeOverlay() {
4511:    function updateClipperUI() {
4516:    function initSubSettings() {
4571:    function reflectSubSettings() {
4613:    function renderSubtitlesCues(segments) {
4646:    function isHotWord(w) {
4652:    function updateLiveSubtitleOverlay() {
4798:    function applySubtitlesToTrackV3() {
4883:    function loadTemplates() {
4889:    function storeTemplates(list) {
4892:    function currentSettingsAsTemplate(name) {
4913:    function applyTemplateToClipper(tpl) {
4955:    function applyPreviewLook() {
4964:    function formatHuman(f) {
4970:    function renderTemplates() {
5012:    function initTemplates() {
5031:    function renderRegionsList() {
5034:    function renderPackClips() {
5100:    function renderReadyClips(clips) {
5172:    function initCutsTree() {
5193:    function fxLabel(c) {
5198:    function isFxTrack(t) {
5201:    function ensureFxTrack() {
5220:    function addFxTrack() {
5238:    function addMarkerAtPlayhead(withNote) {
5262:    function addRegionFromNearestMarker() {
5278:    function addEffectAtPlayhead(kind, color, overrides) {
5302:    function nearestCutTo(t) {
5322:    async function applyChannelPreset() {
5359:    async function saveChannelPreset() {
5392:    function addFxClip(kind, color) {
5430:    function addTextClip() {
5479:    function initSfxLibrary() {
5484:    function triggerFxSounds(prevT, t) {
5501:    function TV_FONT_OK(f) {
5506:    function pluralCuts(n) {
5512:    function renderCutsTree() {
5593:    function addTrackingManualKey() {
5609:    function initTrackingUI() {
5695:    function ensureTrackBoxEl() {
5705:    function fmtBox(b) {
5708:    function updateCropBoxUI() {
5718:    function pickTargetAspect(which) {
5724:    function pickSourceMedia() {
5730:    function enterPickMode(which) {
5761:    function defaultPickBox(vw, vh, targetAspect) {
5766:    function pickContentRect() {
5781:    function layoutPickBox() {
5791:    function exitPickMode(save) {
5807:    function initPickMode() {
5860:    function updateTrackingUI(clip) {
5891:    function findTrackingBaseClip(sel) {
5902:    async function runObjectTracking() {
5991:    function saveProject() {
6041:    function migrateClipsToTracks() {
6068:    function restoreProject() {
6133:    function updateEmptyTimelineHint() {
6192:    function studioSourceToTimeline(srcT) {
```
#### grep editor faceAnchor
```
1842:            faceAnchor(baseClip, t) {
```
#### grep editor CoreTimeMap
```
```
#### grep editor audioClock
```
```
#### grep editor masterClock
```
```
#### grep editor requestAnimationFrame
```
2256:        requestAnimationFrame(playbackLoop);
2304:        requestAnimationFrame(playbackLoop);
```
#### grep editor cropBox
```
41:            cropBox: null,              // область вебки {x,y,w,h} 0..1 (page-recording стримы)
1820:                    cropBox: state.clipper.cropBox,
3194:        const cropDrawBtn = document.getElementById("cropBoxDrawBtn");
3196:        const cropResetBtn = document.getElementById("cropBoxResetBtn");
3200:            state.clipper.cropBox = null;
3432:                crop_box: state.clipper.cropBox || null,
4001:                format: state.clipper.format, crop_box: state.clipper.cropBox || null,
4133:        const faceBox = state.clipper.cropBox || null;
4908:            crop_box: state.clipper.cropBox || null,
4929:        if (tpl.crop_box) state.clipper.cropBox = tpl.crop_box;
5336:            if (p.crop_box) state.clipper.cropBox = p.crop_box;
5348:            if (p.layout === "fullscreen" && !p.crop_box) state.clipper.cropBox = null;
5366:            cam_box: state.clipper.cropBox || null,
5369:            layout: state.clipper.cropBox ? "split" : "fullscreen",
5684:                    state.clipper.cropBox = { x: bx, y: by, w: bw, h: bh };
5709:        const status = document.getElementById("cropBoxStatus");
5711:            const f = fmtBox(state.clipper.cropBox);
5755:            const cur = which === "bg" ? state.clipper.bgBox : state.clipper.cropBox;
5795:            else state.clipper.cropBox = { ...b };
6028:                        cropBox: state.clipper.cropBox || null,
```
#### grep editor hooks\.
```
```
#### grep editor lensAmp\|kind === "lens"\|fxKind === "lens"
```
6233:                else if (kind === "lens") ov.fxPeak = f.amp != null ? Number(f.amp) : 0.18;
```
#### grep web for exporter/glPasses/timeMap
```
web/index.html:1348:    <script src="core/timeMap.js?v=1"></script>
web/index.html:1353:    <script src="core/render/lens.js?v=1"></script>
web/core/canvasMonitor.js:17:    const TM = root.CoreTimeMap;
web/core/render/exporter.js:1:/* Kick Clip Studio — web/core/render/exporter.js
web/core/render/effects.js:16:    const TM = (typeof CoreTimeMap !== "undefined") ? CoreTimeMap : require("../timeMap.js");
web/core/render/glPasses.js:1:/* Kick Clip Studio — web/core/render/glPasses.js
web/core/render/glPasses.js:3: * The shaders mirror the pure JS kernels (effects.js / lens.js) formula-by-
web/core/render/glPasses.js:286:    // Mirrors lens.js mapPoint(): wave and barrel act on the output uv; the CA
web/core/render/gltest.html:6:<script src="../timeMap.js"></script>
web/core/render/gltest.html:8:<script src="lens.js"></script>
web/core/render/gltest.html:9:<script src="glPasses.js"></script>
web/core/render/composer.js:14:    const TM = (typeof CoreTimeMap !== "undefined") ? CoreTimeMap : require("../timeMap.js");
web/core/render/composer.js:18:    const LENS = (typeof CoreLens !== "undefined") ? CoreLens : require("./lens.js");
web/core/render/lens.js:1:/* Kick Clip Studio — web/core/render/lens.js
web/core/render/lens.js:16:    const TM = (typeof CoreTimeMap !== "undefined") ? CoreTimeMap : require("../timeMap.js");
web/core/timeMap.js:1:/* Kick Clip Studio — web/core/timeMap.js
web/core/timeMap.js:7:    root.CoreTimeMap = mod;
web/core/composition.js:12:    const TM = (typeof CoreTimeMap !== "undefined") ? CoreTimeMap : require("./timeMap.js");
web/core/text/canvasText.js:22:    const TM = (typeof CoreTimeMap !== "undefined") ? CoreTimeMap : require("../timeMap.js");
```
#### index.html scripts
```
1240:    <script>
1348:    <script src="core/timeMap.js?v=1"></script>
1349:    <script src="core/geometry.js?v=1"></script>
1350:    <script src="core/lut3d.js?v=1"></script>
1351:    <script src="core/text/canvasText.js?v=1"></script>
1352:    <script src="core/webcodecs.js?v=1"></script>
1353:    <script src="core/render/lens.js?v=1"></script>
1354:    <script src="core/render/grade.js?v=1"></script>
1355:    <script src="core/render/effects.js?v=1"></script>
1356:    <script src="core/render/yuv.js?v=1"></script>
1357:    <script src="core/timeRemap.js"></script><!-- studio:timeremap-script -->
1358:    <script src="core/canvasMonitor.js?v=1"></script>
1359:    <script src="editor.js?v=12"></script>
1360:    <script src="app.js?v=12"></script>
1361:<script src="studio/moments.js"></script><!-- studio:moments-panel -->
1362:<script src="studio/overlay_export.js"></script><!-- studio:overlay-export -->
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
test_fallback_to_ass_when_overlay_fails (studio.tests.test_export_pipeline.ExportWrapperTest.test_fallback_to_ass_when_overlay_fails) ... [studio] canvas text layer failed (overlay ffmpeg rc=254: [concat @ 0x5629cc481680] Impossible to open '/tmp/tmpevizl2g1/ovjob/000000.png'
[in#1 @ 0x5629cc476dc0] Error opening input: No such file or directory
Error opening input file /tmp/tmpevizl2g1/ovjob/list.ffconcat.
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
Ran 45 tests in 10.984s

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

