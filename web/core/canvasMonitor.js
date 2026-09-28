/* Kick Clip Studio — web/core/canvasMonitor.js
 * PLAN §16 P0: the monitor is ONE canvas. One hidden <video> per unique file;
 * split/PiP/crops draw from the same decoded frame (drawImage sub-rects), so
 * a split from one file is frame-synced by construction (§7.4 clap gate).
 * Master clock when playing = audio clock (§16.3); videos follow with rate
 * 0.97/1.03 and seek beyond 150 ms. On pause/scrub: requestVideoFrameCallback
 * + draw by mediaTime. Text is drawn by web/core/text/canvasText.js — no CSS
 * animations. Grade = WebGL2 pass with the own 65^3 LUT (§14.6). Browser-only.
 *
 * Audit fixes: zoom punch (anchored on the tracked face when available),
 * lens punch, threshold hit, whip, freeze and speed ramp are now VISIBLE in
 * the preview (same curves as the export: CoreEffects / CoreTimeRemap);
 * exact VideoFrames are always closed (GPU leak); the grade texture is
 * reused instead of allocated per frame; webglcontextlost/restored handled. */
(function (root) {
    "use strict";
    const TM = root.CoreTimeMap;
    const GEO = root.CoreGeometry;
    const LUT = root.CoreLut3D;
    const TXT = root.CoreCanvasText;
    const TR = root.CoreTimeRemap || null;
    const EF = root.CoreEffects || null;

    function smoothstep(x) { x = Math.max(0, Math.min(1, x)); return x * x * (3 - 2 * x); }
    function fxIn(f) { return f.in != null ? f.in : f.start; }
    function fxOut(f) { return f.out != null ? f.out : f.end; }

    /** Zoom punch scale at t (export curve when CoreEffects is loaded). */
    function zoomScale(f, t) {
        const at = fxIn(f), A = f.amp != null ? f.amp : 0.15;
        if (EF && EF.zoomPunch) return EF.zoomPunch(t, { A: A, overshoot: 0.12, settleMs: 220, at: at }).scale;
        const x = t - at;
        if (x < 0) return 1;
        const dur = Math.max(0.05, (fxOut(f) - at));
        const rise = smoothstep(x / 0.09);
        const back = x > dur ? smoothstep((x - dur) / 0.12) : 0;
        return 1 + A * 1.12 * rise * (1 - back);
    }

    function CanvasMonitor(canvas, hooks) {
        this.canvas = canvas;                 // visible monitor canvas (1080x1920 buffer)
        this.canvas.width = 1080;
        this.canvas.height = 1920;
        this.ctx = canvas.getContext("2d");
        this.hooks = hooks;
        this.videoPool = new Map();           // filename -> <video>  (ONE per file, §16.2)
        this.work = document.createElement("canvas");
        this.work.width = 1080; this.work.height = 1920;
        this.wctx = this.work.getContext("2d");
        this.fxCanvas = document.createElement("canvas");
        this.fxCanvas.width = 1080; this.fxCanvas.height = 1920;
        this.fctx = this.fxCanvas.getContext("2d");
        this.gradeCanvas = document.createElement("canvas");
        this.gradeCanvas.width = 1080; this.gradeCanvas.height = 1920;
        this.gl = null;
        this.lut = null;
        this._lutUrl = null;
        this._srcTex = null;
        this._seekPending = new Set();
        this._stylesLoaded = false;
        this._exact = null;            // {name, t, frame|video} decoded frame (§16 P1)
        this._exactPending = false;
        const self = this;
        this.gradeCanvas.addEventListener("webglcontextlost", function (e) {
            e.preventDefault();
            self.gl = null; self._srcTex = null;
            console.warn("[canvasMonitor] WebGL context lost: 2D fallback until restored");
        });
        this.gradeCanvas.addEventListener("webglcontextrestored", function () {
            self._initGl();
            if (self._lutUrl) self.loadLut(self._lutUrl).catch(() => {});
        });
        this._initGl();
        this._loadStyles();
    }

    CanvasMonitor.prototype._loadStyles = function () {
        if (this._stylesLoaded) return;
        const self = this;
        if (typeof fetch === "function") {
            fetch("/core/styles.json").then(r => r.json()).then(j => {
                root.STYLES_JSON = j;
                self._stylesLoaded = true;
            }).catch(() => { self._stylesLoaded = true; });
        }
    };

    // ── WebGL2 grade pass with the own LUT (§16.6) ──────────────────────
    CanvasMonitor.prototype._initGl = function () {
        try {
            const gl = this.gradeCanvas.getContext("webgl2", { preserveDrawingBuffer: true });
            if (!gl) return;
            const vs = "#version 300 es\nin vec2 p;out vec2 vUv;void main(){vUv=p*.5+.5;gl_Position=vec4(p,0.,1.);}";
            const fs = "#version 300 es\nprecision highp float;precision highp sampler3D;\n" +
                "uniform sampler2D uSrc;uniform sampler3D uLut;uniform float uN;uniform float uOn;\n" +
                "in vec2 vUv;out vec4 o;\nvoid main(){vec3 c=texture(uSrc,vUv).rgb;" +
                "vec3 s=(clamp(c,0.,1.)*(uN-1.)+.5)/uN;" +
                "o=vec4(mix(c,texture(uLut,s).rgb,uOn),1.0);}";
            function sh(type, src) {
                const s = gl.createShader(type);
                gl.shaderSource(s, src); gl.compileShader(s);
                if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
                return s;
            }
            const prog = gl.createProgram();
            gl.attachShader(prog, sh(gl.VERTEX_SHADER, vs));
            gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, fs));
            gl.linkProgram(prog);
            if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog));
            gl.useProgram(prog);
            const buf = gl.createBuffer();
            gl.bindBuffer(gl.ARRAY_BUFFER, buf);
            gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
            const loc = gl.getAttribLocation(prog, "p");
            gl.enableVertexAttribArray(loc);
            gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
            this._uN = gl.getUniformLocation(prog, "uN");
            this._uOn = gl.getUniformLocation(prog, "uOn");
            this._uSrc = gl.getUniformLocation(prog, "uSrc");
            this._uLut = gl.getUniformLocation(prog, "uLut");
            this._prog = prog;
            // one reusable source texture (was: a new texture every frame)
            const tex = gl.createTexture();
            gl.activeTexture(gl.TEXTURE0);
            gl.bindTexture(gl.TEXTURE_2D, tex);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
            this._srcTex = tex;
            this.gl = gl;
        } catch (e) {
            console.warn("[canvasMonitor] WebGL2 grade unavailable, fallback to 2D:", e);
            this.gl = null;
        }
    };

    CanvasMonitor.prototype.loadLut = function (url) {
        const self = this;
        this._lutUrl = url;
        return fetch(url).then(r => r.text()).then(text => {
            const lut = LUT.parseCube(text);
            self.lut = lut;
            const gl = self.gl;
            if (!gl) return lut;
            const tex = gl.createTexture();
            gl.activeTexture(gl.TEXTURE1);
            gl.bindTexture(gl.TEXTURE_3D, tex);
            const rgba = new Uint8Array(lut.N * lut.N * lut.N * 4);
            for (let i = 0; i < lut.N * lut.N * lut.N; i++) {
                rgba[i * 4] = Math.round(255 * lut.data[i * 3]);
                rgba[i * 4 + 1] = Math.round(255 * lut.data[i * 3 + 1]);
                rgba[i * 4 + 2] = Math.round(255 * lut.data[i * 3 + 2]);
                rgba[i * 4 + 3] = 255;
            }
            gl.texImage3D(gl.TEXTURE_3D, 0, gl.RGBA8, lut.N, lut.N, lut.N, 0, gl.RGBA, gl.UNSIGNED_BYTE, rgba);
            gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
            gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
            gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
            gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
            gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_WRAP_R, gl.CLAMP_TO_EDGE);
            gl.uniform1f(self._uN, lut.N);
            return lut;
        });
    };

    // ── video pool: ONE hidden <video> per unique file (§16.2) ───────────
    CanvasMonitor.prototype.getVideo = function (clip) {
        const name = clip.media.filename;
        let el = this.videoPool.get(name);
        if (!el) {
            const existing = [document.getElementById("studioVideoPlayer"),
                              document.getElementById("studioOverlayPlayer")]
                .find(v => v && (v.getAttribute("data-file") || "") === name);
            if (existing) {
                this.videoPool.set(name, existing);
                return existing;
            }
            el = document.createElement("video");
            el.preload = "auto";
            el.playsInline = true;
            el.muted = true;                     // audio lives on the track audio els
            el.style.display = "none";
            el.setAttribute("data-file", name);
            el.setAttribute("data-pool", "1");
            document.body.appendChild(el);
            el.src = clip.media.stream_url;
            this.videoPool.set(name, el);
        }
        return el;
    };

    /** Drop pooled resources of a removed media file (decoder, <video>, frame). */
    CanvasMonitor.prototype.dropMedia = function (filename) {
        const el = this.videoPool.get(filename);
        if (el && el.getAttribute("data-pool") === "1") {
            try { el.pause(); el.removeAttribute("src"); el.load(); el.remove(); } catch (e) {}
        }
        this.videoPool.delete(filename);
        if (this._exact && this._exact.name === filename) this._closeExact();
        if (this.hooks.dropDecoder) { try { this.hooks.dropDecoder(filename); } catch (e) {} }
    };

    CanvasMonitor.prototype.enabled = function () {
        const s = this.hooks.settings();
        return !!(s && s.enabled);
    };

    CanvasMonitor.prototype.stepFrames = function (t, n) {
        const s = this.hooks.settings();
        return TM.stepFrames(t, s.fps || 60, n);
    };

    CanvasMonitor.prototype._decoderFor = function (clip) {
        if (!this.hooks.decoderFor) return null;
        try { return this.hooks.decoderFor(clip); } catch (e) { return null; }
    };

    CanvasMonitor.prototype._closeExact = function () {
        const ex = this._exact;
        if (ex && ex.frame) { try { ex.frame.close(); } catch (e) {} }
        this._exact = null;
    };

    /**
     * §16 P1: exact decoded frame for the paused preview. The frame stays
     * owned by the monitor until replaced and is ALWAYS closed (it used to
     * be dropped without close() -> GPU memory leak while scrubbing).
     */
    CanvasMonitor.prototype._takeExactFrame = function (clip, t, s) {
        const ex = this._exact;
        const halfFrame = 0.5 / (s.fps || 60);
        if (ex && ex.name === clip.media.filename && Math.abs(ex.t - t) < halfFrame) return ex;
        if (ex) this._closeExact();
        if (!s.playing && !this._exactPending) {
            const dec = this._decoderFor(clip);
            if (dec) {
                this._exactPending = true;
                const self = this;
                const tReq = t;
                const name = clip.media.filename;
                dec.requestFrame(tReq).then(function (res) {
                    self._exactPending = false;
                    if (res.ok) {
                        self._closeExact();
                        self._exact = { name: name, t: tReq, frame: res.frame };
                        self.renderAt(self.hooks.now ? self.hooks.now() : tReq);
                    } else if (res.proxy && res.video) {
                        self._closeExact();
                        self._exact = { name: name, t: tReq, video: res.video };
                        self.renderAt(self.hooks.now ? self.hooks.now() : tReq);
                    } else if (res.frame) {
                        try { res.frame.close(); } catch (e) {}
                    }
                }).catch(function () { self._exactPending = false; });
            }
        } else if (s.playing) {
            this._closeExact();
        }
        return null;
    };

    /** Timeline time -> time used for source lookup (freeze/ramp, same curve as export). */
    CanvasMonitor.prototype._remap = function (t, fx) {
        if (!TR || !fx || !fx.length) return t;
        return TR.remapTime(t, fx);
    };

    // ── render ───────────────────────────────────────────────────────────
    CanvasMonitor.prototype.renderAt = function (t) {
        const s = this.hooks.settings();
        if (!s.enabled) return false;
        const fx = this.hooks.fxAt ? (this.hooks.fxAt(t) || []) : [];
        const tSrc = this._remap(t, fx);
        const layers = this.hooks.videoClips(t);           // topmost first, unlimited
        const base = layers.length ? layers[layers.length - 1] : null;
        const w = this.wctx;
        const outW = this.work.width, outH = this.work.height;
        w.setTransform(1, 0, 0, 1, 0, 0);
        w.fillStyle = "#000";
        w.fillRect(0, 0, outW, outH);
        if (!base || !base.media) {
            this._blit(s, null);
            return true;
        }
        // camera fx: shake + whip offsets, zoom/lens scale with anchor
        let shake = { dx: 0, dy: 0 };
        let scale = 1, anchor = { x: 0.5, y: 0.5 }, blurPx = 0, threshold = false;
        for (const f of fx) {
            const a0 = fxIn(f), a1 = fxOut(f);
            if (f.kind === "shake") {
                const a = (f.amp || 12) * (1080 / 608);
                const env = Math.max(0, Math.min(1, Math.min(t - a0, a1 - t) / 0.1));
                shake.dx += a * Math.sin(2 * Math.PI * (f.freq || 7) * t) * env;
                shake.dy += a * Math.cos(2 * Math.PI * (f.freq || 7) * 9 / 7 * t) * env;
            } else if (f.kind === "zoom") {
                const z = zoomScale(f, t);
                if (z > scale) scale = z;
                if (f.anchor) anchor = f.anchor;
                else if (this.hooks.faceAnchor) {
                    const fa = this.hooks.faceAnchor(base, t);
                    if (fa) anchor = fa;
                }
            } else if (f.kind === "lens") {
                const p = Math.max(0, Math.min(1, (t - a0) / Math.max(0.05, a1 - a0)));
                const bell = p > 0 ? Math.exp(-Math.pow((p - 0.32) / 0.35, 2)) : 0;
                scale = Math.max(scale, 1 + 0.5 * (f.amp != null ? f.amp : 0.18) * bell);
            } else if (f.kind === "threshold") {
                if (t >= a0 && t <= a1) threshold = true;
            } else if (f.kind === "whip") {
                const dur = Math.max(0.05, a1 - a0);
                const p = (t - a0) / dur;
                if (p >= 0 && p <= 1) {
                    const dir = f.color === "left" ? -1 : 1;
                    // same clamp as export (0.25*W): never slides the frame out
                    const e = p < 0.5 ? smoothstep(p * 2) : 1 - smoothstep((p - 0.5) * 2);
                    shake.dx += dir * 0.25 * outW * e;
                    blurPx = Math.max(blurPx, 18 * e);
                }
            }
        }
        w.save();
        if (scale !== 1) {
            const ax = anchor.x * outW, ay = anchor.y * outH;
            w.translate(ax, ay);
            w.scale(scale, scale);
            w.translate(-ax, -ay);
        }
        w.translate(shake.dx, shake.dy);

        let v = this.getVideo(base);
        let srcW = v.videoWidth || 1280, srcH = v.videoHeight || 720;
        this._syncTime(v, base, tSrc, s);
        const exact = this._takeExactFrame(base, tSrc, s);
        if (exact) {
            v = exact.frame || exact.video;
            srcW = exact.frame ? exact.frame.displayWidth : (exact.video.videoWidth || srcW);
            srcH = exact.frame ? exact.frame.displayHeight : (exact.video.videoHeight || srcH);
        }
        const ops = GEO.composeDrawOps({
            format: s.format, srcW: srcW, srcH: srcH, outW: outW, outH: outH,
            cropBox: s.cropBox, bgBox: s.bgBox, topRatio: s.topRatio,
            sourceId: base.media.filename
        });
        if (blurPx > 0.5) w.filter = "blur(" + blurPx.toFixed(1) + "px)";
        for (const op of ops) {
            const ready = exact ? (exact.frame || exact.video.readyState >= 2) : v.readyState >= 2;
            if (ready) w.drawImage(v, op.sx, op.sy, op.sw, op.sh, op.dx, op.dy, op.dw, op.dh);
        }
        w.filter = "none";
        for (let i = layers.length - 2; i >= 0; i--) {
            const c = layers[i];
            if (!c.media) continue;
            const cv = this.getVideo(c);
            if (cv.readyState < 2) continue;
            this._syncTime(cv, c, tSrc, s);
            const isPip = c.isPip || c.pipBox || (c.trackPath && c.trackPath.length);
            if (!isPip) continue;
            const box = this.hooks.trackBoxFor(c, tSrc);
            const src = box
                ? { sx: box.x * (cv.videoWidth || 1), sy: box.y * (cv.videoHeight || 1),
                    sw: box.w * (cv.videoWidth || 1), sh: box.h * (cv.videoHeight || 1) }
                : { sx: 0, sy: 0, sw: cv.videoWidth || 1, sh: cv.videoHeight || 1 };
            const pr = GEO.pipRect(outW, outH, this.hooks.pipBoxFor(c));
            const dst = GEO.coverInto(src, pr.dx, pr.dy, pr.dw, pr.dh);
            w.save();
            w.beginPath();
            w.roundRect(pr.dx, pr.dy, pr.dw, pr.dh, Math.round(0.02 * outW));
            w.clip();
            w.drawImage(cv, dst.sx, dst.sy, dst.sw, dst.sh, dst.dx, dst.dy, dst.dw, dst.dh);
            w.restore();
        }
        w.restore();

        if (s.barTop > 0) { w.fillStyle = "#000"; w.fillRect(0, 0, outW, s.barTop); }
        if (s.barBottom > 0) { w.fillStyle = "#000"; w.fillRect(0, outH - s.barBottom, outW, s.barBottom); }

        for (const f of fx) {
            if (f.kind !== "flash") continue;
            const p = (t - fxIn(f)) / Math.max(1e-3, fxOut(f) - fxIn(f));
            if (p < 0 || p > 1) continue;
            const env = p < 0.12 ? p / 0.12 : Math.exp(-(p - 0.12) * 4.2);
            const colors = { white: "255,255,255", red: "255,34,34", green: "57,255,0" };
            const rgb = colors[f.color] || colors.white;
            w.fillStyle = "rgba(" + rgb + "," + ((f.peak || 0.85) * env).toFixed(3) + ")";
            w.fillRect(0, 0, outW, outH);
        }

        this._blit(s, threshold ? "grayscale(1) contrast(12) brightness(1.05)" : null);

        const cue = this.hooks.cueAt ? this.hooks.cueAt(t) : null;
        if (cue && this._stylesLoaded) {
            TXT.drawCue(this.ctx, cue, cue.localT != null ? cue.localT : t, outW, outH, cue.styleOverride);
        }
        return true;
    };

    CanvasMonitor.prototype._syncTime = function (video, clip, t, s) {
        const target = this.hooks.targetTime(clip, t);
        if (!isFinite(video.duration) || video.duration <= 0) return;
        if (s.playing) {
            const corr = TM.clockCorrection(video.currentTime, target);
            if (corr.action === "seek") {
                try { video.currentTime = Math.min(target, video.duration - 0.05); } catch (e) {}
            } else if (corr.action === "rate") {
                try { video.playbackRate = corr.rate; } catch (e) {}
            }
            if (video.paused) video.play().catch(() => {});
        } else {
            if (!video.paused) { try { video.pause(); } catch (e) {} }
            if (Math.abs(video.currentTime - target) > 0.002 && !this._seekPending.has(video)) {
                this._seekPending.add(video);
                const self = this;
                const onReady = () => {
                    self._seekPending.delete(video);
                    video.removeEventListener("seeked", onReady);
                    if (video.requestVideoFrameCallback) {
                        video.requestVideoFrameCallback(() => self.renderAt(self.hooks.now ? self.hooks.now() : t));
                    }
                };
                video.addEventListener("seeked", onReady);
                try { video.currentTime = Math.min(Math.max(0, target), video.duration - 0.05); } catch (e) {
                    this._seekPending.delete(video);
                }
            }
        }
    };

    /** Work canvas → (threshold) → WebGL2 grade (own LUT) → visible canvas. */
    CanvasMonitor.prototype._blit = function (s, filter) {
        const out = this.ctx;
        let src = this.work;
        if (filter) {
            this.fctx.filter = filter;
            this.fctx.drawImage(this.work, 0, 0);
            this.fctx.filter = "none";
            src = this.fxCanvas;
        }
        const gl = this.gl;
        if (gl && this.lut && s.gradeOn && !gl.isContextLost()) {
            gl.viewport(0, 0, this.gradeCanvas.width, this.gradeCanvas.height);
            gl.useProgram(this._prog);
            gl.activeTexture(gl.TEXTURE0);
            gl.bindTexture(gl.TEXTURE_2D, this._srcTex);
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, src);
            gl.uniform1i(this._uSrc, 0);
            gl.uniform1i(this._uLut, 1);
            gl.uniform1f(this._uOn, 1.0);
            gl.drawArrays(gl.TRIANGLES, 0, 3);
            out.drawImage(this.gradeCanvas, 0, 0);
        } else {
            out.drawImage(src, 0, 0);
        }
    };

    CanvasMonitor.prototype.dispose = function () {
        this._closeExact();
        for (const el of this.videoPool.values()) {
            if (el && el.getAttribute && el.getAttribute("data-pool") === "1") {
                try { el.pause(); el.remove(); } catch (e) {}
            }
        }
        this.videoPool.clear();
        if (this.gl && this._srcTex) { try { this.gl.deleteTexture(this._srcTex); } catch (e) {} }
    };

    CanvasMonitor.zoomScale = zoomScale;
    root.CoreCanvasMonitor = CanvasMonitor;
})(typeof self !== "undefined" ? self : this);
