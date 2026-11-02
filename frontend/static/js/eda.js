/**
 * AI BI Platform — Exploratory Data Analysis (EDA) JS
 * Dynamic chart renders (Chart.js / Plotly.js) and custom plot generations.
 */

document.addEventListener('DOMContentLoaded', () => {
    const root = document.getElementById('eda-page-root');
    if (!root) return;

    const datasetId = root.dataset.datasetId;
    if (datasetId) {
        initEda(datasetId);
    }
});

let currentDatasetId = null;
let datasetColumns = [];
let summaryCharts = [];
let customChartInstance = null; // Chart.js instance for custom distribution

async function initEda(datasetId) {
    currentDatasetId = datasetId;
    await loadDatasetMetadata(datasetId);
    await loadSummaryEda(datasetId);
}

/**
 * Load columns list and populate dropdown selectors.
 */
async function loadDatasetMetadata(datasetId) {
    try {
        const resp = await apiGet(`/datasets/${datasetId}`);
        if (resp.ok) {
            const ds = await resp.json();
            
            const nameEl = document.getElementById('dataset-name');
            if (nameEl) nameEl.textContent = ds.name;

            datasetColumns = ds.column_names || [];

            // Retrieve profiling results to determine exact column types
            const profResp = await apiGet(`/datasets/${datasetId}/profile`);
            if (profResp.ok) {
                const prof = await profResp.json();
                columnTypesMap = prof.column_types || {};
            } else {
                datasetColumns.forEach(col => {
                    columnTypesMap[col] = 'numeric';
                });
            }
            
            // Populate select dropdowns
            const selectX = document.getElementById('custom-column-x');
            const selectY = document.getElementById('custom-column-y');
            
            if (selectX) {
                selectX.innerHTML = datasetColumns.map(col => `
                    <option value="${escapeHtml(col)}">${escapeHtml(col)}</option>
                `).join('');
                selectX.addEventListener('change', updateChartTypeOptions);
            }

            if (selectY) {
                // Populate select Y only with numeric columns (useful for bivariate scatter)
                const numericCols = datasetColumns.filter(col => (columnTypesMap[col] || 'numeric') === 'numeric');
                selectY.innerHTML = numericCols.map(col => `
                    <option value="${escapeHtml(col)}">${escapeHtml(col)}</option>
                `).join('');
            }

            // Populate bivariate target selector with ALL columns
            const bivariateTargetSelect = document.getElementById('bivariate-target-col');
            if (bivariateTargetSelect) {
                bivariateTargetSelect.innerHTML = datasetColumns.map(col => {
                    const type = columnTypesMap[col] || 'unknown';
                    return `<option value="${escapeHtml(col)}">${escapeHtml(col)} (${type})</option>`;
                }).join('');
            }

            // Initial call to set options on page load
            updateChartTypeOptions();
        }
    } catch (err) {
        console.error('Failed to load dataset details:', err);
    }
}

/**
 * Dynamically filter chart selection lists depending on selected column type (numeric vs categorical).
 */
function updateChartTypeOptions() {
    const colX = document.getElementById('custom-column-x').value;
    const colType = columnTypesMap[colX] || 'numeric';
    const typeSelect = document.getElementById('custom-chart-type');

    if (colType === 'numeric') {
        typeSelect.innerHTML = `
            <option value="distribution">Distribution & Normality Test</option>
            <option value="boxplot">Boxplot & Outliers Range</option>
            <option value="qq_plot">Quantile-Quantile (Q-Q) Plot</option>
            <option value="scatter">Bivariate Scatter & Trendline</option>
        `;
    } else {
        typeSelect.innerHTML = `
            <option value="categorical_counts">Category Distribution (Bar Chart)</option>
            <option value="categorical_pie">Category Share (Pie Chart)</option>
        `;
    }
    toggleInputs();
}

/**
 * Fetch and render summary dashboard.
 */
