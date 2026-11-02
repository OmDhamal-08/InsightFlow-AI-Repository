/**
 * AI BI Platform — Quality Audit JavaScript
 * Handles retrieving, running, and rendering dataset quality audits.
 */

document.addEventListener('DOMContentLoaded', () => {
    const root = document.getElementById('quality-page-root');
    if (!root) return;

    const datasetId = root.dataset.datasetId;
    if (datasetId) {
        initQualityAudit(datasetId);
    }
});

let currentDatasetId = null;

/**
 * Initialize quality audit page.
 */
async function initQualityAudit(datasetId) {
    currentDatasetId = datasetId;
    await loadDatasetMetadata(datasetId);
    await loadQualityResults(datasetId);
}

/**
 * Load basic dataset metadata (for name display).
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
 * Load data quality results.
 */
async function loadQualityResults(datasetId) {
    const resultsDashboard = document.getElementById('quality-results-dashboard');
    const statusNotAnalyzed = document.getElementById('status-not-analyzed');
    const statusLoading = document.getElementById('status-quality-loading');

    // Show loading spinner
    if (statusLoading) statusLoading.classList.remove('hidden');
    if (statusNotAnalyzed) statusNotAnalyzed.classList.add('hidden');
    if (resultsDashboard) resultsDashboard.classList.add('hidden');

    try {
        const resp = await apiGet(`/datasets/${datasetId}/quality`);
        
        if (resp.status === 404) {
            // Not audited yet
            if (statusLoading) statusLoading.classList.add('hidden');
            if (statusNotAnalyzed) statusNotAnalyzed.classList.remove('hidden');
            return;
        }

        if (!resp.ok) {
            throw new Error('Failed to load quality results');
        }

        const data = await resp.json();
        
        // Hide loading and show dashboard
        if (statusLoading) statusLoading.classList.add('hidden');
        if (resultsDashboard) resultsDashboard.classList.remove('hidden');

        renderQualityDashboard(data);

    } catch (err) {
        console.error(err);
        if (statusLoading) statusLoading.classList.add('hidden');
        if (statusNotAnalyzed) statusNotAnalyzed.classList.remove('hidden');
    }
}

/**
 * Trigger quality analysis run.
 */
async function triggerQualityAnalysis() {
    if (!currentDatasetId) return;

    const statusNotAnalyzed = document.getElementById('status-not-analyzed');
    const statusLoading = document.getElementById('status-quality-loading');

    if (statusNotAnalyzed) statusNotAnalyzed.classList.add('hidden');
    if (statusLoading) statusLoading.classList.remove('hidden');

    try {
        const resp = await apiPost(`/datasets/${currentDatasetId}/quality`);
        if (resp.ok || resp.status === 201) {
            await loadQualityResults(currentDatasetId);
        } else {
            const err = await resp.json().catch(() => ({}));
            alert(err.detail || 'Quality analysis failed.');
            if (statusLoading) statusLoading.classList.add('hidden');
            if (statusNotAnalyzed) statusNotAnalyzed.classList.remove('hidden');
        }
    } catch (err) {
        console.error(err);
        alert('An unexpected error occurred during quality analysis.');
        if (statusLoading) statusLoading.classList.add('hidden');
        if (statusNotAnalyzed) statusNotAnalyzed.classList.remove('hidden');
    }
}

/**
 * Render the Quality Dashboard.
 */
