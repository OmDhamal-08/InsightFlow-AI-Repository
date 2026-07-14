/**
 * AI BI Platform — Main JavaScript
 * Global event listeners, sidebar toggle, dropdown, page transitions, and authentication check/hydration.
 */

document.addEventListener('DOMContentLoaded', async () => {
    // ---- Initialize Theme ----
    initTheme();

    // ---- Page fade-in transition ----
    document.body.classList.add('page-enter');

    // ---- Click-outside handler for dropdowns ----
    document.addEventListener('click', (e) => {
        // Close user dropdown if clicking outside
        const dropdownContainer = document.getElementById('user-dropdown-container');
        const dropdown = document.getElementById('user-dropdown');
        if (dropdownContainer && dropdown && !dropdownContainer.contains(e.target)) {
            dropdown.classList.add('hidden');
            const arrow = document.getElementById('dropdown-arrow');
            if (arrow) arrow.style.transform = 'rotate(0deg)';
        }

        // Close notification dropdown if clicking outside
        const notifContainer = document.getElementById('nav-notification-container');
        const notifDropdown = document.getElementById('nav-notification-dropdown');
        if (notifContainer && notifDropdown && !notifContainer.contains(e.target)) {
            notifDropdown.classList.add('hidden');
        }

        // Close search dropdown if clicking outside
        const searchInput = document.getElementById('nav-search-input');
        const searchDropdown = document.getElementById('nav-search-dropdown');
        if (searchInput && searchDropdown && !searchInput.contains(e.target) && !searchDropdown.contains(e.target)) {
            searchDropdown.classList.add('hidden');
        }
    });

    // ---- Escape key handler ----
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            // Close sidebar on mobile
            const sidebar = document.getElementById('sidebar');
            if (sidebar && !sidebar.classList.contains('-translate-x-full')) {
                if (window.innerWidth < 1024) {
                    toggleSidebar();
                }
            }

            // Close all dropdowns
            const userDd = document.getElementById('user-dropdown');
            if (userDd) userDd.classList.add('hidden');

            const notifDd = document.getElementById('nav-notification-dropdown');
            if (notifDd) notifDd.classList.add('hidden');

            const searchDd = document.getElementById('nav-search-dropdown');
            if (searchDd) searchDd.classList.add('hidden');
        }
    });

    // ---- Setup Logout Handler ----
    const logoutBtn = document.getElementById('nav-logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', handleLogout);
    }

    // ---- Setup Search Bar ----
    initNavSearch();

    // ---- Authentication Check & Hydration ----
    await checkAndHydrateAuth();

    // ---- Load Notifications (after auth) ----
    loadNavNotifications();

    console.log('%c🚀 AI BI Platform loaded', 'color: #3b82f6; font-weight: bold; font-size: 14px;');
});

/**
 * Validates session, redirects if needed, and hydrates the user UI.
 */
async function checkAndHydrateAuth() {
    const path = window.location.pathname;
    const isPublicPage = path === '/' || path === '/login' || path === '/register';

    // Retrieve cached token
    let token = sessionStorage.getItem('access_token');
    if (token) {
        setAccessToken(token);
    }

    // If no token, try to refresh it using HTTPOnly cookie
    if (!token) {
        const refreshed = await refreshToken();
        if (refreshed) {
            token = getAccessToken();
            sessionStorage.setItem('access_token', token);
        }
    }

    if (token) {
        // User is logged in
        if (path === '/login' || path === '/register') {
            // Redirect to dashboard if they try to access login/register while logged in
            window.location.href = '/dashboard';
            return;
        }

        // Hydrate profile data on authenticated pages
        if (!isPublicPage) {
            await hydrateUserProfile();
        }
    } else {
        // User is not logged in
        if (!isPublicPage) {
            // Redirect to login if accessing a protected page
            window.location.href = '/login';
        }
    }
}

/**
 * Fetch current user profile from backend and update DOM elements.
 */
