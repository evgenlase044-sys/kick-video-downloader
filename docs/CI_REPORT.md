## Fold log
```

server.py: {'already': 25, 'applied': 2, 'skipped': 1}
  already  hooks-import                 marker present
  already  progress-nameerror           marker present
  already  cookies-range                marker present
  already  cookies-full                 marker present
  already  cookies-download             marker present
  already  ssrf-guard                   marker present
  already  ssrf-remember                marker present
  already  disk-peak                    marker present
  applied  check-disk-peak              1x
  already  fps-exact-init               marker present
  already  fps-exact-probe              marker present
  already  fps-exact-return             marker present
  already  asr-tempid                   marker present
  already  asr-shortwords               marker present
  already  no-abs-paths-file            marker present
  already  no-abs-paths-src             marker present
  already  import-guard                 marker present
  already  sfx-aliases                  marker present
  already  sfx-labels                   marker present
  already  queue-forward-ref            marker present
  already  queue-parse                  marker present
  already  ws-render                    marker present
  already  fx-timeremap                 marker present
  already  whip-clamp                   marker present
  already  whip-clamp-x                 marker present
  skipped  dead-ass-generator           guard declined
  already  version-mtime                marker present
  applied  main-secure                  1x
  -> written server.py

web/editor.js: {'already': 3, 'applied': 3}
  already  tdz-declare-early            marker present
  already  tdz-drop-late                marker present
  already  queue-sse-reconnect          marker present
  applied  addfx-v2                     replaced 1494 chars
  applied  addfx-source                 1x
  applied  flash-fxpeak                 1x
  -> written web/editor.js

web/index.html: {'skipped': 2, 'already': 3}
  skipped  drop-dead-exporter           guard declined
  already  timeremap-script             marker present
  skipped  effects-script               guard declined
  already  moments-panel                marker present
  already  overlay-export               marker present
```

# CI report (2026-09-28T05:27:37Z, 2909285)

### ✅ python compile
```

```

### ✅ anchored patches (server.py / editor.js / index.html)
```

server.py: {'already': 27, 'skipped': 1}
  already  hooks-import                 marker present
  already  progress-nameerror           marker present
  already  cookies-range                marker present
  already  cookies-full                 marker present
  already  cookies-download             marker present
  already  ssrf-guard                   marker present
  already  ssrf-remember                marker present
  already  disk-peak                    marker present
  already  check-disk-peak              marker present
  already  fps-exact-init               marker present
  already  fps-exact-probe              marker present
  already  fps-exact-return             marker present
  already  asr-tempid                   marker present
  already  asr-shortwords               marker present
  already  no-abs-paths-file            marker present
  already  no-abs-paths-src             marker present
  already  import-guard                 marker present
  already  sfx-aliases                  marker present
  already  sfx-labels                   marker present
  already  queue-forward-ref            marker present
  already  queue-parse                  marker present
  already  ws-render                    marker present
  already  fx-timeremap                 marker present
  already  whip-clamp                   marker present
  already  whip-clamp-x                 marker present
  skipped  dead-ass-generator           guard declined
  already  version-mtime                marker present
  already  main-secure                  marker present

web/editor.js: {'already': 6}
  already  tdz-declare-early            marker present
  already  tdz-drop-late                marker present
  already  queue-sse-reconnect          marker present
  already  addfx-v2                     marker present
  already  addfx-source                 marker present
  already  flash-fxpeak                 marker present

web/index.html: {'skipped': 2, 'already': 3}
  skipped  drop-dead-exporter           guard declined
  already  timeremap-script             marker present
  skipped  effects-script               guard declined
  already  moments-panel                marker present
  already  overlay-export               marker present
```

