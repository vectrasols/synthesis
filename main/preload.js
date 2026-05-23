"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
// preload.js — Context bridge: exposes safe APIs from main to renderer
const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('electronAPI', {
    // Get the port Python backend is running on
    getBackendPort: () => ipcRenderer.invoke('get-backend-port'),
    // Clipboard access
    readClipboardText: () => ipcRenderer.invoke('read-clipboard-text'),
    // Native file dialogs
    openFile: (filters) => ipcRenderer.invoke('open-file', filters),
    saveFile: (defaultName, filters) => ipcRenderer.invoke('save-file', defaultName, filters),
    // Read a file chosen via native dialog as buffer
    readFile: (filePath) => ipcRenderer.invoke('read-file', filePath),
    // Write bytes to a path
    writeFile: (filePath, data) => ipcRenderer.invoke('write-file', filePath, data),
    // Auto-update events
    onUpdateAvailable: (cb) => ipcRenderer.on('update-available', (_, info) => cb(info)),
    onUpdateDownloaded: (cb) => ipcRenderer.on('update-downloaded', (_, info) => cb(info)),
    onUpdateError: (cb) => ipcRenderer.on('update-error', (_, err) => cb(err)),
    onDownloadProgress: (cb) => ipcRenderer.on('download-progress', (_, progress) => cb(progress)),
    onUpdateInstalling: (cb) => ipcRenderer.on('update-installing', (_, info) => cb(info)),
    // Trigger install & restart after update downloaded
    installUpdate: () => ipcRenderer.invoke('install-update'),
    // Platform info
    platform: process.platform,
    // App version
    getVersion: () => ipcRenderer.invoke('get-version'),
});
//# sourceMappingURL=preload.js.map