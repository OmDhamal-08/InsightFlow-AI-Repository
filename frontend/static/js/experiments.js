/**
 * AI BI Platform — AutoML Experiments page (Phase 10).
 * Flow: dataset → target → GET /experiments/recommend → pick algorithms → POST /experiments/.
 */

let expRecommendation = null;

document.addEventListener('DOMContentLoaded', () => {
    const root = document.getElementById('experiments-page-root');
    if (!root) return;

    document.getElementById('exp-dataset').addEventListener('change', onDatasetChange);
    document.getElementById('exp-target').addEventListener('change', onTargetChange);
    document.getElementById('exp-train-btn').addEventListener('click', trainExperiment);
    document.getElementById('exp-tune').addEventListener('change', syncTuningInput);
    syncTuningInput();

    loadDatasetOptions(root.dataset.datasetId || '');
    loadExperiments();
});

/* ---------- Dataset & target selection ---------- */

async function loadDatasetOptions(preselectId) {
    const select = document.getElementById('exp-dataset');
    const resp = await apiGet('/datasets/');
    if (!resp.ok) {
        select.innerHTML = '<option value="">Could not load datasets</option>';
        return;
    }
    const datasets = await resp.json();
    if (datasets.length === 0) {
        select.innerHTML = '<option value="">No datasets yet — upload one first</option>';
        return;
    }
    select.innerHTML = '<option value="">Select a dataset…</option>' + datasets.map(ds =>
        `<option value="${escapeHtml(ds.id)}">${escapeHtml(ds.name)} (${formatNumber(ds.row_count || 0)} rows)</option>`
    ).join('');

    if (preselectId && datasets.some(ds => ds.id === preselectId)) {
        select.value = preselectId;
        onDatasetChange();
    }
}

async function onDatasetChange() {
    const datasetId = document.getElementById('exp-dataset').value;
    const target = document.getElementById('exp-target');
    resetRecommendation();
    if (!datasetId) {
        target.disabled = true;
        target.innerHTML = '<option value="">Select a dataset first</option>';
        return;
    }
    const resp = await apiGet(`/datasets/${datasetId}`);
    if (!resp.ok) {
        showToast(await apiErrorMessage(resp, 'Could not load dataset'), 'error');
        return;
    }
    const ds = await resp.json();
    const columns = ds.column_names || [];
    target.innerHTML = '<option value="">Select the column to predict…</option>' +
        columns.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');
    target.disabled = columns.length === 0;
}

async function onTargetChange() {
    const datasetId = document.getElementById('exp-dataset').value;
    const targetColumn = document.getElementById('exp-target').value;
    resetRecommendation();
    if (!datasetId || !targetColumn) return;

    const params = new URLSearchParams({ dataset_id: datasetId, target_column: targetColumn });
    const resp = await apiGet(`/experiments/recommend?${params}`);
    if (!resp.ok) {
        showToast(await apiErrorMessage(resp, 'Could not analyse target column'), 'error');
        return;
    }
    expRecommendation = await resp.json();
    renderRecommendation(expRecommendation);
}

function resetRecommendation() {
    expRecommendation = null;
    document.getElementById('exp-task-info').classList.add('hidden');
    const metric = document.getElementById('exp-metric');
    metric.innerHTML = '';
    metric.disabled = true;
    document.getElementById('exp-algorithms').innerHTML = 'Choose a target column to see recommendations.';
    document.getElementById('exp-algo-count').textContent = '';
    document.getElementById('exp-train-btn').disabled = true;
}

function renderRecommendation(rec) {
    // Task info
    const info = document.getElementById('exp-task-info');
    let preview = '';
    if (rec.target_preview) {
        preview = '<div class="flex flex-wrap gap-1.5">' + Object.entries(rec.target_preview).map(([label, count]) =>
            `<span class="px-2 py-0.5 rounded bg-white/[0.05] font-mono text-[10px]">${escapeHtml(label)}: ${formatNumber(count)}</span>`
        ).join('') + '</div>';
    }
    info.innerHTML = `
        <div class="flex items-center gap-2"><span class="text-gray-400">Detected task:</span> ${taskBadge(rec.task_type)}</div>
        <div class="text-gray-400">${formatNumber(rec.n_rows)} rows with a value · ${formatNumber(rec.target_unique_values)} distinct values</div>
        ${preview}`;
    info.classList.remove('hidden');

    // Metric options
    const metric = document.getElementById('exp-metric');
    metric.innerHTML = rec.metrics.map(m =>
        `<option value="${escapeHtml(m.key)}" ${m.key === rec.default_metric ? 'selected' : ''}>${escapeHtml(m.label)}</option>`
    ).join('');
    metric.disabled = false;

    // Algorithms
    document.getElementById('exp-algorithms').innerHTML = rec.algorithms.map(a => `
        <label class="flex items-start gap-2.5 p-2.5 rounded-xl border border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.04] cursor-pointer">
            <input type="checkbox" name="exp-algo" value="${escapeHtml(a.key)}" ${a.recommended ? 'checked' : ''}
                   class="mt-0.5 rounded border-white/[0.08] bg-transparent text-primary-500 focus:ring-0">
            <span class="flex-1 min-w-0">
                <span class="flex items-center gap-2">
                    <span class="font-semibold text-gray-200">${escapeHtml(a.name)}</span>
                    ${a.recommended ? '<span class="text-[9px] font-bold uppercase text-emerald-400">Recommended</span>' : ''}
                </span>
                <span class="block text-[10px] text-gray-500">${escapeHtml(a.description)} <span class="text-gray-600">· ${escapeHtml(a.reason)}</span></span>
            </span>
        </label>`).join('');
    document.querySelectorAll('input[name="exp-algo"]').forEach(cb => cb.addEventListener('change', updateAlgorithmCount));
    updateAlgorithmCount();

    // Default name
    const nameInput = document.getElementById('exp-name');
    if (!nameInput.value) nameInput.placeholder = `Predict ${rec.target_column}`;
}

