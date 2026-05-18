// charts.js — Plotly chart rendering
'use strict';

const Charts = (() => {
  function render(divId, figureJson) {
    const el = document.getElementById(divId);
    if (!el) return;
    // Hide placeholder
    const ph = el.previousElementSibling;
    if (ph?.classList.contains('chart-placeholder')) ph.style.display = 'none';

    try {
      const fig = typeof figureJson === 'string' ? JSON.parse(figureJson) : figureJson;
      Plotly.react(el, fig.data || [], fig.layout || {}, {
        responsive: true,
        displayModeBar: true,
        displaylogo: false,
        modeBarButtonsToRemove: ['sendDataToCloud'],
        toImageButtonOptions: { format: 'png', scale: 2 },
      });
    } catch (e) {
      console.error('Chart render error:', e);
    }
  }

  function clear(divId) {
    const el = document.getElementById(divId);
    if (el) {
      Plotly.purge(el);
      el.innerHTML = divId === 'algoChartDiv'
        ? '<div class="chart-placeholder"><div class="placeholder-icon">Plot</div><p>Algorithm visualization will appear here</p></div>'
        : '';
    }
    const ph = el?.previousElementSibling;
    if (ph?.classList.contains('chart-placeholder')) ph.style.display = '';
  }

  async function refreshChart() {
    const xCol = document.getElementById('xCol')?.value || null;
    const yCol = document.getElementById('yCol')?.value || null;
    const zCol = document.getElementById('zCol')?.value || null;
    const chartType = document.getElementById('chartType')?.value || 'scatter';
    const title = document.getElementById('chartTitle')?.value || 'Chart';
    const bins = parseInt(document.getElementById('chartBins')?.value) || 20;
    const opacity = (parseInt(document.getElementById('chartOpacity')?.value) || 70) / 100;
    const useHue = document.getElementById('useHue')?.checked || false;
    const showStats = document.getElementById('showStats')?.checked || false;
    const showGrid = document.getElementById('showGrid')?.checked ?? true;

    try {
      const res = await API.getChart({ chart_type: chartType, x_col: xCol || null, y_col: yCol || null, z_col: zCol || null, title, bins, opacity, use_hue: useHue, show_annotations: showStats, show_grid: showGrid });
      render('chartDiv', res);
    } catch (e) {
      Utils.setStatus(`Chart error: ${e.message}`, true);
    }
  }

  return { render, clear, refreshChart };
})();
