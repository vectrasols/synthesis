// tabs/model-training.js - Model Training tab
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
    const REGRESSION_MODELS = new Set([
        'linear_regression',
        'polynomial_regression',
        'ridge_regression',
        'lasso_regression',
        'decision_tree_regression',
        'random_forest_regression',
        'gradient_boosting_regression',
        'adaboost_regression',
        'bagging_regression',
        'stacking_regression',
        'svr',
        'knn_regression',
    ]);
    const CLASSIFICATION_MODELS = new Set([
        'logistic_regression',
        'naive_bayes',
        'decision_tree_classification',
        'random_forest_classification',
        'gradient_boosting_classification',
        'adaboost_classification',
        'bagging_classification',
        'stacking_classification',
        'svm_classification',
        'knn_classification',
    ]);
    const SEMI_SUPERVISED_MODELS = new Set(['self_training_classification']);
    const ESTIMATOR_MODELS = new Set([
        'random_forest_regression',
        'gradient_boosting_regression',
        'adaboost_regression',
        'bagging_regression',
        'stacking_regression',
        'random_forest_classification',
        'gradient_boosting_classification',
        'adaboost_classification',
        'bagging_classification',
        'stacking_classification',
        'isolation_forest',
    ]);
    const DEPTH_MODELS = new Set([
        'decision_tree_regression',
        'random_forest_regression',
        'gradient_boosting_regression',
        'adaboost_regression',
        'bagging_regression',
        'stacking_regression',
        'decision_tree_classification',
        'random_forest_classification',
        'gradient_boosting_classification',
        'adaboost_classification',
        'bagging_classification',
        'stacking_classification',
    ]);
    const NEIGHBOR_MODELS = new Set([
        'knn_regression',
        'knn_classification',
        'stacking_regression',
        'stacking_classification',
        'dbscan',
    ]);
    const MODEL_LABELS = {};
    let _cols = [];
    let _dtypes = {};
    let _uniqueCounts = {};
    let _rows = 0;
    let _isTraining = false;
    function init() {
        cacheModelLabels();
        document.getElementById('trainModelBtn')?.addEventListener('click', trainModel);
        document.getElementById('modelType')?.addEventListener('change', updateTargetState);
        document.getElementById('targetCol')?.addEventListener('change', updateTargetState);
        document.getElementById('scaleDataCheck')?.addEventListener('change', updateHyperparameterState);
        const ranges = [
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
        updateModelAvailability();
    }
    function onDataLoaded(info) {
        _cols = info.columns || [];
        _dtypes = info.dtypes || {};
        _uniqueCounts = info.unique_counts || {};
        _rows = Number(info.rows || 0);
        updateModelAvailability();
    }
    function cacheModelLabels() {
        const modelEl = document.getElementById('modelType');
        if (!modelEl)
            return;
        Array.from(modelEl.options).forEach(option => {
            MODEL_LABELS[option.value] = option.textContent || option.value;
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
    function numericFeatureCount(exclude = '') {
        return _cols.filter(col => col !== exclude && isNumericCol(col)).length;
    }
    function modelRequiresTarget(modelType) {
        return !UNSUPERVISED_MODELS.has(modelType);
    }
    function isRegressionModel(modelType) {
        return REGRESSION_MODELS.has(modelType);
    }
    function isClassificationModel(modelType) {
        return CLASSIFICATION_MODELS.has(modelType) || SEMI_SUPERVISED_MODELS.has(modelType);
    }
    function isClassificationTarget(col) {
        if (!col || uniqueCount(col) < 2)
            return false;
        if (!isNumericCol(col))
            return true;
        return uniqueCount(col) <= Math.max(10, Math.ceil(_rows * 0.2));
    }
    function validRegressionTargets() {
        return _cols.filter(col => isNumericCol(col) && uniqueCount(col) > 1 && numericFeatureCount(col) > 0);
    }
    function validClassificationTargets() {
        return _cols.filter(col => isClassificationTarget(col) && numericFeatureCount(col) > 0);
    }
    function minRowsForModel(modelType) {
        if (modelType === 'stacking_regression' || modelType === 'stacking_classification')
            return 5;
        if (SEMI_SUPERVISED_MODELS.has(modelType))
            return 6;
        if (modelType === 'dbscan')
            return 3;
        if (modelType === 'isolation_forest' || modelType === 'one_class_svm')
            return 4;
        if (UNSUPERVISED_MODELS.has(modelType))
            return 2;
        return 3;
    }
    function minNumericFeaturesForModel(modelType) {
        if (modelType === 'pca_projection' || modelType === 'ica_projection')
            return 1;
        return 1;
    }
    function unavailable(reason) {
        return { ok: false, reason };
    }
    function available() {
        return { ok: true, reason: '' };
    }
    function modelGeneralRule(modelType) {
        if (!hasData())
            return unavailable('load data first');
        const minRows = minRowsForModel(modelType);
        if (_rows < minRows)
            return unavailable(`needs ${minRows}+ rows`);
        if (REGRESSION_MODELS.has(modelType)) {
            if (!validRegressionTargets().length)
                return unavailable('needs numeric target plus numeric features');
            return available();
        }
        if (CLASSIFICATION_MODELS.has(modelType)) {
            if (!validClassificationTargets().length)
                return unavailable('needs class target plus numeric features');
            return available();
        }
        if (SEMI_SUPERVISED_MODELS.has(modelType)) {
            if (!validClassificationTargets().length)
                return unavailable('needs class target plus numeric features');
            return available();
        }
        const minNumeric = minNumericFeaturesForModel(modelType);
        if (numericFeatureCount() < minNumeric)
            return unavailable(`needs ${minNumeric}+ numeric feature`);
        return available();
    }
    function targetRule(modelType, col) {
        if (!hasData())
            return unavailable('load data first');
        if (!col)
            return modelRequiresTarget(modelType) ? unavailable('select target column') : available();
        if (isRegressionModel(modelType)) {
            if (!isNumericCol(col))
                return unavailable('regression target must be numeric');
            if (uniqueCount(col) < 2)
                return unavailable('target needs at least two values');
            if (numericFeatureCount(col) < 1)
                return unavailable('needs another numeric feature');
            return available();
        }
        if (isClassificationModel(modelType)) {
            if (!isClassificationTarget(col))
                return unavailable('target should be categorical or low-cardinality');
            if (numericFeatureCount(col) < 1)
                return unavailable('needs numeric feature columns');
            return available();
        }
        const minNumeric = minNumericFeaturesForModel(modelType);
        if (numericFeatureCount(col) < minNumeric)
            return unavailable(`would leave fewer than ${minNumeric} numeric feature`);
        return available();
    }
    function selectedModelRule() {
        const modelType = document.getElementById('modelType')?.value || '';
        const target = document.getElementById('targetCol')?.value || '';
        const general = modelGeneralRule(modelType);
        if (!general.ok)
            return general;
        const targetStatus = targetRule(modelType, target);
        if (!targetStatus.ok)
            return targetStatus;
        return available();
    }
    function updateModelAvailability() {
        const modelEl = document.getElementById('modelType');
        if (!modelEl)
            return;
        let firstAllowed = '';
        Array.from(modelEl.options).forEach(option => {
            const label = MODEL_LABELS[option.value] || option.textContent || option.value;
            const rule = modelGeneralRule(option.value);
            option.disabled = !rule.ok;
            option.title = rule.reason || '';
            option.textContent = rule.ok ? label : `${label} - ${rule.reason}`;
            if (rule.ok && !firstAllowed)
                firstAllowed = option.value;
        });
        if (modelEl.selectedOptions[0]?.disabled && firstAllowed) {
            modelEl.value = firstAllowed;
        }
        updateTargetState();
    }
    function updateTargetState() {
        const modelType = document.getElementById('modelType')?.value || '';
        const targetEl = document.getElementById('targetCol');
        const labelEl = document.getElementById('targetColLabel');
        const requiresTarget = modelRequiresTarget(modelType);
        if (labelEl)
            labelEl.textContent = requiresTarget ? 'Target Column' : 'Exclude Column';
        if (targetEl) {
            const previous = targetEl.value;
            targetEl.innerHTML = '';
            targetEl.appendChild(new Option(requiresTarget ? 'Select target...' : 'No exclusion', ''));
            let hasAllowedTarget = false;
            _cols.forEach(col => {
                const rule = targetRule(modelType, col);
                const label = rule.ok ? col : `${col} - ${rule.reason}`;
                const option = new Option(label, col);
                option.disabled = !rule.ok;
                option.title = rule.reason || '';
                targetEl.appendChild(option);
                if (rule.ok)
                    hasAllowedTarget = true;
            });
            const previousOption = Array.from(targetEl.options).find(option => option.value === previous && !option.disabled);
            targetEl.value = previousOption ? previous : '';
            targetEl.required = requiresTarget;
            targetEl.disabled = !hasData() || (requiresTarget && !hasAllowedTarget);
            targetEl.title = requiresTarget
                ? 'Required for supervised and semi-supervised models'
                : 'Optional: choose a column to exclude from unsupervised features';
        }
        updateHyperparameterState();
        updateTrainButton();
    }
    function setControlEnabled(id, enabled) {
        const el = document.getElementById(id);
        if (el)
            el.disabled = !enabled;
    }
    function updateHyperparameterState() {
        const modelType = document.getElementById('modelType')?.value || '';
        const target = document.getElementById('targetCol')?.value || '';
        const hasNumericFeatures = numericFeatureCount(UNSUPERVISED_MODELS.has(modelType) ? target : '') > 0;
        const scaleData = document.getElementById('scaleDataCheck')?.checked ?? true;
        setControlEnabled('testSize', hasData() && modelRequiresTarget(modelType));
        setControlEnabled('scaleDataCheck', hasData() && hasNumericFeatures);
        setControlEnabled('scaleTypeModel', hasData() && hasNumericFeatures && scaleData);
        setControlEnabled('nEstimators', hasData() && ESTIMATOR_MODELS.has(modelType));
        setControlEnabled('maxDepth', hasData() && DEPTH_MODELS.has(modelType));
        setControlEnabled('nNeighbors', hasData() && NEIGHBOR_MODELS.has(modelType));
        setControlEnabled('nClusters', hasData() && modelType === 'kmeans');
    }
    function updateTrainButton() {
        const btn = document.getElementById('trainModelBtn');
        if (!btn || _isTraining)
            return;
        const rule = selectedModelRule();
        btn.disabled = !rule.ok;
        btn.title = rule.reason || '';
        btn.textContent = 'Train Model';
    }
    async function trainModel() {
        const modelType = document.getElementById('modelType')?.value;
        const target = document.getElementById('targetCol')?.value;
        const rule = selectedModelRule();
        if (!rule.ok) {
            return Utils.toast(rule.reason || 'This model is not available for the current data', 'error');
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
        Utils.showSpinner('Training model...');
        Utils.setStatus(`Training ${params.model_type}...`);
        const btn = document.getElementById('trainModelBtn');
        _isTraining = true;
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Training...';
        }
        try {
            const res = await API.trainModel(params);
            renderResults(res);
            Utils.setStatus(`${res.model} trained successfully`);
            Utils.toast('Model trained!', 'success');
        }
        catch (e) {
            Utils.toast(`Training error: ${e.message}`, 'error');
            Utils.setStatus(`Error: ${e.message}`, true);
        }
        finally {
            _isTraining = false;
            Utils.hideSpinner();
            updateModelAvailability();
        }
    }
    function renderResults(res) {
        const el = document.getElementById('modelResults');
        if (!el)
            return;
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
//# sourceMappingURL=model-training.js.map