function selectedAlgorithms() {
    return [...document.querySelectorAll('input[name="exp-algo"]:checked')].map(cb => cb.value);
}

function updateAlgorithmCount() {
    const count = selectedAlgorithms().length;
    document.getElementById('exp-algo-count').textContent = `${count} selected`;
    document.getElementById('exp-train-btn').disabled = count === 0 || !expRecommendation;
}

function syncTuningInput() {
    document.getElementById('exp-tune-iter').disabled = !document.getElementById('exp-tune').checked;
}

/* ---------- Training ---------- */

async function trainExperiment() {
    if (!expRecommendation) return;
    const algorithms = selectedAlgorithms();
    const tune = document.getElementById('exp-tune').checked;
    const body = {
        dataset_id: document.getElementById('exp-dataset').value,
        target_column: document.getElementById('exp-target').value,
        name: document.getElementById('exp-name').value.trim() || null,
        algorithms,
        optimize_metric: document.getElementById('exp-metric').value,
        test_size: parseFloat(document.getElementById('exp-test-size').value),
        cv_folds: parseInt(document.getElementById('exp-cv').value, 10),
        tune_hyperparameters: tune,
        tuning_iterations: Math.min(30, Math.max(2, parseInt(document.getElementById('exp-tune-iter').value, 10) || 10)),
    };

    setTraining(true, `Training ${algorithms.length} model${algorithms.length > 1 ? 's' : ''}${tune ? ' with tuning' : ''}… this can take a minute.`);
    try {
        const resp = await apiPost('/experiments/', body);
        if (!resp.ok) {
            showToast(await apiErrorMessage(resp, 'Training failed'), 'error', 6000);
            setTraining(false);
            return;
        }
        const exp = await resp.json();
        if (exp.status === 'failed') {
            showToast(exp.error_message || 'Training failed', 'error', 6000);
        }
        window.location.href = `/experiments/${exp.id}`;
    } catch (err) {
        console.error(err);
        showToast('Connection error while training', 'error');
        setTraining(false);
    }
}

function setTraining(isTraining, message = '') {
    document.getElementById('exp-train-btn').disabled = isTraining;
    document.getElementById('exp-train-spinner').classList.toggle('hidden', !isTraining);
    document.getElementById('exp-train-text').textContent = isTraining ? 'Training…' : 'Train & compare models';
    const status = document.getElementById('exp-train-status');
    status.textContent = message;
    status.classList.toggle('hidden', !message);
}

/* ---------- History ---------- */

async function loadExperiments() {
    const tbody = document.getElementById('experiments-tbody');
    const empty = document.getElementById('experiments-empty');
    const resp = await apiGet('/experiments/');
    if (!resp.ok) return;
    const experiments = await resp.json();
    empty.classList.toggle('hidden', experiments.length > 0);

    tbody.innerHTML = experiments.map(e => `
        <tr class="hover:bg-white/[0.02]">
            <td class="py-3 px-3 font-semibold text-white"><a href="/experiments/${escapeHtml(e.id)}" class="hover:text-primary-300">${escapeHtml(e.name)}</a></td>
            <td class="py-3 px-3 text-gray-400">${escapeHtml(e.dataset_name || '—')}</td>
            <td class="py-3 px-3 font-mono text-[11px]">${escapeHtml(e.target_column)}</td>
            <td class="py-3 px-3">${taskBadge(e.task_type)}</td>
            <td class="py-3 px-3">${e.best_model_name ? '⭐ ' + escapeHtml(e.best_model_name) : '—'}</td>
            <td class="py-3 px-3 font-mono">${e.best_score != null ? `${formatMetric(e.best_score)} <span class="text-gray-500">${escapeHtml(METRIC_LABELS[e.optimize_metric] || '')}</span>` : '—'}</td>
            <td class="py-3 px-3">${statusBadge(e.status)}</td>
            <td class="py-3 px-3 text-gray-500">${formatDate(e.created_at)}</td>
            <td class="py-3 px-3 text-right whitespace-nowrap">
                <a href="/experiments/${escapeHtml(e.id)}" class="px-2.5 py-1 rounded-lg text-[11px] font-semibold text-primary-400 bg-primary-500/10 hover:bg-primary-500/20">View</a>
                <button data-delete-id="${escapeHtml(e.id)}" class="ml-1 px-2.5 py-1 rounded-lg text-[11px] font-semibold text-red-400 bg-red-500/10 hover:bg-red-500/20">Delete</button>
            </td>
        </tr>`).join('');

    tbody.querySelectorAll('[data-delete-id]').forEach(btn =>
        btn.addEventListener('click', () => deleteExperiment(btn.dataset.deleteId)));
}

async function deleteExperiment(experimentId) {
    if (!confirm('Delete this experiment and all of its trained models?')) return;
    const resp = await apiDelete(`/experiments/${experimentId}`);
    if (resp.ok || resp.status === 204) {
        showToast('Experiment deleted', 'success');
        loadExperiments();
    } else {
        showToast(await apiErrorMessage(resp, 'Could not delete experiment'), 'error');
    }
}
