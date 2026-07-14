/**
 * AI BI Platform — Profiling JavaScript
 * Handles retrieving, triggering, and rendering dataset profiling statistics.
 */

document.addEventListener('DOMContentLoaded', () => {
    const root = document.getElementById('profiling-page-root');
    if (!root) return;

    const datasetId = root.dataset.datasetId;
    if (datasetId) {
        initProfiling(datasetId);
    }
});

let currentDatasetId = null;

/**
 * Initialize profiling page.
 */
async function initProfiling(datasetId) {
    currentDatasetId = datasetId;
    
    // Load dataset basic metadata first (for name display)
    await loadDatasetMetadata(datasetId);

    // Try to load profiling result
    await loadProfilingResults(datasetId);
}

/**
 * Load basic dataset metadata (e.g., original filename).
 */
async function loadDatasetMetadata(datasetId) {
    try {
        const resp = await apiGet(`/datasets/${datasetId}`);
        if (resp.ok) {
            const ds = await resp.json();
            const nameEl = document.getElementById('dataset-name');
            if (nameEl) nameEl.textContent = ds.name;
        }
    } catch (err) {
        console.error('Failed to load dataset metadata:', err);
    }
}

/**
 * Attempt to load profiling results from backend.
 */
async function loadProfilingResults(datasetId) {
    const resultsDashboard = document.getElementById('profiling-results-dashboard');
    const statusNotProfiled = document.getElementById('status-not-profiled');
    const statusLoading = document.getElementById('status-profiling-loading');

    // Show loading spinner
    if (statusLoading) statusLoading.classList.remove('hidden');
    if (statusNotProfiled) statusNotProfiled.classList.add('hidden');
    if (resultsDashboard) resultsDashboard.classList.add('hidden');

    try {
        const resp = await apiGet(`/datasets/${datasetId}/profile`);
        
        if (resp.status === 404) {
            // Not profiled yet
            if (statusLoading) statusLoading.classList.add('hidden');
            if (statusNotProfiled) statusNotProfiled.classList.remove('hidden');
            return;
        }

        if (!resp.ok) {
            throw new Error('Failed to load profiling results');
        }

        const data = await resp.json();
        
        // Hide loading and show dashboard
        if (statusLoading) statusLoading.classList.add('hidden');
        if (resultsDashboard) resultsDashboard.classList.remove('hidden');

        renderProfilingDashboard(data);

    } catch (err) {
        console.error(err);
        if (statusLoading) statusLoading.classList.add('hidden');
        if (statusNotProfiled) statusNotProfiled.classList.remove('hidden');
    }
}

/**
 * Trigger new profiling generation run.
 */
async function triggerProfiling() {
    if (!currentDatasetId) return;

    const statusNotProfiled = document.getElementById('status-not-profiled');
    const statusLoading = document.getElementById('status-profiling-loading');

    if (statusNotProfiled) statusNotProfiled.classList.add('hidden');
    if (statusLoading) statusLoading.classList.remove('hidden');

    try {
        const resp = await apiPost(`/datasets/${currentDatasetId}/profile`);
        if (resp.ok || resp.status === 201) {
            // Load and render results
            await loadProfilingResults(currentDatasetId);
        } else {
            const err = await resp.json().catch(() => ({}));
            alert(err.detail || 'Profiling failed. Check dataset format.');
            if (statusLoading) statusLoading.classList.add('hidden');
            if (statusNotProfiled) statusNotProfiled.classList.remove('hidden');
        }
    } catch (err) {
        console.error(err);
        alert('An unexpected error occurred during profiling.');
        if (statusLoading) statusLoading.classList.add('hidden');
        if (statusNotProfiled) statusNotProfiled.classList.remove('hidden');
    }
}

/**
 * Render complete profiling metrics dashboard.
 */
