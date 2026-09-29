/* Kick Clip Studio — tools/gl_equiv_test.js
 * GPU<->JS equivalence runner: opens a hidden BrowserWindow, loads
 * web/core/render/gltest.html (which runs the WebGL2 passes and the pure JS
 * cores on identical inputs and prints "GLTEST:{json}"), forwards the JSON to
 * stdout and exits. Run: npx electron tools/gl_equiv_test.js
 * On CI: xvfb-run -a npx electron tools/gl_equiv_test.js (headless display).
 * Pass thresholds: jfa<=1, kawase<=0.5, lens<=0.02 (see tests/fixtures/gl_ref.json if pinned).
 * Win headless requires --no-sandbox on some runners; add to BrowserWindow if needed. */
const { app, BrowserWindow } = require("electron");
const path = require("path");

let win = null;
let result = null;
let done = false;

function finish(code) {
    if (done) return;
    done = true;
    if (result) {
        console.log(result);
        try {
            const data = JSON.parse(result.slice(7));
            const limits = { jfa: 1.0, kawase: 0.5, lens: 0.02 };
            const over = Object.entries(limits).filter(([k, lim]) => typeof data[k] === "number" && data[k] > lim);
            if (over.length) console.error("[gl_equiv] threshold exceeded:", over.map(([k]) => `${k}=${data[k]}`).join(", "));
        } catch {}
    } else console.log("GLTEST:" + JSON.stringify({ ok: false, error: "timeout" }));
    app.exit(code);
}

app.whenReady().then(async () => {
    try {
        win = new BrowserWindow({
            show: false,
            width: 800,
            height: 600,
            webPreferences: { backgroundThrottling: false, offscreen: false }
        });
        win.webContents.on("console-message", (ev, level, message) => {
            const msg = typeof ev === "object" && ev.message !== undefined ? ev.message : message;
            if (process.env.GLDEBUG) {
                console.error("[page]", String(msg).slice(0, 250));
            }
            if (typeof msg === "string" && msg.startsWith("GLTEST:")) {
                result = msg;
                try {
                    const data = JSON.parse(msg.slice(7));
                    finish(data.ok ? 0 : 3);
                } catch (e) {
                    finish(3);
                }
            }
        });
        await win.loadFile(path.join(__dirname, "..", "web", "core", "render", "gltest.html"));
    } catch (e) {
        result = "GLTEST:" + JSON.stringify({ ok: false, error: String(e && e.message || e) });
        finish(3);
        return;
    }
    setTimeout(() => finish(2), 10000);
});
setTimeout(() => finish(2), 30000);
if (!app.isReady()) {
    setTimeout(() => {
        if (!done) {
            result = "GLTEST:" + JSON.stringify({ ok: false, error: "app never ready" });
            finish(2);
        }
    }, 15000);
}