async function hydrateUserProfile() {
    try {
        const response = await apiGet('/auth/me');
        if (response.ok) {
            const user = await response.json();
            
            const firstLetter = (user.username || 'U')[0].toUpperCase();
            
            // Hydrate Navbar
            const navAvatar = document.getElementById('nav-avatar-letter');
            const navUsername = document.getElementById('nav-username');
            const navDropdownFullname = document.getElementById('nav-dropdown-fullname');
            const navDropdownEmail = document.getElementById('nav-dropdown-email');
            
            if (navAvatar) navAvatar.textContent = firstLetter;
            if (navUsername) navUsername.textContent = user.username;
            if (navDropdownFullname) navDropdownFullname.textContent = user.profile?.full_name || user.username;
            if (navDropdownEmail) navDropdownEmail.textContent = user.email;
            
            // Hydrate Sidebar
            const sidebarAvatar = document.getElementById('sidebar-avatar-letter');
            const sidebarUsername = document.getElementById('sidebar-username');
            const sidebarEmail = document.getElementById('sidebar-email');
            
            if (sidebarAvatar) sidebarAvatar.textContent = firstLetter;
            if (sidebarUsername) sidebarUsername.textContent = user.username;
            if (sidebarEmail) sidebarEmail.textContent = user.email;
        }
    } catch (err) {
        console.error('Failed to hydrate user profile:', err);
    }
}

/**
 * Handle user logout.
 */
async function handleLogout(e) {
    if (e) e.preventDefault();
    showLoading('Logging out...');
    
    try {
        await apiPost('/auth/logout');
    } catch (err) {
        console.error('Logout request failed:', err);
    }
    
    // Clear tokens & session
    clearAccessToken();
    sessionStorage.removeItem('access_token');
    
    // Redirect to login
    window.location.href = '/login';
}

/* ================================================
   Sidebar Toggle (mobile)
   ================================================ */
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    if (!sidebar) return;

    const isOpen = !sidebar.classList.contains('-translate-x-full');

    if (isOpen) {
        sidebar.classList.add('-translate-x-full');
        if (overlay) overlay.classList.add('hidden');
        document.body.style.overflow = '';
    } else {
        sidebar.classList.remove('-translate-x-full');
        if (overlay) overlay.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    }
}

/* ================================================
   User Dropdown Toggle
   ================================================ */
function toggleUserDropdown() {
    const dropdown = document.getElementById('user-dropdown');
    const arrow = document.getElementById('dropdown-arrow');
    if (!dropdown) return;

    const isHidden = dropdown.classList.contains('hidden');
    dropdown.classList.toggle('hidden');

    if (arrow) {
        arrow.style.transform = isHidden ? 'rotate(180deg)' : 'rotate(0deg)';
    }
}

/* ================================================
   Alert Dismiss
   ================================================ */
function dismissAlert(button) {
    const alert = button.closest('.alert-item');
    if (!alert) return;

    alert.classList.add('dismissing');
    setTimeout(() => {
        alert.remove();
    }, 200);
}

/* ================================================
   Loading Overlay
   ================================================ */
function showLoading(message = 'Loading...') {
    const overlay = document.getElementById('loading-overlay');
    const text = document.getElementById('loading-text');
    if (overlay) {
        overlay.classList.remove('hidden');
        if (text) text.textContent = message;
    }
}

function hideLoading() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.classList.add('hidden');
    }
}

/* ================================================
   Theme Management (Dark / Light Mode Toggle)
   ================================================ */
function initTheme() {
    const theme = localStorage.getItem('theme') || 'dark';
    document.documentElement.className = theme;
    syncThemeUI(theme);
}

function setTheme(theme) {
    localStorage.setItem('theme', theme);
    document.documentElement.className = theme;
    syncThemeUI(theme);
}

function toggleTheme() {
    const currentTheme = localStorage.getItem('theme') || 'dark';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
}