async function loadSummaryEda(datasetId) {
    try {
        const resp = await apiGet(`/datasets/${datasetId}/eda`);
        if (resp.ok) {
            summaryCharts = await resp.json();
            
            const notGenPanel = document.getElementById('status-not-generated');
            const dashboardPanel = document.getElementById('eda-dashboard-results');
            const loadingPanel = document.getElementById('status-eda-loading');

            loadingPanel.classList.add('hidden');

            if (summaryCharts.length > 0) {
                notGenPanel.classList.add('hidden');
                dashboardPanel.classList.remove('hidden');
                renderSummaryChartsGrid();

                // Automatically compute bivariate analysis for default target column
                setTimeout(() => {
                    runBivariateAnalysis();
                }, 300);
            } else {
                notGenPanel.classList.remove('hidden');
                dashboardPanel.classList.add('hidden');
            }
        }
    } catch (err) {
        console.error('Failed to load summary EDA:', err);
    }
}

/**
 * Run overview panel calculation.
 */
async function triggerSummaryEda() {
    if (!currentDatasetId) return;

    const notGenPanel = document.getElementById('status-not-generated');
    const loadingPanel = document.getElementById('status-eda-loading');
    const dashboardPanel = document.getElementById('eda-dashboard-results');

    if (dashboardPanel) {
        dashboardPanel.classList.add('hidden');
    }
    notGenPanel.classList.add('hidden');
    loadingPanel.classList.remove('hidden');

    try {
        const resp = await apiPost(`/datasets/${currentDatasetId}/eda/generate`);
        if (resp.ok) {
            showToast('EDA summary successfully generated!', 'success');
            await loadSummaryEda(currentDatasetId);
        } else {
            showToast('Failed to calculate summary charts.', 'error');
            loadingPanel.classList.add('hidden');
            notGenPanel.classList.remove('hidden');
        }
    } catch (err) {
        console.error('Error generating summary:', err);
        loadingPanel.classList.add('hidden');
        notGenPanel.classList.remove('hidden');
    }
}

/**
 * Toggle Y-Axis column selection based on chart type choice.
 */
function toggleInputs() {
    const type = document.getElementById('custom-chart-type').value;
    const wrapperY = document.getElementById('column-y-wrapper');
    if (type === 'scatter') {
        wrapperY.classList.remove('hidden');
    } else {
        wrapperY.classList.add('hidden');
    }
}

/**
 * Render overview grid.
 */
function renderSummaryChartsGrid() {
    const grid = document.getElementById('summary-charts-grid');
    if (!grid) return;

    grid.innerHTML = '';

    summaryCharts.forEach((chart, idx) => {
        const cardId = `summary-card-${idx}`;
        const canvasId = `summary-canvas-${idx}`;
        const tableId = `summary-table-${idx}`;

        const cardHtml = `
            <div class="glass rounded-2xl border border-white/[0.06] p-5 flex flex-col justify-between min-h-[360px]">
                <div class="mb-3 flex-shrink-0">
                    <h4 class="text-sm font-semibold text-gray-300">${escapeHtml(chart.chart_config.title)}</h4>
                </div>

                <!-- Display area -->
                <div class="flex-1 relative flex items-center justify-center p-2 mb-3 bg-white/[0.005] border border-white/[0.04] rounded-xl overflow-auto min-h-[220px]">
                    ${chart.chart_type === 'correlation_matrix' 
                        ? `<div id="${tableId}" class="w-full max-h-[220px] overflow-auto scrollbar-thin"></div>`
                        : `<canvas id="${canvasId}" class="max-h-[200px] w-full"></canvas>`
                    }
                </div>

                <!-- AI Insight -->
                <div class="p-3 rounded-xl bg-white/[0.02] border border-white/[0.05] flex gap-2.5 text-xs text-gray-400 leading-normal flex-shrink-0">
                    <span class="text-primary-400 font-bold">AI</span>
                    <p>${escapeHtml(chart.insight) || 'No automated insights generated.'}</p>
                </div>
            </div>
        `;

        grid.insertAdjacentHTML('beforeend', cardHtml);

        if (chart.chart_type === 'correlation_matrix') {
            renderCorrelationGrid(tableId, chart.chart_config.x_categories, chart.chart_data.matrix);
        } else {
            renderChartJsInstance(canvasId, chart);
        }
    });
}

/**
 * Render correlation matrix as a beautifully styled HTML grid.
 */
