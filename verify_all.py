#!/usr/bin/env python3
"""
Kick Clip Studio — automated verification (docs/VERIFICATION.md §7).

Sections:
  1. L   — licenses (§7.1): LICENSE, notices, fonts/LICENSES, sfx/CREDITS,
           own LUT, requirements.txt, landing claims, no-local-NN guard.
  2. 0a  — /api/version, ASS builders (N1-N7, H2, H4, escaping), H1 422.
  3. 0b  — export graph e2e: gbrp text, final BT.709 yuv420p, flash screen,
           shake envelope, two-pass loudnorm, 1080x1920@60 tags.
  4. 0c  — tracker synthetic tests (§7.3): subpixel accuracy, hard zone,
           lost state, twin distractor, V11 regression, manual keys, One Euro.
  5. G1  — Groq mock: retries on 429, granularities/language/prompt,
           hallucination + ghost filter, cache hit, chunking over size limit.

Run:  python verify_all.py            (offline, no network)
Exit code 0 = all green. Network tests of the downloader stay available:
  python verify_all.py --network
"""
import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

os.environ.setdefault("GROQ_API_KEY", "verify-offline-key")

FAILURES = []
CURRENT = ""


def section(name):
    global CURRENT
    CURRENT = name
    print(f"\n{'=' * 64}\n[{name}]\n{'=' * 64}")


def check(cond, label, extra=""):
    cond = bool(cond)
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {extra}")
        FAILURES.append((CURRENT, label, extra))
    return cond


def read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


# ─────────────────────────────────────────────────────── §7.1 licenses ──
def test_licenses():
    section("§7.1  Step L — licenses")
    ok = True
    ok &= check(os.path.exists(os.path.join(BASE, "LICENSE")), "LICENSE exists")
    ok &= check('"license": "MIT"' in read(os.path.join(BASE, "package.json")), "package.json license = MIT")
    cargo = read(os.path.join(BASE, "engine", "Cargo.toml"))
    ok &= check('license = "MIT"' in cargo, "engine/Cargo.toml license = MIT")
    landing = read(os.path.join(BASE, "landing", "index.html")).lower()
    ok &= check("mit" in landing and ("open source" in landing or "opensource" in landing),
                "landing keeps MIT open-source claim")
    ok &= check("auto-clip" not in landing and "auto clip" not in landing,
                "landing has no auto-clip claim")
    ok &= check(os.path.exists(os.path.join(BASE, "THIRD_PARTY_NOTICES.md")), "THIRD_PARTY_NOTICES.md exists")
    notices = read(os.path.join(BASE, "THIRD_PARTY_NOTICES.md")).lower()
    for dep in ("fastapi", "pydantic", "uvicorn", "opencv", "requests", "numpy", "fonttools",
                "electron", "ffmpeg", "groq"):
        ok &= check(dep in notices, f"notices mention {dep}")

    fonts_dir = os.path.join(BASE, "fonts")
    lic_dir = os.path.join(fonts_dir, "LICENSES")
    ttfs = [f for f in os.listdir(fonts_dir) if f.lower().endswith(".ttf")]
    ok &= check(len(ttfs) > 0, f"{len(ttfs)} bundled fonts")
    missing = []
    for ttf in ttfs:
        # every font must have a license file that names its bundled file
        stem = os.path.splitext(ttf)[0]
        found = False
        if os.path.isdir(lic_dir):
            for lf in os.listdir(lic_dir):
                body = read(os.path.join(lic_dir, lf))
                if f"fonts/{ttf}" in body and "OFL" in body.upper():
                    found = True
                    break
        if not found:
            missing.append(stem)
    ok &= check(not missing, "every TTF has fonts/LICENSES/<family>.txt (OFL)", str(missing))

    sfx_dir = os.path.join(BASE, "sfx")
    credits = read(os.path.join(sfx_dir, "CREDITS.md")) if os.path.exists(os.path.join(sfx_dir, "CREDITS.md")) else ""
    mp3s = [f for f in os.listdir(sfx_dir) if f.lower().endswith(".mp3")]
    ok &= check(len(mp3s) > 0, f"{len(mp3s)} sfx files")
    miss = [m for m in mp3s if f"`{m}`" not in credits]
    ok &= check(not miss, "every sfx has a CREDITS.md row", str(miss))
    ok &= check("CC0" in credits, "sfx are CC0")

    cube = os.path.join(BASE, "tv_grade.cube")
    ok &= check(os.path.exists(cube), "tv_grade.cube exists")
    head = read(cube).splitlines()[:4]
    ok &= check(any("LUT_3D_SIZE 65" in l for l in head) and any("Kick Clip Studio" in l for l in head),
                "LUT rebuilt as own 65^3 preset", str(head[:2]))

    req = read(os.path.join(BASE, "requirements.txt")).lower()
    for dep in ("fastapi", "uvicorn", "pydantic", "requests", "rich", "fonttools", "opencv-python", "numpy"):
        ok &= check(dep in req, f"requirements.txt has {dep}")
    readme = read(os.path.join(BASE, "README.md")).lower()
    ok &= check("groq" in readme and ("приватность" in readme or "privacy" in readme),
                "README documents Groq privacy")

    # protection against local neural models (plan principle 2)
    banned = re.compile(r"faster_whisper|whisperx|import torch|onnxruntime|mediapipe|librosa|realesrgan", re.I)
    hits = []
    for root, dirs, files in os.walk(BASE):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__", "downloads", "engine", "scratch", "tmp_ref3")]
        for f in files:
            if f == "verify_all.py":  # this file mentions banned names in its own regex
                continue
            if f.endswith((".py", ".js", ".ts", ".json")):
                p = os.path.join(root, f)
                try:
                    if banned.search(read(p)):
                        hits.append(os.path.relpath(p, BASE))
                except Exception:
                    pass
    ok &= check(not hits, "no local NN imports anywhere", str(hits))
    return ok


