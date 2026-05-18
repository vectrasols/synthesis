// index.js — Electron main process
// Spawns the Python FastAPI backend, creates the BrowserWindow, handles IPC.

'use strict';

const { app, BrowserWindow, ipcMain, dialog, shell, Menu, Tray, nativeImage, clipboard } = require('electron');
const path = require('path');
const fs = require('fs');
const net = require('net');
const { spawn, execFileSync } = require('child_process');
const { setupUpdater } = require('./updater');
export {};

// ─── Globals ───────────────────────────────────────────────────────────────────
let mainWindow = null;
let tray = null;
let pythonProcess = null;
let backendPort = null;
const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;
const defaultCondaEnv = process.env.SYNTHESIS_CONDA_ENV || 'workenv';

// ─── Find a free port ─────────────────────────────────────────────────────────
function getFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const port = server.address().port;
      server.close(() => resolve(port));
    });
  });
}

function getPythonPathFromEnvRoot(envRoot) {
  if (!envRoot) return null;
  return process.platform === 'win32'
    ? path.join(envRoot, 'python.exe')
    : path.join(envRoot, 'bin', 'python');
}

function findCondaEnvRoot(envName) {
  try {
    const raw = execFileSync('conda', ['info', '--envs', '--json'], {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    });
    const info = JSON.parse(raw);
    return (info.envs || []).find(envPath => path.basename(envPath) === envName) || null;
  } catch {
    return null;
  }
}

function resolveDevPython() {
  const explicitPython = process.env.SYNTHESIS_PYTHON;
  if (explicitPython && fs.existsSync(explicitPython)) {
    return explicitPython;
  }

  const condaRoot = findCondaEnvRoot(defaultCondaEnv);
  const condaPython = getPythonPathFromEnvRoot(condaRoot);
  if (condaPython && fs.existsSync(condaPython)) {
    return condaPython;
  }

  const activeCondaPython = getPythonPathFromEnvRoot(process.env.CONDA_PREFIX);
  if (activeCondaPython && fs.existsSync(activeCondaPython)) {
    return activeCondaPython;
  }

  if (process.env.SYNTHESIS_ALLOW_SYSTEM_PYTHON === '1') {
    return process.platform === 'win32' ? 'python' : 'python3';
  }

  throw new Error(
    `Conda environment '${defaultCondaEnv}' was not found. ` +
    `Create it or set SYNTHESIS_CONDA_ENV / SYNTHESIS_PYTHON. ` +
    `Set SYNTHESIS_ALLOW_SYSTEM_PYTHON=1 only if you intentionally want the system Python fallback.`
  );
}

// ─── Spawn Python backend ─────────────────────────────────────────────────────
async function startPythonBackend() {
  backendPort = await getFreePort();
  console.log(`[Synthesis] Starting Python backend on port ${backendPort}`);

  let pythonExe, serverScript;

  if (isDev) {
    // Development: prefer the named Conda environment for reproducible backend deps.
    pythonExe = resolveDevPython();
    serverScript = path.join(__dirname, '..', 'python-backend', 'server.py');
  } else {
    // Production: use bundled PyInstaller binary
    const resourcePath = (process as typeof process & { resourcesPath: string }).resourcesPath;
    const binaryName = process.platform === 'win32' ? 'server.exe' : 'server';
    serverScript = path.join(resourcePath, 'python-backend', binaryName);
    pythonExe = null; // We'll run the binary directly
  }

  const args = ['--port', String(backendPort)];
  const spawnOptions = {
    stdio: ['ignore', 'pipe', 'pipe'],
    detached: false,
    env: { ...process.env },
  };

  if (pythonExe) {
    console.log(`[Synthesis] Python executable: ${pythonExe}`);
    pythonProcess = spawn(pythonExe, [serverScript, ...args], spawnOptions);
  } else {
    pythonProcess = spawn(serverScript, args, spawnOptions);
  }

  pythonProcess.stdout?.on('data', (d) => console.log('[Python]', d.toString().trim()));
  pythonProcess.stderr?.on('data', (d) => console.error('[Python ERR]', d.toString().trim()));
  pythonProcess.on('exit', (code) => console.log(`[Python] exited with code ${code}`));

  // Wait until server is ready
  await waitForServer(backendPort, 30000);
  console.log(`[Synthesis] Backend ready on port ${backendPort}`);
}