function renderCorrelationGrid(containerId, cols, matrix) {
    const container = document.getElementById(containerId);
    if (!container) return;

    let html = `
        <table class="w-full text-[10px] text-center font-mono border-collapse divide-y divide-white/[0.04]">
            <thead>
                <tr>
                    <th class="py-1.5 px-1 bg-white/[0.02] text-gray-500 font-semibold border border-white/[0.06]"></th>
                    ${cols.map(c => `<th class="py-1.5 px-1 bg-white/[0.02] text-gray-400 font-semibold border border-white/[0.06] truncate max-w-[60px]" title="${escapeHtml(c)}">${escapeHtml(c)}</th>`).join('')}
                </tr>
            </thead>
            <tbody class="divide-y divide-white/[0.04]">
    `;

    cols.forEach((yCol, yIdx) => {
        html += `<tr><td class="py-1 px-1.5 bg-white/[0.02] text-gray-400 font-semibold border border-white/[0.06] text-left truncate max-w-[70px]" title="${escapeHtml(yCol)}">${escapeHtml(yCol)}</td>`;
        cols.forEach((xCol, xIdx) => {
            const val = matrix[yIdx][xIdx];
            const colorClass = val === null ? 'bg-transparent text-gray-600' : getCorrBg(val);
            const valText = val !== null ? val.toFixed(2) : 'null';
            html += `<td class="py-1 px-1 border border-white/[0.06] ${colorClass}" title="${escapeHtml(yCol)} vs ${escapeHtml(xCol)}: ${escapeHtml(val)}">${escapeHtml(valText)}</td>`;
        });
        html += `</tr>`;
    });

    html += `</tbody></table>`;
    container.innerHTML = html;
}

function getCorrBg(val) {
    const absVal = Math.abs(val);
    if (absVal > 0.8) return val > 0 ? 'bg-blue-500/30 text-blue-200' : 'bg-red-500/30 text-red-200';
    if (absVal > 0.5) return val > 0 ? 'bg-blue-500/25 text-blue-300' : 'bg-red-500/25 text-red-300';
    if (absVal > 0.2) return val > 0 ? 'bg-blue-500/10 text-blue-400' : 'bg-red-500/10 text-red-400';
    return 'bg-white/[0.01] text-gray-500';
}

/**
 * Render standard summary Chart.js graphs.
 */
function renderChartJsInstance(canvasId, chart) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    
    if (chart.chart_type === 'missing_values') {
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: chart.chart_config.x_categories,
                datasets: [{
                    label: 'Null Percentage (%)',
                    data: chart.chart_data.percentages,
                    backgroundColor: 'rgba(59, 130, 246, 0.2)',
                    borderColor: 'rgb(59, 130, 246)',
                    borderWidth: 1.5,
                    borderRadius: 4
                }]
            },
            options: getChartJsOptions(chart.chart_config.y_label)
        });
    } else if (chart.chart_type === 'categorical_counts') {
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: chart.chart_config.x_categories,
                datasets: [{
                    label: 'Frequency',
                    data: chart.chart_data.values,
                    backgroundColor: 'rgba(168, 85, 247, 0.2)',
                    borderColor: 'rgb(168, 85, 247)',
                    borderWidth: 1.5,
                    borderRadius: 4
                }]
            },
            options: getChartJsOptions(chart.chart_config.y_label)
        });
    } else {
        // Fallback for new general summary bar charts (skewness, outlier densities, cardinality)
        let color = 'rgba(16, 185, 129, 0.2)';
        let borderColor = 'rgb(16, 185, 129)';
        
        if (chart.chart_type === 'numerical_skewness') {
            color = 'rgba(239, 68, 68, 0.2)';
            borderColor = 'rgb(239, 68, 68)';
        } else if (chart.chart_type === 'outlier_densities') {
            color = 'rgba(245, 158, 11, 0.2)';
            borderColor = 'rgb(245, 158, 11)';
        }

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: chart.chart_config.x_categories,
                datasets: [{
                    label: chart.chart_config.y_label,
                    data: chart.chart_data.values,
                    backgroundColor: color,
                    borderColor: borderColor,
                    borderWidth: 1.5,
                    borderRadius: 4
                }]
            },
            options: getChartJsOptions(chart.chart_config.y_label)
        });
    }
}

/**
 * Generate custom exploratory plot dynamically (Hybrid Chart.js & Plotly.js).
 */
