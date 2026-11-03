/**
 * AI BI Platform — Experiment leaderboard & model evaluation page.
 */

let currentExperiment = null;
let currentModel = null;

document.addEventListener('DOMContentLoaded', () => {
    const root = document.getElementById('experiment-page-root');
    if (!root) return;
    document.getElementById('eval-download').addEventListener('click', downloadCurrentModel);
    document.getElementById('predict-btn').addEventListener('click', runPrediction);
    loadExperiment(root.dataset.experimentId);
});

/* ---------- Experiment & leaderboard ---------- */

async function loadExperiment(experimentId) {
    const resp = await apiGet(`/experiments/${experimentId}`);
    if (!resp.ok) {
        document.getElementById('exp-title').textContent = 'Experiment not found';
        showError(await apiErrorMessage(resp, 'Could not load experiment'));
        return;
    }
    const exp = await resp.json();
    currentExperiment = exp;

    document.getElementById('exp-title').textContent = exp.name;
    document.getElementById('exp-subtitle').innerHTML =
        `${escapeHtml(exp.dataset_name || 'Dataset')} · target <span class="font-mono text-gray-300">${escapeHtml(exp.target_column)}</span> · ${taskBadge(exp.task_type)}`;

    if (exp.status === 'failed') showError(exp.error_message || 'Training failed');
    showQualityHint(exp);

    renderCards(exp);
    renderDropped(exp.summary);
    renderLeaderboard(exp);

    const best = exp.models.find(m => m.is_best) || exp.models.find(m => m.status === 'completed');
    if (best) selectModel(best.id);
    prefillPredictionForm(exp);
}

/** Plain-English hint when even the best model is not useful. */
function showQualityHint(exp) {
    const best = exp.models.find(m => m.is_best);
    if (!best) return;
    let hint = null;
    if (exp.task_type === 'regression' && best.metrics.r2 !== null && best.metrics.r2 < 0) {
        hint = 'Even the best model scores below R² = 0, i.e. worse than always predicting the average. '
             + 'Check the target for extreme outliers (Data Quality page) or clean the data first.';
    } else if (isClassification(exp.task_type) && best.metrics.f1_weighted !== null && best.metrics.f1_weighted < 0.5) {
        hint = 'The best model has a low F1 score. The features may not carry enough signal for this target — try feature engineering or a different target.';
    }
    if (!hint) return;
    const el = document.getElementById('exp-dropped');
    el.insertAdjacentHTML('beforebegin', `<div class="p-3 rounded-xl bg-sky-500/[0.07] border border-sky-500/20 text-xs text-sky-200">${escapeHtml(hint)}</div>`);
}

function showError(message) {
    const el = document.getElementById('exp-error');
    el.textContent = message;
    el.classList.remove('hidden');
}

function renderCards(exp) {
    const best = exp.models.find(m => m.is_best);
    const s = exp.summary || {};
    const metricLabel = exp.metric_label || METRIC_LABELS[exp.optimize_metric] || 'Score';
    const cards = [
        ['Best model', best ? `⭐ ${escapeHtml(best.display_name)}` : '—'],
        [`Test ${escapeHtml(metricLabel)}`, best ? formatMetric(best.test_score) : '—'],
        ['Models trained', `${exp.model_count} / ${exp.models.length}`],
        ['Rows (train / test)', s.train_rows != null ? `${formatNumber(s.train_rows)} / ${formatNumber(s.test_rows)}` : '—'],
    ];
    document.getElementById('exp-cards').innerHTML = cards.map(([label, value]) => `
        <div class="glass rounded-2xl border border-white/[0.06] p-4">
            <p class="text-[10px] font-semibold text-gray-500 uppercase tracking-wider">${label}</p>
            <p class="mt-1.5 text-lg font-bold text-white truncate">${value}</p>
        </div>`).join('');

    const note = [];
    if (s.cv_folds) note.push(`${s.cv_folds}-fold CV`);
    if (exp.config && exp.config.tune_hyperparameters) note.push(`tuned (${exp.config.tuning_iterations} trials)`);
    if (exp.training_time_seconds != null) note.push(`total ${formatSeconds(exp.training_time_seconds)}`);
    if (s.rows_sampled_from) note.push(`sampled from ${formatNumber(s.rows_sampled_from)} rows`);
    document.getElementById('leaderboard-note').textContent =
        `Ranked by cross-validation ${metricLabel}${exp.lower_is_better ? ' (lower is better)' : ''} · ${note.join(' · ')}`;
}