function syncThemeUI(theme) {
    const isLight = theme === 'light';

    // Settings page buttons
    const darkBtn = document.getElementById('theme-btn-dark');
    const lightBtn = document.getElementById('theme-btn-light');
    if (darkBtn && lightBtn) {
        if (isLight) {
            lightBtn.className = 'px-3 py-1.5 text-xs font-medium rounded-md bg-primary-500 text-white border border-primary-500';
            darkBtn.className = 'px-3 py-1.5 text-xs font-medium rounded-md text-gray-400 hover:text-gray-200';
        } else {
            darkBtn.className = 'px-3 py-1.5 text-xs font-medium rounded-md bg-primary-500/20 text-primary-400 border border-primary-500/20';
            lightBtn.className = 'px-3 py-1.5 text-xs font-medium rounded-md text-gray-500 hover:text-gray-300';
        }
    }

    // Navbar icons
    const navMoon = document.getElementById('theme-moon-icon');
    const navSun = document.getElementById('theme-sun-icon');
    if (navMoon) navMoon.style.display = isLight ? 'block' : 'none';
    if (navSun) navSun.style.display = isLight ? 'none' : 'block';

    // Sidebar icons
    const sidebarMoon = document.getElementById('sidebar-theme-moon-icon');
    const sidebarSun = document.getElementById('sidebar-theme-sun-icon');
    const sidebarText = document.getElementById('sidebar-theme-text');
    if (sidebarMoon) sidebarMoon.style.display = isLight ? 'block' : 'none';
    if (sidebarSun) sidebarSun.style.display = isLight ? 'none' : 'block';
    if (sidebarText) sidebarText.textContent = isLight ? 'Switch to Dark' : 'Switch to Light';
}

/* ================================================
   Format Helpers
   ================================================ */
function formatDate(dateStr) {
    if (!dateStr) return '--';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
    });
}

function formatNumber(num) {
    if (num === null || num === undefined) return '--';
    return Number(num).toLocaleString('en-US');
}

/* ================================================
   Navbar Search
   ================================================ */
let _searchDebounceTimer = null;

function initNavSearch() {
    const searchInput = document.getElementById('nav-search-input');
    if (!searchInput) return;

    searchInput.addEventListener('input', (e) => {
        clearTimeout(_searchDebounceTimer);
        _searchDebounceTimer = setTimeout(() => handleNavSearch(e.target.value), 250);
    });

    searchInput.addEventListener('focus', (e) => {
        if (e.target.value.trim()) {
            const dd = document.getElementById('nav-search-dropdown');
            if (dd) dd.classList.remove('hidden');
        }
    });
}

async function handleNavSearch(rawQuery) {
    const query = rawQuery.trim().toLowerCase();
    const dropdown = document.getElementById('nav-search-dropdown');
    if (!dropdown) return;

    if (!query) {
        dropdown.classList.add('hidden');
        resetLocalDatasetFilter();
        return;
    }

    // Also filter the local datasets table if we're on the upload page
    filterLocalDatasetsTable(query);

    try {
        const token = getAccessToken();
        if (!token) { dropdown.classList.add('hidden'); return; }

        const resp = await apiGet('/datasets/');
        if (!resp.ok) { dropdown.classList.add('hidden'); return; }

        const datasets = await resp.json();
        const matches = datasets.filter(ds =>
            ds.name.toLowerCase().includes(query) ||
            (ds.description && ds.description.toLowerCase().includes(query))
        );

        if (matches.length === 0) {
            dropdown.innerHTML = `
                <div class="px-4 py-4 text-xs text-gray-500 text-center">
                    🔍 No matching datasets for "<span class="text-gray-300">${rawQuery.trim()}</span>"
                </div>`;
        } else {
            dropdown.innerHTML = matches.slice(0, 8).map(ds => `
                <div class="px-4 py-2.5 hover:bg-white/[0.04] transition-colors flex items-center justify-between gap-3">
                    <div class="min-w-0">
                        <p class="text-xs font-semibold text-gray-200 truncate">${ds.name}</p>
                        <p class="text-[10px] text-gray-500 truncate">${ds.row_count || 0} rows &bull; ${ds.column_count || 0} cols</p>
                    </div>
                    <div class="flex gap-1.5 flex-shrink-0">
                        <a href="/datasets/${ds.id}/profile" class="px-2 py-0.5 text-[8px] font-bold uppercase rounded bg-primary-500/10 text-primary-400 hover:bg-primary-500/20 transition-all">Profile</a>
                        <a href="/datasets/${ds.id}/eda" class="px-2 py-0.5 text-[8px] font-bold uppercase rounded bg-purple-500/10 text-purple-400 hover:bg-purple-500/20 transition-all">EDA</a>
                    </div>
                </div>
            `).join('');
        }
        dropdown.classList.remove('hidden');
    } catch (err) {
        console.error('Search failed:', err);
        dropdown.classList.add('hidden');
    }
}

