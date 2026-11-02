/**
 * AI BI Platform — Upload JavaScript
 * Drag-and-drop upload, real API integration, dataset listing, preview, and delete.
 */

document.addEventListener('DOMContentLoaded', () => {
    initUploadZone();
    loadDatasets();
});

let selectedFile = null;

/* ================================================
   Initialize Upload Zone
   ================================================ */
function initUploadZone() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');

    if (!dropZone || !fileInput) return;

    // Prevent default drag behaviors on window
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        document.body.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
        });
    });

    // Highlight on dragover
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.add('drag-over');
        });
    });

    // Remove highlight on dragleave/drop
    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.remove('drag-over');
        });
    });

    // Handle drop
    dropZone.addEventListener('drop', (e) => {
        const files = e.dataTransfer?.files;
        if (files && files.length > 0) {
            handleFileSelection(files[0]);
        }
    });

    // Handle file input change
    fileInput.addEventListener('change', (e) => {
        const files = e.target.files;
        if (files && files.length > 0) {
            handleFileSelection(files[0]);
        }
    });
}

/* ================================================
   Handle File Selection → Auto-upload
   ================================================ */
function handleFileSelection(file) {
    // Validate file type
    const allowedTypes = ['.csv', '.xlsx', '.xls'];
    const extension = '.' + file.name.split('.').pop().toLowerCase();

    if (!allowedTypes.includes(extension)) {
        showUploadError('Unsupported file type. Please upload CSV or Excel files.');
        return;
    }

    // Validate file size (100MB)
    const maxSize = 100 * 1024 * 1024;
    if (file.size > maxSize) {
        showUploadError('File is too large. Maximum size is 100MB.');
        return;
    }

    selectedFile = file;

    // Show file info
    const fileInfo = document.getElementById('file-info');
    const fileName = document.getElementById('file-name');
    const fileSize = document.getElementById('file-size');

    if (fileInfo) fileInfo.classList.remove('hidden');
    if (fileName) fileName.textContent = file.name;
    if (fileSize) fileSize.textContent = formatFileSize(file.size);

    // Auto-trigger real upload
    uploadFile(file);
}

/* ================================================
   Upload File to Backend
   ================================================ */
async function uploadFile(file) {
    const progressSection = document.getElementById('upload-progress');
    const progressBar = document.getElementById('progress-bar');
    const progressPercent = document.getElementById('progress-percent');
    const statusText = document.getElementById('upload-status-text');

    if (progressSection) progressSection.classList.remove('hidden');
    if (statusText) statusText.textContent = 'Uploading...';
    if (progressBar) progressBar.style.width = '10%';
    if (progressPercent) progressPercent.textContent = '10%';

    const formData = new FormData();
    formData.append('file', file);

    try {
        // Use XMLHttpRequest for upload progress tracking
        const result = await new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();

            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    const pct = Math.round((e.loaded / e.total) * 90) + 10; // 10-100
                    if (progressBar) progressBar.style.width = pct + '%';
                    if (progressPercent) progressPercent.textContent = pct + '%';
                }
            });

            xhr.addEventListener('load', () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    resolve(JSON.parse(xhr.responseText));
                } else {
                    try {
                        const errData = JSON.parse(xhr.responseText);
                        reject(new Error(errData.detail || 'Upload failed'));
                    } catch {
                        reject(new Error('Upload failed with status ' + xhr.status));
                    }
                }
            });

            xhr.addEventListener('error', () => reject(new Error('Network error')));
            xhr.addEventListener('abort', () => reject(new Error('Upload cancelled')));

            xhr.open('POST', '/api/v1/datasets/upload');

            // Set auth header
            const token = getAccessToken() || sessionStorage.getItem('access_token');
            if (token) {
                xhr.setRequestHeader('Authorization', 'Bearer ' + token);
            }

            xhr.send(formData);

            // Store xhr for cancel
            window._currentUploadXhr = xhr;
        });

        // Success
        if (progressBar) progressBar.style.width = '100%';
        if (progressPercent) progressPercent.textContent = '100%';
        if (statusText) statusText.textContent = `Upload complete! ${result.row_count || 0} rows, ${result.column_count || 0} columns detected.`;

        // Hide progress after delay and refresh dataset list
        setTimeout(() => {
            if (progressSection) progressSection.classList.add('hidden');
            if (progressBar) progressBar.style.width = '0%';
            removeFile();
            loadDatasets();
        }, 2000);

    } catch (err) {
        if (statusText) statusText.textContent = err.message;
        if (progressBar) {
            progressBar.style.width = '100%';
            progressBar.classList.add('bg-red-500');
            progressBar.classList.remove('bg-gradient-to-r', 'from-primary-500', 'to-blue-500');
        }

        setTimeout(() => {
            if (progressSection) progressSection.classList.add('hidden');
            if (progressBar) {
                progressBar.style.width = '0%';
                progressBar.classList.remove('bg-red-500');
                progressBar.classList.add('bg-gradient-to-r', 'from-primary-500', 'to-blue-500');
            }
        }, 3000);
    } finally {
        window._currentUploadXhr = null;
    }
}