### ❌ python regression tests (exit 1)
```
test_peak_and_safety (studio.tests.test_audit.DiskManagerTest.test_peak_and_safety) ... ok
test_server_patch_signature (studio.tests.test_audit.DiskManagerTest.test_server_patch_signature) ... ok
test_resume_key_stable_across_signed_urls (studio.tests.test_audit.DownloaderTest.test_resume_key_stable_across_signed_urls) ... ok
test_parse (studio.tests.test_audit.HlsParserTest.test_parse) ... ok
test_slice_validation (studio.tests.test_audit.HlsParserTest.test_slice_validation) ... ok
test_fps_exact (studio.tests.test_audit.HooksTest.test_fps_exact) ... ok
test_ramp_duration_preserving (studio.tests.test_audit.HooksTest.test_ramp_duration_preserving) ... ok
test_short_words_kept (studio.tests.test_audit.HooksTest.test_short_words_kept) ... ok
test_time_remap_filters (studio.tests.test_audit.HooksTest.test_time_remap_filters) ... ok
test_finds_injected_peak (studio.tests.test_audit.MomentsTest.test_finds_injected_peak) ... ok
test_llm_fallback (studio.tests.test_audit.MomentsTest.test_llm_fallback) ... ok
test_all_required_patches_apply (studio.tests.test_audit.PatchAnchorsTest.test_all_required_patches_apply) ... ok
test_header_limits_and_command (studio.tests.test_audit.RenderWsTest.test_header_limits_and_command) ... ok
test_paths_and_hosts (studio.tests.test_audit.SecurityTest.test_paths_and_hosts) ... ok
test_policy (studio.tests.test_audit.TemplatesTest.test_policy) ... ok
test_codec_block_replaced_and_input_tags_kept (studio.tests.test_export_pipeline.ArgvRewriteTest.test_codec_block_replaced_and_input_tags_kept) ... ok
test_export_encode_detected_only_in_export_dir (studio.tests.test_export_pipeline.ArgvRewriteTest.test_export_encode_detected_only_in_export_dir) ... ok
test_fps_override_and_ntsc (studio.tests.test_export_pipeline.ArgvRewriteTest.test_fps_override_and_ntsc) ... ok
test_intermediate_is_near_lossless (studio.tests.test_export_pipeline.ArgvRewriteTest.test_intermediate_is_near_lossless) ... ok
test_seek_audit (studio.tests.test_export_pipeline.ArgvRewriteTest.test_seek_audit) ... ok
test_canvas_layer_replaces_ass_text (studio.tests.test_export_pipeline.ExportWrapperTest.test_canvas_layer_replaces_ass_text) ... ok
test_fallback_to_ass_when_overlay_fails (studio.tests.test_export_pipeline.ExportWrapperTest.test_fallback_to_ass_when_overlay_fails) ... [studio] canvas text layer failed (overlay ffmpeg rc=254: [concat @ 0x564a0a417680] Impossible to open '/tmp/tmp3aqmnpze/ovjob/000000.png'
[in#1 @ 0x564a0a40cdc0] Error opening input: No such file or directory
Error opening input file /tmp/tmp3aqmnpze/ovjob/list.ffconcat.
Error opening input files: No such file or directory
), falling back to ASS
ok
test_multi_clip_split (studio.tests.test_export_pipeline.ExportWrapperTest.test_multi_clip_split) ... ok
test_passthrough_without_options (studio.tests.test_export_pipeline.ExportWrapperTest.test_passthrough_without_options) ... ok
test_grade_chain_runs (studio.tests.test_export_pipeline.GradeAndOverlayTest.test_grade_chain_runs) ... ok
test_header_validation (studio.tests.test_export_pipeline.GradeAndOverlayTest.test_header_validation) ... ok
test_overlay_lands_on_exact_frame (studio.tests.test_export_pipeline.GradeAndOverlayTest.test_overlay_lands_on_exact_frame) ... ok
test_export_wrapper_applies_gate_on_plain_exports (studio.tests.test_pr7.LoudnessGateTest.test_export_wrapper_applies_gate_on_plain_exports) ... ok
test_loud_clip_true_peak_limited (studio.tests.test_pr7.LoudnessGateTest.test_loud_clip_true_peak_limited) ... ok
test_no_audio_is_skipped (studio.tests.test_pr7.LoudnessGateTest.test_no_audio_is_skipped) ... ok
test_on_target_clip_untouched (studio.tests.test_pr7.LoudnessGateTest.test_on_target_clip_untouched) ... ok
test_quiet_clip_is_normalized_and_video_kept (studio.tests.test_pr7.LoudnessGateTest.test_quiet_clip_is_normalized_and_video_kept) ... ok
test_editor_patches (studio.tests.test_pr7.Pr7PatchesTest.test_editor_patches) ... ok
test_gl_lens_shader_has_no_debug_output (studio.tests.test_pr7.Pr7PatchesTest.test_gl_lens_shader_has_no_debug_output) ... FAIL
test_server_patches (studio.tests.test_pr7.Pr7PatchesTest.test_server_patches) ... ok

======================================================================
FAIL: test_gl_lens_shader_has_no_debug_output (studio.tests.test_pr7.Pr7PatchesTest.test_gl_lens_shader_has_no_debug_output)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/runner/work/kick-video-downloader/kick-video-downloader/studio/tests/test_pr7.py", line 120, in test_gl_lens_shader_has_no_debug_output
    self.assertNotIn("DEBUG", src)
AssertionError: 'DEBUG' unexpectedly found in '/* Kick Clip Studio — web/core/render/glPasses.js\n * PLAN §12.4/§13/§20: GPU (WebGL2) versions of the render cores.\n * The shaders mirror the pure JS kernels (effects.js / lens.js) formula-by-\n * formula; the GPU<->JS equivalence gate in verify_all.py runs both on the\n * same deterministic inputs inside headless Electron and compares.\n * Browser-only (needs WebGL2 + EXT_color_buffer_float). */\n(function (root) {\n    "use strict";\n\n    const VS_FULLSCREEN = [\n        "#version 300 es",\n        "in vec2 p; out vec2 vUv;",\n        "void main(){ vUv = p*0.5+0.5; gl_Position = vec4(p,0.,1.); }"\n    ].join("\\n");\n\n    function compile(gl, type, src) {\n        const s = gl.createShader(type);\n        gl.shaderSource(s, src);\n        gl.compileShader(s);\n        if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {\n            throw new Error("shader: " + gl.getShaderInfoLog(s));\n        }\n        return s;\n    }\n\n    function program(gl, fs) {\n        const prog = gl.createProgram();\n        gl.attachShader(prog, compile(gl, gl.VERTEX_SHADER, VS_FULLSCREEN));\n        gl.attachShader(prog, compile(gl, gl.FRAGMENT_SHADER, fs));\n        gl.linkProgram(prog);\n        if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {\n            throw new Error("link: " + gl.getProgramInfoLog(prog));\n        }\n        return prog;\n    }\n\n    function makeFBO(gl, W, H, floatMode) {\n        const tex = gl.createTexture();\n        gl.activeTexture(gl.TEXTURE0);\n        gl.bindTexture(gl.TEXTURE_2D, tex);\n        gl.texImage2D(gl.TEXTURE_2D, 0, floatMode ? gl.RGBA32F : gl.RGBA8,\n                      W, H, 0, gl.RGBA, floatMode ? gl.FLOAT : gl.UNSIGNED_BYTE, null);\n        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);\n        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);\n        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);\n        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);\n        const fbo = gl.createFramebuffer();\n        gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);\n        gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);\n        const st = gl.checkFramebufferStatus(gl.FRAMEBUFFER);\n        gl.bindFramebuffer(gl.FRAMEBUFFER, null);\n        if (st !== gl.FRAMEBUFFER_COMPLETE) {\n            throw new Error("FBO incomplete: 0x" + st.toString(16) + " float=" + floatMode);\n        }\n        return { tex: tex, fbo: fbo, W: W, H: H };\n    }\n\n    function drawTo(gl, fbo, W, H) {\n        gl.bindFramebuffer(gl.FRAMEBUFFER, fbo ? fbo.fbo : null);\n        gl.viewport(0, 0, W, H);\n        gl.drawArrays(gl.TRIANGLES, 0, 3);\n    }\n\n    function makeQuad(gl, prog) {\n        gl.useProgram(prog);\n        const buf = gl.createBuffer();\n        gl.bindBuffer(gl.ARRAY_BUFFER, buf);\n        gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);\n        const loc = gl.getAttribLocation(prog, "p");\n        gl.enableVertexAttribArray(loc);\n        gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);\n    }\n\n    function makeContext(W, H) {\n        const canvas = document.createElement("canvas");\n        canvas.width = W; canvas.height = H;\n        const gl = canvas.getContext("webgl2", { preserveDrawingBuffer: true });\n        if (!gl) throw new Error("WebGL2 unavailable");\n        gl.getExtension("EXT_color_buffer_float");\n        gl.getExtension("OES_texture_float_linear");\n        return { canvas: canvas, gl: gl };\n    }\n\n    function bindTex(gl, tex) {\n        gl.activeTexture(gl.TEXTURE0);\n        gl.bindTexture(gl.TEXTURE_2D, tex);\n    }\n\n    // ── SDF stroke: jump flood (§12.4) ───────────────────────────────────\n    // vPx is computed IN the fragment shader from the interpolated vUv.\n    const FS_JFA_STEP = [\n        "#version 300 es",\n        "precision highp float;",\n        "uniform highp sampler2D uSeeds; uniform highp ivec2 uSize; uniform int uStep;",\n        "in vec2 vUv; out vec4 o;",\n        "void main(){",\n        "  ivec2 vPx = ivec2(vUv * vec2(uSize));",\n        "  vec2 best = vec2(-1.0); float bd = 1e30;",\n        "  vec2 self = texelFetch(uSeeds, vPx, 0).xy;",\n        "  if (self.x >= 0.0) { bd = 0.0; best = self; }",\n        "  for (int oy = -1; oy <= 1; oy++) for (int ox = -1; ox <= 1; ox++) {",\n        "    if (ox == 0 && oy == 0) continue;",\n        "    ivec2 n = vPx + ivec2(ox, oy) * uStep;",\n        "    if (n.x < 0 || n.y < 0 || n.x >= uSize.x || n.y >= uSize.y) continue;",\n        "    vec2 s = texelFetch(uSeeds, n, 0).xy;",\n        "    if (s.x < 0.0) continue;",\n        "    float dist = length(s - vec2(vPx));",\n        "    if (dist < bd) { bd = dist; best = s; }",\n        "  }",\n        "  o = vec4(best, 0.0, 1.0);",\n        "}"\n    ].join("\\n");\n    const FS_STROKE = [\n        "#version 300 es",\n        "precision highp float;",\n        "uniform highp sampler2D uSeeds; uniform highp ivec2 uSize; uniform float uRadius;",\n        "in vec2 vUv; out vec4 o;",\n        "void main(){",\n        "  ivec2 vPx = ivec2(vUv * vec2(uSize));",\n        "  vec2 s = texelFetch(uSeeds, vPx, 0).xy;",\n        "  float a = 0.0;",\n        "  if (s.x >= 0.0) {",\n        "    float d = length(s - vec2(vPx));",\n        "    float t = clamp((uRadius + 0.5 - d) / 1.0, 0.0, 1.0);",\n        "    a = t * t * (3.0 - 2.0 * t);",\n        "  }",\n        "  o = vec4(a, a, a, 1.0);",\n        "}"\n    ].join("\\n");\n\n    function StrokePass(W, H) {\n        const ctx = makeContext(W, H);\n        this.gl = ctx.gl;\n        this.W = W; this.H = H;\n        this.progStep = program(this.gl, FS_JFA_STEP);\n        this.progStroke = program(this.gl, FS_STROKE);\n        makeQuad(this.gl, this.progStep);\n        makeQuad(this.gl, this.progStroke);\n        this.a = makeFBO(this.gl, W, H, true);\n        this.b = makeFBO(this.gl, W, H, true);\n        this.sizeLoc = this.gl.getUniformLocation(this.progStep, "uSize");\n        this.stepLoc = this.gl.getUniformLocation(this.progStep, "uStep");\n        this.seedsLoc = this.gl.getUniformLocation(this.progStep, "uSeeds");\n        this.sizeLoc2 = this.gl.getUniformLocation(this.progStroke, "uSize");\n        this.radLoc = this.gl.getUniformLocation(this.progStroke, "uRadius");\n        this.seedsLoc2 = this.gl.getUniformLocation(this.progStroke, "uSeeds");\n    }\n\n    /** mask: Uint8Array (0/255) -> Float32Array stroke alpha. */\n    StrokePass.prototype.run = function (mask, radius) {\n        const gl = this.gl, W = this.W, H = this.H;\n        const seed = new Float32Array(W * H * 4);\n        for (let i = 0; i < W * H; i++) {\n            if (mask[i]) { seed[i * 4] = i % W; seed[i * 4 + 1] = (i / W) | 0; }\n            else { seed[i * 4] = -1; seed[i * 4 + 1] = -1; }\n        }\n        const seedTex = gl.createTexture();\n        bindTex(gl, seedTex);\n        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA32F, W, H, 0, gl.RGBA, gl.FLOAT, seed);\n        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);\n        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);\n        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);\n        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);\n\n        gl.useProgram(this.progStep);\n        gl.uniform2i(this.sizeLoc, W, H);\n        gl.uniform1i(this.seedsLoc, 0);\n        let steps = 1;\n        while (steps < Math.max(W, H)) steps <<= 1;\n        let srcTex = seedTex;\n        for (; steps >= 1; steps >>= 1) {\n            bindTex(gl, srcTex);                       // re-bind: makeFBO clobbers unit 0\n            gl.uniform1i(this.stepLoc, steps);\n            drawTo(gl, this.b, W, H);\n            const t = this.a; this.a = this.b; this.b = t;\n            srcTex = this.a.tex;\n        }\n\n        gl.useProgram(this.progStroke);\n        gl.uniform2i(this.sizeLoc2, W, H);\n        gl.uniform1f(this.radLoc, radius);\n        gl.uniform1i(this.seedsLoc2, 0);\n        const outFbo = makeFBO(gl, W, H, true);\n        bindTex(gl, this.a.tex);                       // re-bind after makeFBO\n        drawTo(gl, outFbo, W, H);\n        const px = new Float32Array(W * H * 4);\n        gl.bindFramebuffer(gl.FRAMEBUFFER, outFbo.fbo);\n        gl.readPixels(0, 0, W, H, gl.RGBA, gl.FLOAT, px);\n        const alpha = new Float32Array(W * H);\n        for (let i = 0; i < W * H; i++) alpha[i] = px[i * 4];\n        return alpha;\n    };\n\n    // ── dual-Kawase (§12.4) — texelFetch mirrors the JS taps exactly ─────\n    const FS_KAWASE_DOWN = [\n        "#version 300 es",\n        "precision highp float;",\n        "uniform highp sampler2D uSrc; uniform highp ivec2 uSrcSize; uniform highp ivec2 uDstSize;",\n        "in vec2 vUv; out vec4 o;",\n        "void main(){",\n        "  ivec2 vPx = ivec2(vUv * vec2(uDstSize));",\n        "  ivec2 s = vPx * 2;",\n        "  ivec2 s1 = min(ivec2(uSrcSize.x - 1, uSrcSize.y - 1), s + 1);",\n        "  float a = texelFetch(uSrc, ivec2(s.x, s.y), 0).r;",\n        "  float b = texelFetch(uSrc, ivec2(s1.x, s.y), 0).r;",\n        "  float c = texelFetch(uSrc, ivec2(s.x, s1.y), 0).r;",\n        "  float d = texelFetch(uSrc, ivec2(s1.x, s1.y), 0).r;",\n        "  o = vec4(vec3((a + b + c + d) * 0.25), 1.0);",\n        "}"\n    ].join("\\n");\n    const FS_KAWASE_UP = [\n        "#version 300 es",\n        "precision highp float;",\n        "uniform highp sampler2D uSrc; uniform highp ivec2 uSrcSize; uniform highp ivec2 uDstSize;",\n        "in vec2 vUv; out vec4 o;",\n        "void main(){",\n        "  ivec2 vPx = ivec2(vUv * vec2(uDstSize));",\n        "  vec2 f = max(vec2(0.0), min(vec2(uSrcSize - ivec2(1)), (vec2(vPx) - 0.5) * 0.5));",\n        "  ivec2 i0 = ivec2(floor(f));",\n        "  vec2 w = f - vec2(i0);",\n        "  ivec2 i1 = min(i0 + ivec2(1), uSrcSize - ivec2(1));",\n        "  float a = texelFetch(uSrc, ivec2(i0.x, i0.y), 0).r;",\n        "  float b = texelFetch(uSrc, ivec2(i1.x, i0.y), 0).r;",\n        "  float c = texelFetch(uSrc, ivec2(i0.x, i1.y), 0).r;",\n        "  float d = texelFetch(uSrc, ivec2(i1.x, i1.y), 0).r;",\n        "  float v = mix(mix(a, b, w.x), mix(c, d, w.x), w.y);",\n        "  o = vec4(vec3(v), 1.0);",\n        "}"\n    ].join("\\n");\n\n    function KawasePass(W, H) {\n        const ctx = makeContext(W, H);\n        this.gl = ctx.gl;\n        this.W = W; this.H = H;\n        this.progDown = program(this.gl, FS_KAWASE_DOWN);\n        this.progUp = program(this.gl, FS_KAWASE_UP);\n        makeQuad(this.gl, this.progDown);\n        makeQuad(this.gl, this.progUp);\n    }\n\n    /** src: Float32Array -> blurred Float32Array (GPU). */\n    KawasePass.prototype.run = function (src, passes) {\n        const gl = this.gl;\n        const tex = gl.createTexture();\n        bindTex(gl, tex);\n        const rgbaSrc = new Float32Array(this.W * this.H * 4);   // RGBA32F needs 4 comps\n        for (let i = 0; i < this.W * this.H; i++) rgbaSrc[i * 4] = src[i];\n        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA32F, this.W, this.H, 0, gl.RGBA, gl.FLOAT, rgbaSrc);\n        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);\n        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);\n        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);\n        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);\n\n        const chain = [{ tex: tex, W: this.W, H: this.H, fbo: makeFBO(gl, this.W, this.H, true) }];\n        gl.useProgram(this.progDown);\n        gl.uniform1i(gl.getUniformLocation(this.progDown, "uSrc"), 0);\n        let cur = { W: this.W, H: this.H };\n        for (let i = 0; i < passes && cur.W >= 2 && cur.H >= 2; i++) {\n            const nw = cur.W >> 1, nh = cur.H >> 1;\n            const fbo = makeFBO(gl, nw, nh, true);\n            bindTex(gl, chain[i].tex);                 // re-bind after makeFBO\n            gl.uniform2i(gl.getUniformLocation(this.progDown, "uSrcSize"), cur.W, cur.H);\n            gl.uniform2i(gl.getUniformLocation(this.progDown, "uDstSize"), nw, nh);\n            drawTo(gl, fbo, nw, nh);\n            chain.push({ tex: fbo.tex, W: nw, H: nh, fbo: fbo });\n            cur = { W: nw, H: nh };\n        }\n        gl.useProgram(this.progUp);\n        gl.uniform1i(gl.getUniformLocation(this.progUp, "uSrc"), 0);\n        for (let i = chain.length - 2; i >= 0; i--) {\n            const dst = chain[i];\n            bindTex(gl, chain[i + 1].tex);\n            gl.uniform2i(gl.getUniformLocation(this.progUp, "uSrcSize"), chain[i + 1].W, chain[i + 1].H);\n            gl.uniform2i(gl.getUniformLocation(this.progUp, "uDstSize"), dst.W, dst.H);\n            drawTo(gl, dst.fbo, dst.W, dst.H);\n        }\n        const out = new Float32Array(this.W * this.H * 4);\n        gl.bindFramebuffer(gl.FRAMEBUFFER, chain[0].fbo.fbo);\n        gl.readPixels(0, 0, this.W, this.H, gl.RGBA, gl.FLOAT, out);\n        const mono = new Float32Array(this.W * this.H);\n        for (let i = 0; i < this.W * this.H; i++) mono[i] = out[i * 4];\n        return mono;\n    };\n\n    // ── Lens & Detail §13.1 (lens + CA + wave) ───────────────────────────\n    const FS_LENS = [\n        "#version 300 es",\n        "precision highp float;",\n        "uniform highp sampler2D uSrc; uniform highp ivec2 uSize;",\n        "uniform float uK1, uK2, uCA, uCx, uCy, uAspect, uNorm;",\n        "uniform float uWaveA, uWaveF, uWaveV, uT;",\n        "in vec2 vUv; out vec4 o;",\n        "vec2 lensMap(vec2 uv){",\n        "  vec2 d = (uv - vec2(uCx, uCy)) * vec2(uAspect, 1.0);",\n        "  float r2 = dot(d, d);",\n        "  return vec2(uCx, uCy) + (uv - vec2(uCx, uCy)) * ((1.0 + uK1*r2 + uK2*r2*r2) / uNorm);",\n        "}",\n        "void main(){",\n        "  vec2 uv = vUv;",\n        "  uv.x += uWaveA * sin(6.28318530718 * (uv.y * uWaveF + uT * uWaveV));",\n        "  uv = lensMap(uv);",\n        "  vec2 c = vec2(uCx, uCy);",\n        "  vec2 dl = (uv - c) * vec2(uAspect, 1.0);",\n        "  float r = length(dl);",\n        "  float k = uCA * r;",\n        "  vec2 offR = (uv - c) * (1.0 + k);",\n        "  vec2 offB = (uv - c) * (1.0 - k);",\n        "  float rr = texture(uSrc, offR).r;",\n        "  float gg = texture(uSrc, uv).g;",\n        "  float bb = texture(uSrc, offB).b;",\n        "  o = vec4(uWaveA * 1000.0, uK1, uCx, uCy);",   // DEBUG\n        "}"\n    ].join("\\n");\n\n    function LensPass(W, H) {\n        const ctx = makeContext(W, H);\n        this.gl = ctx.gl;\n        this.W = W; this.H = H;\n        this.prog = program(this.gl, FS_LENS);\n        makeQuad(this.gl, this.prog);\n    }\n\n    /** rgba: Uint8Array -> lens-mapped Uint8Array (GPU). */\n    LensPass.prototype.run = function (rgba, p) {\n        const gl = this.gl;\n        const tex = gl.createTexture();\n        bindTex(gl, tex);\n        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, this.W, this.H, 0, gl.RGBA, gl.UNSIGNED_BYTE, rgba);\n        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);\n        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);\n        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);\n        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);\n        gl.useProgram(this.prog);\n        gl.uniform1i(gl.getUniformLocation(this.prog, "uSrc"), 0);\n        gl.uniform2i(gl.getUniformLocation(this.prog, "uSize"), this.W, this.H);\n        const aspect = p.W && p.H ? p.W / p.H : 9 / 16;\n        const cx = p.cx != null ? p.cx : 0.5, cy = p.cy != null ? p.cy : 0.5;\n        const rc = Math.hypot(Math.max(cx, aspect - cx), Math.max(cy, 1 - cy));\n        gl.uniform1f(gl.getUniformLocation(this.prog, "uK1"), p.k1 || 0);\n        gl.uniform1f(gl.getUniformLocation(this.prog, "uK2"), p.k2 || 0);\n        gl.uniform1f(gl.getUniformLocation(this.prog, "uCA"), (p.ca || 0) / (p.W || 1080));\n        gl.uniform1f(gl.getUniformLocation(this.prog, "uCx"), cx);\n        gl.uniform1f(gl.getUniformLocation(this.prog, "uCy"), cy);\n        gl.uniform1f(gl.getUniformLocation(this.prog, "uAspect"), aspect);\n        gl.uniform1f(gl.getUniformLocation(this.prog, "uNorm"),\n                     1 + (p.k1 || 0) * rc * rc + (p.k2 || 0) * rc * rc * rc * rc);\n        gl.uniform1f(gl.getUniformLocation(this.prog, "uWaveA"), (p.A || 0) / (p.W || 1080));\n        gl.uniform1f(gl.getUniformLocation(this.prog, "uWaveF"), p.f || 6);\n        gl.uniform1f(gl.getUniformLocation(this.prog, "uWaveV"), p.v || 1.5);\n        gl.uniform1f(gl.getUniformLocation(this.prog, "uT"), p.t || 0);\n        drawTo(gl, null, this.W, this.H);\n        const out = new Uint8Array(this.W * this.H * 4);\n        gl.readPixels(0, 0, this.W, this.H, gl.RGBA, gl.UNSIGNED_BYTE, out);\n        return out;\n    };\n\n    root.CoreGLPasses = { StrokePass: StrokePass, KawasePass: KawasePass, LensPass: LensPass, makeContext: makeContext };\n})(typeof self !== "undefined" ? self : this);\n'

----------------------------------------------------------------------
Ran 35 tests in 9.884s

FAILED (failures=1)
```

