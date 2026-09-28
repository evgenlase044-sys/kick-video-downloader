"""PR #8 anchored fixes (server.py / web/editor.js), found by the live smoke
test of PR #7 and by a filtergraph check with real ffmpeg.

Importing this module appends the patches IN PLACE to
``studio.server_patches.SERVER_PATCHES`` and ``studio.web_patches.EDITOR_PATCHES``
(idempotent), so every consumer (loader, ``python -m studio.patching``, tests,
fold bot) sees one list.

editor.js
* hoist-collectors: collectRegionSubtitles / collectRegionTextItems /
  collectRegionFx were local to initClipperPanel(); requestServerPreviewFrame()
  lives at module scope -> ``ReferenceError: collectRegionSubtitles is not
  defined`` on every seek inside a region (live smoke, editor.js:3953).
  They move to module scope (they only use module-level helpers).
  collectRegionFx now also sends the fx anchor (anchor_x / anchor_y).
* preview-frame-v2: the stale-frame guard compared with an undefined
  ``token`` (ReferenceError inside onload -> the server frame never showed),
  blob URLs leaked, late responses could overwrite a newer frame.
* face-anchor-norm: hooks.faceAnchor returned an ARRAY in track-box units;
  canvasMonitor reads ``anchor.x * outW`` -> NaN transform on every tracked
  zoom. Now {x, y} normalized 0..1.
* drop-tidOfFx: dead since PR #7.

server.py
* fx-anchor-fields: FxOverlay gets anchor_x / anchor_y (normalized output).
* zoom-anim: the export zoom punch was a NO-OP. ``crop`` evaluates w/h once
  at init (t = NAN -> envelope 1), so ``crop=w='iw/env'`` never zoomed: the
  output was bit-identical to the input (checked with framemd5). Now the frame
  is scaled per frame (``scale ... eval=frame``) and overlaid onto itself at an
  offset that keeps the anchor (face) fixed - same envelope as before.
* lens-anim: Lens Punch in the export was a static barrel for the whole
  interval; lenscorrection options are init-only, so k1 now follows the
  preview bell (peak at 32 % of the interval) in 6 enable-gated steps.
"""
from studio.patching import Patch

# required=False: a drifted anchor is reported (and caught by test_pr8), it does
# not abort the fold bot / server start.

