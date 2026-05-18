// tabs/visualization.js — Visualization tab logic
'use strict';

const VizTab = (() => {
  let _dataInfo: DataInfo | null = null;
  let _manualGrid: HTMLTableElement | null = null;
  let _manualSource = 'text';
  const CHART_LABELS = {
    line: 'Line Plot',
    bar: 'Bar Plot',
    scatter: 'Scatter Plot',
    histogram: 'Histogram',
    box: 'Box Plot',
    violin: 'Violin Plot',
    pie: 'Pie Chart',
    heatmap: 'Heatmap',
    kde: 'KDE Plot',
    scatter3d: '3D Scatter',
    surface3d: '3D Surface',
    wireframe3d: '3D Wireframe',
    bar3d: '3D Bar',
  };

  function init() {
    // File loading
    document.getElementById('loadFileBtn')?.addEventListener('click', openFile);
    document.getElementById('pasteBtn')?.addEventListener('click', importFromClipboard);
    document.getElementById('manualBtn')?.addEventListener('click', () => Utils.showModal('manualModal'));
    document.getElementById('urlBtn')?.addEventListener('click', () => Utils.showModal('urlModal'));

    // Drop zone
    const dz = document.getElementById('dropZone');
    if (dz) {
      dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('drag-over'); });
      dz.addEventListener('dragleave', () => dz.classList.remove('drag-over'));
      dz.addEventListener('drop', e => {
        e.preventDefault(); dz.classList.remove('drag-over');
        const file = e.dataTransfer.files[0];
        if (file) loadFile(file);
      });
      dz.addEventListener('click', openFile);
    }

    document.getElementById('chartType')?.addEventListener('change', () => {
      updateVisualizeAvailability();
      Charts.refreshChart();
    });

    // Chart controls — all update chart on change
    ['xCol','yCol','zCol','chartTitle','useHue','showStats','showGrid'].forEach(id => {
      document.getElementById(id)?.addEventListener('change', Charts.refreshChart);
    });
    ['chartBins','chartOpacity'].forEach(id => {
      document.getElementById(id)?.addEventListener('input', Charts.refreshChart);
    });
    document.getElementById('chartTitle')?.addEventListener('input', Charts.refreshChart);

    // Filtering
    document.getElementById('filterCol')?.addEventListener('change', onFilterColChange);
    document.getElementById('filterPick')?.addEventListener('change', e => {
      if (e.target.value) document.getElementById('filterValue').value = e.target.value;
    });
    document.getElementById('applyFilterBtn')?.addEventListener('click', applyFilter);
    document.getElementById('clearFilterBtn')?.addEventListener('click', clearFilters);

    // Export
    document.getElementById('exportChartBtn')?.addEventListener('click', exportChart);

    // URL modal
    document.getElementById('urlLoadBtn')?.addEventListener('click', loadFromUrl);
    document.getElementById('urlCancelBtn')?.addEventListener('click', () => Utils.hideModal('urlModal'));

    // Paste modal
    document.getElementById('pasteLoadBtn')?.addEventListener('click', loadFromPaste);
    document.getElementById('pasteCancelBtn')?.addEventListener('click', () => Utils.hideModal('pasteModal'));

    // Manual modal
    document.getElementById('createManualTableBtn')?.addEventListener('click', createManualTable);
    document.getElementById('parseManualBtn')?.addEventListener('click', parseManualText);
    document.getElementById('manualLoadBtn')?.addEventListener('click', loadManualData);
    document.getElementById('manualCancelBtn')?.addEventListener('click', () => Utils.hideModal('manualModal'));
    document.getElementById('manualText')?.addEventListener('input', () => { _manualSource = 'text'; });
    updateVisualizeAvailability();
  }

  function isNumericDtype(dtype) {
    return /int|float|double|number|decimal|complex/.test(String(dtype || '').toLowerCase());
  }

  function isDateDtype(dtype) {
    return /date|time/.test(String(dtype || '').toLowerCase());
  }

  function columnType(col) {
    const dtype = _dataInfo?.dtypes?.[col] || '';
    if (isNumericDtype(dtype)) return 'number';
    if (isDateDtype(dtype)) return 'date';
    return 'category';
  }

  function getColumns() {
    return _dataInfo?.columns || [];
  }

  function getNumericColumns() {
    return getColumns().filter(col => columnType(col) === 'number');
  }

  function getCategoricalColumns() {
    return getColumns().filter(col => columnType(col) === 'category');
  }

  function chartAvailability(chart) {
    const cols = getColumns();
    const numericCount = getNumericColumns().length;
    if (!_dataInfo?.loaded && !cols.length) return { ok: false, reason: 'load data first' };

    if (['line', 'bar', 'bar3d'].includes(chart)) {
      return numericCount >= 1 ? { ok: true } : { ok: false, reason: 'needs a numeric value column' };
    }
    if (chart === 'scatter' || chart === 'heatmap') {
      return numericCount >= 2 ? { ok: true } : { ok: false, reason: 'needs 2 numeric columns' };
    }
    if (['histogram', 'box', 'violin', 'kde'].includes(chart)) {
      return numericCount >= 1 ? { ok: true } : { ok: false, reason: 'needs a numeric column' };
    }
    if (chart === 'pie') {
      return cols.length >= 1 ? { ok: true } : { ok: false, reason: 'needs a column' };
    }
    if (['scatter3d', 'surface3d', 'wireframe3d'].includes(chart)) {
      return numericCount >= 3 ? { ok: true } : { ok: false, reason: 'needs 3 numeric columns' };
    }
    return { ok: true };
  }

  function axisRule(axis, chart, col) {
    const type = columnType(col);
    const numeric = type === 'number';

    if (axis === 'x') {
      if (['box', 'violin', 'heatmap'].includes(chart)) return { ok: false, reason: 'not used' };
      if (['histogram', 'kde', 'scatter', 'scatter3d', 'surface3d', 'wireframe3d'].includes(chart)) {
        return numeric ? { ok: true } : { ok: false, reason: 'needs numeric' };
      }
      return { ok: true };
    }

    if (axis === 'y') {
      if (['histogram', 'kde', 'pie', 'heatmap'].includes(chart)) return { ok: false, reason: 'not used' };
      return numeric ? { ok: true } : { ok: false, reason: 'needs numeric' };
    }

    if (axis === 'z') {
      if (!['scatter3d', 'surface3d', 'wireframe3d'].includes(chart)) return { ok: false, reason: '3D only' };
      return numeric ? { ok: true } : { ok: false, reason: 'needs numeric' };
    }

    return { ok: true };
  }

  function setSelectOptions(selectId, columns, options: any = {}) {
    const el = document.getElementById(selectId);
    if (!el) return;

    const previous = el.value;
    const placeholder = options.placeholder || 'Select…';
    el.innerHTML = '';
    el.appendChild(new Option(placeholder, ''));

    let firstAllowed = '';
    columns.forEach(col => {
      const rule = options.allow ? options.allow(col) : { ok: true };
      const option = new Option(rule.ok ? col : `${col} - ${rule.reason}`, col);
      option.disabled = !rule.ok;
      option.title = rule.reason || '';
      el.appendChild(option);
      if (rule.ok && !firstAllowed) firstAllowed = col;
    });

    const previousOption = Array.from(el.options).find(option => option.value === previous && !option.disabled);
    el.value = previousOption ? previous : (options.autoSelect ? firstAllowed : '');
    el.disabled = !columns.length || (options.requireAllowed && !firstAllowed);
  }

  function updateChartOptions() {
    const chartType = document.getElementById('chartType');
    if (!chartType) return;

    let firstAllowed = '';
    Array.from(chartType.options).forEach(option => {
      if (!option.value) return;
      const rule = chartAvailability(option.value);
      option.disabled = !rule.ok;
      option.textContent = rule.ok ? CHART_LABELS[option.value] || option.textContent : `${CHART_LABELS[option.value] || option.textContent} - ${rule.reason}`;
      option.title = rule.reason || '';
      if (rule.ok && !firstAllowed) firstAllowed = option.value;
    });

    if (!firstAllowed) {
      chartType.disabled = true;
      chartType.value = '';
      return;
    }

    chartType.disabled = false;
    if (chartType.selectedOptions[0]?.disabled) chartType.value = firstAllowed;
  }

  function updatePresentationControls(chart) {
    const bins = document.getElementById('chartBins');
    const opacity = document.getElementById('chartOpacity');
    const useHue = document.getElementById('useHue');
    const showStats = document.getElementById('showStats');

    if (bins) bins.disabled = chart !== 'histogram';
    if (opacity) opacity.disabled = !['bar', 'scatter', 'histogram', 'scatter3d', 'surface3d', 'wireframe3d', 'bar3d'].includes(chart);

    if (useHue) {
      const enabled = getCategoricalColumns().length > 0 && ['line', 'bar', 'scatter', 'box', 'violin'].includes(chart);
      useHue.disabled = !enabled;
      if (!enabled) useHue.checked = false;
    }

    if (showStats) {
      const enabled = ['line', 'scatter', 'histogram', 'kde'].includes(chart) && getNumericColumns().length > 0;
      showStats.disabled = !enabled;
      if (!enabled) showStats.checked = false;
    }
  }

  function updateFilterControls() {
    const filterCol = document.getElementById('filterCol');
    const filterCond = document.getElementById('filterCond');
    const filterValue = document.getElementById('filterValue');
    const filterPick = document.getElementById('filterPick');
    const applyBtn = document.getElementById('applyFilterBtn');
    const clearBtn = document.getElementById('clearFilterBtn');
    const cols = getColumns();

    if (filterCol && !cols.includes(filterCol.value)) filterCol.value = '';
    const selected = filterCol?.value || '';
    const numeric = selected ? columnType(selected) === 'number' : false;
    const numericOnly = new Set(['gt', 'lt', 'gte', 'lte', 'in_range']);

    if (filterCond) {
      Array.from(filterCond.options).forEach(option => {
        const disabled = !selected || (numericOnly.has(option.value) && !numeric);
        option.disabled = disabled;
        option.title = disabled && numericOnly.has(option.value) ? 'numeric columns only' : '';
      });
      if (filterCond.selectedOptions[0]?.disabled) filterCond.value = selected ? 'equals' : '';
      filterCond.disabled = !selected;
    }

    if (filterValue) filterValue.disabled = !selected;
    if (filterPick) filterPick.disabled = !selected;
    if (applyBtn) applyBtn.disabled = !selected;
    if (clearBtn) clearBtn.disabled = !cols.length;
  }

  function updateVisualizeAvailability() {
    updateChartOptions();

    const chart = document.getElementById('chartType')?.value || '';
    const cols = getColumns();
    setSelectOptions('xCol', cols, {
      placeholder: chart && ['box', 'violin', 'heatmap'].includes(chart) ? 'Not used' : 'Select X…',
      allow: col => axisRule('x', chart, col),
      requireAllowed: true,
    });
    setSelectOptions('yCol', cols, {
      placeholder: chart && ['histogram', 'kde', 'pie', 'heatmap'].includes(chart) ? 'Not used' : 'Select Y…',
      allow: col => axisRule('y', chart, col),
      requireAllowed: true,
    });
    setSelectOptions('zCol', cols, {
      placeholder: ['scatter3d', 'surface3d', 'wireframe3d'].includes(chart) ? 'Select Z…' : '3D only',
      allow: col => axisRule('z', chart, col),
      requireAllowed: ['scatter3d', 'surface3d', 'wireframe3d'].includes(chart),
    });
    setSelectOptions('filterCol', cols, {
      placeholder: 'Select column…',
      allow: () => ({ ok: true }),
    });

    updatePresentationControls(chart);
    updateFilterControls();
    const exportBtn = document.getElementById('exportChartBtn');
    if (exportBtn) exportBtn.disabled = !cols.length;
  }

  async function importFromClipboard() {
    try {
      const text = window.electronAPI?.readClipboardText ? await window.electronAPI.readClipboardText() : '';
      if (!text || !text.trim()) {
        Utils.showModal('pasteModal');
        return;
      }
      Utils.showSpinner('Importing clipboard data…');
      const info = await API.loadText(text, 'Clipboard Data');
      onDataLoaded(info);
    } catch (e) {
      Utils.showModal('pasteModal');
      Utils.toast(`Clipboard import unavailable: ${e.message}`, 'error');
    } finally {
      Utils.hideSpinner();
    }
  }

  async function openFile() {
    if (window.electronAPI) {
      const fp = await window.electronAPI.openFile();
      if (!fp) return;
      const buf = await window.electronAPI.readFile(fp);
      const fname = fp.split(/[\\/]/).pop();
      const file = new File([buf], fname);
      loadFile(file);
    } else {
      const inp = document.createElement('input');
      inp.type = 'file';
      inp.accept = '.csv,.xlsx,.xls,.json,.tsv,.parquet';
      inp.onchange = () => { if (inp.files[0]) loadFile(inp.files[0]); };
      inp.click();
    }
  }

  async function loadFile(file) {
    Utils.showSpinner(`Loading ${file.name}…`);
    Utils.setStatus(`Loading ${file.name}…`);
    try {
      const info = await API.uploadFile(file);
      onDataLoaded(info);
    } catch (e) {
      Utils.toast(`Failed to load file: ${e.message}`, 'error');
      Utils.setStatus(`Error: ${e.message}`, true);
    } finally {
      Utils.hideSpinner();
    }
  }

  async function loadFromUrl() {
    const url = document.getElementById('urlInput').value.trim();
    const fmt = document.getElementById('urlFormat').value;
    if (!url) return Utils.toast('Enter a URL', 'error');
    Utils.hideModal('urlModal');
    Utils.showSpinner('Fetching from URL…');
    try {
      const info = await API.loadUrl(url, fmt);
      onDataLoaded(info);
    } catch (e) {
      Utils.toast(`URL load failed: ${e.message}`, 'error');
    } finally {
      Utils.hideSpinner();
    }
  }

  async function loadFromPaste() {
    const text = document.getElementById('pasteText').value.trim();
    if (!text) return Utils.toast('No data pasted', 'error');
    Utils.hideModal('pasteModal');
    Utils.showSpinner('Parsing data…');
    try {
      const info = await API.loadText(text, 'Clipboard Data');
      onDataLoaded(info);
    } catch (e) {
      Utils.toast(`Parse failed: ${e.message}`, 'error');
    } finally {
      Utils.hideSpinner();
    }
  }

  function parseManualText() {
    const text = document.getElementById('manualText').value.trim();
    if (!text) return Utils.toast('Paste text before parsing', 'error');
    const sep = text.includes('\t') ? '\t' : ',';
    const result = Papa.parse(text, { header: true, delimiter: sep, skipEmptyLines: true });
    if (!result.data.length) return Utils.toast('No rows found in the pasted text', 'error');
    const headers = Object.keys(result.data[0]);
    const rows = result.data.map(row => headers.map(header => row[header] ?? ''));
    renderManualGrid(headers, rows);
    _manualSource = 'grid';
  }

  function createManualTable() {
    const rows = Math.max(1, parseInt(document.getElementById('manualRows')?.value || '5', 10));
    const cols = Math.max(1, parseInt(document.getElementById('manualCols')?.value || '3', 10));
    const headers = Array.from({ length: cols }, (_, i) => `Column_${i + 1}`);
    const data = Array.from({ length: rows }, () => Array.from({ length: cols }, () => ''));
    renderManualGrid(headers, data);
    _manualSource = 'grid';
  }

  function renderManualGrid(headers, rows) {
    const wrap = document.getElementById('manualGridWrap');
    if (!wrap) return;

    wrap.innerHTML = '';
    const table = document.createElement('table');
    table.className = 'data-table';

    const thead = document.createElement('thead');
    const headRow = document.createElement('tr');
    headers.forEach((header, index) => {
      const th = document.createElement('th');
      const input = document.createElement('input');
      input.type = 'text';
      input.className = 'input';
      input.value = header;
      input.dataset.col = String(index);
      th.appendChild(input);
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    rows.forEach((row, rowIndex) => {
      const tr = document.createElement('tr');
      headers.forEach((_, colIndex) => {
        const td = document.createElement('td');
        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'input';
        input.value = row?.[colIndex] ?? '';
        input.dataset.row = String(rowIndex);
        input.dataset.col = String(colIndex);
        td.appendChild(input);
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    wrap.appendChild(table);
    _manualGrid = table;

    table.querySelectorAll('input').forEach(input => {
      input.addEventListener('input', () => { _manualSource = 'grid'; });
    });
  }

  function csvCell(value) {
    const text = String(value ?? '');
    return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  }

  function getManualGridCandidate() {
    if (!_manualGrid) return { valid: false, hasContent: false, text: '', sourceName: 'Manual Entry (Table)' };

    const headerInputs = _manualGrid.querySelectorAll('thead input') as NodeListOf<HTMLInputElement>;
    const bodyRows = Array.from(_manualGrid.querySelectorAll('tbody tr')) as HTMLTableRowElement[];
    const headers = Array.from(headerInputs).map(input => input.value.trim() || 'Column');
    const rows = bodyRows
      .map(tr => Array.from(tr.querySelectorAll('input')).map(input => input.value.trim()))
      .filter(row => row.some(value => value.length > 0));

    if (!rows.length) return { valid: false, hasContent: false, text: '', sourceName: 'Manual Entry (Table)' };

    return {
      valid: true,
      hasContent: true,
      text: [headers.map(csvCell).join(','), ...rows.map(row => row.map(csvCell).join(','))].join('\n'),
      sourceName: 'Manual Entry (Table)',
    };
  }

  function getManualTextCandidate() {
    const text = document.getElementById('manualText').value.trim();
    const lines = text.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
    const valid = lines.length >= 2 && lines.slice(1).some(line => /[^,\t\s]/.test(line));
    return { valid, hasContent: text.length > 0, text, sourceName: 'Manual Entry (Text)' };
  }

  function chooseManualCandidate() {
    const grid = getManualGridCandidate();
    const text = getManualTextCandidate();
    const primary = _manualSource === 'grid' ? grid : text;
    const fallback = _manualSource === 'grid' ? text : grid;
    if (primary.valid) return primary;
    if (_manualSource === 'text' && primary.hasContent) return primary;
    if (fallback.valid) return fallback;
    return { valid: false, hasContent: false, text: '', sourceName: 'Manual Entry' };
  }

  async function loadManualData() {
    const candidate = chooseManualCandidate();
    if (!candidate.valid) {
      return Utils.toast('Add at least one filled table row, or paste text with headers and data rows', 'error');
    }
    Utils.hideModal('manualModal');
    Utils.showSpinner('Loading data…');
    try {
      const info = await API.loadText(candidate.text, candidate.sourceName);
      onDataLoaded(info);
    } catch (e) {
      Utils.toast(`Failed: ${e.message}`, 'error');
    } finally {
      Utils.hideSpinner();
    }
  }

  function onDataLoaded(info) {
    _dataInfo = info;
    const cols = info.columns || [];

    // Update file display
    document.getElementById('dropZone')?.classList.add('hidden');
    const fi = document.getElementById('fileInfo');
    if (fi) fi.classList.remove('hidden');
    const fn = document.getElementById('fileName');
    if (fn) fn.textContent = info.source;
    const fm = document.getElementById('fileMeta');
    if (fm) fm.textContent = `${info.rows.toLocaleString()} rows × ${info.cols} cols`;

    updateVisualizeAvailability();
    Utils.setDataInfo(info);
    Utils.setStatus(`Loaded: ${info.source}`);

    // Notify other tabs
    CleanTab?.onDataLoaded(info);
    ModelTab?.onDataLoaded(info);
    AlgoTab?.onDataLoaded(info);

    Charts.refreshChart();
  }

  async function onFilterColChange() {
    const col = document.getElementById('filterCol').value;
    updateFilterControls();
    if (!col) return;
    const res = await API.getColumnValues(col).catch(() => ({ values: [] }));
    const pick = document.getElementById('filterPick');
    if (pick) {
      pick.innerHTML = '<option value="">Pick value…</option>';
      res.values.forEach(v => pick.appendChild(new Option(v, v)));
    }
  }

  async function applyFilter() {
    const col = document.getElementById('filterCol').value;
    const cond = document.getElementById('filterCond').value;
    const value = document.getElementById('filterValue').value.trim() ||
                  document.getElementById('filterPick').value;
    if (!col || !value) return Utils.toast('Select column and value', 'error');
    try {
      const res = await API.applyFilter(col, cond, value);
      Utils.setStatus(`Filter applied: ${res.filter_desc} (${res.filtered_rows} rows)`);
      renderFilterChips(res.active_filters);
      Charts.refreshChart();
    } catch (e) {
      Utils.toast(`Filter error: ${e.message}`, 'error');
    }
  }

  async function clearFilters() {
    await API.clearFilters();
    document.getElementById('filterChips').innerHTML = '';
    document.getElementById('filterValue').value = '';
    Utils.setStatus('Filters cleared');
    Charts.refreshChart();
  }

  function renderFilterChips(filters) {
    const el = document.getElementById('filterChips');
    if (!el) return;
    el.innerHTML = Object.entries(filters).map(([col, desc]) =>
      `<div class="filter-chip"><span>${desc}</span><button type="button" data-clear-filter="${col}" title="Remove">×</button></div>`
    ).join('');

    el.querySelectorAll('button[data-clear-filter]').forEach(button => {
      button.addEventListener('click', clearFilters);
    });
  }

  async function exportChart() {
    const div = document.getElementById('chartDiv');
    if (!div || !div.data) return Utils.toast('No chart to export', 'error');
    try {
      const savePath = window.electronAPI?.saveFile
        ? await window.electronAPI.saveFile('chart.png', [
            { name: 'PNG Files', extensions: ['png'] },
            { name: 'SVG Files', extensions: ['svg'] },
          ])
        : null;

      if (!savePath) {
        const url = await Plotly.toImage(div, { format: 'png', scale: 2, width: 1400, height: 900 });
        const a = document.createElement('a');
        a.href = url; a.download = 'chart.png';
        a.click();
        Utils.toast('Chart exported!', 'success');
        return;
      }

      const ext = (savePath.split('.').pop() || 'png').toLowerCase();
      const format = ext === 'svg' ? 'svg' : 'png';
      const dataUrl = await Plotly.toImage(div, { format, scale: 2, width: 1400, height: 900 });
      const blob = await (await fetch(dataUrl)).blob();
      const bytes = await blob.arrayBuffer();
      await window.electronAPI.writeFile(savePath, bytes);
      Utils.toast('Chart exported!', 'success');
    } catch (e) {
      Utils.toast(`Export failed: ${e.message}`, 'error');
    }
  }

  return { init, onDataLoaded };
})();