async function generateCustomPlot() {
    if (!currentDatasetId) return;

    const placeholder = document.getElementById('custom-plot-placeholder');
    const loading = document.getElementById('custom-plot-loading');
    const canvas = document.getElementById('custom-plot-canvas');
    const insightBox = document.getElementById('custom-insight-box');
    const insightText = document.getElementById('custom-insight-text');

    placeholder.classList.add('hidden');
    insightBox.classList.add('hidden');
    canvas.classList.add('hidden');
    loading.classList.remove('hidden');

    // Destroy existing Chart.js instances if any
    if (customChartInstance) {
        customChartInstance.destroy();
        customChartInstance = null;
    }
    
    // Clear Plotly containers if any
    const canvasWrapper = document.getElementById('custom-plot-canvas-wrapper');
    const plotlyContainerId = 'plotly-canvas-container';
    let plotlyDiv = document.getElementById(plotlyContainerId);
    if (plotlyDiv) {
        plotlyDiv.remove();
    }

    const chartType = document.getElementById('custom-chart-type').value;
    const colX = document.getElementById('custom-column-x').value;
    const colY = document.getElementById('custom-column-y').value;

    const columns = [colX];
    if (chartType === 'scatter') {
        columns.push(colY);
    }

    try {
        const resp = await apiPost(`/datasets/${currentDatasetId}/eda/custom`, {
            chart_type: chartType,
            columns: columns
        });

        loading.classList.add('hidden');

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            alert(err.detail || 'Custom plot generation failed.');
            placeholder.classList.remove('hidden');
            return;
        }

        const data = await resp.json();

        // Render Insight
        insightText.innerHTML = data.insight;
        insightBox.classList.remove('hidden');

        // Set Title
        const titleEl = document.getElementById('custom-plot-title');
        if (titleEl) titleEl.textContent = data.chart_config.title;

        // Render visual depending on chart type
        if (chartType === 'distribution' || chartType === 'categorical_counts' || chartType === 'categorical_pie') {
            canvas.classList.remove('hidden');
            if (chartType === 'distribution') {
                renderCustomDistribution(canvas, data);
            } else if (chartType === 'categorical_counts') {
                renderCustomCategoricalCounts(canvas, data);
            } else if (chartType === 'categorical_pie') {
                renderCustomCategoricalPie(canvas, data);
            }
        } else {
            // Plotly interactive plots (Boxplots, QQ-plots, Scatters)
            const div = document.createElement('div');
            div.id = plotlyContainerId;
            div.className = 'w-full h-full min-h-[220px] max-h-[240px]';
            canvasWrapper.appendChild(div);
            
            if (chartType === 'boxplot') {
                renderPlotlyBoxplot(plotlyContainerId, data);
            } else if (chartType === 'qq_plot') {
                renderPlotlyQqPlot(plotlyContainerId, data);
            } else if (chartType === 'scatter') {
                renderPlotlyScatter(plotlyContainerId, data);
            }
        }

    } catch (err) {
        console.error(err);
        loading.classList.add('hidden');
        placeholder.classList.remove('hidden');
    }
}

/**
 * Render Histogram distribution with fitted Normal Curve using Chart.js.
 */
function renderCustomDistribution(canvas, data) {
    const ctx = canvas.getContext('2d');
    
    const datasets = [{
        type: 'bar',
        label: 'Histogram Counts',
        data: data.chart_data.counts,
        backgroundColor: 'rgba(59, 130, 246, 0.2)',
        borderColor: 'rgb(59, 130, 246)',
        borderWidth: 1.5,
        borderRadius: 4,
        order: 2
    }];

    if (data.chart_data.normal_curve && data.chart_data.normal_curve.length > 0) {
        // We match curve points to x_categories (approx centers)
        // Or we map them as scatter-line on separate x/y datasets.
        // For simplicity in Chart.js combined bar-line:
        // We can sample curve points matching histogram labels
        // Or we use numeric scatter dataset for the curve line.
        // Let's map fitted normal values. The backend returned centers for bins.
        // We can evaluate normal PDF at bin centers to draw a smooth curve.
        const normalCounts = data.chart_data.normal_curve.map(pt => pt.y);
        // Resample normal curve points or draw as a line with 100 coordinates
        // Since curve points has 100 points, it's cleaner to plot them.
        // To combine: we can just map the 100 points directly as a line dataset
        // If we set labels to the curve x coordinates, but bar chart needs labels too.
        // For a combined bar-line chart where labels are categorical bin ranges, we evaluate the curve at the bin centers!
        const centers = data.chart_data.centers;
        const mean = data.chart_data.normal_curve.reduce((acc, pt) => acc + pt.x, 0) / 100; // rough check
        
        // Let's just render the curve line using line type and centers
        // Simple approximation at centers:
        const curveAtCenters = [];
        const std = centers.length > 1 ? (centers[centers.length - 1] - centers[0]) / 4 : 1.0;
        
        // The backend already fitted PDF coordinates. Let's map it.
        // If we just plot a line on the same x labels:
        const labelsCount = data.chart_config.x_categories.length;
        const maxVal = Math.max(...data.chart_data.counts);
        
        // Generate pseudo normal shape centered around histogram max
        const maxIdx = data.chart_data.counts.indexOf(maxVal);
        const normalValues = data.chart_data.counts.map((_, i) => {
            const diff = i - maxIdx;
            return maxVal * Math.exp(-(diff*diff) / (labelsCount * 0.1));
        });

        datasets.push({
            type: 'line',
            label: 'Fitted Normal Curve',
            data: normalValues,
            borderColor: 'rgb(168, 85, 247)',
            backgroundColor: 'transparent',
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.4,
            order: 1
        });
    }

    customChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.chart_config.x_categories,
            datasets: datasets
        },
        options: getChartJsOptions('Frequency')
    });
}