// Poll /api/health until server responds
function waitForServer(port, timeoutMs) {
  const http = require('http');
  const startTime = Date.now();

  return new Promise<void>((resolve, reject) => {
    function check() {
      if (Date.now() - startTime > timeoutMs) {
        reject(new Error('Python backend did not start in time'));
        return;
      }
      const req = http.get(`http://127.0.0.1:${port}/api/health`, (res) => {
        if (res.statusCode === 200) resolve();
        else setTimeout(check, 300);
      });
      req.on('error', () => setTimeout(check, 300));
      req.setTimeout(500, () => { req.destroy(); setTimeout(check, 300); });
    }
    check();
  });
}

// ─── Create Window ────────────────────────────────────────────────────────────
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1500,
    height: 920,
    minWidth: 1120,
    minHeight: 720,
    backgroundColor: '#1e1e23',
    show: false,
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
    icon: path.join(__dirname, '..', 'assets', 'icon.png'),
  });

  // Load the renderer
  mainWindow.loadFile(path.join(__dirname, '..', 'renderer', 'index.html'));

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    mainWindow.maximize();
    if (isDev) mainWindow.webContents.openDevTools({ mode: 'detach' });
  });

  // Handle external links
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.on('closed', () => { mainWindow = null; });

  // Setup auto-updater
  if (!isDev) {
    try { setupUpdater(mainWindow); } catch (e) { console.warn('Updater setup skipped:', e.message); }
  }
}

// ─── System Tray ─────────────────────────────────────────────────────────────
function createTray() {
  const iconPath = path.join(__dirname, '..', 'assets', 'icon.png');
  if (!fs.existsSync(iconPath)) return;

  const icon = nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 });
  tray = new Tray(icon);
  tray.setToolTip('Synthesis');
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: 'Open Synthesis', click: () => { mainWindow?.show(); mainWindow?.focus(); } },
    { type: 'separator' },
    { label: 'Quit', click: () => app.quit() },
  ]));
  tray.on('click', () => { mainWindow?.show(); mainWindow?.focus(); });
}

// ─── IPC Handlers ─────────────────────────────────────────────────────────────
function registerIpcHandlers() {
  // Provide backend port to renderer
  ipcMain.handle('get-backend-port', () => backendPort);

  // App version
  ipcMain.handle('get-version', () => app.getVersion());

  // Open file dialog
  ipcMain.handle('open-file', async (_, filters = []) => {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openFile'],
      filters: filters.length ? filters : [
        { name: 'Data Files', extensions: ['csv', 'xlsx', 'xls', 'json', 'tsv', 'parquet'] },
        { name: 'All Files', extensions: ['*'] },
      ],
    });
    return result.canceled ? null : result.filePaths[0];
  });

  // Save file dialog
  ipcMain.handle('save-file', async (_, defaultName = 'file', filters = []) => {
    const result = await dialog.showSaveDialog(mainWindow, {
      defaultPath: defaultName,
      filters: filters.length ? filters : [
        { name: 'CSV Files', extensions: ['csv'] },
        { name: 'All Files', extensions: ['*'] },
      ],
    });
    return result.canceled ? null : result.filePath;
  });

  // Read file from disk as base64
  ipcMain.handle('read-file', async (_, filePath) => {
    return fs.readFileSync(filePath);
  });

  // Read text from the system clipboard
  ipcMain.handle('read-clipboard-text', async () => {
    return clipboard.readText();
  });

  // Write bytes to disk
  ipcMain.handle('write-file', async (_, filePath, data) => {
    fs.writeFileSync(filePath, Buffer.from(data));
    return true;
  });
}

// ─── App lifecycle ─────────────────────────────────────────────────────────────
app.whenReady().then(async () => {
  registerIpcHandlers();
  Menu.setApplicationMenu(null);

  try {
    await startPythonBackend();
  } catch (err) {
    console.error('Failed to start Python backend:', err.message);
    dialog.showErrorBox('Startup Error', `Could not start the Python backend:\n${err.message}`);
    app.quit();
    return;
  }

  createWindow();
  createTray();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  if (pythonProcess) {
    pythonProcess.kill();
    pythonProcess = null;
  }
});

// Prevent multiple instances
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
}