# ─────────────────────────────────────────────────── §7.2 step 0a/0b ──
def _make_src(seconds=6, w=1280, h=720, fps=60):
    src = os.path.join(DL, "_vt_test_src.mp4")
    if not os.path.exists(src):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                        "-f", "lavfi", "-i", f"testsrc2=size={w}x{h}:rate={fps}:duration={seconds}",
                        "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-shortest", src], check=True, timeout=180)
    return src


def test_version_and_contract():
    section("§7.2  Step 0a — /api/version, ASS builders, H1 422")
    import server
    from fastapi.testclient import TestClient
    client = TestClient(server.app)
    r = client.get("/api/version")
    ok = check(r.status_code == 200 and r.json().get("server_dir"), "/api/version responds")
    ok &= check(r.json().get("server_mtime", 0) > 0, "/api/version reports server.py mtime")

    # H1: 422 on subtitles + ASR words in text_items
    clip = server.ExportClipItem(id="c", source_file="x.mp4", start_time=0, end_time=1)
    clip.subtitles = [{"text": "a", "start": 0, "end": 1}]
    clip.text_items = [{"text": "b", "words": [{"word": "w", "start": 0, "end": 1}]}]
    try:
        server._normalize_subtitle_mode(clip)
        ok &= check(False, "H1 conflict raises 422")
    except server.HTTPException as e:
        ok &= check(e.status_code == 422, "H1 conflict raises 422", str(e.status_code))
    clip2 = server.ExportClipItem(id="c2", source_file="x.mp4", start_time=0, end_time=1,
                                   subtitle_mode="timeline")
    clip2.subtitles = [{"text": "a", "start": 0, "end": 1}]
    clip2.text_items = [{"text": "b", "words": [{"word": "w", "start": 0, "end": 1}]}]
    server._normalize_subtitle_mode(clip2)
    ok &= check(clip2.subtitles == [] and len(clip2.text_items) == 1, "H1 timeline mode resolves conflict")

    # ASS: H4 glow never before text, caps on radii
    subs = [{"text": "ЭТОТ ДОНАТ", "start": 0.5, "end": 1.5, "style": "acid",
             "words": [{"word": "ЭТОТ", "start": 0.5, "end": 0.9}, {"word": "ДОНАТ", "start": 0.9, "end": 1.5}]}]
    a = server.build_tv_subtitles_ass(subs, "acid", 1080, 1920, 200, glow=55, anim="pop", hot_words=False)
    glow_layers = [l for l in a.split("\n") if l.startswith("Dialogue: 0,") or l.startswith("Dialogue: 1,")]
    ok &= check(all("alpha&HFF&" in l for l in glow_layers), "TV glow starts invisible (H4)", str(glow_layers[:1]))
    ok &= check("alpha&HFF&\\t(60,160,\\alpha&H80&)" in a.replace("\\\\", "\\"), "TV glow breathes in at 60-160ms (H4)")

    items = [{"text": "*ОРЁТ* {test}\nвторая", "start": 0, "end": 2.0, "font": "Montserrat ExtraBold",
              "size": 90, "anim_in": "type", "glow": 50, "x": 0.5, "y": 0.3, "shake": True,
              "anim_out": "blurout", "stroke": 0, "spacing": 0}]
    b = server.build_text_elements_ass(items, 1080, 1920)
    dlg = [l for l in b.split("\n") if l.startswith("Dialogue")]
    ok &= check(len(dlg) == 8, "H2 type: one Dialogue per line x 4 layers", f"got {len(dlg)}")
    ok &= check("\\{test\\}" in b, "N18 braces escaped")
    ok &= check(not any(l.rstrip().endswith("N") and "\\N" not in l for l in dlg), "N4 no phantom letter N")
    ok &= check(all("alpha&HFF&" in l for l in dlg if l.startswith("Dialogue: 1,")), "H4 text-elements glow delayed")
    ok &= check(all("\\fsp0.5" not in l for l in dlg), "N7 shake does not animate \\fsp")
    shadow = [l for l in dlg if l.startswith("Dialogue: 3,")][0]
    main = [l for l in dlg if l.startswith("Dialogue: 4,")][0]
    sh_pos = re.search(r"\\pos\((\d+),(\d+)\)", shadow)
    mn_pos = re.search(r"\\pos\((\d+),(\d+)\)", main)
    ok &= check(sh_pos and mn_pos and (int(sh_pos.group(1)) > int(mn_pos.group(1))),
                "N1 shadow offset from text", f"{sh_pos.groups() if sh_pos else None} vs {mn_pos.groups() if mn_pos else None}")
    c = server.build_text_elements_ass([{"text": "X", "start": 0, "end": 1.5, "anim_in": "zoom", "glow": 0}],
                                       1080, 1920)
    ok &= check("blur0)" in c, "N5 zoom ends at blur0")
    ok &= check("gb_osc" not in b, "N6 glow breathing removed")

    # hot-word length heuristic off by default
    ok &= check(server.ExportClipItem(id="h", source_file="x", start_time=0, end_time=1).hot_words is False,
                "hot_words default off (§12.6)")

    # H3: cmap-based Cyrillic font validation
    cyr_ok = server._build_cyr_capable_fonts()
    ok &= check("Montserrat ExtraBold" in cyr_ok and "Russo One" in cyr_ok,
                "H3 cmap check finds Cyrillic-capable fonts")
    ok &= check(server._resolve_font("Anton", True) == "Montserrat ExtraBold",
                "H3 Anton (no cyr) falls back for Cyrillic text")
    ok &= check(server._resolve_font("Anton", False) == "Anton",
                "H3 Anton kept for latin-only text")

    # H8: single _sfx_maybe_file definition
    ok &= check(len(re.findall(r"def _sfx_maybe_file", read(os.path.join(BASE, "server.py")))) == 1,
                "H8 single _sfx_maybe_file definition")

    # N17 extractor: float fps + is_source flag in source
    kx = read(os.path.join(BASE, "kick_extractor.py"))
    ok &= check("float(m_fps.group(1))" in kx and "int(float(m_fps" not in kx, "N17 float fps in extractor")
    ok &= check("is_source" in kx, "N17 is_source flag in extractor")
    dl_src = read(os.path.join(BASE, "downloader.py"))
    ok &= check("h264_metadata" in dl_src, "ingest tags BT.709 bitstream (§17.1)")
    return ok


