/* Kick Clip Studio — web/core/mp4/ringCache.js
 * PLAN §16 P1: ring cache of at most 12 decoded VideoFrames per asset.
 * LRU eviction; every evicted frame gets close() — the accounting is pure
 * and injectable so Node tests can verify that no frame leaks. */
(function (root, factory) {
    const mod = factory();
    if (typeof module !== "undefined" && module.exports) module.exports = mod;
    root.CoreRingCache = mod;
})(typeof self !== "undefined" ? self : this, function () {
    "use strict";

    function RingCache(capacity, onClose) {
        this.capacity = capacity > 0 ? capacity : 12;
        this.onClose = onClose || function () {};
        this.map = new Map();        // key -> {item, bytes}
        this.closed = 0;
    }

    RingCache.prototype.has = function (key) { return this.map.has(key); };
    RingCache.prototype.get = function (key) {
        const hit = this.map.get(key);
        if (hit) {
            // refresh LRU order
            this.map.delete(key);
            this.map.set(key, hit);
        }
        return hit ? hit.item : null;
    };
    RingCache.prototype.put = function (key, item, bytes) {
        const existing = this.map.get(key);
        if (existing) {
            existing.item = item;
            existing.bytes = bytes || 0;
            return;
        }
        this.map.set(key, { item: item, bytes: bytes || 0 });
        while (this.map.size > this.capacity) {
            const oldestKey = this.map.keys().next().value;
            const oldest = this.map.get(oldestKey);
            this.map.delete(oldestKey);
            try { this.onClose(oldest.item); } catch (e) {}
            this.closed++;
        }
    };
    RingCache.prototype.clear = function () {
        for (const hit of this.map.values()) {
            try { this.onClose(hit.item); } catch (e) {}
            this.closed++;
        }
        this.map.clear();
    };
    Object.defineProperty(RingCache.prototype, "size", { get: function () { return this.map.size; } });

    return RingCache;
});