function filterLocalDatasetsTable(query) {
    const tbody = document.getElementById('datasets-tbody');
    if (!tbody) return;
    const rows = tbody.querySelectorAll('tr');
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(query) ? '' : 'none';
    });
}

function resetLocalDatasetFilter() {
    const tbody = document.getElementById('datasets-tbody');
    if (!tbody) return;
    const rows = tbody.querySelectorAll('tr');
    rows.forEach(row => { row.style.display = ''; });
}

/* ================================================
   Notification Bell Dropdown
   ================================================ */
let _navNotifications = [];

function toggleNotificationDropdown() {
    const dropdown = document.getElementById('nav-notification-dropdown');
    if (!dropdown) return;

    const isHidden = dropdown.classList.contains('hidden');
    dropdown.classList.toggle('hidden');

    if (isHidden) {
        // Mark all as read
        const badge = document.getElementById('nav-notification-badge');
        if (badge) badge.classList.add('hidden');
        _navNotifications.forEach(n => n.is_read = true);
        renderNavNotifications();
    }
}

function loadNavNotifications() {
    const token = getAccessToken();
    if (!token) return;

    apiGet('/dashboard/notifications')
        .then(resp => resp.ok ? resp.json() : [])
        .then(data => {
            _navNotifications = data || [];
            renderNavNotifications();
        })
        .catch(() => {});
}

function renderNavNotifications() {
    const list = document.getElementById('nav-notifications-list');
    const badge = document.getElementById('nav-notification-badge');
    if (!list) return;

    const unread = _navNotifications.filter(n => !n.is_read).length;
    if (badge) {
        badge.classList.toggle('hidden', unread === 0);
    }

    if (_navNotifications.length === 0) {
        list.innerHTML = `
            <div class="px-4 py-6 text-xs text-gray-500 text-center">
                📭 No notifications — you're all caught up!
            </div>`;
        return;
    }

    list.innerHTML = _navNotifications.map(n => `
        <div class="px-4 py-3 hover:bg-white/[0.02] transition-colors ${!n.is_read ? 'bg-primary-500/[0.03]' : ''}">
            <div class="flex items-start justify-between gap-2">
                <p class="text-xs font-semibold text-gray-200">${n.title}</p>
                <span class="text-[9px] text-gray-600 whitespace-nowrap">${formatDate(n.created_at)}</span>
            </div>
            <p class="mt-1 text-[11px] text-gray-400 leading-relaxed">${n.message}</p>
        </div>
    `).join('');
}

function clearAllNotifications() {
    _navNotifications = [];
    renderNavNotifications();
    showToast('Notifications cleared', 'success');
}

/* ================================================
   Coming Soon Alert (Sidebar disabled features)
   ================================================ */
function showComingSoonAlert(featureName, phase) {
    showToast(`🚧 ${featureName} is planned for Phase ${phase} of the development roadmap. Stay tuned!`, 'info');
}
