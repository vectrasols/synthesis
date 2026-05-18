// tabs/model-training.js — Model Training tab
'use strict';

const ModelTab = (() => {
  const UNSUPERVISED_MODELS = new Set([
    'kmeans',
    'dbscan',
    'pca_projection',
    'ica_projection',
    'zscore_anomaly',
    'isolation_forest',
    'one_class_svm',
  ]);

  function init() {
    document.getElementById('trainModelBtn')?.addEventListener('click', trainModel);
    document.getElementById('modelType')?.addEventListener('change', updateTargetState);

    // Live range labels
    const ranges: Array<[string, string, (v: string) => string]> = [
      ['testSize', 'testSizeLabel', v => `${v}%`],
      ['nEstimators', 'nestLabel', v => v],
      ['maxDepth', 'depthLabel', v => v],
      ['nNeighbors', 'kLabel', v => v],
      ['nClusters', 'cLabel', v => v],
    ];
    ranges.forEach(([id, labelId, fmt]) => {
      const el = document.getElementById(id);
      const lbl = document.getElementById(labelId);
      if (el && lbl) {
        el.addEventListener('input', () => { lbl.textContent = fmt(el.value); });
      }
    });

    updateTargetState();
  }

  function onDataLoaded(info) {
    Utils.populateSelect('targetCol', info.columns || [], true, 'Select target…');
    updateTargetState();
  }

  function modelRequiresTarget(modelType) {
    return !UNSUPERVISED_MODELS.has(modelType);
  }

  function updateTargetState() {
    const modelType = document.getElementById('modelType')?.value || '';
    const targetEl = document.getElementById('targetCol');
    const labelEl = document.getElementById('targetColLabel');
    const requiresTarget = modelRequiresTarget(modelType);
    if (labelEl) labelEl.textContent = requiresTarget ? 'Target Column' : 'Exclude Column';
    if (targetEl) {
      targetEl.required = requiresTarget;
      targetEl.title = requiresTarget
        ? 'Required for supervised and semi-supervised models'
        : 'Optional: choose a column to exclude from unsupervised features';
    }
  }

  async function trainModel() {
    const modelType = document.getElementById('modelType')?.value;
    const target = document.getElementById('targetCol')?.value;
    if (modelRequiresTarget(modelType) && !target) {
      return Utils.toast('Select a target column', 'error');
    }

    const params = {
      model_type: modelType,
      target: target || null,
      test_size: parseInt(document.getElementById('testSize')?.value || '20') / 100,
      scale_data: document.getElementById('scaleDataCheck')?.checked ?? true,
      scale_type: document.getElementById('scaleTypeModel')?.value || 'standard',
      n_estimators: parseInt(document.getElementById('nEstimators')?.value || '100'),
      max_depth: parseInt(document.getElementById('maxDepth')?.value || '10'),
      n_neighbors: parseInt(document.getElementById('nNeighbors')?.value || '5'),
      n_clusters: parseInt(document.getElementById('nClusters')?.value || '3'),
    };

    Utils.showSpinner('Training model…');
    Utils.setStatus(`Training ${params.model_type}…`);
    const btn = document.getElementById('trainModelBtn');
    if (btn) { btn.disabled = true; btn.textContent = 'Training…'; }

    try {
      const res = await API.trainModel(params);
      renderResults(res);
      Utils.setStatus(`${res.model} trained successfully`);
      Utils.toast('Model trained!', 'success');
    } catch (e) {
      Utils.toast(`Training error: ${e.message}`, 'error');
      Utils.setStatus(`Error: ${e.message}`, true);
    } finally {
      Utils.hideSpinner();
      if (btn) { btn.disabled = false; btn.textContent = 'Train Model'; }
    }
  }

  function renderResults(res) {
    const el = document.getElementById('modelResults');
    if (!el) return;

    const metricsHtml = Object.entries(res.metrics).map(([k, v]) => `
      <div class="metric-card">
        <div class="metric-label">${k}</div>
        <div class="metric-value">${typeof v === 'number' && v < 100 ? v.toFixed(4) : v}</div>
      </div>`).join('');
    const sampleMeta = res.test_samples
      ? `Train: ${res.train_samples} samples &nbsp;|&nbsp; Test: ${res.test_samples} samples`
      : `Rows analyzed: ${res.train_samples}`;

    el.innerHTML = `
      <div class="model-header">${res.model.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</div>
      <div class="model-meta">${sampleMeta}</div>
      <div class="metrics-grid">${metricsHtml}</div>
      ${res.report ? `<div style="margin-top:16px;font-size:12px;color:var(--text-muted);font-weight:600;margin-bottom:6px;">Classification Report</div><div class="report-block">${res.report}</div>` : ''}
    `;
  }

  return { init, onDataLoaded };
})();
