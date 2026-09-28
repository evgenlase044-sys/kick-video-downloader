"""Studio export pipeline: installs the export-side audit fixes into the
loaded server module at runtime (no anchors in server.py needed).

install(server):
1. server._tv_grade_parts -> studio.grade.grade_chain (explicit BT.709,
   chroma denoise, float LUT at template strength, 16-bit out).
2. server.subprocess -> shim that rewrites final export encodes via
   studio.ffmpeg_argv (NVENC / platform bitrates, template fps, consistent
   loudness) and records a seek audit for every export command.
3. /api/export-pack (and the export queue, which calls the same global) ->
   wrapper applying per-clip studio options and, when the browser uploaded a
   canvas text layer, disabling ASS text and burning the canvas layer in one
   final pass. If that fails, the clip is re-exported with ASS text.
4. routes: WS /ws/overlay/{clip_id}, POST /api/studio/export-options,
   GET /api/studio/export-report.
"""
import collections
import os
import threading
import time
import types
from typing import Any, Dict, Optional

from studio import ffmpeg_argv as FA
from studio import ffmpeg_caps
from studio import grade as G
from studio import overlay as OV

TEMPLATE_OPTS = {
    "hype": {"fps": 60, "grade_strength": 0.55},
    "story": {"fps": 30, "grade_strength": 0.40},
    "clean": {"fps": 30, "grade_strength": 0.30},
}

REPORT = collections.deque(maxlen=60)
_tls = threading.local()
_opts_lock = threading.Lock()
_clip_opts: Dict[str, Dict[str, Any]] = {}
_installed = {"done": False}
_active_lock = threading.Lock()
_active = []


def _ctx() -> Optional[Dict[str, Any]]:
    c = getattr(_tls, "ctx", None)
    if c is not None:
        return c
    with _active_lock:
        return _active[0] if len(_active) == 1 else None


def _enter(ctx):
    _tls.ctx = ctx
    with _active_lock:
        _active.append(ctx)


def _leave(ctx):
    _tls.ctx = None
    with _active_lock:
        if ctx in _active:
            _active.remove(ctx)


def normalize_options(raw: Dict[str, Any]) -> Dict[str, Any]:
    raw = dict(raw or {})
    out: Dict[str, Any] = {}
    tpl = str(raw.get("template") or "").lower()
    if tpl in TEMPLATE_OPTS:
        out.update(TEMPLATE_OPTS[tpl])
        out["template"] = tpl
    if raw.get("fps") not in (None, "", 0):
        f = FA.parse_rate(raw.get("fps"), 0)
        if 10 <= f <= 120:
            out["fps"] = f
    if raw.get("grade_strength") is not None:
        try:
            out["grade_strength"] = max(0.0, min(1.0, float(raw["grade_strength"])))
        except (TypeError, ValueError):
            pass
    out["overlay"] = bool(raw.get("overlay"))
    out["created"] = time.time()
    return out