# ---------------------------------------------------------------- editor.js
HOISTED_COLLECTORS = r'''    // studio:hoist-collectors - region collectors live at MODULE scope: the
    // server preview frame (requestServerPreviewFrame) and the export
    // (initClipperPanel) both call them. They were local to initClipperPanel ->
    // ReferenceError: collectRegionSubtitles is not defined (PR #7 smoke test).
    function collectRegionSubtitles(regs, outBases) {
        // subtitle AND free-text clips from ALL text layers AND video layers
        const tclips = [];
        for (const tid of trackOrder()) {
            const track = getTrack(tid);
            if (!track || track.kind === "audio") continue;
            for (const c of (state.tracks[tid] || [])) {
                if (c.isFx || c.media || !c.title) continue;
                if (!isTextClip(c)) continue;
                tclips.push(c);
            }
        }
        tclips.sort((a, b) => a.startTime - b.startTime);
        const subs = [];
        regs.forEach((r, k) => {
            const base = outBases[k];
            for (const c of tclips) {
                if (c.freeText) continue; // free text -> separate text_items
                const cs = c.startTime, ce = c.startTime + c.duration;
                if (ce <= r.startTime + 0.02 || cs >= r.startTime + r.duration - 0.02) continue;
                const words = Array.isArray(c.words) && c.words.length ? c.words : [{
                    word: c.title || "",
                    abs_start: Math.max(cs, r.startTime),
                    abs_end: Math.min(ce, r.startTime + r.duration)
                }];
                const wout = [];
                for (const w of words) {
                    const ws = Math.max(w.abs_start, r.startTime) - r.startTime;
                    const we = Math.min(w.abs_end, r.startTime + r.duration) - r.startTime;
                    if (!(we > ws + 0.03)) continue;
                    wout.push({ word: w.word, start: base + ws, end: base + we, style: c.subtitleStyle || null });
                }
                if (!wout.length) continue;
                subs.push({
                    text: c.title || "",
                    start: base + Math.max(0, cs - r.startTime),
                    end: base + Math.min(r.duration, ce - r.startTime),
                    abs_start: base + Math.max(0, cs - r.startTime),
                    abs_end: base + Math.min(r.duration, ce - r.startTime),
                    style: c.subtitleStyle || null,
                    words: wout,
                    // позиция, перенесённая вручную на превью (0..1 доли кадра)
                    x: c.textX != null ? c.textX : null,
                    y: c.textY != null ? c.textY : null
                });
            }
        });
        return subs;
    }
    function collectRegionTextItems(regs, outBases) {
        const items = [];
        for (const tid of trackOrder()) {
            const track = getTrack(tid);
            if (!track || track.kind === "audio") continue;
            for (const c of (state.tracks[tid] || [])) {
                if (!c.isText || !c.freeText || !c.title) continue;
                regs.forEach((r, k) => {
                    const base = outBases[k];
                    const cs = c.startTime, ce = c.startTime + c.duration;
                    if (ce <= r.startTime + 0.02 || cs >= r.startTime + r.duration - 0.02) return;
                    const s = base + Math.max(0, cs - r.startTime);
                    const e = base + Math.min(r.duration, ce - r.startTime);
                    if (!(e > s + 0.05)) return;
                    items.push({
                        text: c.title,
                        start: s, end: e,
                        font: c.textFont || state.clipper.subFont || "Montserrat ExtraBold",
                        size: Math.round((c.textSize || 6.0) * 1920 / 100), // % of 1080x1920 height -> px
                        color: c.textColor || "#ffffff",
                        glow: c.textGlow != null ? c.textGlow : 55,
                        anim_in: c.textAnimIn || "pop",
                        anim_out: c.textAnimOut || "fade",
                        x: c.textX != null ? c.textX : 0.5,
                        y: c.textY != null ? c.textY : 0.72,
                        shake: !!c.textShake,
                        stroke: c.textStroke != null ? c.textStroke : 0,
                        spacing: c.textSpacing != null ? c.textSpacing : 0
                    });
                });
            }
        }
        return items;
    }
    // FX overlays + sounds mapped into one region's output.
    // z = позиция слоя в trackList (0 = верхний): вспышка под верхними
    // элементами НЕ действует на них (сервер жжёт её только под композитом)
    function collectRegionFx(r) {
        const overlays = [];
        const sounds = [];
        const order = trackOrder();
        for (let zi = 0; zi < order.length; zi++) {
            const tid = order[zi];
            const track = getTrack(tid);
            if (!track || track.kind !== "video") continue;
            for (const c of (state.tracks[tid] || [])) {
                if (!c.isFx) continue;
                const cs = c.startTime, ce = c.startTime + c.duration;
                if (ce <= r.startTime + 0.02 || cs >= r.startTime + r.duration - 0.02) continue;
                const ov = {
                    start: Math.max(0, cs - r.startTime),
                    end: Math.min(r.duration, ce - r.startTime),
                    kind: c.fxKind || "flash",
                    color: c.fxColor || "white",
                    peak: c.fxPeak != null ? c.fxPeak : 0.75,
                    bar_h: c.fxBarH || 120,
                    amp: c.fxAmp || 12,
                    freq: c.fxFreq || 7,
                    z: zi
                };
                // studio:fx-anchor-export - template face anchor (0..1 of the frame)
                const an = c.anchor;
                if (an && isFinite(Number(an.x)) && isFinite(Number(an.y))) {
                    ov.anchor_x = Math.max(0, Math.min(1, Number(an.x)));
                    ov.anchor_y = Math.max(0, Math.min(1, Number(an.y)));
                }
                overlays.push(ov);
                if (c.fxSound && c.fxSound !== "none") {
                    sounds.push({
                        at: Math.max(0, cs - r.startTime),
                        kind: c.fxSound,
                        gain: c.fxGain != null ? c.fxGain : 1.0
                    });
                }
            }
        }
        return { overlays, sounds };
    }

'''

