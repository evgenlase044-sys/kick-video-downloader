const { app, BrowserWindow, shell } = require('electron');
const path = require('path');
const http = require('http');
const fs = require('fs');
const { spawn, execSync } = require('child_process');

let mainWindow = null;
let backendProcess = null;
const SERVER_PORT = 8765;
const BASE = `http://127.0.0.1:${SERVER_PORT}`;
const VERSION_URL = `${BASE}/api/version`;       // public (no token)
const SHUTDOWN_URL = `${BASE}/api/shutdown`;
const TOKEN_FILE = path.join(__dirname, '.studio', 'token');

function readToken() {
    try { return fs.readFileSync(TOKEN_FILE, 'utf8').trim(); } catch (e) { return ''; }
}

function httpJson(url, method = 'GET', token = '') {
    return new Promise((resolve) => {
        const headers = token ? { 'X-Studio-Token': token } : {};
        const req = http.request(url, { method, timeout: 3000, headers }, (res) => {
            let body = '';
            res.on('data', (c) => { body += c; });
            res.on('end', () => {
                try { resolve({ status: res.statusCode, json: JSON.parse(body) }); }
                catch (e) { resolve({ status: res.statusCode, json: null }); }
            });
        });
        req.on('error', () => resolve(null));
        req.on('timeout', () => { req.destroy(); resolve(null); });
        req.end();
    });
}

async function alive() {
    const r = await httpJson(VERSION_URL);
    return !!(r && r.status === 200);
}

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

// same rule as studio/server_hooks.code_mtime_ms: newest of server.py,
// studio_server.py and studio/*.py
function codeMtime() {
    const files = ['server.py', 'studio_server.py'].map(f => path.join(__dirname, f));
    try {
        for (const f of fs.readdirSync(path.join(__dirname, 'studio'))) {
            if (f.endsWith('.py')) files.push(path.join(__dirname, 'studio', f));
        }
    } catch (e) {}
    let m = 0;
    for (const f of files) { try { m = Math.max(m, fs.statSync(f).mtimeMs); } catch (e) {} }
    return Math.round(m);
}

function killTree(pid) {
    if (!pid) return;
    try {
        if (process.platform === 'win32') {
            // /T: also ffmpeg children (no orphans)
            execSync(`taskkill /PID ${pid} /T /F`, { shell: 'cmd.exe', stdio: 'ignore' });
        } else {
            process.kill(-pid, 'SIGTERM');
        }
    } catch (e) {}
}

// N16: a running backend may belong to another copy or older code
async function ensureFreshBackend() {
    if (!(await alive())) return;
    const ver = await httpJson(VERSION_URL);
    const sameDir = ver && ver.json && path.normalize(ver.json.server_dir || '').toLowerCase() === path.normalize(__dirname).toLowerCase();
    const sameCode = ver && ver.json && Math.abs((ver.json.server_mtime || 0) - codeMtime()) < 2000;
    if (sameDir && sameCode && readToken()) {
        console.log('Existing backend is current. Reusing it.');
        return;
    }
    console.log('Stale/foreign backend on port', SERVER_PORT, '- restarting.');
    await httpJson(SHUTDOWN_URL, 'POST', readToken());
    for (let i = 0; i < 20 && (await alive()); i++) await sleep(250);
    if (await alive() && process.platform === 'win32') {
        try {
            const out = execSync(`netstat -ano | findstr :${SERVER_PORT} | findstr LISTENING`, { shell: 'cmd.exe' }).toString();
            const pids = [...new Set(out.split(/\r?\n/).map(l => l.trim().split(/\s+/).pop()).filter(Boolean))];
            for (const pid of pids) if (pid !== String(process.pid)) killTree(pid);
        } catch (e) { console.warn('Port force-free failed:', e.message); }
        await sleep(500);
    }
}

async function startBackendServer() {
    try { await ensureFreshBackend(); } catch (e) { console.warn('Version check failed:', e); }
    if (await alive()) return;
    backendProcess = spawn('python', [path.join(__dirname, 'studio_server.py'), '--port', String(SERVER_PORT)], {
        cwd: __dirname, stdio: 'ignore', windowsHide: true,
        detached: process.platform !== 'win32'   // own process group -> kill(-pid)
    });
    backendProcess.on('error', (err) => console.error('Failed to start Python backend:', err));
    for (let i = 0; i < 60; i++) {
        await sleep(300);
        if (await alive()) return;
    }
    throw new Error('Server failed to start within timeout');
}

async function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1360, height: 880, minWidth: 1040, minHeight: 700,
        backgroundColor: '#090c0f', autoHideMenuBar: true,
        title: 'Kick Video Studio | Студия видеомонтажа',
        webPreferences: { nodeIntegration: false, contextIsolation: true }
    });
    try {
        await startBackendServer();
        // the token becomes an HttpOnly SameSite=Strict cookie on first load
        mainWindow.loadURL(`${BASE}/index.html?token=${encodeURIComponent(readToken())}`);
    } catch (e) {
        console.error('Initialization error:', e);
        mainWindow.loadFile(path.join(__dirname, 'web', 'index.html'));
    }
    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
        shell.openExternal(url);
        return { action: 'deny' };
    });
    mainWindow.on('closed', () => { mainWindow = null; });
}

app.whenReady().then(createWindow);

function stopBackend() {
    if (backendProcess) { killTree(backendProcess.pid); backendProcess = null; }
}

app.on('window-all-closed', () => {
    stopBackend();
    if (process.platform !== 'darwin') app.quit();
});
app.on('quit', stopBackend);
