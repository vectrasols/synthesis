// app.js — Main application controller
// Initializes Electron IPC, connects to Python backend, wires tabs & theme.
'use strict';
(async function main() {
    // ── Splash progress animation ──────────────────────────────────────────────
    const bar = document.getElementById('splashBar');
    const status = document.getElementById('splashStatus');
    let progress = 0;
    function advanceSplash(pct, msg) {
        progress = pct;
        if (bar)
            bar.style.width = pct + '%';
        if (status)
            status.textContent = msg;
    }
    advanceSplash(10, 'Initializing…');
    // ── Get backend port from Electron or fallback (dev) ──────────────────────
    let port;
    try {
        if (window.electronAPI) {
            advanceSplash(25, 'Connecting to backend engine…');
            port = await window.electronAPI.getBackendPort();
        }
        else {
            // Dev fallback: try default port
            port = 8374;
        }
        API.setPort(port);
        advanceSplash(50, 'Waiting for backend…');
        // Poll until backend is up (max 30s)
        let tries = 0;
        while (tries < 60) {
            try {
                await API.health();
                break;
            }
            catch {
                await new Promise(r => setTimeout(r, 500));
                tries++;
            }
        }
        advanceSplash(80, 'Loading interface…');
    }
    catch (e) {
        advanceSplash(100, 'Error: ' + e.message);
        console.error(e);
        return;
    }
    // ── App version ────────────────────────────────────────────────────────────
    if (window.electronAPI) {
        const ver = await window.electronAPI.getVersion().catch(() => '1.2.0');
        const el = document.getElementById('appVersion');
        if (el)
            el.textContent = `v${ver}`;
    }
    // ── Initialize tabs ────────────────────────────────────────────────────────
    VizTab.init();
    CleanTab.init();
    ModelTab.init();
    AlgoTab.init();
    // ── Tab switching ──────────────────────────────────────────────────────────
    document.getElementById('tabNav')?.addEventListener('click', e => {
        const btn = e.target.closest('.tab-btn');
        if (!btn)
            return;
        const tabId = btn.dataset.tab;
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(`panel-${tabId}`)?.classList.add('active');
    });
    // ── Theme switching ────────────────────────────────────────────────────────
    const themeSelect = document.getElementById('themeSelect');
    function applyTheme(theme) {
        document.body.dataset.theme = theme;
        document.body.className = `theme-${theme.replace(/_/g, '-')}`;
        API.setTheme(theme);
        // Re-render chart with new theme colors
        const info = document.getElementById('dataInfo')?.textContent;
        if (info)
            Charts.refreshChart();
        localStorage.setItem('synthesis-theme', theme);
    }
    themeSelect?.addEventListener('change', e => applyTheme(e.target.value));
    // Restore saved theme
    const savedTheme = localStorage.getItem('synthesis-theme') || 'dark';
    if (themeSelect)
        themeSelect.value = savedTheme;
    applyTheme(savedTheme);
    // ── Auto-update notifications ──────────────────────────────────────────────
    if (window.electronAPI) {
        let pendingUpdateVersion = '';
        let pendingPayloadVersion = '';
        let updateReadyToInstall = false;
        let updateBannerDismissed = false;
        let updateAction = null;
        const banner = document.getElementById('updateBanner');
        const text = document.getElementById('updateBannerText');
        const installBtn = document.getElementById('updateInstallBtn');
        function setUpdateBanner(message, options = {}) {
            const tone = options.tone || 'downloading';
            const canInstall = Boolean(options.canInstall);
            if (banner) {
                banner.classList.remove('hidden', 'is-downloading', 'is-ready', 'is-error', 'is-installing');
                if (updateBannerDismissed && tone === 'downloading' && !options.forceShow) {
                    banner.classList.add('hidden');
                }
                banner.classList.add(`is-${tone}`);
            }
            if (text)
                text.textContent = message;
            if (installBtn) {
                installBtn.disabled = !canInstall;
                installBtn.textContent = options.installLabel || 'Install & Restart';
            }
        }
        if (installBtn)
            installBtn.disabled = true;
        window.electronAPI.onUpdateAvailable(info => {
            pendingUpdateVersion = info.version;
            updateReadyToInstall = false;
            updateAction = null;
            updateBannerDismissed = false;
            setUpdateBanner(`Update v${info.version} is available. Downloading...`, {
                tone: 'downloading',
                canInstall: false,
                installLabel: 'Downloading',
                forceShow: true,
            });
        });
        window.electronAPI.onDownloadProgress(progress => {
            if (progress.version)
                pendingUpdateVersion = progress.version;
            const percent = Number.isFinite(progress.percent) ? Math.max(0, Math.min(100, progress.percent)) : null;
            const version = pendingUpdateVersion ? ` v${pendingUpdateVersion}` : '';
            const suffix = percent === null ? '' : ` ${percent}%`;
            setUpdateBanner(`Downloading update${version}${suffix}...`, {
                tone: 'downloading',
                canInstall: false,
                installLabel: 'Downloading',
            });
        });
        window.electronAPI.onUpdateDownloaded(info => {
            pendingUpdateVersion = info.version;
            updateReadyToInstall = true;
            updateAction = 'installer';
            updateBannerDismissed = false;
            setUpdateBanner(`Update v${info.version} is ready to install.`, {
                tone: 'ready',
                canInstall: true,
            });
        });
        window.electronAPI.onUpdateInstalling(info => {
            const version = info.version || pendingUpdateVersion;
            const suffix = version ? ` v${version}` : '';
            setUpdateBanner(`Installing update${suffix}...`, {
                tone: 'installing',
                canInstall: false,
                installLabel: 'Installing...',
            });
        });
        window.electronAPI.onUpdateError(error => {
            const details = typeof error === 'string' ? error : error?.message;
            const canRetryInstall = typeof error === 'string' ? updateReadyToInstall : Boolean(error?.canRetryInstall);
            updateReadyToInstall = canRetryInstall;
            updateAction = canRetryInstall ? 'installer' : null;
            updateBannerDismissed = false;
            setUpdateBanner(`Update failed: ${details || 'Unknown error'}`, {
                tone: 'error',
                canInstall: canRetryInstall,
            });
        });
        window.electronAPI.onPayloadUpdateAvailable(info => {
            if (updateAction === 'installer' && updateReadyToInstall)
                return;
            pendingPayloadVersion = info.version;
            updateAction = null;
            updateBannerDismissed = false;
            setUpdateBanner(`Content update v${info.version} is available. Downloading...`, {
                tone: 'downloading',
                canInstall: false,
                installLabel: 'Downloading',
                forceShow: true,
            });
        });
        window.electronAPI.onPayloadDownloadProgress(progress => {
            if (updateAction === 'installer' && updateReadyToInstall)
                return;
            if (progress.version)
                pendingPayloadVersion = progress.version;
            const version = pendingPayloadVersion ? ` v${pendingPayloadVersion}` : '';
            const pkg = progress.packageName ? ` ${progress.packageName}` : '';
            const count = progress.packageIndex && progress.packageCount
                ? ` (${progress.packageIndex}/${progress.packageCount})`
                : '';
            const suffix = Number.isFinite(progress.percent) ? ` ${progress.percent}%` : '';
            setUpdateBanner(`Downloading content update${version}${count}${pkg}${suffix}...`, {
                tone: 'downloading',
                canInstall: false,
                installLabel: 'Downloading',
            });
        });
        window.electronAPI.onPayloadUpdateReady(info => {
            if (updateAction === 'installer' && updateReadyToInstall)
                return;
            pendingPayloadVersion = info.version;
            updateAction = 'payload';
            updateBannerDismissed = false;
            setUpdateBanner(`Content update v${info.version} is ready. Restart to apply.`, {
                tone: 'ready',
                canInstall: true,
                installLabel: 'Restart to Apply',
            });
        });
        window.electronAPI.onPayloadUpdateInstalling(info => {
            const version = info.version || pendingPayloadVersion;
            const suffix = version ? ` v${version}` : '';
            setUpdateBanner(`Applying content update${suffix}...`, {
                tone: 'installing',
                canInstall: false,
                installLabel: 'Restarting...',
            });
        });
        window.electronAPI.onPayloadUpdateError(error => {
            if (updateAction === 'installer' && updateReadyToInstall)
                return;
            const details = typeof error === 'string' ? error : error?.message;
            updateAction = null;
            updateBannerDismissed = false;
            setUpdateBanner(`Content update failed: ${details || 'Unknown error'}`, {
                tone: 'error',
                canInstall: false,
            });
        });
        installBtn?.addEventListener('click', async () => {
            if (updateAction === 'payload') {
                const version = pendingPayloadVersion ? ` v${pendingPayloadVersion}` : '';
                setUpdateBanner(`Applying content update${version}...`, {
                    tone: 'installing',
                    canInstall: false,
                    installLabel: 'Restarting...',
                });
                const result = await window.electronAPI.installPayloadUpdate().catch(err => ({
                    ok: false,
                    message: err?.message || String(err),
                }));
                if (!result?.ok) {
                    setUpdateBanner(`Content update failed: ${result?.message || 'Restart did not start'}`, {
                        tone: 'error',
                        canInstall: true,
                        installLabel: 'Restart to Apply',
                    });
                }
                return;
            }
            if (!updateReadyToInstall) {
                const version = pendingUpdateVersion ? ` v${pendingUpdateVersion}` : '';
                setUpdateBanner(`Update${version} is still downloading...`, {
                    tone: 'downloading',
                    canInstall: false,
                    installLabel: 'Downloading',
                });
                return;
            }
            const version = pendingUpdateVersion ? ` v${pendingUpdateVersion}` : '';
            setUpdateBanner(`Installing update${version}...`, {
                tone: 'installing',
                canInstall: false,
                installLabel: 'Installing...',
            });
            const result = await window.electronAPI.installUpdate().catch(err => ({
                ok: false,
                message: err?.message || String(err),
            }));
            if (!result?.ok) {
                setUpdateBanner(`Update failed: ${result?.message || 'Install did not start'}`, {
                    tone: 'error',
                    canInstall: updateReadyToInstall,
                    installLabel: 'Install & Restart',
                });
            }
        });
        document.getElementById('updateDismissBtn')?.addEventListener('click', () => {
            updateBannerDismissed = true;
            document.getElementById('updateBanner')?.classList.add('hidden');
        });
    }
    // ── Hide splash, show app ──────────────────────────────────────────────────
    advanceSplash(100, 'Ready!');
    await new Promise(r => setTimeout(r, 400));
    const splash = document.getElementById('splash');
    const app = document.getElementById('app');
    if (splash) {
        splash.style.opacity = '0';
        splash.style.transition = 'opacity 0.4s';
        setTimeout(() => splash.remove(), 400);
    }
    if (app)
        app.classList.remove('hidden');
    Utils.setStatus('Ready. Load a data file to begin.');
})();
//# sourceMappingURL=app.js.map