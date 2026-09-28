#!/usr/bin/env bash
# Runs every automated check; prints a markdown report on stdout, exit 1 on failure.
set -u
fail=0
run() {
  local name="$1"; shift
  local out
  out=$("$@" 2>&1); local rc=$?
  if [ $rc -eq 0 ]; then echo "### ✅ $name"; else echo "### ❌ $name (exit $rc)"; fail=1; fi
  echo '```'; echo "$out" | tail -n 60; echo '```'; echo
}
echo "# CI report ($(date -u +%Y-%m-%dT%H:%M:%SZ), $(git rev-parse --short HEAD 2>/dev/null))"
echo
run "python compile" python -m compileall -q server.py studio_server.py cli.py downloader.py size_calculator.py disk_manager.py kick_extractor.py studio
run "anchored patches (server.py / editor.js / index.html)" python -m studio.patching
run "python regression tests" python -m unittest discover -s studio/tests -t . -v
run "server imports with fixes (studio.loader)" python -c "import studio.loader as l; s=l.load_server(); bad=[r for r in s._STUDIO_PATCH_REPORT if r['status']=='failed' and r['required']]; print(len(s._STUDIO_PATCH_REPORT),'patches'); assert not bad, bad"
run "web core selftest" node web/core/selftest.js
run "web audit selftest" node web/core/selftest_audit.js
for f in web/editor.js web/app.js web/studio/moments.js web/core/canvasMonitor.js web/core/text/canvasText.js; do
  [ -f "$f" ] && run "node --check $f" node --check "$f"
done
exit $fail
