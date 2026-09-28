"""High-precision grade chain for the export (replaces server._tv_grade_parts).

Old chain (8 bit, LUT at 100 %):
    setparams(tags only) -> lut3d trilinear -> cas -> format=gbrp
New chain, order from the audit (§5 "Цветокор"):
    1. explicit BT.709 conversion (scale with in/out matrix, not just tags)
    2. light chroma denoise (hqdn3d, chroma planes only) BEFORE any sharpening
    3. float RGB (gbrpf32le) -> creative LUT (tetrahedral) blended at
       30-60 % strength (template), never 100 %
    4. light CAS sharpen at the end, output gbrp16le: text/FX are drawn on a
       16-bit surface and the single final yuv420p conversion dithers once.
Every filter used here exists in ffmpeg >= 5.0 builds (checked by tests).
"""
import itertools
import os

_counter = itertools.count()

DEFAULT_STRENGTH = 0.6


def escape_filter_path(path):
    """Path for a filtergraph option value: forward slashes, escaped drive colon."""
    p = str(path).replace("\\", "/")
    p = p.replace("'", r"'\''")
    return p.replace(":", r"\:")


def lut_strength(opts=None):
    env = os.environ.get("STUDIO_LUT_STRENGTH")
    val = None
    if opts and opts.get("grade_strength") is not None:
        val = opts.get("grade_strength")
    elif env:
        val = env
    try:
        s = float(val) if val is not None else DEFAULT_STRENGTH
    except (TypeError, ValueError):
        s = DEFAULT_STRENGTH
    return max(0.0, min(1.0, s))


def grade_chain(src, dst, lut_path=None, strength=DEFAULT_STRENGTH, matrix="bt709",
                denoise=True, sharpen=0.25):
    """Return a list with ONE filter_complex fragment ``{src}...{dst}``."""
    n = next(_counter)
    a, b, l = f"[sg{n}a]", f"[sg{n}b]", f"[sg{n}l]"
    m = "bt709" if matrix not in ("bt601", "bt470bg", "smpte170m") else "bt601"
    parts = []
    tag = "setparams=range=tv:colorspace=bt709:color_primaries=bt709:color_trc=bt709," if m == "bt709" else ""
    parts.append(f"{tag}scale=out_color_matrix={m}:out_range=tv:flags=accurate_rnd+full_chroma_int+full_chroma_inp,"
                 "format=yuv444p16le")
    if denoise:
        parts.append("hqdn3d=luma_spatial=0:chroma_spatial=2.5:luma_tmp=0:chroma_tmp=3")
    parts.append(f"scale=in_color_matrix={m}:in_range=tv:out_range=pc:flags=accurate_rnd+full_chroma_int,"
                 "format=gbrpf32le")
    head = ",".join(parts)
    tail = f"format=gbrp16le,cas={sharpen:.2f}" if sharpen and sharpen > 0 else "format=gbrp16le"
    s = max(0.0, min(1.0, float(strength)))
    if lut_path and os.path.exists(lut_path) and s <= 0.001:
        return [f"{src}{head},{tail}{dst}"]
    if lut_path and os.path.exists(lut_path):
        lut = f"lut3d=file='{escape_filter_path(lut_path)}':interp=tetrahedral"
        if s >= 0.999:
            return [f"{src}{head},{lut},{tail}{dst}"]
        return [f"{src}{head},split=2{a}{b};{b}{lut}{l};"
                f"{l}{a}blend=all_mode=normal:all_opacity={s:.3f},{tail}{dst}"]
    curve = "curves=m='0/0 0.25/0.23 0.5/0.51 0.75/0.77 1/1'"
    return [f"{src}{head},{curve},{tail}{dst}"]
