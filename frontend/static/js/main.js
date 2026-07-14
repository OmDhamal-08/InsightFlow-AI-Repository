/**
 * AI BI Platform — Main JavaScript
 * Global event listeners, sidebar toggle, dropdown, page transitions, and authentication check/hydration.
 */

document.addEventListener('DOMContentLoaded', async () => {
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
    });

    // ---- Escape key handler ----
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            // Close sidebar on mobile
            const sidebar = document.getElementById('sidebar');
            const overlay = document.getElementById('sidebar-overlay');
            if (sidebar && !sidebar.classList.contains('-translate-x-full')) {
                if (window.innerWidth < 1024) {
                    toggleSidebar();
                }
            }

            // Close user dropdown
            const dropdown = document.getElementById('user-dropdown');
            if (dropdown) dropdown.classList.add('hidden');
        }
    });

    // ---- Setup Logout Handler ----
    const logoutBtn = document.getElementById('nav-logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', handleLogout);
    }

    // ---- Authentication Check & Hydration ----
    await checkAndHydrateAuth();

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
   Theme Toggle (placeholder)
   ================================================ */
function toggleTheme() {
    // Theme toggle is dark-mode only
    console.log('Theme toggle: not yet implemented (dark mode only).');
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