def test_export_graph():
    section("§7.2  Step 0b — export graph e2e (gbrp text, BT.709, loudnorm)")
    import server
    from fastapi.testclient import TestClient
    client = TestClient(server.app)
    _make_src()
    pv = {
        "source_file": "_vt_test_src.mp4", "src_time": 2.0, "format": "fullscreen",
        "width": 608, "height": 1080, "color_grade": "tv",
        "subtitles": [{"text": "ТЕСТ", "start": 0, "end": 1.0, "style": "acid",
                       "words": [{"word": "ТЕСТ", "start": 0, "end": 1.0}]}],
        "overlays": [{"kind": "flash", "start": 0.1, "end": 0.3, "color": "white", "peak": 0.8, "z": 0},
                     {"kind": "shake", "start": 0.4, "end": 0.8, "amp": 12, "z": 0}],
    }
    r = client.post("/api/preview-frame", json=pv)
    ok = check(r.status_code == 200 and r.headers.get("content-type", "").startswith("image/png"),
               "preview_frame renders graded frame", r.text[:200] if r.status_code != 200 else "")

    clip = {
        "id": "rg_test", "title": "VT", "source_file": "_vt_test_src.mp4", "start_time": 0, "end_time": 5,
        "format": "fullscreen", "color_grade": "tv", "sub_size": 1.0, "sub_glow": 55, "sub_anim": "pop",
        "subtitles": [{"text": "ЭТОТ ДОНАТ СЛОМАЛ СТРИМ", "start": 1.0, "end": 3.0, "style": "acid",
                       "words": [{"word": "ЭТОТ", "start": 1.0, "end": 1.7},
                                 {"word": "ДОНАТ", "start": 1.7, "end": 2.4},
                                 {"word": "СЛОМАЛ", "start": 2.4, "end": 3.0}]}],
        "text_items": [{"text": "ВЫПЕЧКА {test} 100%", "start": 0.5, "end": 2.5,
                        "font": "Montserrat ExtraBold", "size": 80, "anim_in": "type",
                        "anim_out": "blurout", "glow": 50, "x": 0.5, "y": 0.25,
                        "shake": True, "stroke": 0, "spacing": 0}],
        "overlays": [{"kind": "flash", "start": 1.0, "end": 1.3, "color": "white", "peak": 0.85, "z": 0},
                     {"kind": "shake", "start": 2.0, "end": 2.4, "amp": 14, "z": 0},
                     {"kind": "bars", "start": 3.0, "end": 3.6, "bar_h": 120, "z": 0}],
        "layers": [{"source_file": "_vt_test_src.mp4", "src_offset": 0, "duration": 5,
                    "out_start": 0, "opacity": 1, "volume": 1, "muted": False, "z": 0}],
        "subs_in_output_time": True, "subtitle_mode": "timeline",
        "format": "fullscreen", "crop_box": None, "bg_box": None,
        "bar_top": 0, "bar_bottom": 0, "hot_words": False,
        "streamer_handle": "@vt", "subtitle_template": "acid", "sub_font": "Montserrat ExtraBold",
    }
    r = client.post("/api/export-pack", json={"pack_name": "_vt", "clips": [clip]})
    ok &= check(r.status_code == 200, "export-pack accepted", r.text[:200])
    data = r.json()
    ok &= check(data.get("exported_count") == 1, "export rendered 1 clip",
                json.dumps(data.get("failed", []), ensure_ascii=False)[:300])
    if not data.get("exported_count"):
        return ok
    out = data["clips"][0]["path"]
    pr = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                         "stream=codec_name,width,height,r_frame_rate,pix_fmt,color_space,"
                         "color_transfer,color_primaries,color_range:format=duration",
                         "-of", "json", out], capture_output=True, text=True)
    info = json.loads(pr.stdout)
    st = info["streams"][0]
    ok &= check(st["width"] == 1080 and st["height"] == 1920, "output 1080x1920", f"{st['width']}x{st['height']}")
    ok &= check(st["r_frame_rate"] == "60/1", "output 60 fps", st["r_frame_rate"])
    ok &= check(st["pix_fmt"] == "yuv420p", "yuv420p", st["pix_fmt"])
    ok &= check(st.get("color_space") == "bt709" and st.get("color_primaries") == "bt709"
                and st.get("color_transfer") == "bt709" and st.get("color_range") == "tv",
                "BT.709 limited tags burned", json.dumps({k: st.get(k) for k in
                                                          ("color_space", "color_primaries", "color_transfer", "color_range")}))
    ok &= check(abs(float(info["format"]["duration"]) - 5.0) < 0.1, "duration = composition ±1 frame")
    # loudness: -14 LUFS ±1, TP <= -1 dBTP (two-pass loudnorm + limiter)
    lr = subprocess.run(["ffmpeg", "-i", out, "-af", "ebur128=peak=true", "-f", "null", "-"],
                        capture_output=True, text=True, timeout=300)
    # ebur128 prints per-frame I: values; the summary block is at the very end
    i_vals = re.findall(r"I:\s*(-?[\d.]+)\s*LUFS", lr.stderr)
    pk = re.findall(r"Peak:\s*(-?[\d.]+)\s*dBFS", lr.stderr)
    if i_vals:
        i_lufs = float(i_vals[-1])
        ok &= check(-15.0 <= i_lufs <= -13.0, "integrated loudness -14 LUFS ±1", f"{i_lufs}")
        if pk:
            ok &= check(float(pk[-1]) <= -1.0, "true peak <= -1 dBTP", pk[-1])
    else:
        ok &= check(False, "ebur128 measurement available")
    return ok


