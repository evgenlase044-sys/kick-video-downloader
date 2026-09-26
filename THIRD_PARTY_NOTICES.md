# Third-Party Notices

Kick Clip Studio is licensed under the MIT License (see `LICENSE`). This file lists
all bundled assets and external dependencies with their licenses.

## Bundled assets

### Fonts (`fonts/*.ttf`)
All bundled font families are Google Fonts released under the **SIL Open Font License 1.1 (OFL)**.
Per-family copyright and license texts live in `fonts/LICENSES/<family>.txt`.
The application configures `fontconfig` to prefer the bundled fonts (`fonts/fonts.conf`).
Proprietary system fonts (Impact, Arial Black, …) are **not** bundled.

### Sound effects (`sfx/*.mp3`)
All 18 SFX files are **generated procedurally** by `tools/gen_sfx.py` (numpy synthesis,
encoded with FFmpeg) and released by this project under **CC0 1.0 (Public Domain)**.
Origin and regeneration command for each file: `sfx/CREDITS.md`.
No third-party samples are redistributed.

### Color LUT (`tv_grade.cube`)
Rebuilt by `tools/gen_tv_lut.py` from the project's own analytic preset —
original work of this project, licensed under the project MIT License.

## Runtime dependencies

| Component | License | Notes |
|---|---|---|
| Electron (dev) | MIT | bundles Chromium (BSD-style) and FFmpeg (LGPL 2.1+); Electron ships its own notices |
| FastAPI | MIT | |
| pydantic | MIT | |
| python-multipart | Apache-2.0 | FastAPI form parsing |
| uvicorn | BSD-3-Clause | |
| rich | MIT | |
| fontTools | MIT | |
| numpy | BSD-3-Clause | |
| opencv-python | Apache-2.0 | wheels bundle FFmpeg (LGPL 2.1+); template matching (CPU CV only, no neural nets) |
| requests | Apache-2.0 | |
| FFmpeg | external system dependency, LGPL/GPL build | not bundled; invoked as a separate process |

## Build/dev-time dependencies (optional)

| Component | License |
|---|---|
| Rust crates (`engine/`, frozen): ab_glyph, anyhow, rayon, serde, serde_json, image | MIT / Apache-2.0 |

## Fonts reference
- Google Fonts: https://fonts.google.com — SIL OFL 1.1 texts: https://openfontlicense.org

## Sound effects
- Generated with `tools/gen_sfx.py` (this repository) — CC0 1.0: https://creativecommons.org/publicdomain/zero/1.0/

## Speech-to-text
- Subtitles use the **Groq Cloud API** (`whisper-large-v3-turbo` / `whisper-large-v3`) with the
  user's own API key. Audio is sent to Groq only when the user presses the "Subtitles" action,
  and only for the selected fragment. No local ASR models are used or bundled.
