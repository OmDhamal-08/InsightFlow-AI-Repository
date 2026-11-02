/**
 * AI BI Platform — Shared Utility Functions
 * Pure utility functions used across the platform.
 */

/* ================================================
   HTML Escaping
   ================================================ */

/**
 * Escape a value for safe insertion into HTML text or attribute context.
 * Use this for anything that came from a user or from an uploaded file:
 * dataset names, column headers, CSV cell values, server error messages.
 * @param {*} value - Any value; null/undefined become an empty string
 * @returns {string} HTML-escaped string
 */
function escapeHtml(value) {
    if (value === null || value === undefined) return '';
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

/* ================================================
   Date Formatting
   ================================================ */

/**
 * Format an ISO date string to a human-readable format.
 * @param {string} dateStr - ISO 8601 date string
 * @returns {string} Formatted date (e.g., "Jul 12, 2026")
 */
function formatDate(dateStr) {
    if (!dateStr) return '--';
    try {
        const date = new Date(dateStr);
        if (isNaN(date.getTime())) return '--';
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
        });
    } catch {
        return '--';
    }
}

/**
 * Format an ISO date string to include time.
 * @param {string} dateStr
 * @returns {string} (e.g., "Jul 12, 2026 at 3:45 PM")
 */
function formatDateTime(dateStr) {
    if (!dateStr) return '--';
    try {
        const date = new Date(dateStr);
        if (isNaN(date.getTime())) return '--';
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
        });
    } catch {
        return '--';
    }
}

/* ================================================
   Number Formatting
   ================================================ */

/**
 * Format a number with comma separators.
 * @param {number} num
 * @returns {string} (e.g., "1,234,567")
 */
function formatNumber(num) {
    if (num === null || num === undefined || isNaN(num)) return '--';
    return Number(num).toLocaleString('en-US');
}

/**
 * Convert bytes to human-readable file size.
 * @param {number} bytes
 * @returns {string} (e.g., "4.2 MB")
 */
function formatFileSize(bytes) {
    if (!bytes || bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/* ================================================
   String Utilities
   ================================================ */

/**
 * Truncate text with ellipsis.
 * @param {string} text
 * @param {number} maxLength
 * @returns {string}
 */
function truncateText(text, maxLength = 50) {
    if (!text) return '';
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength).trim() + '…';
}

/* ================================================
   Function Utilities
   ================================================ */

/**
 * Debounce a function.
 * @param {Function} fn - Function to debounce
 * @param {number} delay - Delay in milliseconds
 * @returns {Function} Debounced function
 */
function debounce(fn, delay = 300) {
    let timeoutId;
    return function (...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => fn.apply(this, args), delay);
    };
}

/* ================================================
   Toast Notification
   ================================================ */

/**
 * Show a toast notification.
 * @param {string} message - Toast message
 * @param {string} type - 'success' | 'error' | 'warning' | 'info'
 * @param {number} duration - Duration in ms (default 4000)
 */
function showToast(message, type = 'info', duration = 4000) {
    // Create toast container if it doesn't exist
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'fixed bottom-6 right-6 z-[200] flex flex-col gap-2 items-end';
        document.body.appendChild(container);
    }

    // Color config
    const colors = {
        success: { bg: 'bg-emerald-500/15', border: 'border-emerald-500/30', text: 'text-emerald-400', icon: '✓' },
        error:   { bg: 'bg-red-500/15',     border: 'border-red-500/30',     text: 'text-red-400',     icon: '✕' },
        warning: { bg: 'bg-amber-500/15',   border: 'border-amber-500/30',   text: 'text-amber-400',   icon: '⚠' },
        info:    { bg: 'bg-blue-500/15',    border: 'border-blue-500/30',    text: 'text-blue-400',    icon: 'ℹ' },
    };

    const config = colors[type] || colors.info;

    // Create toast element
    const toast = document.createElement('div');
    toast.className = `flex items-center gap-3 px-4 py-3 rounded-xl border ${config.bg} ${config.border} backdrop-blur-lg shadow-2xl shadow-black/30 max-w-sm animate-slide-up`;
    toast.innerHTML = `
        <span class="flex-shrink-0 w-6 h-6 rounded-lg flex items-center justify-center text-xs font-bold ${config.text}" style="background: currentColor; -webkit-background-clip: unset;">
            <span style="color: white; -webkit-text-fill-color: white;">${config.icon}</span>
        </span>
        <p class="text-sm ${config.text} flex-1">${escapeHtml(message)}</p>
        <button onclick="this.parentElement.remove()" class="flex-shrink-0 p-0.5 rounded hover:bg-white/10 transition-colors">
            <svg class="w-3.5 h-3.5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
        </button>
    `;

    container.appendChild(toast);

    // Auto-remove after duration
    setTimeout(() => {
        toast.style.animation = 'fadeOut 0.3s ease-out forwards';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}
