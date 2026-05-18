// tabs/cleaning.js — Data Cleaning tab
'use strict';

const CleanTab = (() => {
  let _cols = [];
  let _numericCols = [];
  let _dtypes = {};
  let _nullCounts = {};

  function init() {
    document.getElementById('removeDupBtn')?.addEventListener('click', removeDuplicates);
    document.getElementById('applyCleanBtn')?.addEventListener('click', applyCleaning);
    document.getElementById('exportCleanBtn')?.addEventListener('click', exportCleaned);
    document.getElementById('rollbackCleanBtn')?.addEventListener('click', rollbackCleaning);
    document.getElementById('refreshHistoryBtn')?.addEventListener('click', () => refreshHistory());
    document.getElementById('previewSource')?.addEventListener('change', refreshPreview);
    document.getElementById('outlierThreshold')?.addEventListener('input', e => {
      const v = (parseInt(e.target.value) / 10).toFixed(1);
      document.getElementById('outlierLabel').textContent = `IQR × ${v}`;
    });
    [
      'missingMethod', 'removeOutliers', 'dtypeCol', 'dtypeConvert', 'encodeCol',
      'encodeMethod', 'binarizeCol', 'scaleMethod', 'selectionTarget',
      'selectionMethod', 'extractionTarget', 'extractionMethod',
    ].forEach(id => document.getElementById(id)?.addEventListener('change', updateCleaningAvailability));
  }

  function onDataLoaded(info) {
    setCleaningInfo(info);
    appendLog(`Loaded: ${info.source}`, 'ok');
    appendLog(`Shape: ${info.rows} rows × ${info.cols} cols`, 'info');
    refreshPreview();
    refreshHistory();
  }

  function setCleaningInfo(info) {
    _cols = info.columns || [];
    _dtypes = info.dtypes || {};
    _nullCounts = info.null_counts || {};
    _numericCols = _cols.filter(col => isNumericCol(col));
    updateCleaningAvailability();
  }

  function isNumericCol(col) {
    return /int|float|double|number|decimal|complex/.test(String(_dtypes[col] || '').toLowerCase());
  }

  function isCategoricalCol(col) {
    return !isNumericCol(col);
  }

  function numericFeatureCount(exclude = '') {
    return _numericCols.filter(col => col !== exclude).length;
  }

  function setSelectOptions(selectId, rows, placeholder = 'Select…') {
    const el = document.getElementById(selectId);
    if (!el) return;
    const previous = el.value;
    el.innerHTML = '';
    el.appendChild(new Option(placeholder, ''));

    let firstAllowed = '';
    rows.forEach(row => {
      const option = new Option(row.ok ? row.label : `${row.label} - ${row.reason}`, row.value);
      option.disabled = !row.ok;
      option.title = row.reason || '';
      el.appendChild(option);
      if (row.ok && !firstAllowed) firstAllowed = row.value;
    });

    const previousOption = Array.from(el.options).find(option => option.value === previous && !option.disabled);
    el.value = previousOption ? previous : '';
    el.disabled = !_cols.length || !firstAllowed;
  }

  function updateMethodOptions(selectId, rules) {
    const el = document.getElementById(selectId);
    if (!el) return;
    let firstAllowed = '';
    Array.from(el.options).forEach(option => {
      const rule = rules(option.value);
      option.disabled = !rule.ok;
      option.title = rule.reason || '';
      if (rule.ok && !firstAllowed) firstAllowed = option.value;
    });
    if (el.selectedOptions[0]?.disabled) el.value = firstAllowed;
    el.disabled = !_cols.length || !firstAllowed;
  }

  function populateBinarizeSelect() {
    const rows = [
      { value: '__all_numeric__', label: 'All Numeric Columns', ok: _numericCols.length > 0, reason: 'needs numeric columns' },
      ..._cols.map(col => ({
        value: col,
        label: col,
        ok: isNumericCol(col),
        reason: 'numeric columns only',
      })),
    ];
    setSelectOptions('binarizeCol', rows, 'No binarization');
  }

  function updateCleaningAvailability() {
    const hasData = _cols.length > 0;
    const hasNumeric = _numericCols.length > 0;

    updateMethodOptions('missingMethod', value => {
      if (!hasData) return { ok: false, reason: 'load data first' };
      if (['mean', 'median', 'distribution'].includes(value)) {
        const hasNumericMissing = _numericCols.some(col => Number(_nullCounts[col] || 0) > 0);
        return hasNumericMissing ? { ok: true } : { ok: false, reason: 'needs numeric missing values' };
      }
      return { ok: true };
    });

    const removeOutliers = document.getElementById('removeOutliers');
    const outlierThreshold = document.getElementById('outlierThreshold');
    if (removeOutliers) {
      removeOutliers.disabled = !hasNumeric;
      if (!hasNumeric) removeOutliers.checked = false;
    }
    if (outlierThreshold) outlierThreshold.disabled = !hasNumeric || !removeOutliers?.checked;

    setSelectOptions('dtypeCol', _cols.map(col => ({ value: col, label: col, ok: true })), 'Select…');
    updateMethodOptions('dtypeConvert', value => {
      if (!value) return { ok: true };
      const col = document.getElementById('dtypeCol')?.value;
      if (!col) return { ok: false, reason: 'select a column first' };
      if (value === 'numeric' && isNumericCol(col)) return { ok: false, reason: 'already numeric' };
      if (value === 'categorical' && isCategoricalCol(col)) return { ok: false, reason: 'already categorical' };
      return { ok: true };
    });

    setSelectOptions('encodeCol', _cols.map(col => ({
      value: col,
      label: col,
      ok: isCategoricalCol(col),
      reason: 'categorical columns only',
    })), 'Select…');
    updateMethodOptions('encodeMethod', value => {
      if (!value) return { ok: true };
      return document.getElementById('encodeCol')?.value ? { ok: true } : { ok: false, reason: 'select a categorical column first' };
    });

    populateBinarizeSelect();
    const binarizeThreshold = document.getElementById('binarizeThreshold');
    if (binarizeThreshold) binarizeThreshold.disabled = !document.getElementById('binarizeCol')?.value;

    updateMethodOptions('scaleMethod', value => {
      if (!value) return { ok: true };
      return hasNumeric ? { ok: true } : { ok: false, reason: 'needs numeric columns' };
    });

    setSelectOptions('selectionTarget', _cols.map(col => ({
      value: col,
      label: col,
      ok: numericFeatureCount(col) > 0,
      reason: 'needs at least one numeric feature column',
    })), 'Select…');
    updateMethodOptions('selectionMethod', value => {
      if (!value) return { ok: true };
      return document.getElementById('selectionTarget')?.value ? { ok: true } : { ok: false, reason: 'select a target first' };
    });
    const selectionK = document.getElementById('selectionK');
    if (selectionK) selectionK.disabled = !document.getElementById('selectionMethod')?.value;

    setSelectOptions('extractionTarget', _cols.map(col => ({ value: col, label: col, ok: true })), 'Optional…');
    updateMethodOptions('extractionMethod', value => {
      if (!value) return { ok: true };
      if (!hasNumeric) return { ok: false, reason: 'needs numeric columns' };
      if (value === 'lda' && !document.getElementById('extractionTarget')?.value) return { ok: false, reason: 'select a target first' };
      return { ok: true };
    });
    const extractionComponents = document.getElementById('extractionComponents');
    if (extractionComponents) extractionComponents.disabled = !document.getElementById('extractionMethod')?.value;

    ['removeDupBtn', 'applyCleanBtn', 'exportCleanBtn', 'refreshHistoryBtn'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.disabled = !hasData;
    });
  }

  function appendLog(msg, type = 'info') {
    const log = document.getElementById('cleanLog');
    if (!log) return;
    const placeholder = log.querySelector('.log-placeholder');
    if (placeholder) placeholder.remove();
    const line = document.createElement('div');
    line.className = `log-line-${type}`;
    line.textContent = msg;
    log.appendChild(line);
    log.scrollTop = log.scrollHeight;
  }

  async function removeDuplicates() {
    Utils.showSpinner('Removing duplicates…');
    try {
      const res = await API.removeDuplicates();
      appendLog(`Removed ${res.removed} duplicate rows (${res.rows} remain)`, 'ok');
      if (res.info) setCleaningInfo(res.info);
      if (res.history) renderHistory(res.history);
      refreshPreview();
      ModelTab?.onDataLoaded(res.info);
      Utils.toast(`Removed ${res.removed} duplicates`, 'success');
    } catch (e) {
      appendLog(`Error: ${e.message}`, 'warn');
      Utils.toast(e.message, 'error');
    } finally {
      Utils.hideSpinner();
    }
  }

  async function applyCleaning() {
    Utils.showSpinner('Applying cleaning operations…');
    try {
      const threshold = parseInt(document.getElementById('outlierThreshold')?.value || '15') / 10;
      const params = {
        missing_method: document.getElementById('missingMethod')?.value || 'none',
        remove_outliers: document.getElementById('removeOutliers')?.checked || false,
        outlier_threshold: threshold,
        dtype_column: document.getElementById('dtypeCol')?.value || null,
        dtype_convert: document.getElementById('dtypeConvert')?.value || null,
        scale_method: document.getElementById('scaleMethod')?.value || null,
        binarize_column: document.getElementById('binarizeCol')?.value || null,
        binarize_threshold: parseFloat(document.getElementById('binarizeThreshold')?.value || '0'),
        encode_column: document.getElementById('encodeCol')?.value || null,
        encode_method: document.getElementById('encodeMethod')?.value || null,
        selection_target: document.getElementById('selectionTarget')?.value || null,
        selection_method: document.getElementById('selectionMethod')?.value || null,
        selection_k: parseInt(document.getElementById('selectionK')?.value || '5'),
        extraction_target: document.getElementById('extractionTarget')?.value || null,
        extraction_method: document.getElementById('extractionMethod')?.value || null,
        extraction_components: parseInt(document.getElementById('extractionComponents')?.value || '2'),
      };
      const res = await API.applyCleaning(params);
      res.log.forEach(line => {
        const type = /filled|encoded|converted|binarized|scaled|selected|extracted|removed|dropped/i.test(line) ? 'ok' : 'info';
        appendLog(line, type);
      });
      appendLog(`Result: ${res.rows} rows × ${res.cols} cols`, 'info');
      if (res.info) setCleaningInfo(res.info);
      if (res.history) renderHistory(res.history);
      refreshPreview();
      ModelTab?.onDataLoaded(res.info);
      Utils.toast('Cleaning applied!', 'success');
    } catch (e) {
      appendLog(`Error: ${e.message}`, 'warn');
      Utils.toast(e.message, 'error');
    } finally {
      Utils.hideSpinner();
    }
  }

  async function exportCleaned() {
    const url = API.getExportCleanUrl();
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(res.statusText);
      const blob = await res.blob();
      Utils.downloadBlob(blob, 'cleaned_data.csv');
      Utils.toast('Exported cleaned data!', 'success');
    } catch (e) {
      Utils.toast(`Export failed: ${e.message}`, 'error');
    }
  }

  async function refreshHistory() {
    try {
      const history = await API.getCleaningHistory();
      renderHistory(history);
    } catch (e) {
      console.warn('History refresh error:', e.message);
    }
  }

  function renderHistory(history) {
    const select = document.getElementById('cleanHistorySelect');
    const rollbackBtn = document.getElementById('rollbackCleanBtn');
    if (!select) return;
    const steps = history?.steps || [];
    select.innerHTML = '';
    steps.forEach(step => {
      const label = `${step.index + 1}. ${step.label} (${step.rows}x${step.cols})${step.current ? ' - current' : ''}`;
      select.appendChild(new Option(label, String(step.index)));
    });
    select.value = String(history?.current ?? Math.max(0, steps.length - 1));
    select.disabled = steps.length <= 1;
    if (rollbackBtn) rollbackBtn.disabled = steps.length <= 1;
  }

  async function rollbackCleaning() {
    const select = document.getElementById('cleanHistorySelect');
    if (!select?.value) return;
    Utils.showSpinner('Rolling back cleaning step…');
    try {
      const res = await API.rollbackCleaning(parseInt(select.value, 10));
      if (res.info) setCleaningInfo(res.info);
      if (res.history) renderHistory(res.history);
      appendLog(res.message || 'Rolled back cleaning step', 'warn');
      refreshPreview();
      ModelTab?.onDataLoaded(res.info);
      Utils.toast('Cleaning rolled back', 'success');
    } catch (e) {
      appendLog(`Rollback error: ${e.message}`, 'warn');
      Utils.toast(e.message, 'error');
    } finally {
      Utils.hideSpinner();
    }
  }

  async function refreshPreview() {
    const cleaned = document.getElementById('previewSource')?.value === 'cleaned';
    try {
      const preview = await API.getPreview(20, cleaned);
      renderTable(preview.columns, preview.rows);
    } catch (e) {
      console.warn('Preview error:', e.message);
    }
  }

  function renderTable(columns, rows) {
    const head = document.getElementById('previewHead');
    const body = document.getElementById('previewBody');
    const ph = document.getElementById('tablePlaceholder');
    if (!head || !body) return;

    if (!columns.length) { if (ph) ph.style.display = ''; return; }
    if (ph) ph.style.display = 'none';

    head.innerHTML = '<tr>' + columns.map(c => `<th>${c}</th>`).join('') + '</tr>';
    body.innerHTML = rows.map(row =>
      '<tr>' + row.map(v => `<td title="${v}">${v}</td>`).join('') + '</tr>'
    ).join('');
  }

  return { init, onDataLoaded };
})();
