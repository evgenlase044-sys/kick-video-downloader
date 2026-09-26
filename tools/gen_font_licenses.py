#!/usr/bin/env python3
"""Generate fonts/LICENSES/<family>.txt for every TTF in fonts/.

License metadata is extracted from the TTF name table (copyright, designer,
license description, license URL), so the files always match the bundled
binaries. Every Google Font used here is expected to report SIL OFL 1.1;
the script fails loudly if a font claims a different license.
"""
import os
import sys

from fontTools.ttLib import TTFont

FONTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")
OUT_DIR = os.path.join(FONTS_DIR, "LICENSES")

NAME_IDS = {0: "Copyright", 7: "Trademark", 8: "Manufacturer", 9: "Designer",
            13: "License Description", 14: "License URL"}


def name_table(font):
    out = {}
    best = font["name"]
    for nid, label in NAME_IDS.items():
        recs = best.getName(nid, 3, 1, 0x409) or best.getName(nid, 1, 0, 0)
        if recs:
            out[label] = str(recs).replace("\r", "\n").strip()
    return out


def family_of(font):
    rec = (font["name"].getName(16, 3, 1, 0x409) or font["name"].getName(1, 3, 1, 0x409)
           or font["name"].getName(16, 1, 0, 0) or font["name"].getName(1, 1, 0, 0))
    return str(rec).strip() if rec else "Unknown"


def license_of(meta):
    desc = meta.get("License Description", "")
    url = meta.get("License URL", "")
    low = (desc + " " + url).lower()
    if "open font" in low or "ofl" in low or "fonts.google.com" in low:
        return "SIL Open Font License 1.1"
    if desc or url:
        return "UNKNOWN: %s (%s)" % (desc[:120], url)
    return "UNKNOWN: no license record in name table"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    ttfs = sorted(f for f in os.listdir(FONTS_DIR) if f.lower().endswith((".ttf", ".otf")))
    if not ttfs:
        print("no fonts found in", FONTS_DIR)
        return 1
    problems = []
    written = []
    for fn in ttfs:
        path = os.path.join(FONTS_DIR, fn)
        try:
            font = TTFont(path, fontNumber=0, lazy=True)
            meta = name_table(font)
            family = family_of(font)
        except Exception as exc:  # unreadable font -> keep name-based fallback
            problems.append("%s: unreadable (%s)" % (fn, exc))
            family = os.path.splitext(os.path.basename(fn))[0]
            meta = {}
        lic = license_of(meta)
        if "UNKNOWN" in lic:
            problems.append("%s: %s" % (fn, lic))
        slug = "".join(c if c.isalnum() else "_" for c in family).strip("_") or "Unknown"
        out_path = os.path.join(OUT_DIR, slug + ".txt")
        lines = [
            "Font family: %s" % family,
            "Bundled file: fonts/%s" % fn,
            "Source: Google Fonts (https://fonts.google.com)",
            "License: %s" % lic,
            "License URL: https://openfontlicense.org",
            "",
        ]
        if meta.get("Copyright"):
            lines += [meta["Copyright"], ""]
        if meta.get("Designer"):
            lines += ["Designer: %s" % meta["Designer"], ""]
        if meta.get("Manufacturer"):
            lines += ["Manufacturer: %s" % meta["Manufacturer"], ""]
        if meta.get("License Description"):
            lines += ["License record embedded in the font:", meta["License Description"], ""]
        if meta.get("License URL"):
            lines += ["License URL (embedded): %s" % meta["License URL"], ""]
        lines += [
            "This font is bundled with Kick Clip Studio under the terms above.",
            "OFL 1.1 permits bundling and redistribution; sellling the font on its own",
            "and using Reserved Font Names for modified versions is not allowed.",
        ]
        with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines))
        written.append("%s -> %s" % (fn, os.path.basename(out_path)))
    print("wrote %d license files:" % len(written))
    for w in written:
        print("  ", w)
    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print("  !", p)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
