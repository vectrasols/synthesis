"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
// payload-updater.js — Small content payload updater for renderer/backend files.
const { app, ipcMain } = require('electron');
const fs = require('fs');
const fsp = fs.promises;
const path = require('path');
const crypto = require('crypto');
const http = require('http');
const https = require('https');
const zlib = require('zlib');
const log = require('electron-log');
const OWNER = 'vectrasols';
const REPO = 'synthesis-suite';
const PAYLOAD_SCHEMA_VERSION = 1;
const MAX_REDIRECTS = 5;
function getPlatformKey() {
    const os = process.platform === 'win32'
        ? 'win'
        : process.platform === 'darwin'
            ? 'mac'
            : 'linux';
    return `${os}-${process.arch}`;
}
function getBackendPackageName() {
    return `backend-${getPlatformKey()}`;
}
function getPayloadRoot() {
    return path.join(app.getPath('userData'), 'payloads');
}
function getStatePath() {
    return path.join(getPayloadRoot(), 'active.json');
}
function getPendingPath() {
    return path.join(getPayloadRoot(), 'pending.json');
}
function getBundledBaselinePath() {
    return path.join(__dirname, 'payload-baseline.json');
}
function readJsonFile(filePath) {
    try {
        return JSON.parse(fs.readFileSync(filePath, 'utf8'));
    }
    catch {
        return null;
    }
}
function readBundledBaseline() {
    const baseline = readJsonFile(getBundledBaselinePath());
    if (!baseline || baseline.platform !== getPlatformKey())
        return null;
    return baseline;
}
function readActiveState() {
    const state = readJsonFile(getStatePath());
    if (!state || state.platform !== getPlatformKey())
        return null;
    if (compareVersions(state.version, app.getVersion()) < 0)
        return null;
    return state;
}
function getKnownPackage(pkg) {
    const statePackage = readActiveState()?.packages?.[pkg.name];
    if (statePackage)
        return statePackage;
    return readBundledBaseline()?.packages?.find((known) => known.name === pkg.name) || null;
}
function getActivePackageDir(packageName) {
    const dir = readActiveState()?.packages?.[packageName]?.dir;
    if (!dir || !fs.existsSync(dir))
        return null;
    return dir;
}
function getActiveRendererRoot() {
    const dir = getActivePackageDir('renderer');
    if (!dir)
        return null;
    const indexPath = path.join(dir, 'renderer', 'index.html');
    return fs.existsSync(indexPath) ? dir : null;
}
function getActiveBackendDir() {
    const dir = getActivePackageDir(getBackendPackageName());
    if (!dir)
        return null;
    const binaryName = process.platform === 'win32' ? 'server.exe' : 'server';
    const serverPath = path.join(dir, binaryName);
    return fs.existsSync(serverPath) ? dir : null;
}
async function applyPendingPayloadUpdate() {
    const pending = readJsonFile(getPendingPath());
    if (!pending)
        return false;
    if (pending.platform !== getPlatformKey() || compareVersions(pending.version, app.getVersion()) < 0) {
        await fsp.rm(getPendingPath(), { force: true });
        return false;
    }
    for (const pkg of Object.values(pending.packages || {})) {
        if (!pkg.dir || !fs.existsSync(pkg.dir)) {
            throw new Error(`Staged payload package is missing: ${pkg.name}`);
        }
    }
    await fsp.mkdir(getPayloadRoot(), { recursive: true });
    const state = {
        ...pending,
        appliedAt: new Date().toISOString(),
    };
    delete state.stagedAt;
    await writeJsonAtomic(getStatePath(), state);
    await fsp.rm(getPendingPath(), { force: true });
    log.info(`Applied payload update ${state.version}`);
    return true;
}
function setupPayloadUpdater(mainWindow) {
    function send(channel, payload = undefined) {
        if (!mainWindow || mainWindow.isDestroyed())
            return;
        mainWindow.webContents.send(channel, payload);
    }
    ipcMain.removeHandler('install-payload-update');
    ipcMain.handle('install-payload-update', () => {
        const pending = readJsonFile(getPendingPath());
        if (!pending) {
            return { ok: false, message: 'No payload update is ready to apply.' };
        }
        send('payload-update-installing', { version: pending.version });
        app.relaunch();
        app.exit(0);
        return { ok: true };
    });
    if (process.env.SYNTHESIS_DISABLE_PAYLOAD_UPDATES === '1')
        return;
    setTimeout(() => {
        checkForPayloadUpdates(send).catch((err) => {
            log.warn('Payload update check failed:', err.message || err);
            if (err?.showToUser) {
                send('payload-update-error', { message: err.message || String(err) });
            }
        });
    }, 9000);
}
async function checkForPayloadUpdates(send) {
    const manifestUrl = getManifestUrl();
    const manifest = await fetchJson(manifestUrl);
    validateManifest(manifest);
    const packagesToInstall = manifest.packages.filter((pkg) => {
        const known = getKnownPackage(pkg);
        return !known || known.sha512 !== pkg.sha512;
    });
    if (!packagesToInstall.length) {
        log.info(`Payloads are up to date for ${manifest.version}`);
        return;
    }
    send('payload-update-available', {
        version: manifest.version,
        packageCount: packagesToInstall.length,
        totalSize: packagesToInstall.reduce((sum, pkg) => sum + (pkg.size || 0), 0),
    });
    try {
        const stagedPackages = {
            ...(readActiveState()?.packages || {}),
        };
        for (let i = 0; i < packagesToInstall.length; i++) {
            const pkg = packagesToInstall[i];
            const archiveUrl = resolvePackageUrl(manifestUrl, pkg);
            const archivePath = path.join(getPayloadRoot(), 'downloads', pkg.fileName);
            await fsp.mkdir(path.dirname(archivePath), { recursive: true });
            await downloadFile(archiveUrl, archivePath, (transferred, total) => {
                const percent = total ? Math.round((transferred / total) * 100) : null;
                send('payload-download-progress', {
                    version: manifest.version,
                    packageName: pkg.name,
                    packageIndex: i + 1,
                    packageCount: packagesToInstall.length,
                    percent,
                    transferred,
                    total,
                });
            });
            const actualHash = await sha512File(archivePath);
            if (actualHash !== pkg.sha512) {
                throw new Error(`Payload checksum mismatch for ${pkg.name}`);
            }
            const packageDir = path.join(getPayloadRoot(), 'packages', sanitizePathPart(pkg.name), pkg.sha512.slice(0, 16));
            if (!fs.existsSync(packageDir)) {
                const stagingDir = path.join(getPayloadRoot(), 'staging', `${sanitizePathPart(pkg.name)}-${Date.now()}`);
                await fsp.rm(stagingDir, { recursive: true, force: true });
                await extractTarGz(archivePath, stagingDir);
                await fsp.mkdir(path.dirname(packageDir), { recursive: true });
                await fsp.rm(packageDir, { recursive: true, force: true });
                await fsp.rename(stagingDir, packageDir);
            }
            await fsp.rm(archivePath, { force: true });
            stagedPackages[pkg.name] = {
                ...pkg,
                dir: packageDir,
                installedAt: new Date().toISOString(),
            };
        }
        await writeJsonAtomic(getPendingPath(), {
            version: manifest.version,
            platform: manifest.platform,
            packages: stagedPackages,
            stagedAt: new Date().toISOString(),
        });
        send('payload-update-ready', {
            version: manifest.version,
            packageCount: packagesToInstall.length,
        });
    }
    catch (err) {
        err.showToUser = true;
        throw err;
    }
}
function getManifestUrl() {
    if (process.env.SYNTHESIS_PAYLOAD_MANIFEST_URL) {
        return process.env.SYNTHESIS_PAYLOAD_MANIFEST_URL;
    }
    const baseUrl = process.env.SYNTHESIS_PAYLOAD_BASE_URL
        || `https://github.com/${OWNER}/${REPO}/releases/latest/download`;
    return `${baseUrl.replace(/\/$/, '')}/payload-manifest-${getPlatformKey()}.json`;
}
function validateManifest(manifest) {
    if (!manifest || manifest.schemaVersion !== PAYLOAD_SCHEMA_VERSION) {
        throw new Error('Unsupported payload manifest schema.');
    }
    if (manifest.platform !== getPlatformKey()) {
        throw new Error(`Payload manifest platform mismatch: ${manifest.platform}`);
    }
    if (manifest.minimumAppVersion && compareVersions(app.getVersion(), manifest.minimumAppVersion) < 0) {
        throw new Error(`Payload update requires Synthesis Suite ${manifest.minimumAppVersion} or newer.`);
    }
    if (!Array.isArray(manifest.packages) || !manifest.packages.length) {
        throw new Error('Payload manifest does not contain any packages.');
    }
}
function resolvePackageUrl(manifestUrl, pkg) {
    if (pkg.url && /^https?:\/\//i.test(pkg.url))
        return pkg.url;
    const fileName = pkg.url || pkg.fileName;
    return `${manifestUrl.replace(/\/[^/]*$/, '')}/${encodeURIComponent(fileName)}`;
}
async function fetchJson(url) {
    const buffer = await downloadBuffer(url);
    return JSON.parse(buffer.toString('utf8'));
}
function downloadBuffer(url, redirects = 0) {
    return new Promise((resolve, reject) => {
        const req = request(url, redirects, (res) => {
            const chunks = [];
            res.on('data', (chunk) => chunks.push(chunk));
            res.on('end', () => resolve(Buffer.concat(chunks)));
        }, reject);
        req.end();
    });
}
function downloadFile(url, filePath, onProgress, redirects = 0) {
    return new Promise((resolve, reject) => {
        const req = request(url, redirects, (res) => {
            const total = Number(res.headers['content-length'] || 0);
            let transferred = 0;
            const out = fs.createWriteStream(filePath);
            res.on('data', (chunk) => {
                transferred += chunk.length;
                onProgress?.(transferred, total);
            });
            res.pipe(out);
            out.on('finish', () => out.close(resolve));
            out.on('error', reject);
        }, reject);
        req.end();
    });
}
function request(url, redirects, onResponse, onError) {
    const lib = url.startsWith('http://') ? http : https;
    const req = lib.get(url, {
        headers: {
            'User-Agent': `SynthesisSuite/${app.getVersion()}`,
            'Accept': 'application/octet-stream, application/json',
        },
    }, (res) => {
        if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
            res.resume();
            if (redirects >= MAX_REDIRECTS) {
                onError(new Error('Too many redirects while downloading payload update.'));
                return;
            }
            const nextUrl = new URL(res.headers.location, url).toString();
            request(nextUrl, redirects + 1, onResponse, onError).end();
            return;
        }
        if (res.statusCode < 200 || res.statusCode >= 300) {
            res.resume();
            onError(new Error(`Payload request failed (${res.statusCode}) for ${url}`));
            return;
        }
        onResponse(res);
    });
    req.on('error', onError);
    return req;
}
function sha512File(filePath) {
    return new Promise((resolve, reject) => {
        const hash = crypto.createHash('sha512');
        fs.createReadStream(filePath)
            .on('data', (chunk) => hash.update(chunk))
            .on('error', reject)
            .on('end', () => resolve(hash.digest('base64')));
    });
}
async function extractTarGz(archivePath, destination) {
    await fsp.mkdir(destination, { recursive: true });
    const archive = zlib.gunzipSync(await fsp.readFile(archivePath));
    let offset = 0;
    while (offset + 512 <= archive.length) {
        const header = archive.subarray(offset, offset + 512);
        offset += 512;
        if (header.every((byte) => byte === 0))
            break;
        const name = readTarString(header, 0, 100);
        const prefix = readTarString(header, 345, 155);
        const fullName = prefix ? `${prefix}/${name}` : name;
        const size = parseInt(readTarString(header, 124, 12).trim() || '0', 8);
        const mode = parseInt(readTarString(header, 100, 8).trim() || '644', 8);
        const type = readTarString(header, 156, 1) || '0';
        const targetPath = safeJoin(destination, fullName);
        if (type === '5') {
            await fsp.mkdir(targetPath, { recursive: true });
        }
        else if (type === '0' || type === '') {
            await fsp.mkdir(path.dirname(targetPath), { recursive: true });
            await fsp.writeFile(targetPath, archive.subarray(offset, offset + size));
            if (process.platform !== 'win32')
                await fsp.chmod(targetPath, mode);
        }
        offset += size;
        if (offset % 512 !== 0)
            offset += 512 - (offset % 512);
    }
}
function readTarString(buffer, start, length) {
    return buffer.subarray(start, start + length).toString('utf8').replace(/\0.*$/, '');
}
function safeJoin(root, relativePath) {
    const targetPath = path.resolve(root, relativePath);
    const rootPath = path.resolve(root);
    if (targetPath !== rootPath && !targetPath.startsWith(rootPath + path.sep)) {
        throw new Error(`Unsafe payload path: ${relativePath}`);
    }
    return targetPath;
}
function sanitizePathPart(value) {
    return String(value).replace(/[^a-zA-Z0-9._-]/g, '-');
}
function compareVersions(a, b) {
    const left = String(a || '0.0.0').split(/[.-]/).map((part) => Number(part) || 0);
    const right = String(b || '0.0.0').split(/[.-]/).map((part) => Number(part) || 0);
    const length = Math.max(left.length, right.length);
    for (let i = 0; i < length; i++) {
        if ((left[i] || 0) > (right[i] || 0))
            return 1;
        if ((left[i] || 0) < (right[i] || 0))
            return -1;
    }
    return 0;
}
async function writeJsonAtomic(filePath, data) {
    await fsp.mkdir(path.dirname(filePath), { recursive: true });
    const tempPath = `${filePath}.tmp`;
    await fsp.writeFile(tempPath, JSON.stringify(data, null, 2));
    await fsp.rename(tempPath, filePath);
}
module.exports = {
    applyPendingPayloadUpdate,
    getActiveRendererRoot,
    getActiveBackendDir,
    setupPayloadUpdater,
};
//# sourceMappingURL=payload-updater.js.map