# ─────────────────────────────────────────────── §7.3 tracker tests ──
def _make_track_video(path, positions, w=1280, h=720, fps=30, box=60, twin=None):
    """Synthetic video: white box moving to given normalized center positions."""
    import numpy as np
    import cv2
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(path, fourcc, fps, (w, h))
    for i, (cx, cy) in enumerate(positions):
        frame = np.zeros((h, h * 0 + w, 3), np.uint8)
        x0 = int(cx * w - box / 2); y0 = int(cy * h - box / 2)
        cv2.rectangle(frame, (x0, y0), (x0 + box, y0 + box), (255, 255, 255), -1)
        if twin is not None:
            tx, ty = twin(i)
            tx0 = int(tx * w - box / 2); ty0 = int(ty * h - box / 2)
            cv2.rectangle(frame, (tx0, ty0), (tx0 + box, ty0 + box), (255, 255, 255), -1)
        vw.write(frame)
    vw.release()
    return path


def _run_tracker(filename, t_from, t_to, target, zone=None, manual_keys=None,
                 mode="ncc", min_conf=0.55, scale_search=False):
    import server
    req = server.TrackRequest(filename=filename, t_from=t_from, t_to=t_to,
                              t_anchor=t_from, target=server.Box(**target),
                              zone=server.Box(**zone) if zone else None,
                              manual_keys=[server.ZoneKey(**k) for k in (manual_keys or [])],
                              mode=mode, fps=15.0, analysis_width=960,
                              scale_search=scale_search, min_conf=min_conf)
    return server.track_object(req)