function renderDropped(summary) {
    const el = document.getElementById('exp-dropped');
    const dropped = (summary && summary.dropped_columns) || [];
    if (!dropped.length) return el.classList.add('hidden');
    el.innerHTML = '<span class="font-semibold">Columns not used for training:</span> ' + dropped.map(d =>
        `<span class="font-mono">${escapeHtml(d.column)}</span> <span class="text-amber-300/70">(${escapeHtml(d.reason)})</span>`
    ).join(' · ');
    el.classList.remove('hidden');
}

function leaderboardColumns(task) {
    return isClassification(task)
        ? ['accuracy', 'f1_weighted', 'roc_auc', 'precision_weighted', 'recall_weighted']
        : ['r2', 'rmse', 'mae', 'mape'];
}

function renderLeaderboard(exp) {
    const cols = leaderboardColumns(exp.task_type);
    document.getElementById('leaderboard-thead').innerHTML = `
        <tr class="border-b border-white/[0.06] text-[10px] font-semibold uppercase tracking-wider text-gray-500">
            <th class="py-3 px-3">#</th>
            <th class="py-3 px-3">Model</th>
            <th class="py-3 px-3">CV score</th>
            ${cols.map(c => `<th class="py-3 px-3">${escapeHtml(METRIC_LABELS[c] || c)}</th>`).join('')}
            <th class="py-3 px-3">Train time</th>
            <th class="py-3 px-3 text-right"></th>
        </tr>`;

    document.getElementById('leaderboard-tbody').innerHTML = exp.models.map(m => {
        if (m.status !== 'completed') {
            return `
            <tr class="opacity-70">
                <td class="py-3 px-3 text-gray-600">—</td>
                <td class="py-3 px-3 font-semibold text-gray-300">${escapeHtml(m.display_name)}</td>
                <td colspan="${cols.length + 3}" class="py-3 px-3 text-red-400 text-[11px]">Failed: ${escapeHtml(m.error_message || 'unknown error')}</td>
            </tr>`;
        }
        return `
            <tr data-model-row="${escapeHtml(m.id)}" class="cursor-pointer hover:bg-white/[0.03] transition-colors">
                <td class="py-3 px-3 font-bold ${m.is_best ? 'text-amber-300' : 'text-gray-500'}">${m.is_best ? '⭐' : m.rank}</td>
                <td class="py-3 px-3 font-semibold text-white">${escapeHtml(m.display_name)}</td>
                <td class="py-3 px-3 font-mono">${formatMetric(m.cv_score)} <span class="text-gray-500">± ${formatMetric(m.cv_std)}</span></td>
                ${cols.map(c => `<td class="py-3 px-3 font-mono">${formatMetric(m.metrics[c])}</td>`).join('')}
                <td class="py-3 px-3 text-gray-400">${formatSeconds(m.training_time_seconds)}</td>
                <td class="py-3 px-3 text-right"><span class="px-2.5 py-1 rounded-lg text-[11px] font-semibold text-primary-400 bg-primary-500/10">Evaluate</span></td>
            </tr>`;
    }).join('');

    document.querySelectorAll('[data-model-row]').forEach(row =>
        row.addEventListener('click', () => selectModel(row.dataset.modelRow)));
}

/* ---------- Model evaluation ---------- */

async function selectModel(modelId) {
    document.querySelectorAll('[data-model-row]').forEach(row =>
        row.classList.toggle('bg-primary-500/[0.07]', row.dataset.modelRow === modelId));

    const resp = await apiGet(`/experiments/${currentExperiment.id}/models/${modelId}`);
    if (!resp.ok) {
        showToast(await apiErrorMessage(resp, 'Could not load model'), 'error');
        return;
    }
    currentModel = await resp.json();
    renderEvaluation(currentModel, currentExperiment.task_type);
    document.getElementById('predict-output').innerHTML = '';
}

function renderEvaluation(model, task) {
    document.getElementById('eval-section').classList.remove('hidden');
    document.getElementById('eval-title').innerHTML =
        `Evaluation: ${model.is_best ? '⭐ ' : ''}${escapeHtml(model.display_name)} <span class="text-xs font-normal text-gray-500">on ${formatNumber(model.evaluation.test_rows)} held-out rows</span>`;
    document.getElementById('eval-download').disabled = !model.has_artifact;

    const metricKeys = isClassification(task)
        ? ['accuracy', 'f1_weighted', 'roc_auc', 'precision_weighted', 'recall_weighted', 'log_loss']
        : ['r2', 'adjusted_r2', 'rmse', 'mae', 'mse', 'mape'];
    document.getElementById('eval-metrics').innerHTML = metricKeys.map(k => `
        <div class="glass rounded-xl border border-white/[0.06] p-3">
            <p class="text-[10px] font-semibold text-gray-500 uppercase tracking-wider">${escapeHtml(METRIC_LABELS[k] || k)}</p>
            <p class="mt-1 text-base font-bold text-white font-mono">${formatMetric(model.metrics[k])}</p>
        </div>`).join('');

    const ev = model.evaluation || {};
    const isClf = isClassification(task);
    document.getElementById('eval-classification').classList.toggle('hidden', !isClf);
    document.getElementById('eval-regression').classList.toggle('hidden', isClf);

    if (isClf) {
        plotConfusion(ev.confusion_matrix);
        plotRoc(ev.roc_curves || []);
        plotPr(ev.pr_curves || []);
        renderPerClass(ev.per_class || []);
    } else {
        plotPredVsActual(ev.predicted_vs_actual);
        plotResiduals(ev.residuals || []);
    }
    plotImportance(ev.feature_importance || []);
    renderParams(model.hyperparameters || {});
}

