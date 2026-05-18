// tabs/algorithms.js — Algorithms Lab tab
'use strict';
const AlgoTab = (() => {
    function init() {
        document.getElementById('runAlgoBtn')?.addEventListener('click', runAlgorithm);
        document.getElementById('clearAlgoBtn')?.addEventListener('click', clearOutput);
    }
    async function runAlgorithm() {
        const name = document.getElementById('algoSelect')?.value;
        if (!name)
            return;
        const btn = document.getElementById('runAlgoBtn');
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Running…';
        }
        Utils.showSpinner(`Running ${name.replace(/_/g, ' ')}…`);
        Utils.setStatus(`Running: ${name}…`);
        try {
            const res = await API.runAlgorithm(name);
            // Output
            const out = document.getElementById('algoOutput');
            if (out)
                out.textContent = res.output || '(no output)';
            // Chart
            if (res.chart) {
                Charts.render('algoChartDiv', res.chart);
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
            Utils.hideSpinner();
            if (btn) {
                btn.disabled = false;
                btn.textContent = 'Run Algorithm';
            }
        }
    }
    function clearOutput() {
        const out = document.getElementById('algoOutput');
        if (out)
            out.textContent = 'Run an algorithm to see output…';
        Charts.clear('algoChartDiv');
    }
    return { init };
})();
//# sourceMappingURL=algorithms.js.map