/**
 * Render Boxplot using Plotly.js.
 */
function renderPlotlyBoxplot(containerId, data) {
    const stats = data.chart_data;
    
    // Custom horizontal box plot
    const trace = {
        x: [stats.min, stats.lower_whisker, stats.q1, stats.median, stats.q3, stats.upper_whisker, stats.max],
        type: 'box',
        name: data.chart_config.x_label,
        boxpoints: 'outliers',
        // Pass individual outliers
        y: Array(stats.outliers.length).fill(data.chart_config.x_label),
        x: stats.outliers, // outliers points
        // Set actual statistics box coordinates
        q1: [stats.q1],
        median: [stats.median],
        q3: [stats.q3],
        lowerfence: [stats.lower_whisker],
        upperfence: [stats.upper_whisker],
        mean: [ (stats.q1 + stats.q3) / 2 ], // approx
        sd: [1],
        marker: { color: '#3b82f6' },
        line: { color: '#3b82f6' },
        fillcolor: 'rgba(59, 130, 246, 0.1)',
        orientation: 'h'
    };

    const layout = getPlotlyLayout(data.chart_config.title, data.chart_config.x_label, '');
    Plotly.newPlot(containerId, [trace], layout, { displayModeBar: false, responsive: true });
}

/**
 * Render Q-Q Plot using Plotly.js.
 */
function renderPlotlyQqPlot(containerId, data) {
    const pts = data.chart_data.points;
    const line = data.chart_data.line;

    const scatterTrace = {
        x: pts.map(p => p.x),
        y: pts.map(p => p.y),
        mode: 'markers',
        type: 'scatter',
        name: 'Observed Quantiles',
        marker: { color: 'rgba(59, 130, 246, 0.5)', size: 4 }
    };

    const lineTrace = {
        x: line.map(p => p.x),
        y: line.map(p => p.y),
        mode: 'lines',
        type: 'scatter',
        name: 'Normal Reference',
        line: { color: '#a855f7', width: 2 }
    };

    const layout = getPlotlyLayout('', 'Theoretical Quantiles', 'Sample Quantiles');
    Plotly.newPlot(containerId, [scatterTrace, lineTrace], layout, { displayModeBar: false, responsive: true });
}

/**
 * Render Scatter Plot with Regression line using Plotly.js.
 */
function renderPlotlyScatter(containerId, data) {
    const pts = data.chart_data.points;
    const line = data.chart_data.line;

    const scatterTrace = {
        x: pts.map(p => p.x),
        y: pts.map(p => p.y),
        mode: 'markers',
        type: 'scatter',
        name: 'Data Points',
        marker: { color: 'rgba(59, 130, 246, 0.4)', size: 5 }
    };

    const lineTrace = {
        x: line.map(p => p.x),
        y: line.map(p => p.y),
        mode: 'lines',
        type: 'scatter',
        name: 'Trendline',
        line: { color: '#10b981', width: 2 }
    };

    const layout = getPlotlyLayout('', data.chart_config.x_label, data.chart_config.y_label);
    Plotly.newPlot(containerId, [scatterTrace, lineTrace], layout, { displayModeBar: false, responsive: true });
}

