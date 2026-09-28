#!/usr/bin/env bash
# Temporary probe: shows the folded regions touched by PR #7 (round 2).
set -u
sec() { echo; echo "#### $1"; echo '```'; }
end() { echo '```'; }
E=web/editor.js
sec "editor.js addEffectAtPlayhead"; n=$(grep -n "function addEffectAtPlayhead" $E | head -1 | cut -d: -f1); [ -n "$n" ] && sed -n "${n},$((n+26))p" $E; end
sec "editor.js fx ids + studioAddFx loop"; grep -n -E "studio:fx-unique-id|studio:addfx-count|studio:addfx-fxtrack|tidOfFx\(\)" $E; end