/* ================================================
   Remove Selected File
   ================================================ */
function removeFile() {
    selectedFile = null;

    const fileInfo = document.getElementById('file-info');
    const fileInput = document.getElementById('file-input');

    if (fileInfo) fileInfo.classList.add('hidden');
    if (fileInput) fileInput.value = '';
}

/* ================================================
   Cancel Upload
   ================================================ */
function cancelUpload() {
    if (window._currentUploadXhr) {
        window._currentUploadXhr.abort();
        window._currentUploadXhr = null;
    }

    const progressSection = document.getElementById('upload-progress');
    const progressBar = document.getElementById('progress-bar');

    if (progressSection) progressSection.classList.add('hidden');
    if (progressBar) progressBar.style.width = '0%';
}

/* ================================================
   Load Datasets List
   ================================================ */
async function loadDatasets() {
    try {
        const resp = await apiGet('/datasets/');
        if (!resp.ok) return;
        const datasets = await resp.json();

        const emptyState = document.getElementById('datasets-empty');
        const tableWrapper = document.getElementById('datasets-table-wrapper');
        const tbody = document.getElementById('datasets-tbody');
        const countBadge = document.getElementById('dataset-count');

        if (countBadge) countBadge.textContent = `${datasets.length} dataset${datasets.length !== 1 ? 's' : ''}`;

        if (datasets.length === 0) {
            if (emptyState) emptyState.classList.remove('hidden');
            if (tableWrapper) tableWrapper.classList.add('hidden');
            return;
        }

        if (emptyState) emptyState.classList.add('hidden');
        if (tableWrapper) tableWrapper.classList.remove('hidden');

        if (tbody) {
            tbody.innerHTML = datasets.map(ds => `
                <tr class="border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors">
                    <td class="py-3.5 px-4">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 rounded-lg bg-primary-500/10 flex items-center justify-center flex-shrink-0">
                                <span class="text-xs font-bold text-primary-400">${(ds.file_type || 'csv').toUpperCase()}</span>
                            </div>
                            <span class="font-medium text-gray-200 truncate max-w-[200px]">${escapeHtml(ds.name)}</span>
                        </div>
                    </td>
                    <td class="py-3.5 px-4 text-gray-400">${formatFileSize(ds.file_size)}</td>
                    <td class="py-3.5 px-4 text-gray-400">${ds.row_count != null ? formatNumber(ds.row_count) : '--'}</td>
                    <td class="py-3.5 px-4 text-gray-400">${formatDate(ds.created_at)}</td>
                    <td class="py-3.5 px-4">
                        <span class="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-semibold rounded-full bg-emerald-500/10 text-emerald-400">${ds.status}</span>
                    </td>
                    <td class="py-3.5 px-4 text-right">
                        <div class="flex items-center justify-end gap-1">
                            <a href="/datasets/${ds.id}/profile" class="p-1.5 rounded-lg hover:bg-white/10 text-gray-500 hover:text-primary-400 transition-colors" title="Profile & Stats">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>
                            </a>
                            <a href="/datasets/${ds.id}/quality" class="p-1.5 rounded-lg hover:bg-white/10 text-gray-500 hover:text-primary-400 transition-colors" title="Data Quality">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/></svg>
                            </a>
                            <a href="/datasets/${ds.id}/preprocess" class="p-1.5 rounded-lg hover:bg-white/10 text-gray-500 hover:text-primary-400 transition-colors" title="Clean & Preprocess">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"/></svg>
                            </a>
                            <a href="/datasets/${ds.id}/eda" class="p-1.5 rounded-lg hover:bg-white/10 text-gray-500 hover:text-primary-400 transition-colors" title="Exploratory Data Analysis">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z"/></svg>
                            </a>
                            <a href="/datasets/${ds.id}/features" class="p-1.5 rounded-lg hover:bg-white/10 text-gray-500 hover:text-primary-400 transition-colors" title="Feature Engineering">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.663 17h4.673M12 3v1m6.364 .364l-.707 .707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548 .547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>
                            </a>
                            <a href="/experiments?dataset_id=${ds.id}" class="p-1.5 rounded-lg hover:bg-white/10 text-gray-500 hover:text-primary-400 transition-colors" title="Train Models (AutoML)">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5"/></svg>
                            </a>
                            <button onclick="previewDataset('${ds.id}')" class="p-1.5 rounded-lg hover:bg-white/10 text-gray-500 hover:text-primary-400 transition-colors" title="Preview">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>
                            </button>
                            <button onclick="deleteDataset('${ds.id}')" class="p-1.5 rounded-lg hover:bg-red-500/10 text-gray-500 hover:text-red-400 transition-colors" title="Delete">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
                            </button>
                        </div>
                    </td>
                </tr>
            `).join('');
        }

    } catch (err) {
        console.error('Failed to load datasets:', err);
    }
}

