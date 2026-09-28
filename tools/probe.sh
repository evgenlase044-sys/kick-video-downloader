#!/usr/bin/env bash
# Temporary source probe (removed in the next commit).
echo "# PROBE"
node tools/probe.js web/editor.js collectRegionSubtitles collectRegionTextItems collectRegionFx requestServerPreviewFrame tidOfFx
echo '#### initClipperPanel head'; echo '```'; grep -n "function initClipperPanel" web/editor.js; n=$(grep -n "function initClipperPanel" web/editor.js | head -1 | cut -d: -f1); sed -n "${n},$((n+12))p" web/editor.js | cat -A | cut -c1-200; echo '```'
for w in collectRegionSubtitles collectRegionTextItems collectRegionFx requestServerPreviewFrame tidOfFx CoreTimeMap faceAnchor studioSourceToTimeline "anchor"; do
  echo "#### grep $w"; echo '```'; grep -n "$w" web/editor.js | cut -c1-220 | head -40; echo '```'
done
echo '#### core files'; echo '```'; ls -la web/core web/core/render web/studio; echo '```'
echo '#### grep CoreTimeMap / faceAnchor in web/core'; echo '```'; grep -rn "CoreTimeMap\|faceAnchor\|audioClock\|masterClock" web/core web/studio web/index.html | cut -c1-220 | head -40; echo '```'
echo '#### grep glPasses/exporter.js'; echo '```'; grep -rn "glPasses\|exporter.js\|timeMap.js" web --include=*.html --include=*.js | cut -c1-200 | head -20; echo '```'
echo '#### server.py _apply_fx_chain'; echo '```py'; python3 - <<'PY'
import re
src=open("server.py",encoding="utf-8-sig").read().replace("\r","")
for name in ["_apply_fx_chain"]:
    m=re.search(r"^def "+name+r"\(.*?(?=^\S)", src, re.S|re.M)
    if m:
        print("# line", src[:m.start()].count("\n")+1)
        print(m.group(0))
PY
echo '```'
echo '#### grep server anchor / _tv_grade_parts / text_z'; echo '```'; grep -n "anchor\|_tv_grade_parts\|text_z\|def _export_layered_clip\|zoompan" server.py | cut -c1-220 | head -60; echo '```'
