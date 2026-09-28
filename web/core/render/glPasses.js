/* Kick Clip Studio — web/core/render/glPasses.js
 * PLAN §12.4/§13/§20: GPU (WebGL2) versions of the render cores.
 * The shaders mirror the pure JS kernels (effects.js / lens.js) formula-by-
 * formula; tools/gl_equiv_test.js runs both on the same deterministic inputs
 * inside headless Electron (web/core/render/gltest.html) and compares.
 * Browser-only (needs WebGL2 + EXT_color_buffer_float). */
(function (root) {
    "use strict";

    const VS_FULLSCREEN = [
        "#version 300 es",
        "in vec2 p; out vec2 vUv;",
        "void main(){ vUv = p*0.5+0.5; gl_Position = vec4(p,0.,1.); }"
    ].join("\n");

    function compile(gl, type, src) {
        const s = gl.createShader(type);
        gl.shaderSource(s, src);
        gl.compileShader(s);
        if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
            throw new Error("shader: " + gl.getShaderInfoLog(s));
        }
        return s;
    }

    function program(gl, fs) {
        const prog = gl.createProgram();
        gl.attachShader(prog, compile(gl, gl.VERTEX_SHADER, VS_FULLSCREEN));
        gl.attachShader(prog, compile(gl, gl.FRAGMENT_SHADER, fs));
        gl.linkProgram(prog);
        if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
            throw new Error("link: " + gl.getProgramInfoLog(prog));
        }
        return prog;
    }

    function makeFBO(gl, W, H, floatMode) {
        const tex = gl.createTexture();
        gl.activeTexture(gl.TEXTURE0);
        gl.bindTexture(gl.TEXTURE_2D, tex);
        gl.texImage2D(gl.TEXTURE_2D, 0, floatMode ? gl.RGBA32F : gl.RGBA8,
                      W, H, 0, gl.RGBA, floatMode ? gl.FLOAT : gl.UNSIGNED_BYTE, null);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        const fbo = gl.createFramebuffer();
        gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
        gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
        const st = gl.checkFramebufferStatus(gl.FRAMEBUFFER);
        gl.bindFramebuffer(gl.FRAMEBUFFER, null);
        if (st !== gl.FRAMEBUFFER_COMPLETE) {
            throw new Error("FBO incomplete: 0x" + st.toString(16) + " float=" + floatMode);
        }
        return { tex: tex, fbo: fbo, W: W, H: H };
    }

    function drawTo(gl, fbo, W, H) {
        gl.bindFramebuffer(gl.FRAMEBUFFER, fbo ? fbo.fbo : null);
        gl.viewport(0, 0, W, H);
        gl.drawArrays(gl.TRIANGLES, 0, 3);
    }

    function makeQuad(gl, prog) {
        gl.useProgram(prog);
        const buf = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, buf);
        gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
        const loc = gl.getAttribLocation(prog, "p");
        gl.enableVertexAttribArray(loc);
        gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    }

    function makeContext(W, H) {
        const canvas = document.createElement("canvas");
        canvas.width = W; canvas.height = H;
        const gl = canvas.getContext("webgl2", { preserveDrawingBuffer: true });
        if (!gl) throw new Error("WebGL2 unavailable");
        gl.getExtension("EXT_color_buffer_float");
        gl.getExtension("OES_texture_float_linear");
        return { canvas: canvas, gl: gl };
    }

    function bindTex(gl, tex) {
        gl.activeTexture(gl.TEXTURE0);
        gl.bindTexture(gl.TEXTURE_2D, tex);
    }

    // ── SDF stroke: jump flood (§12.4) ───────────────────────────────────
    // vPx is computed IN the fragment shader from the interpolated vUv.
    const FS_JFA_STEP = [
        "#version 300 es",
        "precision highp float;",
        "uniform highp sampler2D uSeeds; uniform highp ivec2 uSize; uniform int uStep;",
        "in vec2 vUv; out vec4 o;",
        "void main(){",
        "  ivec2 vPx = ivec2(vUv * vec2(uSize));",
        "  vec2 best = vec2(-1.0); float bd = 1e30;",
        "  vec2 self = texelFetch(uSeeds, vPx, 0).xy;",
        "  if (self.x >= 0.0) { bd = 0.0; best = self; }",
        "  for (int oy = -1; oy <= 1; oy++) for (int ox = -1; ox <= 1; ox++) {",
        "    if (ox == 0 && oy == 0) continue;",
        "    ivec2 n = vPx + ivec2(ox, oy) * uStep;",
        "    if (n.x < 0 || n.y < 0 || n.x >= uSize.x || n.y >= uSize.y) continue;",
        "    vec2 s = texelFetch(uSeeds, n, 0).xy;",
        "    if (s.x < 0.0) continue;",
        "    float dist = length(s - vec2(vPx));",
        "    if (dist < bd) { bd = dist; best = s; }",
        "  }",
        "  o = vec4(best, 0.0, 1.0);",
        "}"
    ].join("\n");
    const FS_STROKE = [
        "#version 300 es",
        "precision highp float;",
        "uniform highp sampler2D uSeeds; uniform highp ivec2 uSize; uniform float uRadius;",
        "in vec2 vUv; out vec4 o;",
        "void main(){",
        "  ivec2 vPx = ivec2(vUv * vec2(uSize));",
        "  vec2 s = texelFetch(uSeeds, vPx, 0).xy;",
        "  float a = 0.0;",
        "  if (s.x >= 0.0) {",
        "    float d = length(s - vec2(vPx));",
        "    float t = clamp((uRadius + 0.5 - d) / 1.0, 0.0, 1.0);",
        "    a = t * t * (3.0 - 2.0 * t);",
        "  }",
        "  o = vec4(a, a, a, 1.0);",
        "}"
    ].join("\n");

    function StrokePass(W, H) {
        const ctx = makeContext(W, H);
        this.gl = ctx.gl;
        this.W = W; this.H = H;
        this.progStep = program(this.gl, FS_JFA_STEP);
        this.progStroke = program(this.gl, FS_STROKE);
        makeQuad(this.gl, this.progStep);
        makeQuad(this.gl, this.progStroke);
        this.a = makeFBO(this.gl, W, H, true);
        this.b = makeFBO(this.gl, W, H, true);
        this.sizeLoc = this.gl.getUniformLocation(this.progStep, "uSize");
        this.stepLoc = this.gl.getUniformLocation(this.progStep, "uStep");
        this.seedsLoc = this.gl.getUniformLocation(this.progStep, "uSeeds");
        this.sizeLoc2 = this.gl.getUniformLocation(this.progStroke, "uSize");
        this.radLoc = this.gl.getUniformLocation(this.progStroke, "uRadius");
        this.seedsLoc2 = this.gl.getUniformLocation(this.progStroke, "uSeeds");
    }

    /** mask: Uint8Array (0/255) -> Float32Array stroke alpha. */
    StrokePass.prototype.run = function (mask, radius) {
        const gl = this.gl, W = this.W, H = this.H;
        const seed = new Float32Array(W * H * 4);
        for (let i = 0; i < W * H; i++) {
            if (mask[i]) { seed[i * 4] = i % W; seed[i * 4 + 1] = (i / W) | 0; }
            else { seed[i * 4] = -1; seed[i * 4 + 1] = -1; }
        }
        const seedTex = gl.createTexture();
        bindTex(gl, seedTex);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA32F, W, H, 0, gl.RGBA, gl.FLOAT, seed);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);

        gl.useProgram(this.progStep);
        gl.uniform2i(this.sizeLoc, W, H);
        gl.uniform1i(this.seedsLoc, 0);
        let steps = 1;
        while (steps < Math.max(W, H)) steps <<= 1;
        let srcTex = seedTex;
        for (; steps >= 1; steps >>= 1) {
            bindTex(gl, srcTex);                       // re-bind: makeFBO clobbers unit 0
            gl.uniform1i(this.stepLoc, steps);
            drawTo(gl, this.b, W, H);
            const t = this.a; this.a = this.b; this.b = t;
            srcTex = this.a.tex;
        }

        gl.useProgram(this.progStroke);
        gl.uniform2i(this.sizeLoc2, W, H);
        gl.uniform1f(this.radLoc, radius);
        gl.uniform1i(this.seedsLoc2, 0);
        const outFbo = makeFBO(gl, W, H, true);
        bindTex(gl, this.a.tex);                       // re-bind after makeFBO
        drawTo(gl, outFbo, W, H);
        const px = new Float32Array(W * H * 4);
        gl.bindFramebuffer(gl.FRAMEBUFFER, outFbo.fbo);
        gl.readPixels(0, 0, W, H, gl.RGBA, gl.FLOAT, px);
        const alpha = new Float32Array(W * H);
        for (let i = 0; i < W * H; i++) alpha[i] = px[i * 4];
        return alpha;
    };

    // ── dual-Kawase (§12.4) — texelFetch mirrors the JS taps exactly ─────
    const FS_KAWASE_DOWN = [
        "#version 300 es",
        "precision highp float;",
        "uniform highp sampler2D uSrc; uniform highp ivec2 uSrcSize; uniform highp ivec2 uDstSize;",
        "in vec2 vUv; out vec4 o;",
        "void main(){",
        "  ivec2 vPx = ivec2(vUv * vec2(uDstSize));",
        "  ivec2 s = vPx * 2;",
        "  ivec2 s1 = min(ivec2(uSrcSize.x - 1, uSrcSize.y - 1), s + 1);",
        "  float a = texelFetch(uSrc, ivec2(s.x, s.y), 0).r;",
        "  float b = texelFetch(uSrc, ivec2(s1.x, s.y), 0).r;",
        "  float c = texelFetch(uSrc, ivec2(s.x, s1.y), 0).r;",
        "  float d = texelFetch(uSrc, ivec2(s1.x, s1.y), 0).r;",
        "  o = vec4(vec3((a + b + c + d) * 0.25), 1.0);",
        "}"
    ].join("\n");
    const FS_KAWASE_UP = [
        "#version 300 es",
        "precision highp float;",
        "uniform highp sampler2D uSrc; uniform highp ivec2 uSrcSize; uniform highp ivec2 uDstSize;",
        "in vec2 vUv; out vec4 o;",
        "void main(){",
        "  ivec2 vPx = ivec2(vUv * vec2(uDstSize));",
        "  vec2 f = max(vec2(0.0), min(vec2(uSrcSize - ivec2(1)), (vec2(vPx) - 0.5) * 0.5));",
        "  ivec2 i0 = ivec2(floor(f));",
        "  vec2 w = f - vec2(i0);",
        "  ivec2 i1 = min(i0 + ivec2(1), uSrcSize - ivec2(1));",
        "  float a = texelFetch(uSrc, ivec2(i0.x, i0.y), 0).r;",
        "  float b = texelFetch(uSrc, ivec2(i1.x, i0.y), 0).r;",
        "  float c = texelFetch(uSrc, ivec2(i0.x, i1.y), 0).r;",
        "  float d = texelFetch(uSrc, ivec2(i1.x, i1.y), 0).r;",
        "  float v = mix(mix(a, b, w.x), mix(c, d, w.x), w.y);",
        "  o = vec4(vec3(v), 1.0);",
        "}"
    ].join("\n");

    function KawasePass(W, H) {
        const ctx = makeContext(W, H);
        this.gl = ctx.gl;
        this.W = W; this.H = H;
        this.progDown = program(this.gl, FS_KAWASE_DOWN);
        this.progUp = program(this.gl, FS_KAWASE_UP);
        makeQuad(this.gl, this.progDown);
        makeQuad(this.gl, this.progUp);
    }

    /** src: Float32Array -> blurred Float32Array (GPU). */
    KawasePass.prototype.run = function (src, passes) {
        const gl = this.gl;
        const tex = gl.createTexture();
        bindTex(gl, tex);
        const rgbaSrc = new Float32Array(this.W * this.H * 4);   // RGBA32F needs 4 comps
        for (let i = 0; i < this.W * this.H; i++) rgbaSrc[i * 4] = src[i];
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA32F, this.W, this.H, 0, gl.RGBA, gl.FLOAT, rgbaSrc);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);

        const chain = [{ tex: tex, W: this.W, H: this.H, fbo: makeFBO(gl, this.W, this.H, true) }];
        gl.useProgram(this.progDown);
        gl.uniform1i(gl.getUniformLocation(this.progDown, "uSrc"), 0);
        let cur = { W: this.W, H: this.H };
        for (let i = 0; i < passes && cur.W >= 2 && cur.H >= 2; i++) {
            const nw = cur.W >> 1, nh = cur.H >> 1;
            const fbo = makeFBO(gl, nw, nh, true);
            bindTex(gl, chain[i].tex);                 // re-bind after makeFBO
            gl.uniform2i(gl.getUniformLocation(this.progDown, "uSrcSize"), cur.W, cur.H);
            gl.uniform2i(gl.getUniformLocation(this.progDown, "uDstSize"), nw, nh);
            drawTo(gl, fbo, nw, nh);
            chain.push({ tex: fbo.tex, W: nw, H: nh, fbo: fbo });
            cur = { W: nw, H: nh };
        }
        gl.useProgram(this.progUp);
        gl.uniform1i(gl.getUniformLocation(this.progUp, "uSrc"), 0);
        for (let i = chain.length - 2; i >= 0; i--) {
            const dst = chain[i];
            bindTex(gl, chain[i + 1].tex);
            gl.uniform2i(gl.getUniformLocation(this.progUp, "uSrcSize"), chain[i + 1].W, chain[i + 1].H);
            gl.uniform2i(gl.getUniformLocation(this.progUp, "uDstSize"), dst.W, dst.H);
            drawTo(gl, dst.fbo, dst.W, dst.H);
        }
        const out = new Float32Array(this.W * this.H * 4);
        gl.bindFramebuffer(gl.FRAMEBUFFER, chain[0].fbo.fbo);
        gl.readPixels(0, 0, this.W, this.H, gl.RGBA, gl.FLOAT, out);
        const mono = new Float32Array(this.W * this.H);
        for (let i = 0; i < this.W * this.H; i++) mono[i] = out[i * 4];
        return mono;
    };

    // ── Lens & Detail §13.1 (wave -> lens -> radial CA) ──────────────────
    // Mirrors lens.js mapPoint(): wave and barrel act on the output uv; the CA
    // radius is measured on the UNdistorted output uv (caOffsets(u, v)) and
    // scales only the horizontal offset from the lens center (cx_()).
    const FS_LENS = [
        "#version 300 es",
        "precision highp float;",
        "uniform highp sampler2D uSrc; uniform highp ivec2 uSize;",
        "uniform float uK1, uK2, uCA, uCx, uCy, uAspect, uNorm;",
        "uniform float uWaveA, uWaveF, uWaveV, uT;",
        "in vec2 vUv; out vec4 o;",
        "vec2 lensMap(vec2 uv){",
        "  vec2 d = (uv - vec2(uCx, uCy)) * vec2(uAspect, 1.0);",
        "  float r2 = dot(d, d);",
        "  return vec2(uCx, uCy) + (uv - vec2(uCx, uCy)) * ((1.0 + uK1*r2 + uK2*r2*r2) / uNorm);",
        "}",
        "void main(){",
        "  vec2 c = vec2(uCx, uCy);",
        "  vec2 uv = vUv;",
        "  uv.x += uWaveA * sin(6.28318530718 * (uv.y * uWaveF + uT * uWaveV));",
        "  uv = lensMap(uv);",
        "  float r = length((vUv - c) * vec2(uAspect, 1.0));",
        "  float k = uCA * r;",
        "  vec2 uvR = vec2(uCx + (uv.x - uCx) * (1.0 + k), uv.y);",
        "  vec2 uvB = vec2(uCx + (uv.x - uCx) * (1.0 - k), uv.y);",
        "  o = vec4(texture(uSrc, uvR).r, texture(uSrc, uv).g, texture(uSrc, uvB).b, 1.0);",
        "}"
    ].join("\n");

    function LensPass(W, H) {
        const ctx = makeContext(W, H);
        this.gl = ctx.gl;
        this.W = W; this.H = H;
        this.prog = program(this.gl, FS_LENS);
        makeQuad(this.gl, this.prog);
    }

    /** rgba: Uint8Array -> lens-mapped Uint8Array (GPU). */
    LensPass.prototype.run = function (rgba, p) {
        const gl = this.gl;
        const tex = gl.createTexture();
        bindTex(gl, tex);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, this.W, this.H, 0, gl.RGBA, gl.UNSIGNED_BYTE, rgba);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.useProgram(this.prog);
        gl.uniform1i(gl.getUniformLocation(this.prog, "uSrc"), 0);
        gl.uniform2i(gl.getUniformLocation(this.prog, "uSize"), this.W, this.H);
        const aspect = p.W && p.H ? p.W / p.H : 9 / 16;
        const cx = p.cx != null ? p.cx : 0.5, cy = p.cy != null ? p.cy : 0.5;
        const rc = Math.hypot(Math.max(cx, aspect - cx), Math.max(cy, 1 - cy));
        gl.uniform1f(gl.getUniformLocation(this.prog, "uK1"), p.k1 || 0);
        gl.uniform1f(gl.getUniformLocation(this.prog, "uK2"), p.k2 || 0);
        gl.uniform1f(gl.getUniformLocation(this.prog, "uCA"), (p.ca || 0) / (p.W || 1080));
        gl.uniform1f(gl.getUniformLocation(this.prog, "uCx"), cx);
        gl.uniform1f(gl.getUniformLocation(this.prog, "uCy"), cy);
        gl.uniform1f(gl.getUniformLocation(this.prog, "uAspect"), aspect);
        gl.uniform1f(gl.getUniformLocation(this.prog, "uNorm"),
                     1 + (p.k1 || 0) * rc * rc + (p.k2 || 0) * rc * rc * rc * rc);
        gl.uniform1f(gl.getUniformLocation(this.prog, "uWaveA"), (p.A || 0) / (p.W || 1080));
        gl.uniform1f(gl.getUniformLocation(this.prog, "uWaveF"), p.f || 6);
        gl.uniform1f(gl.getUniformLocation(this.prog, "uWaveV"), p.v || 1.5);
        gl.uniform1f(gl.getUniformLocation(this.prog, "uT"), p.t || 0);
        drawTo(gl, null, this.W, this.H);
        const out = new Uint8Array(this.W * this.H * 4);
        gl.readPixels(0, 0, this.W, this.H, gl.RGBA, gl.UNSIGNED_BYTE, out);
        return out;
    };

    root.CoreGLPasses = { StrokePass: StrokePass, KawasePass: KawasePass, LensPass: LensPass, makeContext: makeContext };
})(typeof self !== "undefined" ? self : this);
