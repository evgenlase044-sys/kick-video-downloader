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
run "python compile" python -m compileall -q server.py studio_server.py cli.py downloader.py size_calculator.py disk_manager.py kick_extractor.py chat_recorder.py studio
run "anchored patches (server.py / editor.js / index.html)" python -m studio.patching
run "python regression tests" python -m unittest discover -s studio/tests -t . -v
run "server imports with fixes (studio.loader)" python -c "import studio.loader as l; s=l.load_server(); bad=[r for r in s._STUDIO_PATCH_REPORT if r['status']=='failed' and r['required']]; print(len(s._STUDIO_PATCH_REPORT),'patches'); assert not bad, bad"
run "export pipeline installs into the real server" python -c "import studio.loader as l, studio.export_pipeline as E; s=l.load_server(); i=E.install(s); print(i); assert i.get('grade') and i.get('encoder_shim') and i.get('export_route') and i.get('loudness_gate'), i"
run "studio API exposes chat recording (PR #10)" python -c "import studio.api as A; r=A.build_router('downloads'); p={x.path for x in r.routes}; print(sorted(p)); assert {'/api/studio/chat/record','/api/studio/chat/stop','/api/studio/chat/status'} <= p, p"
run "web core selftest" node web/core/selftest.js
run "web audit selftest" node web/core/selftest_audit.js
run "overlay export selftest" node web/studio/selftest_overlay.js
for f in web/editor.js web/app.js web/studio/moments.js web/studio/overlay_export.js web/core/canvasMonitor.js web/core/text/canvasText.js web/core/render/glPasses.js; do
  [ -f "$f" ] && run "node --check $f" node --check "$f"
done
exit $fail