def set_clip_options(clip_id: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    opts = normalize_options(raw)
    with _opts_lock:
        now = time.time()
        for k in [k for k, v in _clip_opts.items() if now - v.get("created", now) > OV.TTL_S]:
            _clip_opts.pop(k, None)
        _clip_opts[str(clip_id)] = opts
    return opts


def pop_clip_options(clip_id: str) -> Optional[Dict[str, Any]]:
    with _opts_lock:
        return _clip_opts.pop(str(clip_id), None)


def make_grade_parts(base_dir: str):
    lut = os.path.join(base_dir, "tv_grade.cube")

    def _tv_grade_parts(src: str, dst: str, is_vertical: bool = True):
        ctx = _ctx() or {}
        return G.grade_chain(src, dst, lut_path=lut if os.path.exists(lut) else None,
                             strength=G.lut_strength(ctx), matrix=ctx.get("matrix", "bt709"))
    _tv_grade_parts.studio = True
    return _tv_grade_parts


def _rewrite(cmd, export_dir):
    if not isinstance(cmd, (list, tuple)) or not FA.is_export_encode(list(cmd), export_dir):
        return cmd
    ctx = _ctx() or {}
    try:
        new, info = FA.rewrite_export(list(cmd), h264_args=ffmpeg_caps.h264_args,
                                      fps_override=ctx.get("fps"),
                                      intermediate=bool(ctx.get("intermediate")))
        audit = FA.seek_audit(list(cmd))
        REPORT.append({"t": time.time(), "out": os.path.basename(str(cmd[-1])), "codec": info["codec"],
                       "fps": info["fps"], "loudnorm_fixed": info["loudnorm"],
                       "intermediate": bool(ctx.get("intermediate")), "seek": audit})
        if audit["slow_seek"]:
            print(f"[studio] export seek audit: input decoded from 0 (trim start "
                  f"{audit['max_trim_start']:.1f}s) -> {os.path.basename(str(cmd[-1]))}", flush=True)
        return new
    except Exception as exc:
        print(f"[studio] export argv rewrite skipped: {exc}", flush=True)
        return cmd


def make_subprocess_shim(real_subprocess, export_dir):
    shim = types.ModuleType("subprocess_studio_shim")
    shim.__dict__.update({k: getattr(real_subprocess, k) for k in dir(real_subprocess) if not k.startswith("__")})

    def run(args, *a, **kw):
        return real_subprocess.run(_rewrite(args, export_dir), *a, **kw)

    class Popen(real_subprocess.Popen):
        def __init__(self, args, *a, **kw):
            super().__init__(_rewrite(args, export_dir), *a, **kw)

    def check_call(args, *a, **kw):
        return real_subprocess.check_call(_rewrite(args, export_dir), *a, **kw)

    def call(args, *a, **kw):
        return real_subprocess.call(_rewrite(args, export_dir), *a, **kw)

    shim.run, shim.Popen, shim.check_call, shim.call = run, Popen, check_call, call
    shim.studio_shim = True
    return shim


def _result_files(res, export_dir):
    files = []
    for c in (res or {}).get("clips", []) or []:
        if not isinstance(c, dict):
            continue
        p = c.get("path") or c.get("output_path") or c.get("file") or c.get("filename")
        if not p:
            continue
        p = str(p)
        if not os.path.isabs(p):
            p = os.path.join(export_dir, os.path.basename(p))
        files.append((c, p))
    return files


def _strip_text(clip):
    for k, v in (("subtitles", []), ("text_items", []), ("subtitle_mode", "none")):
        try:
            setattr(clip, k, v)
        except Exception:
            pass


def _merge(results):
    out: Dict[str, Any] = {}
    for r in results:
        for k, v in (r or {}).items():
            if isinstance(v, list):
                out.setdefault(k, []).extend(v)
            elif isinstance(v, (int, float)) and not isinstance(v, bool) and k.endswith("count"):
                out[k] = out.get(k, 0) + v
            else:
                out.setdefault(k, v)
    return out


def make_export_wrapper(server, original):
    export_dir = server.EXPORTED_PACKS_DIR
    Req = server.ExportPackRequest

    def run_one(req, clip, opts, job):
        ctx = dict(opts or {}, intermediate=bool(job))
        _enter(ctx)
        try:
            if job:
                text_backup = (list(getattr(clip, "subtitles", []) or []),
                               list(getattr(clip, "text_items", []) or []),
                               getattr(clip, "subtitle_mode", None))
                _strip_text(clip)
            res = original(req)
        finally:
            _leave(ctx)
        if not job:
            return res
        errors = []
        files = _result_files(res, export_dir)
        if not files:
            OV.discard(job)
            return res
        fps = (opts or {}).get("fps")
        for entry, path in files:
            if not os.path.exists(path):
                errors.append(f"{os.path.basename(path)}: file not found")
                continue
            ok, msg = OV.burn_overlay(path, job, lambda f: ffmpeg_caps.h264_args(fps or f))
            if ok:
                entry["text_layer"] = "canvas"
            else:
                errors.append(msg)
        OV.discard(job)
        REPORT.append({"t": time.time(), "overlay": not errors, "errors": errors[-3:]})
        if not errors:
            return res
        print(f"[studio] canvas text layer failed ({'; '.join(errors)[:300]}), falling back to ASS", flush=True)
        clip.subtitles, clip.text_items, clip.subtitle_mode = text_backup
        ctx2 = dict(opts or {}, intermediate=False)
        _enter(ctx2)
        try:
            res2 = original(req)
        finally:
            _leave(ctx2)
        for c in (res2 or {}).get("clips", []) or []:
            if isinstance(c, dict):
                c["text_layer"] = "ass_fallback"
        return res2

    def export_clip_pack(req):
        clips = list(req.clips or [])
        plan = []
        for c in clips:
            cid = str(getattr(c, "id", "") or "")
            opts = pop_clip_options(cid) if cid else None
            job = OV.take(cid) if cid else None
            plan.append((c, opts, job))
        if not any(o or j for _, o, j in plan):
            return original(req)
        if len(clips) == 1:
            c, o, j = plan[0]
            return run_one(req, c, o, j)
        results = []
        for i, (c, o, j) in enumerate(plan):
            tpl = req.name_template or "{channel}_{date}_{n}_{title}"
            sub = Req(pack_name=req.pack_name, clips=[c], name_template=tpl.replace("{n}", str(i + 1)))
            results.append(run_one(sub, c, o, j))
        return _merge(results)

    export_clip_pack.__annotations__ = {"req": Req}
    export_clip_pack.__name__ = "export_clip_pack"
    export_clip_pack.__doc__ = (original.__doc__ or "") + "\n(studio: template options + canvas text layer)"
    export_clip_pack.studio = True
    return export_clip_pack


def _replace_route(app, path, method, endpoint):
    from fastapi.routing import APIRoute
    routes = app.router.routes
    for i, r in enumerate(routes):
        if isinstance(r, APIRoute) and r.path == path and method in (r.methods or set()):
            routes[i] = APIRoute(path, endpoint, methods=[method], response_model=None)
            return True
    return False


def install(server):
    if _installed["done"]:
        return {"already": True}
    from fastapi import Body, HTTPException, WebSocket
    from fastapi.routing import APIRoute, APIWebSocketRoute

    info: Dict[str, Any] = {}
    base = getattr(server, "BASE_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if hasattr(server, "_tv_grade_parts"):
        server._tv_grade_parts = make_grade_parts(base)
        info["grade"] = True
    import subprocess as _real
    if not getattr(server.subprocess, "studio_shim", False):
        server.subprocess = make_subprocess_shim(_real, server.EXPORTED_PACKS_DIR)
        info["encoder_shim"] = True
    if hasattr(server, "export_clip_pack") and hasattr(server, "ExportPackRequest"):
        wrapped = make_export_wrapper(server, server.export_clip_pack)
        server.export_clip_pack = wrapped
        info["export_route"] = _replace_route(server.app, "/api/export-pack", "POST", wrapped)

    overlay_root = os.path.join(server.DOWNLOADS_DIR, ".overlays")

    async def ws_overlay(ws: WebSocket, clip_id: str):
        await OV.ws_overlay(ws, clip_id, root_dir=overlay_root)

    def export_options(payload: Dict[str, Any] = Body(...)):
        items = payload.get("clips") if isinstance(payload.get("clips"), list) else [payload]
        out = {}
        for it in items:
            cid = str((it or {}).get("clip_id") or "")
            if not OV._ID.match(cid):
                raise HTTPException(status_code=400, detail="clip_id required ([A-Za-z0-9_.-])")
            out[cid] = set_clip_options(cid, it)
        return {"ok": True, "options": out}

    def export_report():
        return {"encoder": "h264_nvenc" if ffmpeg_caps.nvenc_available() else "libx264",
                "installed": info, "recent": list(REPORT)[-20:]}

    routes = server.app.router.routes
    new = [APIWebSocketRoute("/ws/overlay/{clip_id}", ws_overlay),
           APIRoute("/api/studio/export-options", export_options, methods=["POST"]),
           APIRoute("/api/studio/export-report", export_report, methods=["GET"])]
    routes[0:0] = new
    _installed["done"] = True
    print(f"[studio] export pipeline: {info}", flush=True)
    return info
