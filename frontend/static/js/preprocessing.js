/**
 * AI BI Platform — Preprocessing Wizard JavaScript
 * Dynamically binds column configurations, preview comparisons, and runs pipelines.
 */

document.addEventListener('DOMContentLoaded', () => {
    const root = document.getElementById('preprocessing-page-root');
    if (!root) return;

    const datasetId = root.dataset.datasetId;
    if (datasetId) {
        initPreprocessing(datasetId);
    }
});

let currentDatasetId = null;
let datasetColumns = [];
let columnTypesMap = {};

/**
 * Initialize preprocessing page.
 */
async function initPreprocessing(datasetId) {
    currentDatasetId = datasetId;
    await loadDatasetMetadata(datasetId);
}

/**
 * Load dataset details and columns list.
 */
async function loadDatasetMetadata(datasetId) {
    try {
        const resp = await apiGet(`/datasets/${datasetId}`);
        if (resp.ok) {
            const ds = await resp.json();
            
            const nameEl = document.getElementById('dataset-name');
            if (nameEl) nameEl.textContent = ds.name;

            const nameInput = document.getElementById('pipeline-name');
            if (nameInput) nameInput.value = `${ds.name.split('.')[0]}_cleaned`;

            datasetColumns = ds.column_names || [];
            
            // We need types from profiling. Try to fetch profiling to understand types
            const profResp = await apiGet(`/datasets/${datasetId}/profile`);
            if (profResp.ok) {
                const prof = await profResp.json();
                columnTypesMap = prof.column_types || {};
            } else {
                // Fallback types
                datasetColumns.forEach(col => {
                    columnTypesMap[col] = 'numeric'; // Default fallback
                });
            }

            renderColumnsConfigTable();
        }
    } catch (err) {
        console.error('Failed to load dataset details:', err);
    }
}

/**
 * Render the column configurations list.
 */
function renderColumnsConfigTable() {
    const tbody = document.getElementById('columns-config-tbody');
    if (!tbody) return;

    tbody.innerHTML = datasetColumns.map(col => {
        const type = columnTypesMap[col] || 'text';
        const isNumeric = type === 'numeric';
        const isDatetime = type === 'datetime';

        // Imputation dropdown
        const impSelect = `
            <select id="imp-${col}" class="w-full bg-white/[0.03] border border-white/[0.08] rounded px-2 py-1 text-xs focus:outline-none focus:border-primary-500">
                <option value="none">No Action</option>
                <option value="impute_cca">CCA (Drop Rows)</option>
                <option value="impute_mean" ${isNumeric ? '' : 'disabled'}>Mean Impute</option>
                <option value="impute_median" ${isNumeric ? '' : 'disabled'}>Median Impute</option>
                <option value="impute_mode">Mode Impute</option>
                <option value="impute_constant">Constant Value</option>
                <option value="impute_random">Random Impute</option>
                <option value="impute_end_of_dist" ${isNumeric ? '' : 'disabled'}>End of Dist Impute</option>
                <option value="impute_knn" ${isNumeric ? '' : 'disabled'}>KNN Imputer</option>
                <option value="impute_iterative" ${isNumeric ? '' : 'disabled'}>MICE Imputer</option>
            </select>
        `;

        // Outlier dropdown
        const outSelect = `
            <select id="out-${col}" class="w-full bg-white/[0.03] border border-white/[0.08] rounded px-2 py-1 text-xs focus:outline-none focus:border-primary-500" ${isNumeric ? '' : 'disabled'}>
                <option value="none">No Action</option>
                <option value="outliers_cap">Cap Outliers (IQR)</option>
                <option value="outliers_drop">Drop Outlier Rows</option>
                <option value="outliers_impute_median">Impute Median</option>
                <option value="outliers_impute_mean">Impute Mean</option>
                <option value="outliers_set_nan">Set Outliers to NaN</option>
            </select>
        `;

        // Scaling & skewness dropdowns
        const scaleSelect = `
            <select id="scale-${col}" class="w-full bg-white/[0.03] border border-white/[0.08] rounded px-2 py-1 text-xs focus:outline-none focus:border-primary-500" ${isNumeric ? '' : 'disabled'}>
                <option value="none">No Action</option>
                <option value="scale_standard">Standardize (Z-score)</option>
                <option value="scale_minmax">Normalize (MinMax)</option>
                <option value="scale_robust">Robust Scaling</option>
                <option value="apply_log_transform">Log Transform (log1p)</option>
                <option value="apply_sqrt_transform">Square Root Transform</option>
                <option value="apply_reciprocal_transform">Reciprocal Transform</option>
                <option value="apply_boxcox_transform">Box-Cox Transform</option>
                <option value="apply_yeojohnson_transform">Yeo-Johnson Transform</option>
            </select>
        `;

        // Encoding & binning dropdown
        const binSelect = `
            <select id="bin-${col}" class="w-full bg-white/[0.03] border border-white/[0.08] rounded px-2 py-1 text-xs focus:outline-none focus:border-primary-500">
                <option value="none">No Action</option>
                <option value="discretize_equal_width" ${isNumeric ? '' : 'disabled'}>Equal Width Binning (5)</option>
                <option value="discretize_equal_frequency" ${isNumeric ? '' : 'disabled'}>Equal Freq Binning (5)</option>
                <option value="discretize_kmeans" ${isNumeric ? '' : 'disabled'}>K-means Binning (5)</option>
                <option value="binarize" ${isNumeric ? '' : 'disabled'}>Binarize (Threshold 0)</option>
                <option value="encode_onehot" ${isNumeric || isDatetime ? 'disabled' : ''}>One-Hot Encode</option>
                <option value="encode_label" ${isNumeric || isDatetime ? 'disabled' : ''}>Label Encode</option>
                <option value="handle_datetime" ${isDatetime ? '' : 'disabled'}>Datetime features (Y,M,D)</option>
            </select>
        `;

        const typeBadgeColor = {
            'numeric': 'bg-blue-500/10 text-blue-400 border-blue-500/20',
            'categorical': 'bg-purple-500/10 text-purple-400 border-purple-500/20',
            'boolean': 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
            'datetime': 'bg-amber-500/10 text-amber-400 border-amber-500/20',
            'text': 'bg-red-500/10 text-red-400 border-red-500/20'
        }[type] || 'bg-white/10 text-white border-white/20';

        return `
            <tr class="hover:bg-white/[0.01] transition-colors" id="row-${col}">
                <td class="py-3 px-4 font-semibold text-white font-mono whitespace-nowrap">${col}</td>
                <td class="py-3 px-3 whitespace-nowrap">
                    <span class="inline-flex px-2 py-0.5 text-[9px] font-bold border rounded-full uppercase ${typeBadgeColor}">${type}</span>
                </td>
                <td class="py-3 px-3">${impSelect}</td>
                <td class="py-3 px-3">${outSelect}</td>
                <td class="py-3 px-3">${scaleSelect}</td>
                <td class="py-3 px-3">${binSelect}</td>
                <td class="py-3 px-3 text-center">
                    <input type="checkbox" id="drop-${col}" class="rounded border-white/[0.08] bg-transparent text-primary-500 focus:ring-0 focus:ring-offset-0">
                </td>
            </tr>
        `;
    }).join('');
}

