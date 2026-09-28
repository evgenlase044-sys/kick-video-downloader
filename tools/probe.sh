#!/usr/bin/env bash
# Temporary source probe #2 (removed in the next commit).
echo "# PROBE 2"
node tools/probe.js web/editor.js ensureFxTrack addFxClip fxLabel resolvePackSource isTextClip hideServerPreviewFrame trackPosAt
sec() { echo "#### $1 lines $2-$3"; echo '```'; awk -v a="$2" -v b="$3" 'NR>=a && NR<=b {printf "%d|%s\n", NR, $0}' "$1"; echo '```'; }
sec web/editor.js 3405 3424
sec web/editor.js 3540 3580
sec web/editor.js 1740 1752
sec web/editor.js 1800 1870
sec web/editor.js 3930 3943
sec web/editor.js 4015 4030
sec web/core/canvasMonitor.js 280 330
echo "#### grep pvTimer / token in editor"; echo '```'; grep -n "pvTimer\|dataset.token\|\btoken\b" web/editor.js | cut -c1-200 | head; echo '```'
echo "#### grep lensPunch in lens.js"; echo '```'; grep -n "unction\|punch\|Punch" web/core/render/lens.js | cut -c1-200 | head -40; echo '```'
node tools/probe.js web/core/render/lens.js lensPunchK1 punchK1 lensPunch
echo "#### templates anchor"; echo '```'; grep -n "anchor" studio/templates.py studio/*.py web/studio/*.js | cut -c1-220 | head -30; echo '```'
python3 - <<'PY'
import re
src=open("server.py",encoding="utf-8-sig").read().replace("\r","")
def cls(name):
    m=re.search(r"^class "+name+r"\b.*?(?=^\S)", src, re.S|re.M)
    print("#### class", name); print("```py")
    if m: print("# line", src[:m.start()].count("\n")+1); print(m.group(0))
    print("```")
for n in ["FxOverlay","PreviewFrameRequest"]: cls(n)
lines=src.split("\n")
def show(a,b,t):
    print("####",t); print("```py")
    for i in range(a-1,min(b,len(lines))): print(f"{i+1}|{lines[i]}")
    print("```")
show(2000,2035,"clip model around text_z")
show(3360,3380,"_export_layered_clip text_z")
for i,l in enumerate(lines):
    if "_apply_fx_chain(" in l or "preview-frame" in l or "def _tv_grade_parts" in l: print(f"HIT {i+1}|{l[:200]}")
PY
