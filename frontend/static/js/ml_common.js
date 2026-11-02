/**
 * AI BI Platform — shared helpers for the AutoML (Phase 10) and evaluation (Phase 11) pages.
 */

const TASK_LABELS = {
    binary_classification: 'Binary classification',
    multiclass_classification: 'Multiclass classification',
    regression: 'Regression',
};

const METRIC_LABELS = {
    accuracy: 'Accuracy',
    f1_weighted: 'F1 (weighted)',
    f1_macro: 'F1 (macro)',
    precision_weighted: 'Precision (weighted)',
    precision_macro: 'Precision (macro)',
    recall_weighted: 'Recall (weighted)',
    recall_macro: 'Recall (macro)',
    roc_auc: 'ROC-AUC',
    log_loss: 'Log loss',
    r2: 'R²',
    adjusted_r2: 'Adjusted R²',
    rmse: 'RMSE',
    mae: 'MAE',
    mse: 'MSE',
    mape: 'MAPE (%)',
};

function isClassification(task) {
    return task === 'binary_classification' || task === 'multiclass_classification';
}

function taskBadge(task) {
    if (!task) return '<span class="text-gray-500">—</span>';
    const color = isClassification(task)
        ? 'bg-purple-500/10 text-purple-300 border-purple-500/20'
        : 'bg-sky-500/10 text-sky-300 border-sky-500/20';
    return `<span class="inline-flex px-2 py-0.5 text-[10px] font-semibold rounded-full border ${color}">${escapeHtml(TASK_LABELS[task] || task)}</span>`;
}

function statusBadge(status) {
    const colors = {
        completed: 'bg-emerald-500/10 text-emerald-400',
        failed: 'bg-red-500/10 text-red-400',
        running: 'bg-amber-500/10 text-amber-400',
    };
    return `<span class="inline-flex px-2 py-0.5 text-[10px] font-semibold rounded-full ${colors[status] || 'bg-white/5 text-gray-400'}">${escapeHtml(status)}</span>`;
}

/** Format a metric value: small values to 3 decimals, large ones with separators. */
function formatMetric(value) {
    if (value === null || value === undefined || Number.isNaN(value)) return '—';
    const v = Number(value);
    if (Math.abs(v) >= 1000) return v.toLocaleString('en-US', { maximumFractionDigits: 1 });
    if (Math.abs(v) >= 10) return v.toFixed(2);
    return v.toFixed(3);
}

function formatSeconds(seconds) {
    if (seconds === null || seconds === undefined) return '—';
    return seconds < 1 ? `${Math.round(seconds * 1000)} ms` : `${seconds.toFixed(1)} s`;
}

/** Turn a FastAPI error response into a readable message. */
async function apiErrorMessage(resp, fallback = 'Request failed') {
    const data = await resp.json().catch(() => ({}));
    const detail = data.detail;
    if (!detail) return fallback;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return detail.map(d => `${(d.loc || []).slice(-1)[0] || 'field'}: ${d.msg}`).join('; ');
    return fallback;
}

/** Plotly layout that matches the dark glass theme. */
function mlPlotLayout(xTitle, yTitle, extra = {}) {
    const axis = (title) => ({
        title: { text: title, font: { color: '#94a3b8', size: 10 } },
        tickfont: { color: '#94a3b8', size: 9 },
        gridcolor: 'rgba(148, 163, 184, 0.12)',
        zerolinecolor: 'rgba(148, 163, 184, 0.25)',
    });
    return {
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        margin: { l: 55, r: 15, t: 15, b: 45 },
        font: { color: '#cbd5e1', size: 10 },
        legend: { font: { color: '#cbd5e1', size: 9 }, orientation: 'h', y: -0.25 },
        xaxis: axis(xTitle),
        yaxis: axis(yTitle),
        ...extra,
    };
}

const ML_PLOT_CONFIG = { displayModeBar: false, responsive: true };
