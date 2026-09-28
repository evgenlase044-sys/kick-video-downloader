"""Install the studio layer into server.app: security middleware, patched
web files (editor.js / index.html), /api/studio/status, moments + templates."""
from __future__ import annotations

import os
import re
import threading

from fastapi import Request
from fastapi.responses import HTMLResponse, Response

from studio.patching import apply_patches, read_source, summarize
from studio.security import COOKIE_NAME, StudioSecurityMiddleware
from studio.sfx import ensure_riser
from studio.web_patches import EDITOR_PATCHES, INDEX_PATCHES


class _PatchedFile:
    def __init__(self, path, patches, name):
        self.path, self.patches, self.name = path, patches, name
        self._lock = threading.Lock()
        self._mtime = None
        self._text = ""
        self.results = []

    def text(self):
        m = os.path.getmtime(self.path)
        with self._lock:
            if m != self._mtime:
                src, _ = read_source(self.path)
                self._text, self.results = apply_patches(src, self.patches, self.name)
                self._mtime = m
                print(f"[studio] {self.name} patches: {summarize(self.results)}", flush=True)
            return self._text


def install(app, *, token, port, web_dir, sfx_dir, allowed_hosts=("127.0.0.1", "localhost", "::1"),
            server_report=None, downloads_dir=None):
    index = _PatchedFile(os.path.join(web_dir, "index.html"), INDEX_PATCHES, "web/index.html")
    editor = _PatchedFile(os.path.join(web_dir, "editor.js"), EDITOR_PATCHES, "web/editor.js")
    editor_paths = {"/editor.js"}
    for m in re.finditer(r"src=[\"']([^\"'?#]*editor\.js)", index.text()):
        if not m.group(1).startswith(("http:", "https:")):
            editor_paths.add("/" + m.group(1).lstrip("./").lstrip("/"))

    def html(request: Request):
        resp = HTMLResponse(index.text(), headers={"Cache-Control": "no-store"})
        if token and request.query_params.get("token") == token:
            resp.set_cookie(COOKIE_NAME, token, httponly=True, samesite="strict", path="/")
        return resp

    def editor_js():
        return Response(editor.text(), media_type="application/javascript", headers={"Cache-Control": "no-store"})

    def status():
        rep = {"server.py": server_report or [], "web/index.html": [r.as_dict() for r in index.results],
               "web/editor.js": [r.as_dict() for r in editor.results]}
        return {"patches": rep, "failed": [f"{k}:{r['id']}" for k, v in rep.items() for r in v
                                           if r["status"] == "failed" and r.get("required", True)]}

    n_before = len(app.router.routes)
    for p in ("/", "/index.html"):
        app.add_api_route(p, html, methods=["GET"], include_in_schema=False)
    for p in sorted(editor_paths):
        app.add_api_route(p, editor_js, methods=["GET"], include_in_schema=False)
    app.add_api_route("/api/studio/status", status, methods=["GET"])
    if downloads_dir:
        from studio.api import build_router
        app.include_router(build_router(downloads_dir))
    routes = app.router.routes
    n = len(routes) - n_before
    moved = routes[-n:]
    del routes[-n:]
    routes[0:0] = moved   # before the StaticFiles mount at "/"
    app.add_middleware(StudioSecurityMiddleware, token=token, port=port, allowed_hosts=tuple(allowed_hosts))
    return {"editor_paths": sorted(editor_paths), "riser": ensure_riser(sfx_dir)}