function plotConfusion(cm) {
    if (!cm) return;
    const labels = cm.labels;
    const z = cm.matrix;
    // Reverse rows so the first class is at the top, like a printed confusion matrix.
    const zRev = [...z].reverse();
    const yRev = [...labels].reverse();
    const annotations = [];
    zRev.forEach((row, i) => row.forEach((value, j) => annotations.push({
        x: labels[j], y: yRev[i], text: String(value), showarrow: false,
        font: { color: '#fff', size: 12 },
    })));
    Plotly.newPlot('chart-confusion', [{
        type: 'heatmap', z: zRev, x: labels, y: yRev, colorscale: 'Blues', showscale: false,
        hovertemplate: 'Actual %{y}<br>Predicted %{x}<br>%{z} rows<extra></extra>',
    }], mlPlotLayout('Predicted', 'Actual', {
        annotations,
        xaxis: { ...mlPlotLayout('Predicted', '').xaxis, type: 'category' },
        yaxis: { ...mlPlotLayout('', 'Actual').yaxis, type: 'category' },
    }), ML_PLOT_CONFIG);
}

function plotRoc(curves) {
    const traces = curves.map(c => ({
        x: c.fpr, y: c.tpr, mode: 'lines', type: 'scatter',
        name: `${c.label} (AUC ${formatMetric(c.auc)})`,
    }));
    traces.push({ x: [0, 1], y: [0, 1], mode: 'lines', name: 'Random', line: { dash: 'dot', color: '#64748b' } });
    Plotly.newPlot('chart-roc', traces, mlPlotLayout('False positive rate', 'True positive rate'), ML_PLOT_CONFIG);
}

function plotPr(curves) {
    const traces = curves.map(c => ({
        x: c.recall, y: c.precision, mode: 'lines', type: 'scatter',
        name: `${c.label} (AP ${formatMetric(c.average_precision)})`,
    }));
    Plotly.newPlot('chart-pr', traces, mlPlotLayout('Recall', 'Precision', { yaxis: { ...mlPlotLayout('', 'Precision').yaxis, range: [0, 1.05] } }), ML_PLOT_CONFIG);
}

function renderPerClass(rows) {
    document.getElementById('eval-per-class').innerHTML = rows.map(r => `
        <tr>
            <td class="py-2 px-3 font-mono text-white">${escapeHtml(r.label)}</td>
            <td class="py-2 px-3 font-mono">${formatMetric(r.precision)}</td>
            <td class="py-2 px-3 font-mono">${formatMetric(r.recall)}</td>
            <td class="py-2 px-3 font-mono">${formatMetric(r.f1)}</td>
            <td class="py-2 px-3 text-gray-400">${formatNumber(r.support)}</td>
        </tr>`).join('');
}

function plotPredVsActual(data) {
    if (!data) return;
    const all = data.actual.concat(data.predicted).filter(v => v !== null);
    const lo = Math.min(...all), hi = Math.max(...all);
    Plotly.newPlot('chart-pred-actual', [
        { x: data.actual, y: data.predicted, mode: 'markers', type: 'scatter', name: 'Rows', marker: { size: 6, opacity: 0.7, color: '#818cf8' } },
        { x: [lo, hi], y: [lo, hi], mode: 'lines', name: 'Perfect', line: { dash: 'dot', color: '#64748b' } },
    ], mlPlotLayout('Actual', 'Predicted'), ML_PLOT_CONFIG);
}

function plotResiduals(residuals) {
    Plotly.newPlot('chart-residuals', [
        { x: residuals, type: 'histogram', marker: { color: '#38bdf8' }, nbinsx: 30 },
    ], mlPlotLayout('Residual (actual − predicted)', 'Rows', { showlegend: false }), ML_PLOT_CONFIG);
}

