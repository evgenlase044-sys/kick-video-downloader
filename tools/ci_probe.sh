#!/usr/bin/env bash
# Temporary probe: shows the folded regions touched by PR #7.
set -u
sec() { echo; echo "#### $1"; echo '```'; }
end() { echo '```'; }
E=web/editor.js; S=server.py
sec "editor.js from studio:addfx-v2 to EOF"; n=$(grep -n "studio:addfx-v2" $E | head -1 | cut -d: -f1); [ -n "$n" ] && sed -n "${n},\$p" $E; end
sec "editor.js flash hotkey"; grep -n 'addEffectAtPlayhead("flash"' $E; end
sec "editor.js addFxClip head"; n=$(grep -n "function addFxClip" $E | head -1 | cut -d: -f1); [ -n "$n" ] && sed -n "${n},$((n+40))p" $E; end
sec "server.py check_disk"; n=$(grep -n "^def check_disk" $S | head -1 | cut -d: -f1); [ -n "$n" ] && sed -n "${n},$((n+7))p" $S; end
sec "server.py __main__"; n=$(grep -n '^if __name__ == "__main__"' $S | head -1 | cut -d: -f1); [ -n "$n" ] && sed -n "${n},\$p" $S; end
