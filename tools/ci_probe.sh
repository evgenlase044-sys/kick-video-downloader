#!/usr/bin/env bash
# Temporary recon probe: prints exact source regions of the two huge files.
set -u
sec() { echo; echo "#### $1"; echo '```'; }
end() { echo '```'; }
E=web/editor.js; S=server.py
sec "editor.js definitions"; grep -n -E "function (addEffectAtPlayhead|ensureFxTrack|fxLabel|showToast|saveProject|showConfirm|nearestCutTo|currentBaseClip|baseClipAt)\b" $E; end
sec "editor.js addEffectAtPlayhead body"; n=$(grep -n "function addEffectAtPlayhead" $E | head -1 | cut -d: -f1); [ -n "$n" ] && sed -n "${n},$((n+75))p" $E; end
sec "editor.js ensureFxTrack body"; n=$(grep -n "function ensureFxTrack" $E | head -1 | cut -d: -f1); [ -n "$n" ] && sed -n "${n},$((n+25))p" $E; end
sec "editor.js fxLabel body"; n=$(grep -n "function fxLabel" $E | head -1 | cut -d: -f1); [ -n "$n" ] && sed -n "${n},$((n+20))p" $E; end
sec "editor.js hotkeys addEffectAtPlayhead calls"; grep -n "addEffectAtPlayhead(" $E; end
sec "editor.js clock / master"; grep -n -i -E "masterclock|audioclock|MasterClock|CoreTimeMap\." $E | head -40; end
sec "editor.js video base clip helpers (sourceOffset mapping)"; grep -n -E "function (firstVideoTrackId|clipAtTime|videoClipAt|findClipAt|activeVideoClip)" $E; end
sec "editor.js tail from Studio Integrations"; n=$(grep -n "Studio Integrations" $E | head -1 | cut -d: -f1); [ -n "$n" ] && sed -n "${n},\$p" $E; end
sec "server.py __main__ to EOF"; n=$(grep -n '^if __name__ == "__main__"' $S | head -1 | cut -d: -f1); [ -n "$n" ] && sed -n "${n},\$p" $S; end
sec "server.py _two_pass_loudnorm"; grep -n "_two_pass_loudnorm" $S; n=$(grep -n "def _two_pass_loudnorm" $S | head -1 | cut -d: -f1); [ -n "$n" ] && sed -n "${n},$((n+45))p" $S; end
sec "server.py loudnorm occurrences"; grep -n "loudnorm" $S; end
sec "server.py export_clip_pack audio block"; n=$(grep -n 'concat=n={n_seg}:v=0:a=1,loudnorm' $S | head -1 | cut -d: -f1); [ -n "$n" ] && sed -n "$((n-45)),$((n+40))p" $S; end
sec "server.py -ss usages"; grep -n '"-ss"' $S; end
sec "server.py _export_layered_clip head"; n=$(grep -n "def _export_layered_clip" $S | head -1 | cut -d: -f1); [ -n "$n" ] && sed -n "${n},$((n+30))p" $S; end
sec "server.py defs"; grep -n -E "^def (_source_has_audio|_tv_grade_parts|export_clip_pack|_export_layered_clip|check_disk)|^class (CheckDiskRequest|ExportClipItem)" $S; end
sec "server.py export_clip_pack inputs"; n=$(grep -n "^def export_clip_pack" $S | head -1 | cut -d: -f1); [ -n "$n" ] && grep -n -E 'inputs \+?= |inputs\.(append|extend)' $S | awk -F: -v a=$n '$1>a' | head -20; end
sec "disk_manager.check_space signature"; grep -n -A6 "def check_space" disk_manager.py; end
sec "studio/loader.py"; cat studio/loader.py; end
