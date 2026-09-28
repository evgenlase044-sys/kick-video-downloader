#!/usr/bin/env bash
# Temporary source probe #2 for PR #9 recon (removed before merge).
echo "# PROBE PR9 #2"
sec() { echo "#### $1 lines $2-$3"; echo '```'; awk -v a="$2" -v b="$3" 'NR>=a && NR<=b {printf "%d|%s\n", NR, $0}' "$1"; echo '```'; }
sec web/editor.js 1808 1915
sec web/editor.js 2235 2306
sec web/editor.js 2019 2060
sec server.py 3353 3400
sec server.py 3605 3700
sec server.py 4411 4440
echo "#### grep top_h"; echo '```'; grep -n "top_h =\|top_h=\|bot_h =" server.py web/editor.js web/core/*.js web/studio/*.js | cut -c1-200; echo '```'
echo "#### grep splitTop/topFrac"; echo '```'; grep -rn "topFrac\|TOP_FRAC\|split_adhd" web/editor.js web/core/canvasMonitor.js web/core/composition.js web/core/geometry.js | cut -c1-200 | head -30; echo '```'
echo "#### grep lens in canvasMonitor"; echo '```'; grep -n "lens\|Lens" web/core/canvasMonitor.js | cut -c1-200; echo '```'
echo "#### ffmpeg filters"; echo '```'; ffmpeg -hide_banner -filters 2>/dev/null | grep -E " (hsvkey|chromashift|tmix|lenscorrection|remap|colorkey|maskedmerge) " ; ffmpeg -version | head -1; echo '```'