PREVIEW_FRAME_V2 = r'''    // studio:preview-frame-v2 - (1) the collectors are module-level now (was a
    // ReferenceError); (2) the stale-frame guard compared with an undefined
    // `token` (ReferenceError in onload: the frame never appeared) -> request
    // sequence number; (3) superseded blob URLs are revoked (leak on scrubbing);
    // (4) a late response never overwrites a newer frame.
    let pvSeq = 0;
    let pvShownUrl = null;
    function requestServerPreviewFrame() {
        if (state.isPlaying) { hideServerPreviewFrame(); return; }
        const r = (state.regions || []).find(rg => state.currentTime >= rg.startTime && state.currentTime < rg.startTime + rg.duration);
        if (!r) { hideServerPreviewFrame(); return; }
        const mc = resolvePackSource(r.startTime);
        if (!mc || !mc.media) { hideServerPreviewFrame(); return; }
        if (pvTimer) clearTimeout(pvTimer);
        const seq = ++pvSeq;
        pvTimer = setTimeout(async () => {
            if (state.isPlaying || seq !== pvSeq) return;
            let subs, tis, fx;
            try {
                subs = collectRegionSubtitles([r], [0]);
                tis = collectRegionTextItems([r], [0]);
                fx = collectRegionFx(r);
            } catch (e) {
                console.warn("[preview-frame] collect failed:", e);
                return;
            }
            const srcTime = (mc.sourceOffset || 0) + (state.currentTime - mc.startTime);
            const payload = {
                source_file: mc.media.filename, src_time: srcTime,
                format: state.clipper.format, crop_box: state.clipper.cropBox || null,
                bg_box: state.clipper.bgBox || null, color_grade: state.clipper.colorGrade,
                subtitle_template: state.clipper.subtitleTemplate, sub_font: state.clipper.subFont,
                sub_size: state.clipper.subSize, hot_words: state.clipper.hotWords !== false,
                subtitles: subs, text_items: tis, overlays: fx.overlays,
                region_time: state.currentTime - r.startTime
            };
            try {
                const res = await fetch("/api/preview-frame", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
                if (!res.ok || seq !== pvSeq) return;
                const blob = await res.blob();
                if (seq !== pvSeq || state.isPlaying) return;
                let img = document.getElementById("serverFrameImg");
                if (!img) {
                    img = document.createElement("img");
                    img.id = "serverFrameImg";
                    img.style.cssText = "position:absolute;inset:0;width:100%;height:100%;object-fit:contain;z-index:30;pointer-events:none;";
                    const mon = document.getElementById("videoMonitor");
                    (mon || document.body).appendChild(img);
                }
                // безмигательная подмена: новый кадр подменяется только после загрузки
                const url = URL.createObjectURL(blob);
                const probe = new Image();
                probe.onload = () => {
                    if (seq !== pvSeq || state.isPlaying) { URL.revokeObjectURL(url); return; }
                    const prev = pvShownUrl;
                    pvShownUrl = url;
                    img.src = url;
                    img.style.display = "block";
                    if (prev && prev !== url) URL.revokeObjectURL(prev);
                };
                probe.onerror = () => URL.revokeObjectURL(url);
                probe.src = url;
            } catch (e) { /* превью не критично */ }
        }, 380);
    }
'''

FACE_ANCHOR_NORM = r'''                // studio:face-anchor-norm - canvasMonitor reads anchor.x / anchor.y
                // as 0..1 of the frame; an array gave NaN (broken zoom transform).
                let fx_ = box.x + box.w / 2, fy_ = box.y + box.h / 2;
                if (!isFinite(fx_) || !isFinite(fy_)) return null;
                if (fx_ > 1.001 || fy_ > 1.001) {       // track box in source pixels
                    const m = baseClip.media || {};
                    const mw = Number(m.width || m.w || (videoEl && videoEl.videoWidth)) || 1920;
                    const mh = Number(m.height || m.h || (videoEl && videoEl.videoHeight)) || 1080;
                    fx_ /= mw; fy_ /= mh;
                }
                // keep the punch inside the frame even for a face at the very edge
                return { x: Math.max(0.15, Math.min(0.85, fx_)), y: Math.max(0.15, Math.min(0.85, fy_)) };
'''