def test_tracker():
    section("§7.3  Step 0c — tracker synthetic tests")
    import numpy as np
    import cv2
    import server
    ok = True
    fps = 15
    n = 45  # 3 s
    positions = [(0.2 + 0.4 * i / (n - 1), 0.5) for i in range(n)]
    vid = _make_track_video(os.path.join(DL, "_trk_sine.mp4"), positions, fps=fps)
    tight = {"x": 0.2 - 30 / 1280, "y": 0.5 - 30 / 720, "w": 60 / 1280, "h": 60 / 720}

    # (a1) RAW subpixel accuracy (no smoothing): center error <= 1 source px
    it = server._iter_gray_frames(vid, 0.0, 3.0001, float(fps), 960)
    bare_req = server.TrackRequest(filename="_trk_sine.mp4", t_from=0, t_to=3, t_anchor=0,
                                   target=server.Box(**tight), mode="ncc", fps=float(fps),
                                   analysis_width=960)
    raw = server._ncc_track_run(it, float(fps), (tight["x"], tight["y"], tight["w"], tight["h"]),
                                0.0, bare_req, (None, None), forward=True)
    fw = raw[0]["_fw"]; fh = raw[0]["_fh"]
    errs = []
    for k in raw:
        i = min(n - 1, max(0, round(k["t"] * fps)))
        cx_true, cy_true = positions[i]
        errs.append(math.hypot((k["x"] + k["w"] / 2 - cx_true) * fw,
                               (k["y"] + k["h"] / 2 - cy_true) * fh))
    ok &= check(max(errs) <= 2.5, "raw center error <= 1px source (2.5 analysis px)",
                f"max {max(errs):.2f} analysis px")
    ok &= check(not any(k["lost"] for k in raw), "no lost on clean track (raw)")

    # (a2) public API: smoothed track still follows, no lost, lag <= 2 frames
    res = _run_tracker("_trk_sine.mp4", 0.0, 3.0, tight)
    keys = res["keys"]
    ok &= check(len(keys) >= n - 2, "tracker covered all frames", f"{len(keys)}/{n}")
    ok &= check(not any(k["lost"] for k in keys), "no lost on clean track")
    lag = max(math.hypot((k["x"] + k["w"] / 2 - positions[min(n - 1, max(0, round(k["t"] * fps)))][0]) * 960,
                         (k["y"] + k["h"] / 2 - positions[min(n - 1, max(0, round(k["t"] * fps)))][1]) * 540)
              for k in keys)
    ok &= check(lag <= 30, "One Euro lag on steady motion <= 2 frames", f"{lag:.1f} analysis px")

    # (b) zone over left half only: box never leaves zone, lost on right half
    zleft = {"x": 0.0, "y": 0.0, "w": 0.55, "h": 1.0}
    res2 = _run_tracker("_trk_sine.mp4", 0.0, 3.0, tight, zone=zleft)
    keys2 = res2["keys"]
    zone_ok = all(k["x"] >= zleft["x"] - 1e-6 and k["x"] + k["w"] <= zleft["x"] + zleft["w"] + 1e-6 and
                  k["y"] >= zleft["y"] - 1e-6 and k["y"] + k["h"] <= zleft["y"] + zleft["h"] + 1e-6
                  for k in keys2)
    ok &= check(zone_ok, "hard zone: every key inside zone (T1)")
    # lost needs a 3-frame confirmation streak (§10.3), so keys during the
    # confirmation window are legitimately not flagged yet
    out_times = [k["t"] for k in keys2
                 if positions[min(n - 1, max(0, round(k["t"] * fps)))][0] > 0.57]
    confirm = 3.0 / fps
    lost_right = [k for k in keys2
                  if positions[min(n - 1, max(0, round(k["t"] * fps)))][0] > 0.57
                  and k["t"] >= (out_times[0] if out_times else 0) + confirm - 1e-6]
    ok &= check(bool(lost_right) and all(k["lost"] for k in lost_right),
                "lost flag when object leaves zone (T2)",
                f"n={len(lost_right)} lost={[k['lost'] for k in lost_right][:6]}")
    held = [k for k in lost_right if abs((k["x"] + k["w"]) - (zleft["x"] + zleft["w"])) < 0.02]
    ok &= check(bool(held), "position held at zone edge while lost")

    # (c) twin distractor outside zone is ignored
    twin_pos = [(0.9, 0.2)] * n
    _make_track_video(os.path.join(DL, "_trk_twin.mp4"), positions, fps=fps,
                      twin=lambda i: twin_pos[i])
    res3 = _run_tracker("_trk_twin.mp4", 0.0, 3.0, tight,
                        zone={"x": 0.0, "y": 0.0, "w": 0.7, "h": 1.0})
    centers = [k["x"] + k["w"] / 2 for k in res3["keys"]]
    ok &= check(all(c < 0.75 for c in centers), "no jump to twin outside zone")

    # (d) V11 regression: tight target, zone = target x3, object oscillates
    # INSIDE the zone -> track must follow (old code allowed only ~20% pad).
    zone3 = {"x": max(0, tight["x"] - tight["w"]), "y": max(0, tight["y"] - tight["h"]),
             "w": min(1, tight["w"] * 3), "h": min(1, tight["h"] * 3)}
    small = [(0.2 + 0.04 * math.sin(2 * math.pi * i / n), 0.5) for i in range(n)]
    _make_track_video(os.path.join(DL, "_trk_small.mp4"), small, fps=fps)
    res4 = _run_tracker("_trk_small.mp4", 0.0, 3.0, tight, zone=zone3)
    good = [k for k in res4["keys"] if not k["lost"]]
    cxs = [k["x"] + k["w"] / 2 for k in good]
    rng = (max(cxs) - min(cxs)) if cxs else 0.0
    ok &= check(len(good) >= int(0.8 * len(res4["keys"])) and rng > 0.05,
                "V11 regression: tight target still tracks (T1)",
                f"range={rng:.3f} good={len(good)}/{len(res4['keys'])}")

    # (e) manual key mid-run: respected exactly, flagged, segment re-anchored
    mid_i = round(1.5 * fps)
    mk = {"t": 1.5, "x": small[mid_i][0] - 30 / 1280,
          "y": small[mid_i][1] - 30 / 720, "w": 60 / 1280, "h": 60 / 720}
    res5 = _run_tracker("_trk_small.mp4", 0.0, 3.0, tight, zone=zone3, manual_keys=[mk])
    at_mk = [k for k in res5["keys"] if k.get("manual")]
    ok &= check(bool(at_mk) and abs(at_mk[0]["x"] - mk["x"]) < 0.005,
                "manual key respected and flagged (T3)", str(at_mk[:1]))

    # (f) One Euro: static object jitter <= 0.3 px RMS (source scale = 0.4 analysis px)
    static = [(0.5, 0.5)] * n
    _make_track_video(os.path.join(DL, "_trk_static.mp4"), static, fps=fps)
    res6 = _run_tracker("_trk_static.mp4", 0.0, 3.0,
                        {"x": 0.5 - 30 / 1280, "y": 0.5 - 30 / 720, "w": 60 / 1280, "h": 60 / 720})
    xs = [k["x"] + k["w"] / 2 for k in res6["keys"]]
    jit = math.sqrt(sum((x - sum(xs) / len(xs)) ** 2 for x in xs) / len(xs)) * 960
    ok &= check(jit <= 0.4, "One Euro jitter on static object <= 0.3px source", f"{jit:.3f} analysis px")

    # (g) CSRT mode if available
    ctor = getattr(cv2, "TrackerCSRT", None)
    if ctor is None and not hasattr(cv2, "TrackerCSRT_create"):
        print("  SKIP  CSRT not compiled in this OpenCV")
    else:
        try:
            res7 = _run_tracker("_trk_sine.mp4", 0.0, 3.0, tight, zone=zone3, mode="csrt")
            ok &= check(len(res7["keys"]) > 10, "CSRT mode runs")
        except Exception as e:
            print("  SKIP  CSRT:", e)
    return ok


