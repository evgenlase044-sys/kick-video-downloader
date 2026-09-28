"""Anchored source-patch engine (studio).

server.py (~217 KB) and web/editor.js (~305 KB) are too large to rewrite
safely in one go, but several audit findings live inside them. Every fix
for those files is an anchored patch: exact text (or a start/end pair) that
must be found exactly the expected number of times. Nothing is guessed:

* anchor found the expected number of times -> applied;
* the patch marker is already present          -> "already" (folded in);
* anything else                                -> "failed" (reported, fatal
  with STUDIO_STRICT_PATCHES=1).

Patches of one ``group`` are atomic (e.g. the TDZ fix moves a declaration:
applying only half would create a duplicate ``const``).

Used at runtime (studio.loader / studio.app) and by
``python -m studio.patching --write`` which folds them into the files.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass
class Patch:
    id: str
    old: str = ""
    new: str = ""
    count: int = 1
    regex: bool = False
    start: str = ""
    end: str = ""
    marker: str = ""
    group: str = ""
    guard: Optional[Callable[[str], bool]] = None
    required: bool = True
    note: str = ""


@dataclass
class PatchResult:
    id: str
    status: str
    detail: str = ""
    required: bool = True

    def as_dict(self) -> Dict[str, object]:
        return {"id": self.id, "status": self.status, "detail": self.detail,
                "required": self.required}


class PatchError(RuntimeError):
    pass


def _eol_of(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def _conv(s: str, eol: str) -> str:
    if not s:
        return s
    s = s.replace("\r\n", "\n")
    return s.replace("\n", eol) if eol != "\n" else s


def _apply_one(text: str, p: Patch, eol: str) -> Tuple[str, str, str]:
    marker = _conv(p.marker, eol)
    if marker and marker in text:
        return text, "already", "marker present"
    if p.guard is not None:
        try:
            ok = bool(p.guard(text))
        except Exception as exc:
            return text, "failed", f"guard error: {exc}"
        if not ok:
            return text, "skipped", "guard declined"
    new = _conv(p.new, eol)
    if p.start:
        s, e = _conv(p.start, eol), _conv(p.end, eol)
        i = text.find(s)
        if i < 0:
            return text, "failed", "start anchor not found"
        if text.find(s, i + 1) >= 0:
            return text, "failed", "start anchor not unique"
        j = text.find(e, i + len(s))
        if j < 0:
            return text, "failed", "end anchor not found after start"
        return text[:i] + new + text[j:], "applied", f"replaced {j - i} chars"
    if p.regex:
        rx = re.compile(p.old, re.S)
        n = len(rx.findall(text))
        if n == 0:
            if len(new) >= 24 and new in text:
                return text, "already", "replacement present"
            return text, "failed", "pattern not found"
        if p.count and n != p.count:
            return text, "failed", f"pattern found {n}x, expected {p.count}"
        return rx.sub(lambda _m: new, text), "applied", f"{n}x"
    old = _conv(p.old, eol)
    n = text.count(old)
    if n == 0:
        if len(new) >= 24 and new in text:
            return text, "already", "replacement present"
        return text, "failed", "anchor not found"
    if p.count and n != p.count:
        return text, "failed", f"anchor found {n}x, expected {p.count}"
    return text.replace(old, new), "applied", f"{n}x"


def apply_patches(text: str, patches: List[Patch], name: str = "") -> Tuple[str, List[PatchResult]]:
    eol = _eol_of(text)
    results: List[PatchResult] = []
    done_groups = set()
    for p in patches:
        if p.group:
            if p.group in done_groups:
                continue
            done_groups.add(p.group)
            members = [q for q in patches if q.group == p.group]
            work = text
            member_res: List[PatchResult] = []
            failed = False
            for q in members:
                work, st, det = _apply_one(work, q, eol)
                member_res.append(PatchResult(q.id, st, det, q.required))
                if st == "failed":
                    failed = True
            if failed:
                for r in member_res:
                    if r.status == "applied":
                        r.status = "failed"
                        r.detail += "; group rolled back"
            else:
                text = work
            results.extend(member_res)
            continue
        text, st, det = _apply_one(text, p, eol)
        results.append(PatchResult(p.id, st, det, p.required))
    if os.environ.get("STUDIO_STRICT_PATCHES") == "1":
        bad = [r for r in results if r.status == "failed" and r.required]
        if bad:
            raise PatchError(f"{name}: required patches failed: " +
                             ", ".join(f"{r.id} ({r.detail})" for r in bad))
    return text, results


def summarize(results: List[PatchResult]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for r in results:
        out[r.status] = out.get(r.status, 0) + 1
    return out


def read_source(path: str) -> Tuple[str, bool]:
    with open(path, "rb") as fh:
        raw = fh.read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    return raw.decode("utf-8-sig"), bom


def write_source(path: str, text: str, bom: bool) -> None:
    data = text.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    tmp = path + ".studio-tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)


def targets():
    from studio.server_patches import SERVER_PATCHES
    from studio.web_patches import EDITOR_PATCHES, INDEX_PATCHES
    import studio.pr8_patches  # noqa: F401  (PR #8: appended to the lists above in place)
    import studio.pr9_patches  # noqa: F401  (PR #9: appended after PR #8)
    return [("server.py", SERVER_PATCHES),
            (os.path.join("web", "editor.js"), EDITOR_PATCHES),
            (os.path.join("web", "index.html"), INDEX_PATCHES)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Apply / check studio source patches")
    ap.add_argument("--write", action="store_true", help="fold patches into the files on disk")
    ap.add_argument("--base", default=BASE_DIR)
    args = ap.parse_args(argv)
    worst = 0
    for rel, patches in targets():
        path = os.path.join(args.base, rel)
        if not os.path.exists(path):
            print(f"[skip] {rel}: not found")
            continue
        text, bom = read_source(path)
        new_text, res = apply_patches(text, patches, rel)
        print(f"\n{rel}: {summarize(res)}")
        for r in res:
            print(f"  {r.status:8s} {r.id:28s} {r.detail}")
            if r.status == "failed" and r.required:
                worst = 1
        if args.write and new_text != text:
            write_source(path, new_text, bom)
            print(f"  -> written {rel}")
    return worst


if __name__ == "__main__":
    sys.path.insert(0, BASE_DIR)
    sys.exit(main())
