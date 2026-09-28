"""Anchored fixes for web/editor.js and web/index.html."""
from studio.patching import Patch

EDITOR_PATCHES = [
    # §1 TDZ: exportPackBtn read before `const exportPackBtn` -> export init died
    Patch(id="tdz-declare-early", group="tdz",
          old="        const queueExportBtn = document.createElement(\"button\");\n",
          new=("        // studio:tdz-exportPackBtn - declared before its first use\n"
               "        const exportPackBtn = document.getElementById(\"exportPackBtn\");\n"
               "        const queueExportBtn = document.createElement(\"button\");\n"),
          marker="studio:tdz-exportPackBtn"),
    Patch(id="tdz-drop-late", group="tdz",
          old=("        const addHighlightBtn = document.getElementById(\"addHighlightToPackBtn\");\n"
               "        const exportPackBtn = document.getElementById(\"exportPackBtn\");\n"),
          new=("        const addHighlightBtn = document.getElementById(\"addHighlightToPackBtn\");\n"
               "        // (exportPackBtn is declared above - studio:tdz-late-removed)\n"),
          marker="studio:tdz-late-removed"),
    Patch(id="queue-sse-reconnect", required=False,
          old=("            queueES.onerror = () => {\n"
               "                if (queueES) { queueES.close(); queueES = null; }\n"
               "            };\n"),
          new=("            queueES.onerror = () => {\n"
               "                // studio:queue-sse-reconnect\n"
               "                if (queueES) { queueES.close(); queueES = null; }\n"
               "                setTimeout(() => {\n"
               "                    fetch(\"/api/export-queue/status\").then(r => r.json()).then(st => {\n"
               "                        if (st && st.running && !queueES) listenExportQueue();\n"
               "                    }).catch(() => {});\n"
               "                }, 1500);\n"
               "            };\n"),
          marker="studio:queue-sse-reconnect"),
]

INDEX_PATCHES = [
    # §2 unreachable browser exporter: frozen, not loaded
    Patch(id="drop-dead-exporter", required=False, regex=True, count=0,
          old=r"[ \t]*<script[^>]*src=[\"'][^\"']*core/render/exporter\.js[^\"']*[\"'][^>]*>\s*</script>[ \t]*\r?\n?",
          new=""),
    Patch(id="timeremap-script", required=False, regex=True, count=1,
          old=r"(?=<script[^>]*src=[\"'][^\"']*core/canvasMonitor\.js)",
          new="<script src=\"core/timeRemap.js\"></script><!-- studio:timeremap-script -->\n    ",
          marker="studio:timeremap-script"),
    # preview fx use the SAME zoom curve as the export (CoreEffects)
    Patch(id="effects-script", required=False, regex=True, count=1,
          guard=lambda src: "core/render/effects.js" not in src,
          old=r"(?=<script[^>]*src=[\"'][^\"']*core/canvasMonitor\.js)",
          new="<script src=\"core/render/effects.js\"></script><!-- studio:effects-script -->\n    ",
          marker="studio:effects-script"),
    # §6 moment finder + §7 templates panel
    Patch(id="moments-panel", required=False, regex=True, count=1,
          old=r"(?=</body>)",
          new="<script src=\"studio/moments.js\"></script><!-- studio:moments-panel -->\n",
          marker="studio:moments-panel"),
    # §2 one text renderer: canvas text layer for the export, key words, emoji,
    # export templates, Backspace guard (web/studio/overlay_export.js)
    Patch(id="overlay-export", required=False, regex=True, count=1,
          old=r"(?=</body>)",
          new="<script src=\"studio/overlay_export.js\"></script><!-- studio:overlay-export -->\n",
          marker="studio:overlay-export"),
]