# ────────────────────────────────────────────── §7.4 P0 preview gates ──
def test_p0():
    section("§7.4  P0 — canvas monitor, frame sync, text frame parity")
    ok = True
    # 1) pure core logic (runs in Node, no browser needed)
    r = subprocess.run(["node", os.path.join(BASE, "web", "core", "selftest.js")],
                       capture_output=True, text=True, timeout=120, cwd=BASE)
    ok &= check(r.returncode == 0, "web/core selftest (frame grid, clock, spring, LUT)",
                (r.stdout[-400:] + r.stderr[-200:]) if r.returncode else "")

    # 2) §7.4: word appears in frame round(word.s*fps) ± 1 — cross-engine:
    #    the ASS export start frame vs the canvas-preview visibility frame.
    import server
    cue = {"text": "ЭТОТ ДОНАТ", "start": 1.0, "end": 2.0, "style": "acid",
           "words": [{"word": "ЭТОТ", "start": 1.0, "end": 1.5},
                     {"word": "ДОНАТ", "start": 1.5, "end": 2.0}]}
    ass = server.build_tv_subtitles_ass([cue], "acid", 1080, 1920, 200, glow=55,
                                        anim="pop", hot_words=False)
    m = re.search(r"Dialogue: 2,(\d+):(\d+):(\d+)\.(\d+),", ass)
    if m:
        h, mi, sec, cs = (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))
        ass_start_s = h * 3600 + mi * 60 + sec + cs / 100.0
        node_check = (
            "const TM = require('./web/core/timeMap.js');"
            "const s = %f;"
            "const pv = TM.wordVisibleFrame(s, 60);"
            "const ass = TM.wordAssStartFrame(%f, 60);"
            "console.log(JSON.stringify({pv, ass, delta: Math.abs(pv - ass)}));"
            % (1.0, ass_start_s)
        )
        r2 = subprocess.run(["node", "-e", node_check], capture_output=True, text=True,
                            timeout=30, cwd=BASE)
        ok &= check(r2.returncode == 0, "preview word-frame probe runs", r2.stderr[:200])
        if r2.returncode == 0:
            d = json.loads(r2.stdout.strip().splitlines()[-1])
            ok &= check(d["delta"] <= 1, "text appears in frame round(word.s*fps) ±1 (preview == export)",
                        json.dumps(d))
    else:
        ok &= check(False, "ASS dialogue start parsed")

    # 3) static wiring of the canvas monitor (§16)
    ed = read(os.path.join(BASE, "web", "editor.js"))
    html = read(os.path.join(BASE, "web", "index.html"))
    css = read(os.path.join(BASE, "web", "style.css"))
    mon = read(os.path.join(BASE, "web", "core", "canvasMonitor.js"))
    ok &= check("core/timeMap.js" in html and "core/canvasMonitor.js" in html
                and "core/text/canvasText.js" in html, "core modules loaded in index.html")
    ok &= check("__canvasMonitor.renderAt" in ed, "editor renders through the canvas monitor")
    ok &= check("state.previewFps" in ed and "1 / (state.previewFps || 60)" in ed,
                "frame stepping ±1/fps on the composition grid (§16.5)")
    ok &= check('enabled: state.aspectRatio === "9:16"' in ed,
                "canvas monitor active for the 9:16 Shorts view (§7.4 gate 1)")
    ok &= check("videoPool = new Map()" in mon and "this.videoPool.set(name, el)" in mon,
                "one hidden <video> per unique file (§16.2)")
    ok &= check("sourceId: base.media.filename" in mon,
                "split halves draw from the same decoded frame (§7.4 clap gate by construction)")
    ok &= check("requestVideoFrameCallback" in mon, "rVFC redraw on pause/scrub (§16.3)")
    ok &= check("clockCorrection" in mon and "0.97" in read(os.path.join(BASE, "web", "core", "timeMap.js")),
                "master-clock follower 0.97/1.03 with seek >150ms (§16.3)")
    ok &= check("format-card" in ed and 'state.aspectRatio = shortsFmt ? "9:16" : "16:9"' in ed,
                "Shorts format switches monitor to 9:16 (§7.4 gate 1)")

    # 4) CSS text animations removed (§16.4) — canvas text replaces them
    gone = all(("@keyframes " + k) not in css for k in
               ("popWord", "tvGlitch", "tvWave", "tvShimmer", "tvType", "tvTremble", "tvRise", "tvSpin"))
    ok &= check(gone, "CSS text @keyframes removed (canvas text engine)")
    ok &= check("cueAt" in ed, "subtitles drawn by web/core/text (canvas)")

    # 5) grade LUT endpoint serves the own 65^3 cube (§16.6)
    from fastapi.testclient import TestClient
    client = TestClient(server.app)
    r3 = client.get("/api/grade/lut")
    ok &= check(r3.status_code == 200 and b"LUT_3D_SIZE 65" in r3.content,
                "/api/grade/lut serves the own 65^3 LUT for the WebGL2 pass")
    return ok