### ✅ server imports with fixes (studio.loader)
```
[studio] server.py patches: {'already': 27, 'skipped': 1}
28 patches
```

### ✅ export pipeline installs into the real server
```
[studio] server.py patches: {'already': 27, 'skipped': 1}
[studio] export pipeline: {'grade': True, 'encoder_shim': True, 'export_route': True, 'loudness_gate': True}
{'grade': True, 'encoder_shim': True, 'export_route': True, 'loudness_gate': True}
```

### ✅ web core selftest
```
  PASS  pcg hash golden
  PASS  value noise golden
  PASS  jump-flood distance golden
  PASS  SDF stroke smoothstep golden
  PASS  Kawase energy preserved
  PASS  Kawase spreads the impulse
  PASS  glow alpha is ZERO when word opacity is 0
  PASS  glowAlpha = opacity^1.5 * amount
  PASS  zoom punch scale golden
  PASS  zoom punch peak = 1 + A*(1+overshoot)
  PASS  shake state golden (seed 7 @200ms)
  PASS  shake is zero after its duration (no permanent shake)
  PASS  shake constant overscan 1+2*amp/W (N11)
  PASS  BT.709 white = Y235 Cb128
  PASS  BT.709 black = Y16
  PASS  yuv420 plane sizes
  PASS  Y plane within 1 LSB of the BT.709 formula
  PASS  raw frame = w*h*1.5 bytes (WS protocol)

[шаг 3 lens & grade: k1=0 бит-в-бит, overscan, Viral Punch (§7.5)]
  PASS  k1=0: бит-в-бит равен входу (zero-lens == no-lens)
  PASS  auto-overscan: при k1>0 углы остаются в кадре
  PASS  lens bends symmetrically around the center
  PASS  Lens Punch starts and ends at zero
  PASS  Lens Punch k1 peaks ~0.18 near 80 ms
  PASS  bulge center invariant
  PASS  fisheye fov=0 identity
  PASS  wave A=0 identity
  PASS  twirl center invariant
  PASS  Viral Punch clipping < 0.5% of channels
  PASS  skin hue within ±10 degrees on all skin samples
  PASS  autoLevels expo = log2(0.40/p50)
  PASS  autoLevels expo clamped +1
  PASS  strength 0 = identity params
  PASS  strength 1 = full preset
  PASS  preset §14.5: viral_punch
  PASS  preset §14.5: teal_orange
  PASS  preset §14.5: night_neon
  PASS  preset §14.5: clean_natural
  PASS  preset §14.5: moody_film
  PASS  preset §14.5: bw_contrast
  PASS  preset §14.5: tv_acid
  PASS  lens preset §13.3: lens_punch
  PASS  lens preset §13.3: fisheye_hold
  PASS  lens preset §13.3: bulge_face
  PASS  lens preset §13.3: crispy
  PASS  lens preset §13.3: heat_wobble
  PASS  lens preset §13.3: crispy_lens
  PASS  Detail increases edge contrast (MTF50 up)

[шаг 4: fx композера §15 + time-remap (§7.3/§8.3)]
  PASS  zoom punch: scale > 1 inside the window
  PASS  zoom scale = 1 outside the window
  PASS  threshold hit active in its window
  PASS  threshold inactive outside
  PASS  freeze holds the source time
  PASS  ramp re-times the source (0.35x..1.8x)
  PASS  outside fx windows the timeline is untouched

ALL CORE SELFTESTS PASSED
```

