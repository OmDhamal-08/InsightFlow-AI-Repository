/**
 * AI BI Platform — Dashboard JavaScript
 * Dashboard data loading and dynamic rendering.
 */

document.addEventListener('DOMContentLoaded', () => {
    // Only load dashboard data if we are authenticated
    if (getAccessToken() || sessionStorage.getItem('access_token')) {
        loadDashboardData();
    }
});

/* ================================================
   Load Dashboard Data
   ================================================ */
async function loadDashboardData() {
    console.log('Dashboard: loading data...');

    try {
        // 1. Load summary stats
        const statsResp = await apiGet('/dashboard/summary');
        if (statsResp.ok) {
            const stats = await statsResp.json();
            updateSummaryCards(stats);
        }

        // 2. Load recent datasets
        const datasetsResp = await apiGet('/dashboard/recent-datasets');
        if (datasetsResp.ok) {
            const datasets = await datasetsResp.json();
            renderRecentDatasets(datasets);
        }

        // 3. Load recent experiments
        const experimentsResp = await apiGet('/experiments/');
        if (experimentsResp.ok) {
            const experiments = await experimentsResp.json();
            renderRecentExperiments(experiments.slice(0, 5));
        }

        // 4. Load notifications
        const notificationsResp = await apiGet('/dashboard/notifications');
        if (notificationsResp.ok) {
            const notifications = await notificationsResp.json();
            renderNotifications(notifications);
        }

    } catch (error) {
        console.error('Failed to load dashboard data:', error);
    }
}

/* ================================================
   Update Summary Cards
   ================================================ */
function updateSummaryCards(stats) {
    const dsCount = document.getElementById('dashboard-datasets-count');
    const mdCount = document.getElementById('dashboard-models-count');
    const expCount = document.getElementById('dashboard-experiments-count');
    const qScore = document.getElementById('dashboard-quality-score');

    if (dsCount) dsCount.textContent = formatNumber(stats.datasets_count);
    if (mdCount) mdCount.textContent = formatNumber(stats.models_count);
    if (expCount) expCount.textContent = formatNumber(stats.experiments_count);
    if (qScore) {
        qScore.textContent = stats.data_quality_score !== null && stats.data_quality_score !== undefined
            ? `${formatNumber(stats.data_quality_score)}%`
            : '--';
    }
}

/* ================================================
   Render Recent Datasets
   ================================================ */
function renderRecentDatasets(datasets) {
    const container = document.getElementById('recent-datasets-container');
    if (!container) return;

    if (!datasets || datasets.length === 0) {
        // Leave the default empty state
        return;
    }

    // Build table of datasets (Will be implemented in Phase 4 when uploading actually saves items)
    let html = `
        <div class="overflow-x-auto">
            <table class="w-full text-left text-sm text-gray-300">
                <thead>
                    <tr class="border-b border-white/[0.06] text-xs font-semibold uppercase text-gray-500">
                        <th class="py-3 px-4">Name</th>
                        <th class="py-3 px-4">Size</th>
                        <th class="py-3 px-4">Rows</th>
                        <th class="py-3 px-4">Uploaded</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-white/[0.04]">
    `;

    datasets.forEach(ds => {
        html += `
            <tr class="hover:bg-white/[0.02] transition-colors">
                <td class="py-3.5 px-4 font-medium text-white">${escapeHtml(ds.name)}</td>
                <td class="py-3.5 px-4">${formatFileSize(ds.file_size)}</td>
                <td class="py-3.5 px-4">${formatNumber(ds.row_count)}</td>
                <td class="py-3.5 px-4">${formatDate(ds.created_at)}</td>
            </tr>
        `;
    });

    html += `
                </tbody>
            </table>
        </div>
    `;

    container.innerHTML = html;
}

/* ================================================
   Render Recent Reports
   ================================================ */
function renderRecentExperiments(experiments) {
    const container = document.getElementById('recent-experiments-container');
    if (!container || !experiments || experiments.length === 0) return;  // keep empty state

    const taskLabels = { binary_classification: 'Binary', multiclass_classification: 'Multiclass', regression: 'Regression' };
    container.innerHTML = `
        <div class="overflow-x-auto">
            <table class="w-full text-left text-sm text-gray-300">
                <thead>
                    <tr class="border-b border-white/[0.06] text-xs font-semibold uppercase text-gray-500">
                        <th class="py-3 px-4">Experiment</th>
                        <th class="py-3 px-4">Task</th>
                        <th class="py-3 px-4">Best model</th>
                        <th class="py-3 px-4">Test score</th>
                        <th class="py-3 px-4">Created</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-white/[0.04]">
                    ${experiments.map(e => `
                        <tr class="hover:bg-white/[0.02] transition-colors">
                            <td class="py-3.5 px-4 font-medium text-white"><a href="/experiments/${escapeHtml(e.id)}" class="hover:text-primary-300">${escapeHtml(e.name)}</a></td>
                            <td class="py-3.5 px-4">${escapeHtml(taskLabels[e.task_type] || e.task_type || '—')}</td>
                            <td class="py-3.5 px-4">${e.best_model_name ? '⭐ ' + escapeHtml(e.best_model_name) : '—'}</td>
                            <td class="py-3.5 px-4 font-mono">${e.best_score != null ? Number(e.best_score).toFixed(3) : '—'}</td>
                            <td class="py-3.5 px-4">${formatDate(e.created_at)}</td>
                        </tr>`).join('')}
                </tbody>
            </table>
        </div>`;
}

/* ================================================
   Render Notifications
   ================================================ */
function renderNotifications(notifications) {
    const container = document.getElementById('notifications-container');
    const badge = document.getElementById('notifications-count-badge');
    if (!container) return;

    if (!notifications || notifications.length === 0) {
        if (badge) badge.textContent = '0';
        return;
    }

    if (badge) badge.textContent = notifications.length;

    let html = `<div class="space-y-3">`;

    notifications.forEach(n => {
        html += `
            <div class="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.04] hover:bg-white/[0.04] transition-all">
                <div class="flex items-start justify-between gap-2">
                    <p class="text-xs font-semibold text-white">${escapeHtml(n.title)}</p>
                    <span class="text-[9px] text-gray-500">${formatDate(n.created_at)}</span>
                </div>
                <p class="mt-1 text-xs text-gray-400 leading-relaxed">${escapeHtml(n.message)}</p>
            </div>
        `;
    });

    html += `</div>`;
    container.innerHTML = html;
}

/**
 * Format file size helper.
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}