function renderProfilingDashboard(data) {
    // 1. Summary Cards
    const rowCount = data.total_rows;
    document.getElementById('stat-rows').textContent = formatNumber(rowCount);
    document.getElementById('stat-cols').textContent = formatNumber(data.total_columns);
    document.getElementById('stat-duplicates').textContent = formatNumber(data.duplicate_row_count);
    document.getElementById('stat-created').textContent = formatDate(data.created_at);

    // 2. Column type breakdown counts
    const types = data.column_types || {};
    let numeric = 0, categorical = 0, boolean = 0, datetime = 0, text = 0;
    
    Object.values(types).forEach(type => {
        if (type === 'numeric') numeric++;
        else if (type === 'categorical') categorical++;
        else if (type === 'boolean') boolean++;
        else if (type === 'datetime') datetime++;
        else if (type === 'text') text++;
    });

    document.getElementById('type-numeric-count').textContent = numeric;
    document.getElementById('type-categorical-count').textContent = categorical;
    document.getElementById('type-boolean-count').textContent = boolean;
    document.getElementById('type-datetime-count').textContent = datetime;
    document.getElementById('type-text-count').textContent = text;

    // 3. Render Columns Detailed Stats Table
    const tbody = document.getElementById('columns-stats-tbody');
    if (tbody) {
        const cols = Object.keys(types);
        tbody.innerHTML = cols.map(col => {
            const type = types[col];
            const nullCount = data.null_counts[col] || 0;
            const nullPct = rowCount > 0 ? ((nullCount / rowCount) * 100).toFixed(1) : '0';
            const unique = data.unique_counts[col] ?? '--';
            const stats = data.descriptive_stats[col] || {};

            let statsHtml = '';
            let typeBadgeColor = 'bg-blue-500/10 text-blue-400 border-blue-500/20';

            if (type === 'numeric') {
                typeBadgeColor = 'bg-blue-500/10 text-blue-400 border-blue-500/20';
                statsHtml = `
                    <div class="grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-1 text-xs">
                        <div><span class="text-gray-500">Mean:</span> <span class="font-medium text-white">${formatFloat(stats.mean)}</span></div>
                        <div><span class="text-gray-500">Median:</span> <span class="font-medium text-white">${formatFloat(stats.median)}</span></div>
                        <div><span class="text-gray-500">StdDev:</span> <span class="font-medium text-white">${formatFloat(stats.std)}</span></div>
                        <div><span class="text-gray-500">Skewness:</span> <span class="font-medium text-white">${formatFloat(stats.skewness)}</span></div>
                        <div><span class="text-gray-500">Min:</span> <span class="font-medium text-white">${formatFloat(stats.min)}</span></div>
                        <div><span class="text-gray-500">Max:</span> <span class="font-medium text-white">${formatFloat(stats.max)}</span></div>
                        <div><span class="text-gray-500">Q1 (25%):</span> <span class="font-medium text-white">${formatFloat(stats.q1)}</span></div>
                        <div><span class="text-gray-500">Q3 (75%):</span> <span class="font-medium text-white">${formatFloat(stats.q3)}</span></div>
                    </div>
                `;
            } else {
                if (type === 'categorical') typeBadgeColor = 'bg-purple-500/10 text-purple-400 border-purple-500/20';
                else if (type === 'boolean') typeBadgeColor = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
                else if (type === 'datetime') typeBadgeColor = 'bg-amber-500/10 text-amber-400 border-amber-500/20';
                else if (type === 'text') typeBadgeColor = 'bg-red-500/10 text-red-400 border-red-500/20';

                const topVal = stats.top_value !== null && stats.top_value !== undefined ? stats.top_value : '--';
                const freq = stats.frequency != null ? formatNumber(stats.frequency) : '--';
                const freqPct = stats.frequency != null && rowCount > 0 ? ((stats.frequency / rowCount) * 100).toFixed(1) : null;
                const freqPctStr = freqPct ? ` (${freqPct}%)` : '';

                let dateRangeHtml = '';
                if (type === 'datetime' && stats.min_date) {
                    dateRangeHtml = `
                        <div class="mt-1 text-[11px] text-gray-500">
                            Range: <span class="text-gray-300 font-medium">${formatSimpleDate(stats.min_date)}</span> to <span class="text-gray-300 font-medium">${formatSimpleDate(stats.max_date)}</span>
                        </div>
                    `;
                }

                statsHtml = `
                    <div class="text-xs">
                        <span class="text-gray-500">Most Frequent:</span> <code class="px-1.5 py-0.5 rounded bg-white/[0.04] text-primary-300 font-mono text-[11px]">${topVal}</code>
                        <span class="text-gray-500 ml-3">Occurrences:</span> <span class="font-medium text-white">${freq}${freqPctStr}</span>
                        ${dateRangeHtml}
                    </div>
                `;
            }

            return `
                <tr class="hover:bg-white/[0.02] transition-colors">
                    <td class="py-4 px-6 font-semibold text-white whitespace-nowrap">${col}</td>
                    <td class="py-4 px-4 whitespace-nowrap">
                        <span class="inline-flex px-2 py-0.5 text-[10px] font-semibold border rounded-full uppercase ${typeBadgeColor}">${type}</span>
                    </td>
                    <td class="py-4 px-4 whitespace-nowrap text-gray-400">
                        ${nullCount > 0 ? `<span class="text-red-400 font-medium">${formatNumber(nullCount)}</span>` : '0'}
                        <span class="text-xs text-gray-500 ml-1">(${nullPct}%)</span>
                    </td>
                    <td class="py-4 px-4 whitespace-nowrap text-gray-400">${formatNumber(unique)}</td>
                    <td class="py-4 px-6">${statsHtml}</td>
                </tr>
            `;
        }).join('');
    }

    // 4. Render Categorical Value Distributions (Frequencies list)
    const distGrid = document.getElementById('categorical-distributions-grid');
    const distSection = document.getElementById('distributions-section');
    if (distGrid && distSection) {
        let count = 0;
        let html = '';

        Object.keys(types).forEach(col => {
            const type = types[col];
            const stats = data.descriptive_stats[col] || {};
            
            if ((type === 'categorical' || type === 'boolean') && stats.frequencies) {
                count++;
                const freqs = stats.frequencies;
                
                let barsHtml = '';
                const maxVal = Math.max(...Object.values(freqs), 1);

                Object.keys(freqs).forEach(k => {
                    const countVal = freqs[k];
                    const pct = ((countVal / rowCount) * 100).toFixed(1);
                    const barWidth = ((countVal / maxVal) * 100).toFixed(0);

                    barsHtml += `
                        <div class="space-y-1">
                            <div class="flex items-center justify-between text-xs">
                                <span class="text-gray-300 truncate max-w-[150px] font-mono text-[11px]">${k}</span>
                                <span class="text-gray-500">${formatNumber(countVal)} <span class="text-[10px] ml-0.5">(${pct}%)</span></span>
                            </div>
                            <div class="h-1.5 rounded-full bg-white/[0.04] overflow-hidden">
                                <div class="h-full bg-primary-500/60 rounded-full" style="width: ${barWidth}%"></div>
                            </div>
                        </div>
                    `;
                });

                html += `
                    <div class="glass border border-white/[0.05] rounded-xl p-4 space-y-3">
                        <div class="flex items-center justify-between">
                            <h5 class="text-xs font-bold text-white truncate">${col}</h5>
                            <span class="text-[10px] font-semibold bg-purple-500/10 text-purple-400 px-2 py-0.5 rounded-full uppercase">${type}</span>
                        </div>
                        <div class="space-y-2">
                            ${barsHtml}
                        </div>
                    </div>
                `;
            }
        });

        if (count > 0) {
            distGrid.innerHTML = html;
            distSection.classList.remove('hidden');
        } else {
            distSection.classList.add('hidden');
        }
    }
}

/**
 * Formatting helpers.
 */
function formatFloat(val) {
    if (val === null || val === undefined) return '--';
    const num = Number(val);
    if (isNaN(num)) return '--';
    if (Number.isInteger(num)) return num.toLocaleString('en-US');
    return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
}

function formatSimpleDate(isoStr) {
    if (!isoStr) return '--';
    try {
        const date = new Date(isoStr);
        return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    } catch {
        return isoStr;
    }
}