### ✅ web audit selftest
```

[text layout: no lost words]
  PASS  every word lands on some page
  PASS  ≤2 rows per page
  PASS  page follows the active word
  PASS  short phrase: one page, full size
  PASS  layoutLines keeps all words
  PASS  UI id 'mrbeast' resolves to styles.json 'mrbeast_3d'
  PASS  text block clamped to the safe zone

[ramp: preview == export curve]
  PASS  composer ramp == timeRemap.js curve
  PASS  duration preserving: back in sync, no jump at the window end

[yuv420: true 2x2 chroma mean]
  PASS  U/V = mean of the 4 pixels

ALL AUDIT SELFTESTS PASSED
```

### ✅ overlay export selftest
```
overlay_export selftest: OK
```

### ✅ node --check web/editor.js
```

```

### ✅ node --check web/app.js
```

```

### ✅ node --check web/studio/moments.js
```

```

### ✅ node --check web/studio/overlay_export.js
```

```

### ✅ node --check web/core/canvasMonitor.js
```

```

### ✅ node --check web/core/text/canvasText.js
```

```

## Probe

#### editor.js from studio:addfx-v2 to EOF
```
    // studio:addfx-v2 - template/moment fx go through the SAME builder as the
    // hotkeys (addEffectAtPlayhead): per-kind fields (zoom/lens/threshold/flash
    // -> fxPeak, shake -> fxAmp/fxFreq), anchor for the face zoom, and the
    // moment's SOURCE time is mapped onto the timeline via the clip showing it.
    function studioSourceToTimeline(srcT) {
        let best = null;
        const ids = (typeof videoTrackIds === "function") ? videoTrackIds() : [];
        for (const tid of ids) {
            for (const c of (state.tracks[tid] || [])) {
                if (!c || !c.media || c.isFx) continue;
                const off = Number(c.sourceOffset) || 0;
                const rate = Number(c.speed) > 0 ? Number(c.speed) : 1;
                const srcLen = (Number(c.duration) || 0) * rate;
                if (srcT >= off && srcT < off + srcLen) {
                    const t = c.startTime + (srcT - off) / rate;
                    if (best === null || t < best) best = t;
                }
            }
        }
        return best;
    }
    window.studioSourceToTimeline = studioSourceToTimeline;

    window.studioAddFx = function (fxList, baseTime, opts) {
        if (!Array.isArray(fxList) || !fxList.length) return 0;
        const o = opts || {};
        let base = Number(baseTime) || 0;
        if (o.timeBase === "source") {
            const mapped = studioSourceToTimeline(base);
            if (mapped === null) {
                showToast("Момент не попадает ни в один клип на таймлайне: эффекты не добавлены", "info");
                return 0;
            }
            base = mapped;
        }
        const savedTime = state.currentTime;
        let added = 0;
        try {
            for (const f of fxList) {
                if (!f || !f.kind) continue;
                const kind = String(f.kind);
                const s = Number(f.start) || 0;
                const dur = Math.max(0.05, f.end != null ? (Number(f.end) - s) : (Number(f.duration) || 0.35));
                const ov = { duration: dur, fxSound: f.sfx || f.fxSound || "none" };
                if (kind === "zoom") ov.fxPeak = f.amp != null ? Number(f.amp) : 0.15;
                else if (kind === "lens") ov.fxPeak = f.amp != null ? Number(f.amp) : 0.18;
                else if (kind === "threshold") ov.fxPeak = f.amp != null ? Number(f.amp) : 0.45;
                else if (kind === "flash") ov.fxPeak = f.peak != null ? Number(f.peak) : 0.75;
                else if (kind === "shake") {
                    ov.fxAmp = f.amp != null ? Number(f.amp) : 12;
                    if (f.freq != null) ov.fxFreq = Number(f.freq);
                }
                if (f.anchor) ov.anchor = f.anchor;
                const before = (state.tracks[tidOfFx()] || []).length;
                state.currentTime = Math.max(0, base + s);
                addEffectAtPlayhead(kind, f.color || "white", ov);
                if ((state.tracks[tidOfFx()] || []).length > before) added++;
            }
        } finally {
            state.currentTime = savedTime;
        }
        const fxTid = tidOfFx();
        if (state.tracks[fxTid]) state.tracks[fxTid].sort((a, b) => a.startTime - b.startTime);
        recalcTotalDuration();
        renderTimeline();
        syncVideoToCurrentTime();
        saveProject();
        return added;
    };

    document.addEventListener("studio:template-plan", (e) => {
        const plan = e.detail;
        if (plan && Array.isArray(plan.fx) && plan.fx.length) {
            const base = (plan.moment && typeof plan.moment.start === "number") ? plan.moment.start : state.currentTime;
            const added = window.studioAddFx(plan.fx, base, { timeBase: "source" });  // studio:addfx-source
            if (added) showToast(`Шаблон «${plan.template || ""}»: добавлено ${added} эффектов на таймлайн`, "ok");
        }
    });

})();

```