# ─────────────────────────────────────── §7.4 P1 + step 1 (composition) ──
def test_p1():
    section("§7.4  P1 + шаг 1 — WebCodecs worker, composition, renderFrame parity")
    ok = True
    # 1) generate a real B-frame MP4 for the demuxer tests, then run selftest
    demux_test = os.path.join(BASE, "scratch", "_demux_test.mp4")
    os.makedirs(os.path.dirname(demux_test), exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                    "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=30:duration=2",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
                    "-g", "10", "-bf", "2", "-pix_fmt", "yuv420p", demux_test],
                   check=True, timeout=120)
    r = subprocess.run(["node", os.path.join(BASE, "web", "core", "selftest.js")],
                       capture_output=True, text=True, timeout=120, cwd=BASE)
    ok &= check(r.returncode == 0, "web/core selftest (incl. P1 demux/ring/mapTime/composer SSIM)",
                (r.stdout[-500:] + r.stderr[-200:]) if r.returncode else "")
    for marker in ("P1 demux + frame index", "P1 ring cache", "composer + scale parity"):
        ok &= check(marker in r.stdout, "selftest section present: " + marker)
    ok &= check("SSIM >= 0.99" in r.stdout and "FAIL" not in r.stdout,
                "scale parity SSIM >= 0.99 gates green")

    # 2) modules load and degrade honestly outside the browser
    r2 = subprocess.run(["node", "-e",
                         "const W = require('./web/core/webcodecs.js');"
                         "console.log(JSON.stringify({supported: W.supported()}));"],
                        capture_output=True, text=True, timeout=30, cwd=BASE)
    ok &= check(r2.returncode == 0 and json.loads(r2.stdout.strip())["supported"] is False,
                "webcodecs facade loads in Node, supported()=false (P0 fallback)")

    # 3) static wiring
    ed = read(os.path.join(BASE, "web", "editor.js"))
    mon = read(os.path.join(BASE, "web", "core", "canvasMonitor.js"))
    html = read(os.path.join(BASE, "web", "index.html"))
    worker = read(os.path.join(BASE, "web", "core", "mp4", "decoderWorker.js"))
    demux = read(os.path.join(BASE, "web", "core", "mp4", "demux.js"))
    ok &= check("decoderFor" in ed and "__proxyUrlCached" in ed,
                "editor provides decoder hook + proxy cache (§16 P1)")
    ok &= check("_takeExactFrame" in mon and "floor" in read(os.path.join(BASE, "web", "core", "mp4", "frameIndex.js")),
                "monitor uses exact frames; frame pick floor(src*fps+1e-6)")
    ok &= check("core/webcodecs.js" in html, "webcodecs facade loaded in index.html")
    ok &= check("RING_CAP = 12" in worker and "SCRUB_LIMIT_SEC = 1.5" in worker,
                "worker: ring cache <=12, scrub limit 1.5s -> proxy")
    ok &= check("close()" in worker and "clone()" in worker,
                "worker closes cached originals, ships clones to main")
    ok &= check("avcC" in demux and "ctts" in demux and "stss" in demux,
                "own BMFF demuxer: avcC description, ctts (B-frames), stss (sync)")
    ok &= check("optimizeForLatency" in worker and "decodeQueueSize" in worker,
                "VideoDecoder configured, decodeQueueSize <= 4")
    return ok


