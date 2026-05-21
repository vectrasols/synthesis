// updater.js — Auto-update logic using electron-updater
const { autoUpdater, AppImageUpdater, DebUpdater, RpmUpdater } = require('electron-updater');
const { ipcMain } = require('electron');
const log = require('electron-log');
const fs = require('fs');
export {};

const updater = createUpdater();
updater.logger = log;
updater.logger.transports.file.level = 'info';

// Disable auto-install on quit for manual control
updater.autoInstallOnAppQuit = false;

function createUpdater() {
  if (process.platform !== 'linux') return autoUpdater;
  if (process.env.APPIMAGE) return new AppImageUpdater();

  const distro = readLinuxDistro();
  if (/(debian|ubuntu|linuxmint|pop|elementary|zorin|kali|raspbian)/.test(distro)) {
    log.info(`Using DebUpdater for Linux distro: ${distro || 'unknown'}`);
    return new DebUpdater();
  }
  if (/(fedora|rhel|centos|rocky|almalinux|opensuse|suse|mageia)/.test(distro)) {
    log.info(`Using RpmUpdater for Linux distro: ${distro || 'unknown'}`);
    return new RpmUpdater();
  }

  log.info(`Using default Linux updater for distro: ${distro || 'unknown'}`);
  return autoUpdater;
}

function readLinuxDistro() {
  try {
    const text = fs.readFileSync('/etc/os-release', 'utf8').toLowerCase();
    const values: Record<string, string> = {};
    text.split(/\r?\n/).forEach(line => {
      const match = line.match(/^([a-z_]+)=(.*)$/);
      if (!match) return;
      values[match[1]] = match[2].replace(/^"|"$/g, '');
    });
    return `${values.id || ''} ${values.id_like || ''}`;
  } catch {
    return '';
  }
}

function setupUpdater(mainWindow) {
  // Forward updater events to renderer
  updater.on('checking-for-update', () => {
    log.info('Checking for update...');
  });

  updater.on('update-available', (info) => {
    log.info('Update available:', info.version);
    mainWindow.webContents.send('update-available', {
      version: info.version,
      releaseDate: info.releaseDate,
      releaseNotes: info.releaseNotes,
    });
  });

  updater.on('update-not-available', () => {
    log.info('Update not available');
  });

  updater.on('error', (err) => {
    log.error('Update error:', err.message);
    mainWindow.webContents.send('update-error', err.message);
  });

  updater.on('download-progress', (progress) => {
    mainWindow.webContents.send('download-progress', {
      percent: Math.round(progress.percent),
      transferred: progress.transferred,
      total: progress.total,
      speed: progress.bytesPerSecond,
    });
  });

  updater.on('update-downloaded', (info) => {
    log.info('Update downloaded:', info.version);
    mainWindow.webContents.send('update-downloaded', {
      version: info.version,
    });
  });

  // Handle install request from renderer
  ipcMain.on('install-update', () => {
    updater.quitAndInstall(false, true);
  });

  // Check for updates (delay 3 seconds after app loads)
  setTimeout(() => {
    updater.checkForUpdates().catch((err) => {
      log.warn('Update check failed (this is normal in dev):', err.message);
    });
  }, 3000);
}

module.exports = { setupUpdater };
