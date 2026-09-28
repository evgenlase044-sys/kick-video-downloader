"""Anchored fixes for server.py @ d91ca83 (mechanism: studio/patching.py)."""
from studio.patching import Patch

MSG404 = "            raise HTTPException(status_code=404, detail=f\"Медиафайл {base_name} не найден\")\n"

SERVER_PATCHES = [
    Patch(id="hooks-import",
          old="from downloader import KickDownloader, sanitize_filename\n",
          new=("from downloader import KickDownloader, sanitize_filename\n"
               "import studio.server_hooks as _studio  # studio:hooks-import\n"),
          marker="studio:hooks-import"),
    # §1 /api/progress: **snap -> NameError
    Patch(id="progress-nameerror",
          old=("                data = dict(download_state)\n"
               "            yield f\"data: {json.dumps({'type': 'progress', **snap}"),
          new=("                data = dict(download_state)\n"
               "            # studio:progress-nameerror (was **snap -> NameError)\n"
               "            yield f\"data: {json.dumps({'type': 'progress', **data}"),
          marker="studio:progress-nameerror"),
    # §1 cookies/UA for playlist + segments (403 from Cloudflare)
    Patch(id="cookies-range",
          old="            detailed, _ = calculator.fetch_playlist_segments_detailed(req.playlist_url)\n",
          new=("            detailed, _ = _studio.size_calculator(extractor, calculator)"
               ".fetch_playlist_segments_detailed(req.playlist_url)  # studio:cookies-range\n"),
          marker="studio:cookies-range"),
    Patch(id="cookies-full",
          old="            segments, _ = calculator.fetch_playlist_segments(req.playlist_url)\n",
          new=("            segments, _ = _studio.size_calculator(extractor, calculator)"
               ".fetch_playlist_segments(req.playlist_url)  # studio:cookies-full\n"),
          marker="studio:cookies-full"),
    Patch(id="cookies-download",
          old="    downloader = KickDownloader(output_dir=DOWNLOADS_DIR)\n",
          new=("    downloader = KickDownloader(output_dir=DOWNLOADS_DIR, "
               "headers=_studio.download_headers(extractor))  # studio:cookies-download\n"),
          marker="studio:cookies-download"),
    # §3 SSRF
    Patch(id="ssrf-guard",
          old="    # 1. Resolve segment list: whole VOD or [start_time, end_time) slice\n",
          new=("    _studio.validate_download_request(req)  # studio:ssrf-guard\n"
               "    # 1. Resolve segment list: whole VOD or [start_time, end_time) slice\n"),
          marker="studio:ssrf-guard"),
    Patch(id="ssrf-remember",
          old="    return {\n        \"url\": video_info[\"url\"],\n",
          new=("    _studio.remember_playlists(qualities_with_size)  # studio:ssrf-remember\n"
               "    return {\n        \"url\": video_info[\"url\"],\n"),
          marker="studio:ssrf-remember"),
    # §3 disk peak
    Patch(id="disk-peak",
          old=("    space_check = disk_manager.check_space(req.required_bytes)\n"
               "    if not space_check[\"is_enough\"]:\n"),
          new=("    space_check = disk_manager.check_space(req.required_bytes, "
               "peak_factor=_studio.DOWNLOAD_PEAK_FACTOR)  # studio:disk-peak\n"
               "    if not space_check[\"is_enough\"]:\n"),
          marker="studio:disk-peak"),
    # §3 exact fps
    Patch(id="fps-exact-init", group="fps",
          old=("    fps = 60\n    try:\n        cmd = [\n"
               "            \"ffprobe\", \"-v\", \"quiet\", \"-print_format\", \"json\",\n"),
          new=("    fps = 60\n    fps_exact = 60.0  # studio:fps-exact-init\n    fps_rational = \"60/1\"\n"
               "    try:\n        cmd = [\n"
               "            \"ffprobe\", \"-v\", \"quiet\", \"-print_format\", \"json\",\n"),
          marker="studio:fps-exact-init"),
    Patch(id="fps-exact-probe", group="fps",
          old=("                    r_frame_rate = stream.get(\"r_frame_rate\", \"60/1\")\n"
               "                    if \"/\" in r_frame_rate:\n"
               "                        num, den = r_frame_rate.split(\"/\")\n"
               "                        if int(den) > 0:\n"
               "                            fps = round(int(num) / int(den))\n"),
          new=("                    r_frame_rate = stream.get(\"r_frame_rate\", \"60/1\")\n"
               "                    fps_exact, fps_rational = _studio.stream_fps(stream)  # studio:fps-exact-probe\n"
               "                    fps = int(round(fps_exact))\n"),
          marker="studio:fps-exact-probe"),
    Patch(id="fps-exact-return", group="fps",
          old="        \"height\": height,\n        \"fps\": fps\n    }\n",
          new=("        \"height\": height,\n        \"fps\": fps,\n"
               "        \"fps_exact\": fps_exact,  # studio:fps-exact-return\n"
               "        \"fps_rational\": fps_rational,\n    }\n"),
          marker="studio:fps-exact-return"),
    # §3 ASR
    Patch(id="asr-tempid", old="    temp_id = int(time.time() * 1000)\n",
          new="    temp_id = _studio.unique_id()  # studio:asr-tempid\n", marker="studio:asr-tempid"),
    Patch(id="asr-shortwords",
          old=("        clean_words = [w for w in clean_words if (w[\"end\"] - w[\"start\"]) >= 0.02 "
               "or w[\"end\"] > w[\"start\"]]\n"),
          new=("        clean_words = _studio.enforce_min_word_duration(clean_words, 2.0 / 60.0)"
               "  # studio:asr-shortwords\n"),
          marker="studio:asr-shortwords"),
    # §3 arbitrary absolute paths
    Patch(id="no-abs-paths-file", count=2,
          old=("    if not os.path.exists(file_path):\n"
               "        if os.path.exists(req.filename):\n"
               "            file_path = req.filename\n"
               "        else:\n" + MSG404),
          new=("    if not os.path.exists(file_path):\n"
               "        # studio:no-abs-paths-file (only files inside downloads/)\n" + MSG404[4:]),
          marker="studio:no-abs-paths-file"),
    Patch(id="no-abs-paths-src", count=2,
          old=("    if not os.path.exists(src):\n"
               "        if os.path.exists(req.filename):\n"
               "            src = req.filename\n"
               "        else:\n" + MSG404),
          new=("    if not os.path.exists(src):\n"
               "        # studio:no-abs-paths-src (only files inside downloads/)\n" + MSG404[4:]),
          marker="studio:no-abs-paths-src"),
    Patch(id="import-guard", old="    src = req.path.strip().strip('\"').strip(\"'\")\n",
          new="    src = _studio.check_import_path(req.path)  # studio:import-guard\n",
          marker="studio:import-guard"),
    # §1 missing SFX keys for hotkeys R/L/B
    Patch(id="sfx-aliases", old="    \"coin\": \"coin_win.mp3\",\n}\n",
          new=("    \"coin\": \"coin_win.mp3\",\n    # studio:sfx-aliases\n"
               "    \"whoosh_magic\": \"whoosh_magic.mp3\",\n    \"hit_small\": \"hit_small.mp3\",\n"
               "    \"riser\": \"riser.mp3\",\n}\n"),
          marker="studio:sfx-aliases"),
    Patch(id="sfx-labels", old="    \"levelup\": \"Левел-ап\", \"coin\": \"Монетка\",\n}\n",
          new=("    \"levelup\": \"Левел-ап\", \"coin\": \"Монетка\",\n"
               "    \"whoosh_magic\": \"Магия-спаркл\", \"hit_small\": \"Удар\", "
               "\"riser\": \"Райзер (нарастание)\",  # studio:sfx-labels\n}\n"),
          marker="studio:sfx-labels"),
    # ExportQueueRequest used ExportClipItem before definition (NameError on py<=3.13)
    Patch(id="queue-forward-ref", group="queue",
          old="class ExportQueueRequest(BaseModel):\n    clips: List[ExportClipItem]\n",
          new=("class ExportQueueRequest(BaseModel):\n"
               "    # studio:queue-forward-ref (ExportClipItem is defined further below)\n"
               "    clips: List[Dict[str, Any]]\n"),
          marker="studio:queue-forward-ref"),
    Patch(id="queue-parse", group="queue",
          old=("        for i, clip in enumerate(req.clips):\n"
               "            _export_queue.append({\"index\": start + i, \"clip\": clip,\n"),
          new=("        for i, clip in enumerate(_studio.parse_queue_clips(req.clips, ExportClipItem)):"
               "  # studio:queue-parse\n"
               "            _export_queue.append({\"index\": start + i, \"clip\": clip,\n"),
          marker="studio:queue-parse"),
    # §3 WS render rewrite
    Patch(id="ws-render",
          start="@app.websocket(\"/ws/render/{job_id}\")\n",
          end="PRESETS_DIR = os.path.join(BASE_DIR, \"presets\", \"channels\")",
          new=("@app.websocket(\"/ws/render/{job_id}\")\n"
               "async def ws_render(ws: WebSocket, job_id: str):\n"
               "    \"\"\"PLAN §17.2 raw-frame render. studio:ws-render - see studio/render_ws.py.\"\"\"\n"
               "    await _studio.ws_render(ws, job_id, exported_dir=EXPORTED_PACKS_DIR,\n"
               "                            downloads_dir=DOWNLOADS_DIR)\n\n\n"
               "# Channel presets: manual webcam/content/layout/style per channel (PLAN §9.4)\n"),
          marker="studio:ws-render"),
    # §2 ramp/freeze were silently skipped in export
    Patch(id="fx-timeremap",
          old=("            print(f\"[fx] kind={fx.kind} skipped in transition path (needs renderer)\")\n"
               "            continue\n"),
          new=("            # studio:fx-timeremap - rendered in the filtergraph (video only)\n"
               "            _tr_parts, curr_v = _studio.fx_time_remap(fx.kind, curr_v, "
               "f\"{tag_prefix}v{fi}\", s0, e0)\n"
               "            filter_parts.extend(_tr_parts)\n"),
          marker="studio:fx-timeremap"),
    # §3 whip out of frame
    Patch(id="whip-clamp", group="whip",
          old="            shift = f\"{dirn}*0.35*iw*{ease}\"\n",
          new="            shift = f\"{dirn}*0.25*iw*{ease}\"  # studio:whip-clamp\n",
          marker="studio:whip-clamp"),
    Patch(id="whip-clamp-x", group="whip",
          old="                f\"crop=w=iw/2:h=ih:x='(iw-iw/2)/2+({shift})':y=0,\"\n",
          new=("                f\"crop=w=iw/2:h=ih:x='max(0{BS},min(iw/2{BS},(iw-iw/2)/2+({shift})))':y=0,\""
               "  # studio:whip-clamp-x\n"),
          marker="studio:whip-clamp-x"),
    # §3 dead duplicate ASS generator (only if nothing calls it)
    Patch(id="dead-ass-generator", required=False,
          start="def generate_ass_subtitle_content(", end="TV_TEMPLATES_CONFIG = {",
          guard=lambda src: src.count("generate_ass_subtitle_content(") == 1,
          new=("# studio:dead-ass-removed - legacy generate_ass_subtitle_content() had no callers.\n\n"
               "# TV templates: viral subtitle styles + AE-grade color + white flash cuts\n"),
          marker="studio:dead-ass-removed"),
    Patch(id="version-mtime",
          old="        mtime = int(os.path.getmtime(os.path.join(BASE_DIR, \"server.py\")) * 1000)\n",
          new="        mtime = _studio.code_mtime_ms(BASE_DIR)  # studio:version-mtime\n",
          marker="studio:version-mtime"),
]