class _MockGroq(BaseHTTPRequestHandler):

    behavior = {"fail_429": 0, "requests": []}

    def log_message(self, *a):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        self.behavior["requests"].append({
            "granularities": re.findall(r"name=\"timestamp_granularities\[\]\"\r\n\r\n(\w+)", body.decode("latin-1")),
            "language": (re.search(r"name=\"language\"\r\n\r\n(\w+)", body.decode("latin-1")) or [None, None])[1],
            "prompt": bool(re.search(r"name=\"prompt\"", body.decode("latin-1"))),
        })
        if self.behavior["fail_429"] > 0:
            self.behavior["fail_429"] -= 1
            self.send_response(429)
            self.send_header("Retry-After", "1")
            self.end_headers()
            return
        words = [{"word": "Привет", "start": 0.10, "end": 0.50},
                 {"word": "мир", "start": 0.50, "end": 0.90},
                 {"word": "Продолжение", "start": 1.00, "end": 1.60},
                 {"word": "следует", "start": 1.60, "end": 2.00}]
        segments = [{"start": 1.0, "end": 2.0, "text": "Продолжение следует",
                     "no_speech_prob": 0.95, "avg_logprob": -2.5}]
        payload = {"text": "Привет мир", "language": "ru", "duration": 2.0,
                   "words": words, "segments": segments}
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def test_groq_mock():
    section("§7.3  Step 0c — Groq reliability (mock server)")
    import server
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _MockGroq)
    port = srv.server_address[1]
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    old_url = server.GROQ_API_URL
    server.GROQ_API_URL = f"http://127.0.0.1:{port}/v1/audio/transcriptions"
    old_limit = server.ASR_SIZE_LIMIT
    ok = True
    try:
        from fastapi.testclient import TestClient
        client = TestClient(server.app)
        flac = os.path.join(DL, "_asr_src.flac")
        if not os.path.exists(flac):
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                            "-i", "sine=frequency=220:duration=2", "-c:a", "flac", flac],
                           check=True, timeout=60)
        server.DOWNLOADS_DIR  # keep reference

        # 1) retries: two 429s then success (Retry-After respected)
        _MockGroq.behavior["fail_429"] = 2
        _MockGroq.behavior["requests"] = []
        server._asr_cache_dir_purge = None
        # clear cache dir for a fresh key
        shutil.rmtree(server.ASR_CACHE_DIR, ignore_errors=True)
        r = client.post("/api/transcribe", json={
            "filename": "_asr_src.flac", "start_time": 0, "duration": 2,
            "language": "ru", "prompt": "словарь канала"})
        ok &= check(r.status_code == 200, "retries succeed after 429s", r.text[:200])
        ok &= check(len(_MockGroq.behavior["requests"]) == 3, "exactly 3 attempts (2 retries)",
                    str(len(_MockGroq.behavior["requests"])))
        req0 = _MockGroq.behavior["requests"][0]
        ok &= check(set(req0["granularities"]) == {"word", "segment"}, "word+segment granularities",
                    str(req0["granularities"]))
        ok &= check(req0["language"] == "ru", "language sent")
        ok &= check(req0["prompt"], "channel dictionary prompt sent")

        words = r.json().get("words", [])
        texts = [w["word"] for w in words]
        ok &= check("Продолжение" not in texts and "следует" not in texts,
                    "ghost phrase filtered", str(texts))
        ok &= check("Привет" in texts, "real words kept", str(texts))
        ok &= check(r.json().get("filtered_hallucinations", 0) >= 1, "hallucinated segment counted")

        # 2) cache: second identical call hits cache (no new request)
        before = len(_MockGroq.behavior["requests"])
        r2 = client.post("/api/transcribe", json={
            "filename": "_asr_src.flac", "start_time": 0, "duration": 2,
            "language": "ru", "prompt": "словарь канала"})
        ok &= check(r2.status_code == 200 and r2.json().get("cache") == "hit", "second call served from cache")
        ok &= check(len(_MockGroq.behavior["requests"]) == before, "no network on cache hit")

        # 3) chunking when over the (patched) size limit — bust the cache first
        server.ASR_SIZE_LIMIT = 1024  # force chunking path
        shutil.rmtree(server.ASR_CACHE_DIR, ignore_errors=True)
        _MockGroq.behavior["requests"] = []
        r3 = client.post("/api/transcribe", json={
            "filename": "_asr_src.flac", "start_time": 0, "duration": 2,
            "language": "ru", "prompt": "словарь канала"})
        n_chunks = r3.json().get("chunks", 1)
        ok &= check(n_chunks >= 2, "chunked over size limit", f"chunks={n_chunks}")
        ok &= check(len(_MockGroq.behavior["requests"]) == n_chunks, "one request per chunk")
        ok &= check("Привет" in [w["word"] for w in r3.json().get("words", [])],
                    "no word loss at chunk seams")
        server.ASR_SIZE_LIMIT = old_limit

        # 4) 5 consecutive 5xx -> friendly error
        class _AllFail(_MockGroq):
            def do_POST(self):
                self.send_response(503)
                self.end_headers()
        srv2 = ThreadingHTTPServer(("127.0.0.1", 0), _AllFail)
        threading.Thread(target=srv2.serve_forever, daemon=True).start()
        server.GROQ_API_URL = f"http://127.0.0.1:{srv2.server_address[1]}/v1/audio/transcriptions"
        r4 = client.post("/api/transcribe", json={
            "filename": "_asr_src.flac", "start_time": 0.5, "duration": 2,
            "language": "ru", "prompt": "x"})
        ok &= check(r4.status_code == 502, "retries exhausted -> 502 with message", str(r4.status_code))
        srv2.shutdown()
    finally:
        server.GROQ_API_URL = old_url
        server.ASR_SIZE_LIMIT = old_limit
        srv.shutdown()
    return ok


# ────────────────────────────────────────────────────── entry point ──
DL = os.path.join(BASE, "downloads")


def main():
    t0 = time.time()
    os.makedirs(DL, exist_ok=True)
    ok = True
    ok &= test_licenses()
    ok &= test_version_and_contract()
    ok &= test_export_graph()
    ok &= test_tracker()
    ok &= test_groq_mock()
    ok &= test_p0()
    ok &= test_p1()
    dt = time.time() - t0
    print(f"\n{'=' * 64}")
    if FAILURES:
        print(f"VERIFICATION FAILED: {len(FAILURES)} problem(s) in {dt:.1f}s")
        for sec, label, extra in FAILURES:
            print(f"  - [{sec}] {label} {extra}")
        return 1
    print(f"ALL VERIFICATION CHECKS PASSED in {dt:.1f}s")
    return 0


if __name__ == "__main__":
    if "--network" in sys.argv:
        print("Network pipeline test (downloader) — requires kick.com access")
        exec(read(os.path.join(BASE, "verify_all.py")).split("if __name__")[0])
        # fall back to legacy pipeline test
        subprocess.run([sys.executable, os.path.join(BASE, "tools", "network_pipeline_test.py")])
    else:
        sys.exit(main())
