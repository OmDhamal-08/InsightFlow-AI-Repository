/**
 * AI BI Platform — Feature Engineering JS
 * Binds dynamic form parameter states, loads previews, and saves datasets.
 */

document.addEventListener('DOMContentLoaded', () => {
    const root = document.getElementById('features-page-root');
    if (!root) return;

    const datasetId = root.dataset.datasetId;
    if (datasetId) {
        initFeatures(datasetId);
    }
});

let currentDatasetId = null;
let datasetColumns = [];
let columnTypesMap = {};
let lastFeatureSetId = null;

async function initFeatures(datasetId) {
    currentDatasetId = datasetId;
    await loadDatasetMetadata(datasetId);
    await loadSavedFeatureSets(datasetId);
    toggleMethodInputs();
}

/**
 * Load dataset details and populate column dropdowns.
 */
async function loadDatasetMetadata(datasetId) {
    try {
        const resp = await apiGet(`/datasets/${datasetId}`);
        if (resp.ok) {
            const ds = await resp.json();
            
            const nameEl = document.getElementById('dataset-name');
            if (nameEl) nameEl.textContent = ds.name;

            const nameInput = document.getElementById('feature-set-name');
            if (nameInput) nameInput.value = `${ds.name.split('.')[0]}_engineered`;

            datasetColumns = ds.column_names || [];

            // Fetch types
            const profResp = await apiGet(`/datasets/${datasetId}/profile`);
            if (profResp.ok) {
                const prof = await profResp.json();
                columnTypesMap = prof.column_types || {};
            }

            populateSelectors();
        }
    } catch (err) {
        console.error('Failed to load dataset details:', err);
    }
}

/**
 * Populate selectors.
 */
function populateSelectors() {
    const singleSelect = document.getElementById('select-single-col');
    const intSelect1 = document.getElementById('select-int-col-1');
    const intSelect2 = document.getElementById('select-int-col-2');
    const targetSelect = document.getElementById('select-target-col');
    const multiCheckDiv = document.getElementById('checkboxes-multi-cols');

    // Filter different types
    const numericCols = datasetColumns.filter(c => columnTypesMap[c] === 'numeric');
    const datetimeCols = datasetColumns.filter(c => columnTypesMap[c] === 'datetime');
    const textCols = datasetColumns.filter(c => columnTypesMap[c] === 'text');

    // Populate Target Column Select
    if (targetSelect) {
        targetSelect.innerHTML = datasetColumns.map(c => `
            <option value="${escapeHtml(c)}">${escapeHtml(c)}</option>
        `).join('');
        // Set last column as default target (typical pattern)
        if (datasetColumns.length > 0) {
            targetSelect.value = datasetColumns[datasetColumns.length - 1];
        }
    }

    // Populate Single Select (e.g. date splits/text splits)
    // We show datetime/text options depending on active method in toggle
    
    // Populate Interaction Selects
    if (intSelect1 && intSelect2) {
        const numericOptions = numericCols.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');
        intSelect1.innerHTML = numericOptions;
        intSelect2.innerHTML = numericOptions;
        if (numericCols.length > 1) {
            intSelect2.value = numericCols[1];
        }
    }

    // Populate Multi Checkboxes (PCA / Polynomial)
    if (multiCheckDiv) {
        multiCheckDiv.innerHTML = numericCols.map(c => `
            <div class="flex items-center gap-2">
                <input type="checkbox" name="multi-col-checkbox" value="${escapeHtml(c)}" id="chk-${escapeHtml(c)}" class="rounded border-white/[0.08] bg-transparent text-primary-500 focus:ring-0 focus:ring-offset-0">
                <label for="chk-${escapeHtml(c)}" class="text-[11px] text-gray-300 font-mono">${escapeHtml(c)}</label>
            </div>
        `).join('');
    }
}

/**
 * Dynamic Form parameters layout switching.
 */
function toggleMethodInputs() {
    const method = document.getElementById('feature-method').value;
    
    const divSingle = document.getElementById('div-single-col');
    const divInteraction = document.getElementById('div-interaction-cols');
    const divMulti = document.getElementById('div-multi-cols');
    const divSelection = document.getElementById('div-selection-params');
    const pcaWrapper = document.getElementById('pca-components-wrapper');
    const singleLabel = document.getElementById('label-single-col');
    const singleSelect = document.getElementById('select-single-col');

    // Hide all
    divSingle.classList.add('hidden');
    divInteraction.classList.add('hidden');
    divMulti.classList.add('hidden');
    divSelection.classList.add('hidden');
    pcaWrapper.classList.add('hidden');

    const datetimeCols = datasetColumns.filter(c => columnTypesMap[c] === 'datetime');
    const textCols = datasetColumns.filter(c => columnTypesMap[c] === 'text');

    if (method === 'date') {
        divSingle.classList.remove('hidden');
        singleLabel.textContent = 'Select Datetime Column';
        singleSelect.innerHTML = datetimeCols.length > 0
            ? datetimeCols.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('')
            : datasetColumns.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');
    } else if (method === 'text') {
        divSingle.classList.remove('hidden');
        singleLabel.textContent = 'Select Text Column';
        singleSelect.innerHTML = textCols.length > 0
            ? textCols.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('')
            : datasetColumns.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');
    } else if (method === 'interaction') {
        divInteraction.classList.remove('hidden');
    } else if (method === 'polynomial') {
        divMulti.classList.remove('hidden');
    } else if (method === 'pca') {
        divMulti.classList.remove('hidden');
        pcaWrapper.classList.remove('hidden');
    } else if (method === 'selection') {
        divSelection.classList.remove('hidden');
    }
}

/**
 * Generate preview.
 */