PR8_EDITOR_PATCHES = [
    Patch(id="hoist-collectors-subs", required=False, group="hoist-collectors", regex=True, count=1,
          old=r"        function collectRegionSubtitles\(regs, outBases\) \{\n.*?\n            return subs;\n        \}[ \t]*\n",
          new="        // collectRegionSubtitles -> module scope (studio:hoist-collectors)\n"),
    Patch(id="hoist-collectors-text", required=False, group="hoist-collectors", regex=True, count=1,
          old=r"        function collectRegionTextItems\(regs, outBases\) \{\n.*?\n            return items;\n        \}[ \t]*\n",
          new="        // collectRegionTextItems -> module scope (studio:hoist-collectors)\n"),
    Patch(id="hoist-collectors-fx", required=False, group="hoist-collectors", regex=True, count=1,
          old=r"        function collectRegionFx\(r\) \{\n.*?\n            return \{ overlays, sounds \};\n        \}[ \t]*\n",
          new="        // collectRegionFx -> module scope (studio:hoist-collectors)\n"),
    Patch(id="hoist-collectors-define", required=False, group="hoist-collectors", regex=True, count=1,
          old=r"(?=    // Серверный кадр превью: )",
          new=HOISTED_COLLECTORS, marker="studio:hoist-collectors - region collectors"),
    Patch(id="preview-frame-v2", required=False, regex=True, count=1,
          old=r"    function requestServerPreviewFrame\(\) \{\n.*?\n        \}, 380\);\n    \}[ \t]*\n",
          new=PREVIEW_FRAME_V2, marker="studio:preview-frame-v2"),
    Patch(id="face-anchor-norm", required=False, regex=True, count=1,
          old=r"                return \[box\.x \+ box\.w / 2, box\.y \+ box\.h / 2\];[ \t]*\n",
          new=FACE_ANCHOR_NORM, marker="studio:face-anchor-norm"),
    Patch(id="drop-tidOfFx", required=False, regex=True, count=1,
          old=r"    function tidOfFx\(\) \{\n.*?\n        return ensureFxTrack\(\);\n    \}[ \t]*\n",
          new="    // tidOfFx() removed: unused since PR #7 (studio:drop-tidOfFx)\n",
          marker="studio:drop-tidOfFx"),
]

# ---------------------------------------------------------------- server.py
FX_ANCHOR_FIELDS = r'''    freq: float = 7.0            # shake frequency Hz (kind=shake)
    # studio:fx-anchor-fields - zoom anchor (template face), 0..1 of the output
    anchor_x: Optional[float] = None
    anchor_y: Optional[float] = None
'''

