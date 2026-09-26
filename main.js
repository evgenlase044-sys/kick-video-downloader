const { app, BrowserWindow, shell } = require('electron');
const path = require('path');
const http = require('http');
const { spawn } = require('child_process');

let mainWindow = null;
let backendProcess = null;
const SERVER_PORT = 8765;
const SERVER_URL = `http://127.0.0.1:${SERVER_PORT}/index.html`;
const HEALTH_URL = `http://127.0.0.1:${SERVER_PORT}/api/disk-info`;

function checkBackendHealth() {
    return new Promise((resolve) => {
        http.get(HEALTH_URL, (res) => {
            resolve(res.statusCode === 200);
        }).on('error', () => {
            resolve(false);
        });
    });
}

function startBackendServer() {
    return new Promise(async (resolve, reject) => {
        const isAlreadyRunning = await checkBackendHealth();
        if (isAlreadyRunning) {
            console.log('Python server already running on port', SERVER_PORT);
            return resolve();
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