async function generateFeaturePreview() {
    if (!currentDatasetId) return;

    const placeholder = document.getElementById('preview-placeholder');
    const loading = document.getElementById('preview-loading');
    const table = document.getElementById('preview-table');
    const applyBtn = document.getElementById('apply-feature-set-btn');

    placeholder.classList.add('hidden');
    table.classList.add('hidden');
    loading.classList.remove('hidden');
    applyBtn.disabled = true;

    const name = document.getElementById('feature-set-name').value.trim();
    const method = document.getElementById('feature-method').value;
    
    if (!name) {
        alert('Please enter a name for the feature set.');
        loading.classList.add('hidden');
        placeholder.classList.remove('hidden');
        return;
    }

    const config = {};
    if (method === 'date' || method === 'text') {
        config.column = document.getElementById('select-single-col').value;
    } else if (method === 'interaction') {
        config.columns = [
            document.getElementById('select-int-col-1').value,
            document.getElementById('select-int-col-2').value
        ];
    } else if (method === 'polynomial' || method === 'pca') {
        const checked = [];
        document.querySelectorAll('input[name="multi-col-checkbox"]:checked').forEach(chk => {
            checked.push(chk.value);
        });
        if (checked.length === 0) {
            alert('Please select at least one feature column.');
            loading.classList.add('hidden');
            placeholder.classList.remove('hidden');
            return;
        }
        config.columns = checked;
        if (method === 'pca') {
            config.n_components = document.getElementById('pca-n-components').value;
        }
    } else if (method === 'selection') {
        config.target_column = document.getElementById('select-target-col').value;
        config.k = document.getElementById('selection-k-features').value;
    }

    try {
        const resp = await apiPost(`/datasets/${currentDatasetId}/features/generate`, {
            name,
            method,
            config
        });

        loading.classList.add('hidden');

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            alert(err.detail || 'Preview generation failed.');
            placeholder.classList.remove('hidden');
            return;
        }

        const data = await resp.json();
        lastFeatureSetId = data.feature_set.id;

        // Render preview table
        renderPreviewData(data.preview.columns, data.preview.rows);
        
        table.classList.remove('hidden');
        applyBtn.disabled = false;
        showToast('Feature preview generated successfully!', 'success');

    } catch (err) {
        console.error(err);
        loading.classList.add('hidden');
        placeholder.classList.remove('hidden');
    }
}

/**
 * Execute transformations and apply file output.
 */
async function applyFeatureSet() {
    if (!currentDatasetId || !lastFeatureSetId) return;

    try {
        const resp = await apiPost(`/datasets/${currentDatasetId}/features/${lastFeatureSetId}/apply`);
        if (resp.ok) {
            showToast('Feature Set successfully applied! Engineered dataset created.', 'success');
            
            // Redirect back to upload datasets list
            setTimeout(() => {
                window.location.href = '/upload';
            }, 2000);
        } else {
            const err = await resp.json().catch(() => ({}));
            alert(err.detail || 'Failed to apply feature set.');
        }
    } catch (err) {
        console.error(err);
    }
}

/**
 * Fetch and load saved feature sets.
 */
async function loadSavedFeatureSets(datasetId) {
    const tbody = document.getElementById('saved-feature-sets-tbody');
    if (!tbody) return;

    try {
        const resp = await apiGet(`/datasets/${datasetId}/features`);
        if (resp.ok) {
            const sets = await resp.json();
            if (sets.length > 0) {
                tbody.innerHTML = sets.map(s => {
                    const fileCell = s.output_file_path 
                        ? `<span class="text-emerald-400 font-mono text-[10px] truncate max-w-[120px] block" title="${escapeHtml(s.output_file_path)}">Clean CSV applied</span>`
                        : `<span class="text-amber-400">Preview only</span>`;
                    
                    return `
                        <tr class="hover:bg-white/[0.01] transition-colors border-b border-white/[0.04]">
                            <td class="py-3 px-4 font-semibold text-white">${escapeHtml(s.name)}</td>
                            <td class="py-3 px-3 uppercase text-primary-400">${escapeHtml(s.method)}</td>
                            <td class="py-3 px-3">${s.feature_count}</td>
                            <td class="py-3 px-3">${fileCell}</td>
                            <td class="py-3 px-3 text-gray-500">${new Date(s.created_at).toLocaleDateString()}</td>
                        </tr>
                    `;
                }).join('');
            } else {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="5" class="py-4 text-center text-gray-500">No feature engineering sets applied yet.</td>
                    </tr>
                `;
            }
        }
    } catch (err) {
        console.error(err);
    }
}

/**
 * Hydrate preview rows.
 */
function renderPreviewData(columns, rows) {
    const thead = document.getElementById('preview-thead');
    const tbody = document.getElementById('preview-tbody');

    if (!thead || !tbody) return;

    // Headers
    thead.innerHTML = `
        <tr class="border-b border-white/[0.06] text-gray-500 bg-white/[0.01]">
            ${columns.map(col => `
                <th class="py-2 px-3 whitespace-nowrap font-mono text-[10px] uppercase font-bold">${escapeHtml(col)}</th>
            `).join('')}
        </tr>
    `;

    // Rows
    tbody.innerHTML = rows.map(row => `
        <tr class="hover:bg-white/[0.01] transition-colors border-b border-white/[0.04]">
            ${columns.map(col => {
                const val = row[col];
                const isNull = val === null || val === undefined;
                const text = isNull ? '<span class="text-gray-600">null</span>' : escapeHtml(val);
                return `<td class="py-2 px-3 font-mono text-[11px] whitespace-nowrap truncate max-w-[120px]" title="${escapeHtml(val)}">${text}</td>`;
            }).join('')}
        </tr>
    `).join('');
}
