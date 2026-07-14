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

        // 3. Load recent reports
        const reportsResp = await apiGet('/dashboard/recent-reports');
        if (reportsResp.ok) {
            const reports = await reportsResp.json();
            renderRecentReports(reports);
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
    const rpCount = document.getElementById('dashboard-reports-count');
    const qScore = document.getElementById('dashboard-quality-score');

    if (dsCount) dsCount.textContent = formatNumber(stats.datasets_count);
    if (mdCount) mdCount.textContent = formatNumber(stats.models_count);
    if (rpCount) rpCount.textContent = formatNumber(stats.reports_count);
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
                <td class="py-3.5 px-4 font-medium text-white">${ds.filename}</td>
                <td class="py-3.5 px-4">${formatFileSize(ds.size_bytes)}</td>
                <td class="py-3.5 px-4">${formatNumber(ds.rows_count)}</td>
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
function renderRecentReports(reports) {
    const container = document.getElementById('recent-reports-container');
    if (!container) return;

    if (!reports || reports.length === 0) {
        return;
    }

    // Render reports list (will be populated dynamically after Phase 16)
    let html = `
        <div class="space-y-3">
    `;

    reports.forEach(report => {
        html += `
            <div class="flex items-center justify-between p-3 rounded-xl bg-white/[0.02] hover:bg-white/[0.04] border border-white/[0.04] transition-all">
                <div class="flex items-center gap-3">
                    <span class="text-xl">📋</span>
                    <div>
                        <p class="text-sm font-medium text-white">${report.title}</p>
                        <p class="text-xs text-gray-500">${formatDate(report.created_at)}</p>
                    </div>
                </div>
                <a href="/reports/${report.id}/download" class="text-xs text-primary-400 hover:underline">Download</a>
            </div>
        `;
    });

    html += `</div>`;
    container.innerHTML = html;
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
                    <p class="text-xs font-semibold text-white">${n.title}</p>
                    <span class="text-[9px] text-gray-500">${formatDate(n.created_at)}</span>
                </div>
                <p class="mt-1 text-xs text-gray-400 leading-relaxed">${n.message}</p>
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
