"""PR #9 anchored fixes for server.py (docs/REMAINING_FIXES.md section 1).

* lens-v2: Lens Punch = lens.js kernel (k1 mapped to ffmpeg units, auto-overscan
  -> no dark corners, chromashift in YUV instead of rgbashift). Keeps the
  PR #8 marker text so lens-anim reports "already".
* zoom-mblur / whip-mblur: motion blur only on the motion interval.
* grade-bands-*: split layout graded per band, skin protect on the facecam band.
"""
from studio.patching import Patch

LENS_V2 = r'''        elif fx.kind == "lens":
            # studio:lens-v2 (supersedes studio:lens-anim) - lens.js kernel,
            # auto-overscan, YUV chroma shift; enable-gated steps. See studio/fx_extra.py
            _lp, curr_v = _studio.lens_punch_parts(curr_v, f"{tag_prefix}v{fi}", s0, e0, fx.peak, out_w, out_h)
            filter_parts.extend(_lp)
'''

ZOOM_MBLUR_OLD = '            curr_v = f"[{tag_prefix}v{fi}]"\n        elif fx.kind == "lens":\n'
ZOOM_MBLUR_NEW = ('            curr_v = f"[{tag_prefix}v{fi}]"\n'
                  '            # studio:zoom-mblur - trail only while the punch moves\n'
                  '            _zb0, _zb1 = _studio.zoom_blur_window(s0, e0)\n'
                  '            _mb, curr_v = _studio.motion_blur_parts(curr_v, f"{tag_prefix}v{fi}z", _zb0, _zb1)\n'
                  '            filter_parts.extend(_mb)\n'
                  '        elif fx.kind == "lens":\n')

WHIP_TAIL = ('f"[{tag_prefix}v{fi}a][{tag_prefix}v{fi}s]overlay=x=0:y=0:enable={en}[{tag_prefix}v{fi}]")\n'
             '            curr_v = f"[{tag_prefix}v{fi}]"\n')
WHIP_NEXT = '        elif fx.kind in ("ramp", "freeze"):'
WHIP_NEW = (WHIP_TAIL +
            '            # studio:whip-mblur - directional smear across the whip\n'
            '            _mb, curr_v = _studio.motion_blur_parts(curr_v, f"{tag_prefix}v{fi}w", s0, e0, 6)\n'
            '            filter_parts.extend(_mb)\n' + WHIP_NEXT)

PR9_SERVER_PATCHES = [
    Patch(id="zoom-mblur", required=False, old=ZOOM_MBLUR_OLD, new=ZOOM_MBLUR_NEW, marker="studio:zoom-mblur"),
    Patch(id="lens-v2", required=False,
          start="        elif fx.kind == \"lens\":\n",
          end="        elif fx.kind == \"threshold\":\n",
          new=LENS_V2, marker="studio:lens-v2"),
    Patch(id="whip-mblur", required=False, old=WHIP_TAIL + WHIP_NEXT, new=WHIP_NEW, marker="studio:whip-mblur"),
    Patch(id="grade-bands-layered", required=False,
          old='        filter_parts.extend(_tv_grade_parts(comp, "[graded]", is_vertical=(out_w < out_h)))\n',
          new=('        filter_parts.extend(_studio.grade_bands(_tv_grade_parts, comp, "[graded]", out_w, out_h, '
               '_studio.split_top_h(locals())))  # studio:grade-bands-layered\n'),
          marker="studio:grade-bands-layered"),
    Patch(id="grade-bands-pack", required=False,
          old='            filter_parts.extend(_tv_grade_parts(curr_v, "[graded]", is_vertical=(out_w < out_h)))\n',
          new=('            filter_parts.extend(_studio.grade_bands(_tv_grade_parts, curr_v, "[graded]", out_w, out_h, '
               '_studio.split_top_h(locals())))  # studio:grade-bands-pack\n'),
          marker="studio:grade-bands-pack"),
    Patch(id="grade-bands-preview", required=False,
          old='            fp.extend(_tv_grade_parts(comp, "[graded]", is_vertical=(W < H)))\n',
          new=('            fp.extend(_studio.grade_bands(_tv_grade_parts, comp, "[graded]", W, H, '
               '_studio.split_top_h(locals())))  # studio:grade-bands-preview\n'),
          marker="studio:grade-bands-preview"),
]


def install() -> None:
    from studio import server_patches as SP
    have = {p.id for p in SP.SERVER_PATCHES}
    SP.SERVER_PATCHES.extend(p for p in PR9_SERVER_PATCHES if p.id not in have)


import studio.pr8_patches  # noqa: E402,F401  (PR #8 first: order matters)
install()