function renderQualityDashboard(data) {
    const score = Math.round(data.quality_score);
    const scoreText = document.getElementById('score-text');
    const scoreGauge = document.getElementById('score-gauge-fill');
    const scoreLabel = document.getElementById('score-label');

    // 1. Render Circular Score Gauge
    if (scoreText) scoreText.textContent = `${score}%`;
    if (scoreGauge) {
        // Circumference = 390
        const offset = 390 - (390 * score) / 100;
        scoreGauge.style.strokeDashoffset = offset;

        // Change color based on score
        if (score >= 80) {
            scoreGauge.setAttribute('stroke', '#10b981'); // emerald-500
            if (scoreLabel) {
                scoreLabel.textContent = 'Excellent';
                scoreLabel.className = 'text-[10px] uppercase font-bold tracking-wider text-emerald-400 mt-1';
            }
        } else if (score >= 50) {
            scoreGauge.setAttribute('stroke', '#f59e0b'); // amber-500
            if (scoreLabel) {
                scoreLabel.textContent = 'Warning';
                scoreLabel.className = 'text-[10px] uppercase font-bold tracking-wider text-amber-400 mt-1';
            }
        } else {
            scoreGauge.setAttribute('stroke', '#ef4444'); // red-500
            if (scoreLabel) {
                scoreLabel.textContent = 'Critical';
                scoreLabel.className = 'text-[10px] uppercase font-bold tracking-wider text-red-500 mt-1';
            }
        }
    }

    // 2. Render Actionable Recommendations
    const recContainer = document.getElementById('recommendations-container');
    const recBadge = document.getElementById('rec-count-badge');
    const recs = data.recommendations || [];

    if (recBadge) recBadge.textContent = `${recs.length} issue${recs.length !== 1 ? 's' : ''}`;

    if (recContainer) {
        if (recs.length === 0) {
            recContainer.innerHTML = `
                <div class="text-center py-8 text-gray-500 text-xs">
                    ✨ No data quality issues detected! Your dataset is clean and ready.
                </div>
            `;
        } else {
            recContainer.innerHTML = recs.map(rec => {
                let badgeClass = 'bg-blue-500/10 text-blue-400 border-blue-500/20';
                if (rec.severity === 'critical') {
                    badgeClass = 'bg-red-500/10 text-red-400 border-red-500/20';
                } else if (rec.severity === 'warning') {
                    badgeClass = 'bg-amber-500/10 text-amber-400 border-amber-500/20';
                }

                const actionDisplay = formatActionName(rec.recommended_action);

                return `
                    <div class="glass border border-white/[0.04] p-3 rounded-xl flex items-start justify-between gap-3 text-xs">
                        <div class="space-y-1">
                            <div class="flex items-center gap-2">
                                <span class="inline-flex px-1.5 py-0.5 text-[9px] font-bold border rounded uppercase ${badgeClass}">${rec.severity}</span>
                                ${rec.column ? `<span class="font-semibold text-white font-mono text-[10px]">${escapeHtml(rec.column)}</span>` : '<span class="text-gray-500">Dataset</span>'}
                            </div>
                            <p class="text-gray-300 leading-relaxed">${escapeHtml(rec.description)}</p>
                        </div>
                        <div class="text-right flex-shrink-0">
                            <span class="inline-flex items-center px-2 py-1 rounded bg-primary-500/10 text-primary-400 font-medium text-[10px]">
                                Action: ${actionDisplay}
                            </span>
                        </div>
                    </div>
                `;
            }).join('');
        }
    }

    // 3. Render Completeness Tab
    const compBody = document.getElementById('completeness-tbody');
    const dupText = document.getElementById('duplicate-stats-text');
    if (dupText && data.duplicate_report) {
        dupText.textContent = `Duplicate rows: ${formatNumber(data.duplicate_report.duplicate_count)} (${data.duplicate_report.duplicate_percentage.toFixed(1)}%)`;
    }

    if (compBody && data.missing_value_report) {
        const cols = Object.keys(data.missing_value_report);
        compBody.innerHTML = cols.map(col => {
            const stats = data.missing_value_report[col];
            const fillPct = (100 - stats.null_percentage).toFixed(1);

            let barColor = 'bg-emerald-500';
            if (fillPct < 50.0) barColor = 'bg-red-500';
            else if (fillPct < 95.0) barColor = 'bg-amber-500';

            return `
                <tr class="hover:bg-white/[0.02] transition-colors">
                    <td class="py-3 px-4 font-semibold text-white font-mono text-xs">${escapeHtml(col)}</td>
                    <td class="py-3 px-4 text-gray-400">${formatNumber(stats.null_count)} (${stats.null_percentage.toFixed(1)}%)</td>
                    <td class="py-3 px-4 text-gray-300">${fillPct}% filled</td>
                    <td class="py-3 px-4">
                        <div class="w-32 h-2 rounded-full bg-white/[0.05] overflow-hidden">
                            <div class="h-full ${barColor}" style="width: ${fillPct}%"></div>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    }

    // 4. Render Outliers Tab
    const outBody = document.getElementById('outliers-tbody');
    if (outBody && data.outlier_report) {
        const cols = Object.keys(data.outlier_report);
        if (cols.length === 0) {
            outBody.innerHTML = `
                <tr>
                    <td colspan="4" class="text-center py-6 text-gray-500 text-xs">No numeric columns found to calculate outliers.</td>
                </tr>
            `;
        } else {
            outBody.innerHTML = cols.map(col => {
                const stats = data.outlier_report[col];
                const pct = stats.outlier_percentage.toFixed(1);
                
                const boundsText = stats.lower_bound !== null
                    ? `[${formatFloat(stats.lower_bound)}, ${formatFloat(stats.upper_bound)}]`
                    : '--';

                return `
                    <tr class="hover:bg-white/[0.02] transition-colors">
                        <td class="py-3 px-4 font-semibold text-white font-mono text-xs">${escapeHtml(col)}</td>
                        <td class="py-3 px-4 text-gray-400">${formatNumber(stats.outlier_count)}</td>
                        <td class="py-3 px-4 text-gray-400">${pct}%</td>
                        <td class="py-3 px-4 text-gray-500 font-mono text-xs">${boundsText}</td>
                    </tr>
                `;
            }).join('');
        }
    }

    // 5. Render Distribution Tab (Skewness + Multicollinearity)
    const skewBody = document.getElementById('skewness-tbody');
    if (skewBody && data.skewness_report) {
        const cols = Object.keys(data.skewness_report);
        if (cols.length === 0) {
            skewBody.innerHTML = `
                <tr>
                    <td colspan="3" class="text-center py-4 text-gray-500">No numeric columns found.</td>
                </tr>
            `;
        } else {
            skewBody.innerHTML = cols.map(col => {
                const skew = data.skewness_report[col].skewness;
                let badge = '<span class="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/10">Normal</span>';
                
                if (skew !== null) {
                    if (abs(skew) > 1.5) {
                        badge = '<span class="px-2 py-0.5 rounded bg-red-500/10 text-red-400 border border-red-500/10">Highly Skewed</span>';
                    } else if (abs(skew) > 0.8) {
                        badge = '<span class="px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/10">Moderately Skewed</span>';
                    }
                }
                const skewValText = skew !== null ? skew.toFixed(2) : '--';

                return `
                    <tr class="hover:bg-white/[0.02] transition-colors">
                        <td class="py-2.5 px-3 font-medium text-white font-mono">${escapeHtml(col)}</td>
                        <td class="py-2.5 px-3 text-gray-400">${skewValText}</td>
                        <td class="py-2.5 px-3 text-xs">${badge}</td>
                    </tr>
                `;
            }).join('');
        }
    }

    // Multicollinearity list
    const multiContainer = document.getElementById('multicollinearity-container');
    if (multiContainer && data.correlation_report) {
        const pairs = data.correlation_report.high_correlation_pairs || [];
        if (pairs.length === 0) {
            multiContainer.innerHTML = `
                <div class="text-center py-8 text-gray-500 text-xs">
                    ✨ No high multicollinearity issues detected. Features are sufficiently independent.
                </div>
            `;
        } else {
            multiContainer.innerHTML = pairs.map(pair => `
                <div class="p-3 rounded-xl bg-white/[0.02] border border-white/[0.04] flex items-center justify-between text-xs">
                    <div class="flex items-center gap-2">
                        <span class="font-mono text-white font-semibold">${escapeHtml(pair.col1)}</span>
                        <span class="text-gray-500">&harr;</span>
                        <span class="font-mono text-white font-semibold">${escapeHtml(pair.col2)}</span>
                    </div>
                    <span class="font-bold text-red-400 font-mono">r = ${pair.coefficient.toFixed(2)}</span>
                </div>
            `).join('');
        }
    }
}

/**
 * Helper to display tab switching.
 */
function switchTab(tabId) {
    // Headers
    const btns = document.querySelectorAll('.tab-btn');
    btns.forEach(btn => {
        btn.classList.remove('active', 'text-primary-400', 'border-primary-500');
        btn.classList.add('text-gray-400', 'border-transparent');
    });

    const activeBtn = document.getElementById(`tab-btn-${tabId}`);
    if (activeBtn) {
        activeBtn.classList.add('active', 'text-primary-400', 'border-primary-500');
        activeBtn.classList.remove('text-gray-400', 'border-transparent');
    }

    // Contents
    const contents = document.querySelectorAll('.tab-content');
    contents.forEach(content => content.classList.add('hidden'));

    const activeContent = document.getElementById(`tab-content-${tabId}`);
    if (activeContent) activeContent.classList.remove('hidden');
}

/**
 * Format actions to readable strings.
 */
function formatActionName(action) {
    if (!action) return '--';
    const mappings = {
        'drop_column': 'Drop Column',
        'impute_mean_median': 'Impute Median/Mean',
        'impute_median': 'Impute Median',
        'impute_knn': 'Impute KNN',
        'impute_mode': 'Impute Mode',
        'drop_duplicates': 'Drop Duplicates',
        'outliers_drop': 'Drop Outlier Rows',
        'outliers_cap': 'Cap Outliers (Winsorize)',
        'impute_outliers_median': 'Impute Outliers Median',
        'drop_correlated_column': 'Drop Correlated Feature',
        'apply_pca': 'Dimensionality Reduction (PCA)',
        'apply_log_transform': 'Log Transform',
        'apply_power_transform': 'Power Transform',
        'resample_oversample': 'Over-sample Minority Class',
        'use_class_weights': 'Balanced Class Weights'
    };
    return mappings[action] || action.replace(/_/g, ' ');
}

function formatFloat(val) {
    if (val === null || val === undefined) return '--';
    const num = Number(val);
    if (isNaN(num)) return '--';
    if (Number.isInteger(num)) return num.toLocaleString('en-US');
    return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
}

function abs(v) {
    return Math.abs(v);
}
