/* Kick Clip Studio — web/core/webcodecs.js
 * PLAN §16 P1 main-thread façade: feature detection, one AssetDecoder per
 * asset (worker with mp4 demux + VideoDecoder + ring cache), scrub policy
 * (jumps > 1.5 s display the proxy 960x540 GOP-10 frame instantly) and a
 * hard guarantee: any failure falls back to the P0 <video> pool. */
(function (root, factory) {
    const mod = factory();
    if (typeof module !== "undefined" && module.exports) module.exports = mod;
    root.CoreWebCodecs = mod;
})(typeof self !== "undefined" ? self : this, function () {
    "use strict";

    function supported() {
        return typeof VideoDecoder !== "undefined" &&
               typeof EncodedVideoChunk !== "undefined" &&
               typeof Worker !== "undefined" &&
               typeof fetch === "function";
    }

    /**
     * AssetDecoder: exact-frame requests for one media file.
     * Results: {ok:true, frame, display, t} — caller MUST frame.close() after
     * drawing; {proxy:true, video, t} — scrub jump, draw the proxy video;
     * {ok:false, error} — caller falls back to the P0 path.
     */
    function AssetDecoder(opts) {
        this.url = opts.url;
        this.proxyUrl = opts.proxyUrl || null;
        this.fps = opts.fps || 0;
        this.ready = false;
        this.failed = false;
        this._readyResolve = null;
        this._pending = new Map();     // t -> resolve
        this._reqSeq = 0;
        this._proxyVideo = null;
        const self = this;
        this.worker = new Worker("core/mp4/decoderWorker.js");
        this.worker.onmessage = function (ev) {
            const m = ev.data;
            if (m.type === "ready") {
                self.ready = true;
                if (self._readyResolve) { self._readyResolve(m); self._readyResolve = null; }
            } else if (m.type === "frame") {
                const r = self._pending.get(m.t);
                if (r) { self._pending.delete(m.t); r({ ok: true, frame: m.frame, display: m.display, t: m.t }); }
            } else if (m.type === "far") {
                // decode continues in the background; the proxy resolves now
                self._resolveAllViaProxy();
            } else if (m.type === "error") {
                self.failed = true;
                self._resolveAll({ ok: false, error: m.message });
            }
        };
        this.worker.onerror = function (e) {
            self.failed = true;
            self._resolveAll({ ok: false, error: e.message || "worker error" });
        };
        this._initPromise = new Promise(resolve => {
            self._readyResolve = resolve;
            setTimeout(() => {
                if (!self.ready && self._readyResolve) {
                    self._resolveAll({ ok: false, error: "init timeout" });
                    self.failed = true;
                }
            }, 8000);
            this.worker.postMessage({ type: "init", url: this.url });
        });
    }

    AssetDecoder.prototype._resolveAll = function (result) {
        for (const [t, r] of Array.from(this._pending)) {
            this._pending.delete(t);
            r(result);
        }
        if (this._readyResolve) { this._readyResolve({ error: result.error }); this._readyResolve = null; }
    };

    AssetDecoder.prototype._resolveAllViaProxy = function () {
        const self = this;
        for (const [t, r] of Array.from(this._pending)) {
            this._pending.delete(t);
            self._proxyFrame(t).then(p => r(p)).catch(e => r({ ok: false, error: String(e) }));
        }
    };

    AssetDecoder.prototype._proxyFrame = function (t) {
        const self = this;
        return new Promise(resolve => {
            if (!this.proxyUrl) { resolve({ ok: false, error: "no proxy" }); return; }
            if (!this._proxyVideo) {
                const v = document.createElement("video");
                v.preload = "auto";
                v.muted = true;
                v.playsInline = true;
                v.style.display = "none";
                v.src = this.proxyUrl;
                document.body.appendChild(v);
                this._proxyVideo = v;
            }
            const v = this._proxyVideo;
            const onReady = () => {
                v.removeEventListener("seeked", onReady);
                resolve({ proxy: true, video: v, t: t });
            };
            v.addEventListener("seeked", onReady);
            try { v.currentTime = t; } catch (e) { resolve({ ok: false, error: String(e) }); }
            setTimeout(() => resolve({ proxy: true, video: v, t: t }), 400); // debounce fallback
        });
    };

    /** Request the exact frame at source time t. Never rejects. */
    AssetDecoder.prototype.requestFrame = function (t) {
        const self = this;
        if (this.failed) return Promise.resolve({ ok: false, error: "failed" });
        return this._initPromise.then(info => {
            if (!self.ready) return { ok: false, error: (info && info.error) || "not ready" };
            return new Promise(resolve => {
                const tKey = Math.round(t * 1000) / 1000;
                self._pending.set(tKey, resolve);
                self.worker.postMessage({ type: "frame", t: tKey, fps: self.fps });
                setTimeout(() => {
                    if (self._pending.has(tKey)) {
                        self._pending.delete(tKey);
                        resolve({ ok: false, error: "timeout" });
                    }
                }, 3000);
            });
        });
    };

    AssetDecoder.prototype.close = function () {
        try { this.worker.postMessage({ type: "close" }); } catch (e) {}
        try { this.worker.terminate(); } catch (e) {}
        if (this._proxyVideo) { try { this._proxyVideo.remove(); } catch (e) {} }
    };

    const registry = new Map();   // filename -> AssetDecoder

    function decoderFor(filename, url, proxyUrl, fps) {
        if (!supported()) return null;
        let d = registry.get(filename);
        if (!d) {
            d = new AssetDecoder({ url: url, proxyUrl: proxyUrl, fps: fps });
            registry.set(filename, d);
        }
        return d;
    }

    function drop(filename) {
        const d = registry.get(filename);
        if (d) { d.close(); registry.delete(filename); }
    }

    return {
        supported: supported,
        AssetDecoder: AssetDecoder,
        decoderFor: decoderFor,
        drop: drop
    };
});