/* ================================================
   Preview Dataset
   ================================================ */
let _previewDatasetId = null;

async function previewDataset(datasetId) {
    _previewDatasetId = datasetId;
    const rowCountSelect = document.getElementById('preview-row-count');
    const rows = rowCountSelect ? parseInt(rowCountSelect.value) : 10;
    await _fetchAndRenderPreview(datasetId, rows);
}

function reloadPreview() {
    if (!_previewDatasetId) return;
    const rowCountSelect = document.getElementById('preview-row-count');
    const rows = rowCountSelect ? parseInt(rowCountSelect.value) : 10;
    _fetchAndRenderPreview(_previewDatasetId, rows);
}

async function _fetchAndRenderPreview(datasetId, rows) {
    const previewSection = document.getElementById('data-preview-section');
    const thead = document.getElementById('preview-thead');
    const tbody = document.getElementById('preview-tbody');
    const rowInfo = document.getElementById('preview-row-info');

    if (!previewSection || !thead || !tbody) return;

    try {
        const queryParam = rows > 0 ? `?rows=${rows}` : '?rows=100000';
        const resp = await apiGet(`/datasets/${datasetId}/preview${queryParam}`);
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            alert(err.detail || 'Failed to load preview');
            return;
        }

        const data = await resp.json();

        // Show row info
        if (rowInfo) {
            rowInfo.textContent = `(showing ${data.rows.length} of ${data.total_rows || data.rows.length} rows, ${data.columns.length} columns)`;
        }

        // Render headers
        thead.innerHTML = `
            <tr class="border-b border-white/[0.06]">
                ${data.columns.map(col => `
                    <th class="py-3 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">${escapeHtml(col)}</th>
                `).join('')}
            </tr>
        `;

        // Render rows
        tbody.innerHTML = data.rows.map(row => `
            <tr class="border-b border-white/[0.04] hover:bg-white/[0.02]">
                ${data.columns.map(col => `
                    <td class="py-2.5 px-4 text-xs text-gray-300 whitespace-nowrap max-w-[200px] truncate">${row[col] != null ? escapeHtml(row[col]) : '<span class="text-gray-600">null</span>'}</td>
                `).join('')}
            </tr>
        `).join('');

        // Show section
        previewSection.classList.remove('hidden');
        previewSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

    } catch (err) {
        console.error('Preview failed:', err);
    }
}

/* ================================================
   Delete Dataset
   ================================================ */
async function deleteDataset(datasetId) {
    if (!confirm('Are you sure you want to delete this dataset? This cannot be undone.')) return;

    try {
        const resp = await apiDelete(`/datasets/${datasetId}`);
        if (resp.ok || resp.status === 204) {
            loadDatasets(); // Refresh list
        } else {
            const err = await resp.json().catch(() => ({}));
            alert(err.detail || 'Failed to delete dataset');
        }
    } catch (err) {
        console.error('Delete failed:', err);
    }
}

/* ================================================
   Helpers
   ================================================ */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function showUploadError(message) {
    alert(message); // Simple — no complex toast needed
}