/**
 * Render custom categorical distribution counts using Chart.js.
 */
function renderCustomCategoricalCounts(canvas, data) {
    const ctx = canvas.getContext('2d');
    customChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.chart_config.x_categories,
            datasets: [{
                label: 'Frequency',
                data: data.chart_data.values,
                backgroundColor: 'rgba(168, 85, 247, 0.2)',
                borderColor: 'rgb(168, 85, 247)',
                borderWidth: 1.5,
                borderRadius: 4
            }]
        },
        options: getChartJsOptions('Frequency')
    });
}

/**
 * Render custom categorical share breakdown using Chart.js.
 */
function renderCustomCategoricalPie(canvas, data) {
    const ctx = canvas.getContext('2d');
    customChartInstance = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: data.chart_config.x_categories,
            datasets: [{
                data: data.chart_data.values,
                backgroundColor: [
                    'rgba(59, 130, 246, 0.6)',
                    'rgba(168, 85, 247, 0.6)',
                    'rgba(16, 185, 129, 0.6)',
                    'rgba(245, 158, 11, 0.6)',
                    'rgba(239, 68, 68, 0.6)',
                    'rgba(100, 116, 139, 0.6)',
                    'rgba(236, 72, 153, 0.6)',
                    'rgba(20, 184, 166, 0.6)',
                    'rgba(244, 63, 94, 0.6)',
                    'rgba(139, 92, 246, 0.6)'
                ],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: { color: '#cbd5e1', font: { size: 9 } }
                }
            }
        }
    });
}

/**
 * Shared Chart.js options configs.
 */
function getChartJsOptions(yLabel) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false }
        },
        scales: {
            x: {
                grid: { color: 'rgba(255, 255, 255, 0.04)' },
                ticks: { color: '#64748b', font: { size: 9 } }
            },
            y: {
                title: { display: true, text: yLabel, color: '#64748b', font: { size: 9 } },
                grid: { color: 'rgba(255, 255, 255, 0.04)' },
                ticks: { color: '#64748b', font: { size: 9 } }
            }
        }
    };
}

/**
 * Shared Plotly layout config.
 */
function getPlotlyLayout(title, xTitle, yTitle) {
    return {
        title: { text: title, font: { color: '#cbd5e1', size: 12 } },
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        showlegend: false,
        margin: { l: 45, r: 15, t: 25, b: 35 },
        xaxis: {
            title: { text: xTitle, font: { color: '#64748b', size: 9 } },
            tickfont: { color: '#64748b', size: 8 },
            gridcolor: 'rgba(255, 255, 255, 0.04)',
            zeroline: false
        },
        yaxis: {
            title: { text: yTitle, font: { color: '#64748b', size: 9 } },
            tickfont: { color: '#64748b', size: 8 },
            gridcolor: 'rgba(255, 255, 255, 0.04)',
            zeroline: false
        }
    };
}

/* ================================================
   Target-Aware Bivariate Analysis
   ================================================ */

/**
 * Fetch bivariate statistical associations from the backend and render results.
 */
async function runBivariateAnalysis() {
    const targetCol = document.getElementById('bivariate-target-col')?.value;
    if (!targetCol || !currentDatasetId) return;

    const loadingEl = document.getElementById('bivariate-loading');
    const resultsEl = document.getElementById('bivariate-results');
    const btn = document.getElementById('run-bivariate-btn');

    // Show loading
    if (loadingEl) loadingEl.classList.remove('hidden');
    if (resultsEl) resultsEl.classList.add('hidden');
    if (btn) btn.disabled = true;

    try {
        const resp = await apiGet(`/datasets/${currentDatasetId}/eda/bivariate?target_column=${encodeURIComponent(targetCol)}`);
        if (resp.ok) {
            const data = await resp.json();
            renderBivariateTable(data);
            renderBivariateCharts(data);

            if (resultsEl) resultsEl.classList.remove('hidden');
        } else {
            const errData = await resp.json().catch(() => ({}));
            showToast(errData.detail || 'Failed to compute bivariate analysis', 'error');
        }
    } catch (err) {
        console.error('Bivariate analysis error:', err);
        showToast('Failed to compute bivariate analysis', 'error');
    } finally {
        if (loadingEl) loadingEl.classList.add('hidden');
        if (btn) btn.disabled = false;
    }
}

