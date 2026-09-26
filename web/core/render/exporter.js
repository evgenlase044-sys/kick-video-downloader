/* Kick Clip Studio — web/core/render/exporter.js
 * PLAN §17.2: draw-list executor + WebSocket render session. The renderer
 * evaluates renderFrame(comp, f) per composition frame, rasterizes it with
 * the SAME deterministic core the preview uses (2D composite -> WebGL2 LUT
 * grade -> canvas text), packs RGBA -> yuv420p (BT.709 limited, §17.2
 * formulas) and streams raw frames over ws://…/ws/render/{job} with ≤ 8
 * unacked credit frames. Browser-only (needs canvas/WebSocket). */
(function (root) {
    "use strict";
    const CMP = root.CoreComposition;
    const COMP = root.CoreComposer;
    const TXT = root.CoreCanvasText;
    const YUV = root.CoreYuv;

    /** WebGL2 grade pass with the own 65^3 LUT (same mapping as the monitor). */
    function makeGradePass(lut) {
        const canvas = document.createElement("canvas");
        canvas.width = 1080; canvas.height = 1920;
        const gl = canvas.getContext("webgl2", { preserveDrawingBuffer: true });
        if (!gl) return null;
        try {
            const vs = "#version 300 es\nin vec2 p;out vec2 vUv;void main(){vUv=p*.5+.5;gl_Position=vec4(p,0.,1.);}";
            const fs = "#version 300 es\nprecision highp float;precision highp sampler3D;\n" +
                "uniform sampler2D uSrc;uniform sampler3D uLut;uniform float uN;\n" +
                "in vec2 vUv;out vec4 o;\nvoid main(){vec3 c=texture(uSrc,vUv).rgb;" +
                "vec3 s=(clamp(c,0.,1.)*(uN-1.)+.5)/uN;" +
                "o=vec4(texture(uLut,s).rgb,1.0);}";
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
            gl.uniform1f(gl.getUniformLocation(prog, "uN"), lut.N);
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
            gl.uniform1i(gl.getUniformLocation(prog, "uSrc"), 0);
            gl.uniform1i(gl.getUniformLocation(prog, "uLut"), 1);
            return { canvas: canvas, gl: gl, prog: prog };
        } catch (e) {
            console.warn("[exporter] grade pass unavailable:", e);
            return null;
        }
    }

    /**
     * ExportSession: streams one composition to /ws/render/{job}.
     * opts: { comp, lut, audioWav, out, wsBase,
     *         videoSource(assetName, srcTime) -> {image, w, h} | null }
     */
    function ExportSession(opts) {
        this.comp = opts.comp;
        this.lut = opts.lut || null;
        this.audioWav = opts.audioWav || "";
        this.out = opts.out || ("RendererExport_" + Date.now() + ".mp4");
        this.wsBase = opts.wsBase || ("ws://127.0.0.1:" + location.port);
        this.videoSource = opts.videoSource || function () { return null; };
        this.onProgress = opts.onProgress || function () {};
        this.W = this.comp.canvas.w;
        this.H = this.comp.canvas.h;
        this.fps = this.comp.canvas.fps;
        this.frames = Math.max(1, Math.round((this.comp.duration || 0) * this.fps));
        this.work = document.createElement("canvas");
        this.work.width = this.W; this.work.height = this.H;
        this.ctx = this.work.getContext("2d", { willReadFrequently: true });
        this.grade = this.lut ? makeGradePass(this.lut) : null;
    }

    ExportSession.prototype._rasterize = function (f) {
        const frame = COMP.renderFrame(this.comp, f, { scale: 1 });
        const ctx = this.ctx;
        const W = this.W, H = this.H;
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.fillStyle = "#000";
        ctx.fillRect(0, 0, W, H);
        ctx.save();
        ctx.translate(frame.shake.dx, frame.shake.dy);
        for (const op of frame.ops) {
            if (op.op !== "video") continue;
            const mt = CMP.mapTime(this.comp.layers.find(l => l.id === op.layerId) || {}, frame.t);
            const vs = this.videoSource(op.asset, mt.src);
            if (!vs || !vs.image) continue;
            ctx.drawImage(vs.image, op.sx, op.sy, op.sw, op.sh, op.dx, op.dy, op.dw, op.dh);
        }
        ctx.restore();
        for (const op of frame.ops) {
            if (op.op === "bars") {
                ctx.fillStyle = "#000";
                if (op.band === "top") ctx.fillRect(0, 0, W, op.h);
                else ctx.fillRect(0, H - op.h, W, op.h);
            }
        }
        for (const op of frame.ops) {
            if (op.op !== "flash") continue;
            const colors = { white: "255,255,255", red: "255,34,34", green: "57,255,0" };
            ctx.fillStyle = "rgba(" + (colors[op.color] || colors.white) + "," + op.alpha.toFixed(3) + ")";
            ctx.fillRect(0, 0, W, H);
        }
        // grade via WebGL2 LUT pass (§14.6); ungraded otherwise
        if (frame.grade.on && this.grade) {
            const gl = this.grade.gl;
            gl.viewport(0, 0, W, H);
            gl.useProgram(this.grade.prog);
            const tex = gl.createTexture();
            gl.activeTexture(gl.TEXTURE0);
            gl.bindTexture(gl.TEXTURE_2D, tex);
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, this.work);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
            gl.drawArrays(gl.TRIANGLES, 0, 3);
            gl.deleteTexture(tex);
            ctx.drawImage(this.grade.canvas, 0, 0);
        }
        // text last, ungraded (preview == export parity)
        for (const cue of frame.textCues) {
            TXT.drawCue(ctx, cue, cue.localT, W, H);
        }
        return frame;
    };

    /** Stream the whole composition. Resolves with the final server message. */
    ExportSession.prototype.run = function () {
        const self = this;
        return new Promise((resolve, reject) => {
            const job = "r" + Date.now().toString(36);
            const ws = new WebSocket(this.wsBase + "/ws/render/" + job);
            let unacked = 0;
            let f = 0;
            let opened = false;
            const t0 = performance.now();
            ws.onerror = (e) => { if (!opened) reject(new Error("ws error")); };
            ws.onmessage = (ev) => {
                const m = JSON.parse(ev.data);
                if (m.ack != null) {
                    unacked -= 1;
                    self.onProgress({ frame: m.ack, frames: self.frames });
                    pump();
                } else if (m.done != null) {
                    resolve(Object.assign(m, { seconds: (performance.now() - t0) / 1000 }));
                } else if (m.error) {
                    reject(new Error(m.error));
                }
            };
            ws.onclose = () => { if (opened) reject(new Error("ws closed before done")); };
            ws.onopen = () => {
                opened = true;
                ws.send(JSON.stringify({
                    w: self.W, h: self.H, fps: self.fps,
                    frames: self.frames, audio_wav: self.audioWav, out: self.out
                }));
                pump();
            };
            function pump() {
                while (opened && unacked < 8 && f < self.frames) {
                    self._rasterize(f);
                    const data = self.ctx.getImageData(0, 0, self.W, self.H).data;
                    const pl = YUV.packYuv420(data, self.W, self.H);
                    ws.send(YUV.interleave(pl).buffer);
                    f += 1;
                    unacked += 1;
                }
                if (f >= self.frames && unacked === 0 && opened) {
                    // all frames acked; wait for done (server closes after)
                }
            }
        });
    };

    root.CoreExporter = {
        makeGradePass: makeGradePass,
        ExportSession: ExportSession
    };
})(typeof self !== "undefined" ? self : this);
