// api.js — HTTP client for the Python FastAPI backend
'use strict';

const API = (() => {
  let _port = null;
  let _theme = 'dark';

  function setPort(port) { _port = port; }
  function setTheme(t) { _theme = t; }
  function base() { return `http://127.0.0.1:${_port}`; }

  async function request(method, path, body = null, isFormData = false) {
    const opts = { method } as RequestInit;
    if (body && !isFormData) {
      opts.headers = { 'Content-Type': 'application/json' };
      opts.body = JSON.stringify(body);
    } else if (isFormData) {
      opts.body = body; // FormData
    }
    const res = await fetch(base() + path, opts);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || res.statusText);
    }
    const ct = res.headers.get('content-type') || '';
    if (ct.includes('application/json')) return res.json();
    return res;
  }

  return {
    setPort,
    setTheme,

    // Health
    health: () => request('GET', '/api/health'),

    // Data loading
    uploadFile: (file) => {
      const fd = new FormData();
      fd.append('file', file);
      return request('POST', '/api/data/upload', fd, true);
    },
    loadUrl: (url, fmt = 'auto') => request('POST', '/api/data/load-url', { url, fmt }),
    loadText: (text, source_name = 'Clipboard Data') => request('POST', '/api/data/load-text', { text, source_name }),
    getInfo: () => request('GET', '/api/data/info'),
    getPreview: (n = 20, cleaned = false) => request('GET', `/api/data/preview?n=${n}&cleaned=${cleaned}`),
    getColumnValues: (col) => request('GET', `/api/data/column-values?col=${encodeURIComponent(col)}`),

    // Filtering
    applyFilter: (col, condition, value) => request('POST', '/api/data/filter', { col, condition, value }),
    clearFilters: () => request('POST', '/api/data/clear-filters'),

    // Chart
    getChart: (params) => request('POST', '/api/chart/plot', { ...params, theme: _theme }),

    // Cleaning
    applyCleaning: (params) => request('POST', '/api/clean/apply', params),
    removeDuplicates: () => request('POST', '/api/clean/remove-duplicates'),
    getCleaningHistory: () => request('GET', '/api/clean/history'),
    rollbackCleaning: (step_index) => request('POST', '/api/clean/rollback', { step_index }),
    getExportCleanUrl: () => base() + '/api/clean/export',

    // Model training
    trainModel: (params) => request('POST', '/api/model/train', params),

    // Algorithms
    runAlgorithm: (name) => request('POST', '/api/algorithms/run', { name }),
  };
})();