function plotImportance(items) {
    if (!items.length) {
        document.getElementById('chart-importance').innerHTML = '<p class="text-xs text-gray-500">Not available for this model.</p>';
        return;
    }
    const sorted = [...items].reverse(); // largest at the top of a horizontal bar chart
    Plotly.newPlot('chart-importance', [{
        type: 'bar', orientation: 'h',
        x: sorted.map(i => i.importance), y: sorted.map(i => i.feature),
        error_x: { type: 'data', array: sorted.map(i => i.std || 0), color: '#64748b' },
        marker: { color: '#a78bfa' },
        hovertemplate: '%{y}: %{x:.4f}<extra></extra>',
    }], mlPlotLayout('Score drop when shuffled', '', {
        showlegend: false,
        margin: { l: 130, r: 15, t: 10, b: 45 },
        yaxis: { ...mlPlotLayout('', '').yaxis, type: 'category', automargin: true },
    }), ML_PLOT_CONFIG);
}

function renderParams(params) {
    const entries = Object.entries(params);
    document.getElementById('eval-params').innerHTML = entries.length
        ? entries.map(([k, v]) => `
            <div class="flex items-center justify-between gap-3 px-3 py-1.5 rounded-lg bg-white/[0.03]">
                <span class="font-mono text-gray-400">${escapeHtml(k)}</span>
                <span class="font-mono text-white">${escapeHtml(String(v))}</span>
            </div>`).join('')
        : '<p class="text-gray-500">Default settings (tuning was off or the model has no search space).</p>';
}

/* ---------- Download ---------- */

async function downloadCurrentModel() {
    if (!currentModel) return;
    const resp = await apiGet(`/experiments/${currentExperiment.id}/models/${currentModel.id}/download`);
    if (!resp.ok) {
        showToast(await apiErrorMessage(resp, 'Download failed'), 'error');
        return;
    }
    const blob = await resp.blob();
    const disposition = resp.headers.get('content-disposition') || '';
    const match = disposition.match(/filename="?([^";]+)"?/);
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = match ? match[1] : `${currentModel.algorithm}.joblib`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(link.href);
}

/* ---------- Live prediction ---------- */

async function prefillPredictionForm(exp) {
    const s = exp.summary || {};
    const columns = s.feature_columns || [];
    const numeric = new Set(s.numeric_features || []);
    let sample = {};
    const resp = await apiGet(`/datasets/${exp.dataset_id}/preview?rows=1`);
    if (resp.ok) {
        const preview = await resp.json();
        sample = (preview.rows && preview.rows[0]) || {};
    }
    document.getElementById('predict-fields').innerHTML = columns.map((col, i) => `
        <div class="space-y-1">
            <label for="predict-field-${i}" class="text-[10px] font-mono text-gray-400 truncate block" title="${escapeHtml(col)}">${escapeHtml(col)}</label>
            <input id="predict-field-${i}" data-column="${escapeHtml(col)}" data-numeric="${numeric.has(col)}"
                   type="${numeric.has(col) ? 'number' : 'text'}" step="any" value="${escapeHtml(sample[col] ?? '')}"
                   class="w-full bg-white/[0.03] border border-white/[0.08] rounded-lg px-2.5 py-1.5 text-xs text-gray-200 focus:outline-none focus:border-primary-500">
        </div>`).join('');
}

async function runPrediction() {
    if (!currentModel) return;
    const row = {};
    document.querySelectorAll('#predict-fields input').forEach(input => {
        const raw = input.value.trim();
        if (raw === '') return;
        row[input.dataset.column] = input.dataset.numeric === 'true' ? Number(raw) : raw;
    });

    const output = document.getElementById('predict-output');
    output.textContent = 'Predicting…';
    const resp = await apiPost(`/experiments/${currentExperiment.id}/models/${currentModel.id}/predict`, { rows: [row] });
    if (!resp.ok) {
        output.innerHTML = `<span class="text-red-400">${escapeHtml(await apiErrorMessage(resp, 'Prediction failed'))}</span>`;
        return;
    }
    const result = (await resp.json()).predictions[0];
    let html = `<span class="text-gray-400">${escapeHtml(currentExperiment.target_column)} =</span> <span class="text-lg font-bold text-white font-mono">${escapeHtml(typeof result.prediction === 'number' ? formatMetric(result.prediction) : result.prediction)}</span>`;
    if (result.probabilities) {
        const probs = Object.entries(result.probabilities).sort((a, b) => b[1] - a[1]);
        html += ' <span class="ml-2 text-[11px] text-gray-500">' + probs.map(([label, p]) =>
            `${escapeHtml(label)}: ${(p * 100).toFixed(1)}%`).join(' · ') + '</span>';
    }
    output.innerHTML = html;
}