#### editor.js flash hotkey
```
225:                addEffectAtPlayhead("flash", col, { duration: 0.18, peak: 0.95, fxPeak: 0.95, fxSound: "impact_epic" });  // studio:flash-fxpeak
```

#### editor.js addFxClip head
```
    function addFxClip(kind, color) {
        const tid = ensureFxTrack();
        ensureTracksInitialized();
        const fxKind = kind || "flash";
        const fxColor = fxKind === "flash" ? (color || "white") : (color || "white");
        const dur = fxKind === "flash" ? 0.6 : (fxKind === "bars" ? 1.8 : 1.2);
        const c = {
            id: "fx_" + Date.now().toString(36),
            trackId: tid,
            startTime: Math.max(0, state.currentTime),
            duration: dur,
            sourceOffset: 0,
            sourceDuration: dur,
            title: "",
            isFx: true,
            fxKind,
            fxColor,
            fxPeak: 0.75,
            fxSound: fxKind === "flash" ? (FX_DEFAULT_SOUND[fxColor] || "click") : "whoosh",
            fxGain: 1.0,
            fxBarH: 160,
            fxAmp: 12,
            fxFreq: 7,
            media: null,
            volume: 1.0,
            opacity: 1.0
        };
        c.title = fxLabel(c);
        (state.tracks[tid] = state.tracks[tid] || []).push(c);
        state.tracks[tid].sort((a, b) => a.startTime - b.startTime);
        selectClip(c.id);
        recalcTotalDuration();
        renderTimeline();
        saveProject();
        switchTab("inspector");
    }
    // «+Текст»: свободный текстовый элемент (не субтитры) с полными параметрами;
    // живёт на текстовом слое, но его можно перетащить на любой другой слой
    function addTextClip() {
        ensureTracksInitialized();
        let tid = textTrackId();
```

#### server.py check_disk
```
def check_disk(req: CheckDiskRequest):
    """
    Check if disk has enough free space for the requested size.
    Returns status, shortage, and clear messages if space is insufficient.
    """
    return disk_manager.check_space(req.required_bytes, peak_factor=_studio.DOWNLOAD_PEAK_FACTOR)  # studio:check-disk-peak

@app.post("/api/probe")
```

#### server.py __main__
```
if __name__ == "__main__":
    # studio:main-secure - hardened server (127.0.0.1 + token + Host/Origin checks +
    # export pipeline). The old unprotected server: KICK_LEGACY_SERVER=1 python server.py
    if os.environ.get("KICK_LEGACY_SERVER") == "1":
        run_server()
    else:
        import studio_server
        sys.exit(studio_server.main())
```
