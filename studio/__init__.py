"""Kick Clip Studio - audit fixes and new backend features.

Modules:
  patching / server_patches / web_patches / loader  - anchored fixes for the
      two oversized files (server.py, web/editor.js), applied on load and
      foldable into the files with `python -m studio.patching --write`;
  security    - token / Host / Origin middleware, path + SSRF guards;
  render_ws   - fixed /ws/render implementation;
  ffmpeg_caps - encoder presets (NVENC when usable, else x264), probes;
  timeremap   - freeze / speed-ramp curve shared with the web preview;
  moments     - moment finder (audio + chat + transcript + optional LLM);
  templates   - Hype / Story / Clean templates with effect policy;
  app         - installs all of the above into server.app.
"""