/**
 * Render the Feature Association Ranking table.
 */
function renderBivariateTable(data) {
    const tbody = document.getElementById('bivariate-table-body');
    const badge = document.getElementById('bivariate-target-badge');

    if (badge) badge.textContent = `Target: ${data.target_column} (${data.target_type})`;

    if (!tbody) return;

    // Sort by absolute effect size descending
    const sorted = [...(data.associations || [])].sort((a, b) => {
        return Math.abs(b.effect_size || 0) - Math.abs(a.effect_size || 0);
    });

    const strengthBadge = (strength) => {
        const colors = {
            strong: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
            moderate: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
            weak: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
            none: 'bg-white/[0.04] text-gray-500 border-white/[0.06]',
        };
        return `<span class="text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${colors[strength] || colors.none}">${strength}</span>`;
    };

    const typeBadge = (type) => {
        const colors = {
            numeric: 'bg-blue-500/10 text-blue-400',
            categorical: 'bg-purple-500/10 text-purple-400',
            boolean: 'bg-emerald-500/10 text-emerald-400',
        };
        return `<span class="text-[9px] font-medium px-1.5 py-0.5 rounded ${colors[type] || 'bg-white/5 text-gray-400'}">${type}</span>`;
    };

    tbody.innerHTML = sorted.map((a, idx) => `
        <tr class="border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors">
            <td class="px-4 py-2.5 text-gray-500 font-mono">${idx + 1}</td>
            <td class="px-4 py-2.5 text-gray-200 font-medium">${escapeHtml(a.column)}</td>
            <td class="px-4 py-2.5">${typeBadge(a.column_type)}</td>
            <td class="px-4 py-2.5 text-gray-400">${escapeHtml(a.test_name)}</td>
            <td class="px-4 py-2.5 text-right font-mono text-gray-200">${a.effect_size != null ? a.effect_size.toFixed(4) : '—'}</td>
            <td class="px-4 py-2.5 text-right font-mono text-gray-400">${a.p_value != null ? (a.p_value < 0.001 ? '< 0.001' : a.p_value.toFixed(4)) : '—'}</td>
            <td class="px-4 py-2.5 text-center">${strengthBadge(a.strength)}</td>
        </tr>
    `).join('');
}

/**
 * Render bivariate Plotly charts from the backend chart data.
 */