/**
 * Fetch recommendations from backend and pre-fill selections.
 */
async function fetchRecommendations() {
    if (!currentDatasetId) return;

    try {
        const resp = await apiPost(`/datasets/${currentDatasetId}/preprocess/analyze`);
        if (!resp.ok) return;

        const recs = await resp.json();
        
        // Reset all first
        datasetColumns.forEach(col => {
            const imp = document.getElementById(`imp-${col}`);
            const out = document.getElementById(`out-${col}`);
            const scale = document.getElementById(`scale-${col}`);
            const drop = document.getElementById(`drop-${col}`);
            const bin = document.getElementById(`bin-${col}`);

            if (imp) imp.value = 'none';
            if (out) out.value = 'none';
            if (scale) scale.value = 'none';
            if (bin) bin.value = 'none';
            if (drop) drop.checked = false;
        });

        // Apply recommended values
        recs.forEach(rec => {
            const col = rec.column;
            if (!col) return; // Skip dataset-wide issues

            const imp = document.getElementById(`imp-${col}`);
            const out = document.getElementById(`out-${col}`);
            const scale = document.getElementById(`scale-${col}`);
            const drop = document.getElementById(`drop-${col}`);

            if (rec.recommended_action === 'drop_column' || rec.recommended_action === 'drop_correlated_column') {
                if (drop) drop.checked = true;
            } else if (rec.recommended_action.startsWith('impute_') && imp) {
                imp.value = rec.recommended_action;
            } else if (rec.recommended_action.startsWith('outliers_') || rec.recommended_action.startsWith('cap_') && out) {
                out.value = rec.recommended_action === 'cap_outliers' ? 'outliers_cap' : rec.recommended_action;
            } else if (rec.recommended_action.startsWith('apply_log') && scale) {
                scale.value = rec.recommended_action;
            }
        });

        showToast('Quality recommendations successfully pre-filled!', 'success');

    } catch (err) {
        console.error('Failed to load quality recommendations:', err);
    }
}

/**
 * Compile selections into steps payload.
 */
function getSelectedSteps() {
    const steps = [];

    // Check for duplicates step in quality recommendations
    // If duplicates drop is needed, we always run it first
    // For simplicity, we can inspect a global flag or append it automatically
    steps.push({ action: 'drop_duplicates' });

    datasetColumns.forEach(col => {
        // Drop column check first
        const drop = document.getElementById(`drop-${col}`);
        if (drop && drop.checked) {
            steps.push({ action: 'drop_column', column: col });
            return; // Skip other steps if dropping column
        }

        const imp = document.getElementById(`imp-${col}`);
        const out = document.getElementById(`out-${col}`);
        const scale = document.getElementById(`scale-${col}`);
        const bin = document.getElementById(`bin-${col}`);

        if (imp && imp.value !== 'none') {
            steps.push({ action: imp.value, column: col });
        }
        if (out && out.value !== 'none') {
            steps.push({ action: out.value, column: col });
        }
        if (scale && scale.value !== 'none') {
            steps.push({ action: scale.value, column: col });
        }
        if (bin && bin.value !== 'none') {
            steps.push({ action: bin.value, column: col });
        }
    });

    return steps;
}

