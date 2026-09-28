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
import studio.pr8_patches  # noqa: E402,F401  (PR #8: appended to SERVER_PATCHES in place)

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
