const { app, BrowserWindow, shell } = require('electron');
const path = require('path');
const http = require('http');
const fs = require('fs');
const { spawn, execSync } = require('child_process');

let mainWindow = null;
let backendProcess = null;
const SERVER_PORT = 8765;
const SERVER_URL = `http://127.0.0.1:${SERVER_PORT}/index.html`;
const HEALTH_URL = `http://127.0.0.1:${SERVER_PORT}/api/disk-info`;
const VERSION_URL = `http://127.0.0.1:${SERVER_PORT}/api/version`;
const SHUTDOWN_URL = `http://127.0.0.1:${SERVER_PORT}/api/shutdown`;

function httpJson(url, method = 'GET') {
    return new Promise((resolve) => {
        const req = http.request(url, { method, timeout: 3000 }, (res) => {
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

function checkBackendHealth() {
    return new Promise((resolve) => {
        http.get(HEALTH_URL, (res) => {
            res.resume();
            resolve(res.statusCode === 200);
        }).on('error', () => resolve(false));
    });
}

function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
}

// N16: a running server.py may belong to another copy of the repo or predate
// the current code. Verify identity and restart it if stale.
async function ensureFreshBackend() {
    const alive = await checkBackendHealth();
    if (!alive) return; // nothing running; spawn below

    const ver = await httpJson(VERSION_URL);
    const expectedMtime = Math.round(fs.statSync(path.join(__dirname, 'server.py')).mtimeMs);
    const sameDir = ver && ver.json && path.normalize(ver.json.server_dir || '').toLowerCase() === path.normalize(__dirname).toLowerCase();
    const sameCode = ver && ver.json && Math.abs((ver.json.server_mtime || 0) - expectedMtime) < 2000;
    if (ver && ver.json && sameDir && sameCode) {
        console.log('Existing python server is current (dir + mtime match). Reusing it.');
        return;
    }
    console.log('Stale/foreign server.py detected on port', SERVER_PORT, '— restarting backend.', JSON.stringify(ver && ver.json));

    if (ver && ver.json && ver.status === 200) {
        await httpJson(SHUTDOWN_URL, 'POST');
    }
    // wait for the port to free up
    for (let i = 0; i < 20; i++) {
        if (!(await checkBackendHealth())) break;
        await sleep(250);
    }
    // last resort: kill whatever still holds the port
    if (await checkBackendHealth()) {
        try {
            if (process.platform === 'win32') {
                const out = execSync(`netstat -ano | findstr :${SERVER_PORT} | findstr LISTENING`, { shell: 'cmd.exe' }).toString();
                const pids = [...new Set(out.split(/\r?\n/).map(l => l.trim().split(/\s+/).pop()).filter(Boolean))];
                for (const pid of pids) {
                    if (pid && pid !== String(process.pid)) execSync(`taskkill /PID ${pid} /F`, { shell: 'cmd.exe' });
                }
            }
        } catch (e) { console.warn('Port force-free failed:', e.message); }
        await sleep(500);
    }
}

function startBackendServer() {
    return new Promise(async (resolve, reject) => {
        try {
            await ensureFreshBackend();
        } catch (e) {
            console.warn('Version check failed:', e);
        }

        console.log('Spawning Python server.py...');
        const scriptPath = path.join(__dirname, 'server.py');
        backendProcess = spawn('python', [scriptPath], {
            cwd: __dirname,
            stdio: 'ignore',
            windowsHide: true
        });

        backendProcess.on('error', (err) => {
            console.error('Failed to start Python backend:', err);
            reject(err);
        });

        // Poll for server availability
        let attempts = 0;
        const interval = setInterval(async () => {
            attempts++;
            const ready = await checkBackendHealth();
            if (ready) {
                clearInterval(interval);
                // N16: verify the freshly spawned copy answers with our identity
                const ver = await httpJson(VERSION_URL);
                if (ver && ver.json && ver.json.server_dir) {
                    const same = path.normalize(ver.json.server_dir).toLowerCase() === path.normalize(__dirname).toLowerCase();
                    if (!same) {
                        clearInterval(interval);
                        return reject(new Error('Server identity mismatch after restart'));
                    }
                }
                console.log('Python server is ready!');
                resolve();
            } else if (attempts > 30) {
                clearInterval(interval);
                reject(new Error('Server failed to start within timeout'));
            }
        }, 300);
    });
}

async function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1360,
        height: 880,
        minWidth: 1040,
        minHeight: 700,
        backgroundColor: '#090c0f',
        autoHideMenuBar: true,
        title: 'Kick Video Studio | Студия видеомонтажа',
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true
        }
    });

    try {
        await startBackendServer();
        mainWindow.loadURL(SERVER_URL);
    } catch (e) {
        console.error('Initialization error:', e);
        mainWindow.loadFile(path.join(__dirname, 'web', 'index.html'));
    }

    // Open external links in default browser
    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
        shell.openExternal(url);
        return { action: 'deny' };
    });

    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
    if (backendProcess) {
        try {
            backendProcess.kill();
        } catch (e) {}
    }
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('quit', () => {
    if (backendProcess) {
        try {
            backendProcess.kill();
        } catch (e) {}
    }
});