/**
 * Fetch and render preview.
 */
async function getPreview() {
    if (!currentDatasetId) return;

    const previewPane = document.getElementById('preview-pane-card');
    if (previewPane) previewPane.classList.add('hidden');

    const steps = getSelectedSteps();

    try {
        const resp = await apiPost(`/datasets/${currentDatasetId}/preprocess/preview`, { steps });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            alert(err.detail || 'Preview failed.');
            return;
        }

        const previewData = await resp.json();
        
        // Render preview summary stats
        renderStatsTable('preview-before-tbody', previewData.before.summary);
        renderStatsTable('preview-after-tbody', previewData.after.summary);

        // Render preview rows
        renderRowsTable(previewData.after.columns, previewData.after.rows);

        // Render shape text
        const shapeText = document.getElementById('preview-shape-text');
        if (shapeText) {
            shapeText.textContent = `DataFrame Shapes — Before: [${previewData.before.shape[0]} rows, ${previewData.before.shape[1]} columns] | After: [${previewData.after.shape[0]} rows, ${previewData.after.shape[1]} columns]`;
        }

        // Show pane
        if (previewPane) {
            previewPane.classList.remove('hidden');
            previewPane.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }

    } catch (err) {
        console.error(err);
    }
}

/**
 * Execute preprocessing and save pipeline.
 */
async function applyPipeline() {
    if (!currentDatasetId) return;

    const pipelineName = document.getElementById('pipeline-name').value.trim();
    if (!pipelineName) {
        alert('Please enter a name for your preprocessing pipeline.');
        return;
    }

    const steps = getSelectedSteps();
    if (steps.length <= 1) { // 1 step is drop_duplicates (default)
        if (!confirm('No other preprocessing operations selected. Proceed anyway?')) return;
    }

    try {
        const resp = await apiPost(`/datasets/${currentDatasetId}/preprocess/apply`, {
            name: pipelineName,
            steps: steps
        });

        if (resp.ok || resp.status === 201) {
            showToast('Preprocessing successfully applied! Cleaned dataset created.', 'success');
            
            // Redirect back to upload datasets list
            setTimeout(() => {
                window.location.href = '/upload';
            }, 2000);
        } else {
            const err = await resp.json().catch(() => ({}));
            alert(err.detail || 'Failed to apply preprocessing pipeline.');
        }
    } catch (err) {
        console.error(err);
    }
}

/**
 * Render stats list helper.
 */
function renderStatsTable(tbodyId, summary) {
    const tbody = document.getElementById(tbodyId);
    if (!tbody || !summary) return;

    const cols = Object.keys(summary);
    tbody.innerHTML = cols.map(col => {
        const stats = summary[col] || {};
        const mean = stats.mean;
        const std = stats.std;
        const meanText = (mean !== null && mean !== undefined && !isNaN(mean)) ? Number(mean).toFixed(2) : '--';
        const stdText = (std !== null && std !== undefined && !isNaN(std)) ? Number(std).toFixed(2) : '--';
        const nullCount = stats.null_count != null ? stats.null_count : '--';

        return `
            <tr>
                <td class="py-2 px-3 font-mono font-medium text-white">${col}</td>
                <td class="py-2 px-3">${meanText}</td>
                <td class="py-2 px-3">${stdText}</td>
                <td class="py-2 px-3">${nullCount}</td>
            </tr>
        `;
    }).join('');
}

/**
 * Render rows preview table helper.
 */
function renderRowsTable(columns, rows) {
    const thead = document.getElementById('preview-rows-thead');
    const tbody = document.getElementById('preview-rows-tbody');

    if (!thead || !tbody) return;

    // Headers
    thead.innerHTML = `
        <tr class="border-b border-white/[0.06] text-gray-500 bg-white/[0.01]">
            ${columns.map(col => `
                <th class="py-2 px-3 whitespace-nowrap font-mono text-[10px] uppercase font-bold">${col}</th>
            `).join('')}
        </tr>
    `;

    // Rows
    tbody.innerHTML = rows.map(row => `
        <tr class="hover:bg-white/[0.01] transition-colors border-b border-white/[0.04]">
            ${columns.map(col => {
                const val = row[col];
                const text = val !== null && val !== undefined ? val : '<span class="text-gray-600">null</span>';
                return `<td class="py-2 px-3 font-mono text-[11px] whitespace-nowrap truncate max-w-[120px]" title="${val}">${text}</td>`;
            }).join('')}
        </tr>
    `).join('');
}
