# Kick Video Downloader: Audit Fixes Summary

**Total PRs Merged:** 3 (Step 1 main fixes + Step 2 Part A-B)  
**Total Commits:** ~25 (squashed into PRs)  
**Date Range:** 2026-09-28

## What Was Fixed

### ✅ Step 1: "Разблокировать" (Unblock Critical Bugs)

#### 1. Core Rendering Issues
- **composer.js**: Removed double 0.35× multiplier in speed ramp (fixes jerky freeze/ramp playback)
- **canvasText.js**: Increased max lines from 2 to 3 (prevents word loss on Russian phrases)
- **web/core/yuv.js**: Fixed chroma averaging (proper 2×2 box filter, not running average)
- **web/core/demux.js**: Fixed sync sample detection for keyframe identification
- **web/core/timeRemap.js**: Shared ramp/freeze curve (UMD-compatible)
- **web/core/decoderWorker.js**: Fixed frame index calculation (uses source FPS, not preview FPS)

#### 2. Server-Side Fixes (via patching engine)
- **Progress stream**: Fixed NameError (`**snap` → `**data`)
- **Export button**: Fixed temporal dead zone (TDZ) in editor.js
- **Download cookies**: Added to both probe and segment download (fixes 403 from Cloudflare)
- **WS render**: Rewritten stderr handling (uses temp file, no deadlock), added `-shortest`/`apad`, exact FPS
- **SSRF protection**: Playlist URL allowlisting for `/api/proxy`
- **Disk peak**: Added accounting for simultaneous segments + final MP4
- **Disk collision**: Fixed temp file naming (milliseconds → random per-launch)

#### 3. Download & CLI
- **cli.py**: Added 5% buffer calculation for disk space warning (was KeyError)
- **downloader.py**: Proper merge via ffmpeg concat with BT.709 color tags

#### 4. Dead Code Cleanup
- **Disabled exporter.js path** (browser export not implemented)
- **Removed Rust engine calls** (engine/ is frozen, never invoked)
- **Marked old ASS generator** as legacy

### ✅ Step 2: Text Rendering Improvements (Part A-B)

#### Text & Export Parity
- Speed ramp calculation corrected (§15 spec compliance)
- Text layout supports 3-line Russian phrases
- CLI disk warnings now calculate 5% safety buffer

---

## What Remains

### 🔶 Step 2 Part C: Preview Effect Visibility
**Not yet done** — requires applying zoom/whip/lens/freeze to canvas preview
- Zoom punch not visible in 9:16 monitor preview
- Whip offset not shown
- Lens distortion not applied
- Would require: new `canvasEffects.js` module + integration into `canvasMonitor.js`

### 🔶 Step 2 Part D: Unified Canvas→FFmpeg Path
**Architecture redesign** — true WYSIWYG text rendering  
- Text currently renders in preview + export differently
- Solution: Canvas layer → PNG sequence → ffmpeg overlay
- Effort: 5–7 days estimated
- **Code infrastructure exists** (studio/render_ws.py partial implementation)

### 🔶 Step 3: Template System (Hype / Story / Clean)
**Mostly coded, not activated**
- `/api/templates` endpoint exists
- `/api/templates/policy` returns effect policy
- **Missing**: Web UI dropdown, hotkey validation against policy, composition storage
- **Effort**: 1–2 days (mostly UI/integration)

### 🔶 Step 4: Auto-Moment Finding
**Fully coded, not activated**
- Audio envelope detection (spikes)
- Chat signal ranking
- Transcript keywords → LLM re-ranking
- `/api/moments` endpoint returns top-10
- **Missing**: UI integration, moment selection list, auto-fetch VOD segments
- **Effort**: 2–3 days (mostly UI/UX)

### 🔴 Lower Priority Issues Still Open

#### HLS Parser (size_calculator.py)
- Only supports avc1, no HEVC/fMP4/MPEG-TS
- No byte-range, EXT-X-MAP, discontinuity support
- Length calc from first stts sample (breaks on VFR)
- **Impact**: Low (works for most Kick streams)

#### Preview GPU Issues
- VideoFrame memory leak on scrub (close() not called)
- WebGL context loss not handled (black screen)
- No RVFC (RequestVideoFrameCallback) fallback
- **Impact**: Medium (affects responsive scrubbing)

#### Export Quality
- 8-bit grading (banding on dark streams, needs 10-bit or dither)
- No hardware encode fallback (only `libx264 slow crf16`)
- `-ss` placement not optimized (may decode whole file instead of seek)
- Two loudnorm paths (layered vs legacy) → inconsistent loudness
- **Impact**: Medium (affects YouTube/TikTok quality)

#### Download Robustness
- No resume across launches (temp folder recreated)
- Segment retry logic good, but no exponential backoff
- No parallel segment speed reporting
- **Impact**: Low (UX polish)

---

## Architecture & Code Quality

### What Was Improved
✓ Patching engine (studio/patching.py) handles large file edits safely  
✓ Server-side hooks (studio/server_hooks.py) separate concerns  
✓ Security layer (studio/security.py) enforces loopback + token-based auth  
✓ Moment finder & templates are fully deterministic, testable  
✓ WS render rewrite eliminates deadlock  

### What Still Needs Work
- Canvas rendering doesn't fully match export (effects visibility)
- No unified LUT/grade pipeline (three renderers)
- Text rendering duplicated (canvas + ASS)
- Verification suite is synthetic (no real VOD tests)

---

## Recommended Next Steps

### Phase 1: Quick Wins (3–5 days)
1. **Activate templates UI** (Step 3 integration, 1–2 days)
   - Add dropdown to editor for Hype/Story/Clean
   - Validate hotkeys against template policy
   
2. **Activate moment finder** (Step 4 integration, 2–3 days)
   - Show top-10 moments on timeline
   - Add "fetch segment" button
   
3. **Preview effect visibility** (Step 2 Part C, 2 days)
   - Integrate canvasEffects.js
   - Show zoom/whip/lens in monitor

### Phase 2: Unified Rendering (5–7 days)
- Canvas→PNG layer path (Step 2 Part D)
- Proper WYSIWYG text (major quality bump)

### Phase 3: Polish (Ongoing)
- GPU leak fixes
- Export quality improvements
- HLS parser enhancements

---

## Testing Notes

All fixes have been verified with:
- Unit tests for ramp curve, moments scoring, template policies
- Integration tests for WS render (ffmpeg command building)
- Parity checks between composer.js (export) and canvas (preview)

**No real VOD export tests yet** (verification suite uses synthetic video only).  
**Recommend**: Test with actual Kick stream before production use.

---

## Files Changed

**Core Rendering (Web)**
- web/core/render/composer.js
- web/core/text/canvasText.js
- web/core/render/canvasMonitor.js (partial, effects still TODO)
- web/core/yuv.js
- web/core/mp4/demux.js
- web/core/mp4/decoderWorker.js
- web/core/timeRemap.js

**Server (Python)**
- studio/patching.py
- studio/server_patches.py
- studio/web_patches.py
- studio/loader.py
- studio/server_hooks.py
- studio/security.py
- studio/render_ws.py
- studio/templates.py (ready)
- studio/moments.py (ready)
- studio/app.py (ready)
- studio_server.py (entry point)
- cli.py
- main.js

**Total: 20 files modified/created, ~3000 lines of code**

---

## Build & Run

```bash
python studio_server.py
# Output: listening on http://127.0.0.1:8000 with token
# Open URL in browser
```

Token changes per launch (security against hijacking).

---

**Status**: Ready for manual testing on real streams.  
**Next Blocker**: UI integration for templates/moments (Step 3-4).