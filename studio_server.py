#!/usr/bin/env python3
"""Kick Clip Studio backend entrypoint (use instead of `python server.py`).

Loads server.py with the audit fixes, installs the security layer, binds to
127.0.0.1 only with a per-launch token (written to .studio/token, printed as
a ready URL; the page keeps it in an HttpOnly SameSite=Strict cookie).
Also mounts the moment finder and templates API (/api/studio/*) and the
export pipeline (studio/export_pipeline.py: canvas text layer, NVENC /
platform bitrates, template fps, 16-bit grade, consistent loudness).
"""
import argparse
import ipaddress
import os
import secrets
import sys
import webbrowser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
TOKEN_FILE = os.path.join(BASE_DIR, ".studio", "token")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=int(os.environ.get("STUDIO_PORT", "8765")))
    ap.add_argument("--open-browser", action="store_true")
    ap.add_argument("--allow-remote", action="store_true")
    a = ap.parse_args(argv)
    try:
        loop = ipaddress.ip_address(a.host).is_loopback
    except ValueError:
        loop = a.host == "localhost"
    if not loop and not a.allow_remote:
        print(f"[studio] refusing to bind to {a.host}: loopback only (use --allow-remote)")
        return 2
    token = os.environ.get("STUDIO_TOKEN") or secrets.token_urlsafe(32)
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    fd = os.open(TOKEN_FILE + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(token)
    os.replace(TOKEN_FILE + ".tmp", TOKEN_FILE)

    from studio import loader
    server = loader.load_server()
    failed = [r for r in getattr(server, "_STUDIO_PATCH_REPORT", [])
              if r.get("status") == "failed" and r.get("required", True)]
    if failed:
        print("[studio] WARNING: required server.py fixes failed to apply: " +
              ", ".join(r["id"] for r in failed), flush=True)
    try:
        from studio import export_pipeline
        export_pipeline.install(server)
    except Exception as exc:          # the legacy export keeps working without it
        print(f"[studio] WARNING: export pipeline not installed: {exc}", flush=True)
    from studio.app import install
    hosts = ["127.0.0.1", "localhost", "::1"] + ([a.host] if a.allow_remote else [])
    info = install(server.app, token=token, port=a.port, web_dir=server.WEB_DIR, sfx_dir=server.SFX_DIR,
                   allowed_hosts=hosts, server_report=getattr(server, "_STUDIO_PATCH_REPORT", []),
                   downloads_dir=getattr(server, "DOWNLOADS_DIR", os.path.join(BASE_DIR, "downloads")))
    url = f"http://127.0.0.1:{a.port}/index.html?token={token}"
    print(f"[studio] UI: {url}", flush=True)
    if not info.get("riser"):
        print("[studio] warning: sfx/riser.mp3 could not be generated")
    if a.open_browser:
        webbrowser.open(url)
    import uvicorn
    uvicorn.run(server.app, host=a.host, port=a.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