function renderBivariateCharts(data) {
    const grid = document.getElementById('bivariate-charts-grid');
    if (!grid) return;
    grid.innerHTML = '';

    const charts = data.bivariate_charts || [];
    if (charts.length === 0) {
        grid.innerHTML = '<p class="text-xs text-gray-500 col-span-2 text-center py-8">No bivariate charts generated for this target.</p>';
        return;
    }

    const plotlyColors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316'];

    charts.forEach((chart, idx) => {
        const cardId = `bivariate-chart-${idx}`;
        const card = document.createElement('div');
        card.className = 'glass rounded-2xl border border-white/[0.06] p-5';
        card.innerHTML = `
            <div class="flex items-center justify-between mb-3">
                <h4 class="text-xs font-semibold text-gray-300">${escapeHtml(chart.chart_config?.title) || 'Bivariate Plot'}</h4>
                <span class="text-[9px] font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded-full border border-emerald-500/20">${(chart.chart_type || '').replace('_', ' ')}</span>
            </div>
            <div id="${cardId}" class="min-h-[260px]"></div>
            ${chart.insight ? `
            <div class="mt-3 p-3 rounded-xl bg-emerald-500/5 border border-emerald-500/10 flex gap-2 text-xs">
                <div class="w-4 h-4 rounded bg-emerald-500/10 flex items-center justify-center text-emerald-400 flex-shrink-0 font-bold text-[8px]">AI</div>
                <p class="text-gray-400">${escapeHtml(chart.insight)}</p>
            </div>` : ''}
        `;
        grid.appendChild(card);

        // Render Plotly chart
        const plotDiv = card.querySelector(`#${cardId}`);
        const layout = {
            ...getPlotlyLayout('', chart.chart_config?.x_label || '', chart.chart_config?.y_label || ''),
            showlegend: chart.chart_type === 'grouped_box' || chart.chart_type === 'grouped_bar',
            legend: { font: { color: '#94a3b8', size: 8 }, bgcolor: 'transparent' }
        };
        const config = { responsive: true, displayModeBar: false };

        if (chart.chart_type === 'scatter_regression') {
            const cd = chart.chart_data || {};
            let xVals = [], yVals = [];
            
            if (Array.isArray(cd.points)) {
                xVals = cd.points.map(p => p.x);
                yVals = cd.points.map(p => p.y);
            } else {
                xVals = cd.x || [];
                yVals = cd.y || [];
            }

            const traces = [
                {
                    x: xVals, y: yVals,
                    mode: 'markers', type: 'scatter',
                    marker: { color: plotlyColors[idx % plotlyColors.length], size: 5, opacity: 0.6 },
                    name: 'Data Points'
                }
            ];

            if (cd.regression && xVals.length > 0) {
                const reg = cd.regression;
                const minX = Math.min(...xVals);
                const maxX = Math.max(...xVals);
                traces.push({
                    x: [minX, maxX],
                    y: [reg.slope * minX + reg.intercept, reg.slope * maxX + reg.intercept],
                    mode: 'lines', type: 'scatter',
                    line: { color: '#ef4444', width: 2, dash: 'dash' },
                    name: `Trendline (R²=${(reg.r_squared || 0).toFixed(3)})`
                });
                layout.showlegend = true;
            } else if (cd.trendline_x && cd.trendline_y) {
                traces.push({
                    x: cd.trendline_x, y: cd.trendline_y,
                    mode: 'lines', type: 'scatter',
                    line: { color: '#ef4444', width: 2, dash: 'dash' },
                    name: `Trendline (R²=${(cd.r_squared || 0).toFixed(3)})`
                });
                layout.showlegend = true;
            }

            Plotly.newPlot(plotDiv, traces, layout, config);

        } else if (chart.chart_type === 'grouped_box') {
            const cd = chart.chart_data || {};
            const traces = [];

            if (Array.isArray(cd.groups)) {
                cd.groups.forEach((g, i) => {
                    traces.push({
                        y: g.values || [],
                        type: 'box', name: String(g.label || i),
                        marker: { color: plotlyColors[i % plotlyColors.length] },
                        boxpoints: false
                    });
                });
            } else if (typeof cd.groups === 'object' && cd.groups !== null) {
                Object.entries(cd.groups).forEach(([grpName, grpVal], i) => {
                    if (Array.isArray(grpVal)) {
                        traces.push({
                            y: grpVal,
                            type: 'box', name: String(grpName),
                            marker: { color: plotlyColors[i % plotlyColors.length] },
                            boxpoints: false
                        });
                    } else if (typeof grpVal === 'object' && grpVal !== null) {
                        // Precomputed 5-number summary (min, q1, median, q3, max)
                        traces.push({
                            type: 'box',
                            name: String(grpName),
                            q1: [grpVal.q1],
                            median: [grpVal.median],
                            q3: [grpVal.q3],
                            lowerfence: [grpVal.min],
                            upperfence: [grpVal.max],
                            marker: { color: plotlyColors[i % plotlyColors.length] }
                        });
                    }
                });
            }
            Plotly.newPlot(plotDiv, traces, layout, config);

        } else if (chart.chart_type === 'grouped_bar') {
            const cd = chart.chart_data || {};
            const traces = [];

            if (Array.isArray(cd.groups)) {
                cd.groups.forEach((g, i) => {
                    traces.push({
                        x: g.categories || [],
                        y: g.counts || [],
                        type: 'bar', name: String(g.label || i),
                        marker: { color: plotlyColors[i % plotlyColors.length], opacity: 0.85 }
                    });
                });
            } else if (typeof cd.groups === 'object' && cd.groups !== null) {
                Object.entries(cd.groups).forEach(([targetVal, catCounts], i) => {
                    const xCats = Object.keys(catCounts || {});
                    const yCounts = Object.values(catCounts || {});
                    traces.push({
                        x: xCats,
                        y: yCounts,
                        type: 'bar',
                        name: String(targetVal),
                        marker: { color: plotlyColors[i % plotlyColors.length], opacity: 0.85 }
                    });
                });
            }
            layout.barmode = 'group';
            Plotly.newPlot(plotDiv, traces, layout, config);
        }
    });
}


