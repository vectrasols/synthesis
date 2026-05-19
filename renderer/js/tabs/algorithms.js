// tabs/algorithms.js - Algorithms Lab tab
'use strict';
const AlgoTab = (() => {
    const ALGO_LABELS = {};
    const ALGO_RULES = {
        dataset_profile: { rows: 1, numeric: 0 },
        correlation_matrix: { rows: 2, numeric: 2 },
        pca_user: { rows: 2, numeric: 2 },
        kmeans_user: { rows: 2, numeric: 1 },
        dbscan_user: { rows: 3, numeric: 1 },
        zscore_user: { rows: 2, numeric: 1 },
        isolation_user: { rows: 4, numeric: 1 },
    };
    let _cols = [];
    let _dtypes = {};
    let _uniqueCounts = {};
    let _rows = 0;
    let _isRunning = false;
    function init() {
        cacheAlgorithmLabels();
        document.getElementById('runAlgoBtn')?.addEventListener('click', runAlgorithm);
        document.getElementById('clearAlgoBtn')?.addEventListener('click', clearOutput);
        document.getElementById('algoSelect')?.addEventListener('change', updateRunButton);
        document.getElementById('algoShowGrid')?.addEventListener('change', applyGuideLines);
        updateAlgorithmAvailability();
    }
    function onDataLoaded(info) {
        _cols = info.columns || [];
        _dtypes = info.dtypes || {};
        _uniqueCounts = info.unique_counts || {};
        _rows = Number(info.rows || 0);
        updateAlgorithmAvailability();
    }
    function cacheAlgorithmLabels() {
        const select = document.getElementById('algoSelect');
        if (!select)
            return;
        Array.from(select.options).forEach(option => {
            ALGO_LABELS[option.value] = option.textContent || option.value;
        });
    }
    function hasData() {
        return _cols.length > 0 && _rows > 0;
    }
    function isNumericCol(col) {
        return /int|float|double|number|decimal|complex/.test(String(_dtypes[col] || '').toLowerCase());
    }
    function uniqueCount(col) {
        const count = Number(_uniqueCounts[col]);
        return Number.isFinite(count) ? count : 2;
    }
    function varyingNumericCount() {
        return _cols.filter(col => isNumericCol(col) && uniqueCount(col) > 1).length;
    }
    function unavailable(reason) {
        return { ok: false, reason };
    }
    function available() {
        return { ok: true, reason: '' };
    }
    function algorithmRule(name) {
        if (!hasData())
            return unavailable('load data first');
        const rule = ALGO_RULES[name] || { rows: 1, numeric: 0 };
        if (_rows < rule.rows)
            return unavailable(`needs ${rule.rows}+ rows`);
        if (varyingNumericCount() < rule.numeric) {
            return unavailable(`needs ${rule.numeric}+ usable numeric column${rule.numeric === 1 ? '' : 's'}`);
        }
        return available();
    }
    function updateAlgorithmAvailability() {
        const select = document.getElementById('algoSelect');
        if (!select)
            return;
        let firstAllowed = '';
        Array.from(select.options).forEach(option => {
            const label = ALGO_LABELS[option.value] || option.textContent || option.value;
            const rule = algorithmRule(option.value);
            option.disabled = !rule.ok;
            option.title = rule.reason || '';
            option.textContent = rule.ok ? label : `${label} - ${rule.reason}`;
            if (rule.ok && !firstAllowed)
                firstAllowed = option.value;
        });
        if (select.selectedOptions[0]?.disabled && firstAllowed) {
            select.value = firstAllowed;
        }
        updateRunButton();
    }
    function updateRunButton() {
        const btn = document.getElementById('runAlgoBtn');
        if (!btn || _isRunning)
            return;
        const name = document.getElementById('algoSelect')?.value || '';
        const rule = algorithmRule(name);
        btn.disabled = !rule.ok;
        btn.title = rule.reason || '';
        btn.textContent = 'Run Algorithm';
    }
    async function runAlgorithm() {
        const name = document.getElementById('algoSelect')?.value;
        if (!name)
            return;
        const rule = algorithmRule(name);
        if (!rule.ok) {
            return Utils.toast(rule.reason || 'This algorithm is not available for the current data', 'error');
        }
        const btn = document.getElementById('runAlgoBtn');
        _isRunning = true;
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Running...';
        }
        Utils.showSpinner(`Running ${name.replace(/_/g, ' ')}...`);
        Utils.setStatus(`Running: ${name}...`);
        try {
            const res = await API.runAlgorithm(name);
            const out = document.getElementById('algoOutput');
            if (out)
                out.textContent = res.output || '(no output)';
            if (res.chart) {
                Promise.resolve(Charts.render('algoChartDiv', res.chart)).then(applyGuideLines);
            }
            else {
                Charts.clear('algoChartDiv');
            }
            Utils.setStatus(`Executed: ${name}`);
        }
        catch (e) {
            const out = document.getElementById('algoOutput');
            if (out)
                out.textContent = `Error: ${e.message}`;
            Utils.toast(`Algorithm error: ${e.message}`, 'error');
            Utils.setStatus(`Error: ${e.message}`, true);
        }
        finally {
            _isRunning = false;
            Utils.hideSpinner();
            updateAlgorithmAvailability();
        }
    }
    function clearOutput() {
        const out = document.getElementById('algoOutput');
        if (out)
            out.textContent = 'Run an algorithm to see output...';
        Charts.clear('algoChartDiv');
    }
    function applyGuideLines() {
        const div = document.getElementById('algoChartDiv');
        if (!div?.data)
            return;
        const showGrid = document.getElementById('algoShowGrid')?.checked ?? true;
        Plotly.relayout(div, {
            'xaxis.showgrid': showGrid,
            'xaxis.zeroline': showGrid,
            'yaxis.showgrid': showGrid,
            'yaxis.zeroline': showGrid,
            'scene.xaxis.showgrid': showGrid,
            'scene.yaxis.showgrid': showGrid,
            'scene.zaxis.showgrid': showGrid,
        });
    }
    return { init, onDataLoaded };
})();
//# sourceMappingURL=algorithms.js.map