ZOOM_ANIM = r'''        elif fx.kind == "zoom":
            # studio:zoom-anim - §15 zoom punch that REALLY animates. The old
            # crop=w='iw/env' was a no-op: crop evaluates w/h once at init
            # (t=NAN -> env=1), so every exported zoom was bit-identical to the
            # input; crop x/y are also clamped to the INIT size, so a crop after
            # a per-frame scale cannot move. Now: the frame is scaled per frame
            # (scale eval=frame, lanczos) and overlaid onto itself at a per-frame
            # offset that keeps the fx anchor (template face anchor, 0..1 of the
            # output; default centre) fixed, clamped so no edge ever shows.
            # Same envelope as before (and as the preview curve).
            a = max(0.02, min(0.5, float(fx.peak if fx.peak and fx.peak < 1 else 0.15)))
            ax = getattr(fx, "anchor_x", None)
            ay = getattr(fx, "anchor_y", None)
            ax = 0.5 if ax is None else max(0.0, min(1.0, float(ax)))
            ay = 0.5 if ay is None else max(0.0, min(1.0, float(ay)))
            zx = (f"(1+{a:.4f}*(0.12+0.88*exp(-3*max(t-{s0:.3f}\\,0)/{max(1e-3, d):.3f}))"
                  f"*between(t\\,{s0:.3f}\\,{e0:.3f}))")
            ox = f"-max(0\\,min({out_w}*{zx}-{out_w}\\,{ax:.4f}*{out_w}*{zx}-{ax:.4f}*{out_w}))"
            oy = f"-max(0\\,min({out_h}*{zx}-{out_h}\\,{ay:.4f}*{out_h}*{zx}-{ay:.4f}*{out_h}))"
            filter_parts.append(
                f"{curr_v}scale={out_w}:{out_h}:flags=lanczos+accurate_rnd,"
                f"split=2[{tag_prefix}v{fi}b][{tag_prefix}v{fi}s]")
            filter_parts.append(
                f"[{tag_prefix}v{fi}s]scale=w='2*trunc(iw*{zx}/2+0.5)':h='2*trunc(ih*{zx}/2+0.5)':"
                f"eval=frame:flags=lanczos+accurate_rnd[{tag_prefix}v{fi}z]")
            filter_parts.append(
                f"[{tag_prefix}v{fi}b][{tag_prefix}v{fi}z]overlay=x='{ox}':y='{oy}':eval=frame,"
                f"setsar=1[{tag_prefix}v{fi}]")
            curr_v = f"[{tag_prefix}v{fi}]"
'''

LENS_ANIM = r'''        elif fx.kind == "lens":
            # studio:lens-anim - animated Lens Punch (§13.3). lenscorrection
            # options are init-only, so the old code held one static barrel for
            # the whole interval. k1 now follows the preview bell (canvasMonitor:
            # peak at 32 % of the interval, width 0.35) in 6 enable-gated steps;
            # the CA shift follows k1.
            k1p = max(-0.45, min(0.45, float(fx.peak or 0.12)))
            steps = 6
            for si in range(steps):
                t0 = s0 + d * si / steps
                t1 = e0 if si == steps - 1 else s0 + d * (si + 1) / steps
                pm = (si + 0.5) / steps
                k = k1p * (2.718281828459045 ** (-((pm - 0.32) / 0.35) ** 2))
                if abs(k) < 0.004:
                    continue
                sen = f"'gte(t,{t0:.3f})*lt(t,{t1:.3f})'"
                shift = max(1, int(round(abs(k) * 12)))
                lbl = f"[{tag_prefix}v{fi}l{si}]"
                filter_parts.append(
                    f"{curr_v}lenscorrection=k1={k:.4f}:k2=0:cx=0.5:cy=0.5:enable={sen},"
                    f"rgbashift=rh={shift}:bh=-{shift}:enable={sen}{lbl}")
                curr_v = lbl
'''

PR8_SERVER_PATCHES = [
    Patch(id="fx-anchor-fields", required=False, regex=True, count=1,
          old=r"    freq: float = 7\.0 +# shake frequency Hz \(kind=shake\)[ \t]*\n",
          new=FX_ANCHOR_FIELDS, marker="studio:fx-anchor-fields"),
    Patch(id="zoom-anim", required=False,
          start="        elif fx.kind == \"zoom\":\n",
          end="        elif fx.kind == \"lens\":\n",
          new=ZOOM_ANIM, marker="studio:zoom-anim"),
    Patch(id="lens-anim", required=False,
          start="        elif fx.kind == \"lens\":\n",
          end="        elif fx.kind == \"threshold\":\n",
          new=LENS_ANIM, marker="studio:lens-anim"),
]


def install() -> None:
    """Append the PR #8 patches to the shared lists (idempotent)."""
    from studio import server_patches as SP, web_patches as WP
    for lst, extra in ((SP.SERVER_PATCHES, PR8_SERVER_PATCHES), (WP.EDITOR_PATCHES, PR8_EDITOR_PATCHES)):
        have = {p.id for p in lst}
        lst.extend(p for p in extra if p.id not in have)


install()
