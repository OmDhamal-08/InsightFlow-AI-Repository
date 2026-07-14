/**
 * AI BI Platform — Settings JavaScript
 * Tab switching and form handlers.
 * NOTE: Scaffold only — no real API calls.
 */

document.addEventListener('DOMContentLoaded', () => {
    // Profile form
    const profileForm = document.getElementById('profile-form');
    if (profileForm) {
        profileForm.addEventListener('submit', handleProfileSave);
    }

    // Password form
    const passwordForm = document.getElementById('password-form');
    if (passwordForm) {
        passwordForm.addEventListener('submit', handlePasswordChange);
    }
});

/* ================================================
   Tab Switching (WORKING)
   ================================================ */
function switchSettingsTab(tabName) {
    // Update tab buttons
    const tabs = document.querySelectorAll('.settings-tab');
    tabs.forEach(tab => {
        tab.classList.remove('text-white', 'bg-white/[0.08]');
        tab.classList.add('text-gray-400');
    });

    const activeTab = document.getElementById(`tab-${tabName}`);
    if (activeTab) {
        activeTab.classList.remove('text-gray-400');
        activeTab.classList.add('text-white', 'bg-white/[0.08]');
    }

    // Update panels
    const panels = document.querySelectorAll('.settings-panel');
    panels.forEach(panel => {
        panel.classList.add('hidden');
    });

    const activePanel = document.getElementById(`panel-${tabName}`);
    if (activePanel) {
        activePanel.classList.remove('hidden');
        // Add fade-in effect
        activePanel.style.animation = 'fadeIn 0.3s ease-out forwards';
    }
}

/* ================================================
   Profile Save (placeholder)
   ================================================ */
async function handleProfileSave(e) {
    e.preventDefault();

    const name = document.getElementById('settings-name')?.value?.trim();
    const company = document.getElementById('settings-company')?.value?.trim();
    const role = document.getElementById('settings-role')?.value?.trim();
    const bio = document.getElementById('settings-bio')?.value?.trim();

    console.log('Profile save:', { name, company, role, bio });

    // TODO Phase 2: apiPut('/users/me', { full_name: name, company, role, bio })
    //   .then(() => showToast('Profile updated successfully!', 'success'))
    //   .catch(err => showToast(err.message, 'error'));

    // For now, show a console message
    if (typeof showToast === 'function') {
        showToast('Profile saved (demo mode).', 'success');
    }
}

/* ================================================
   Password Change (placeholder)
   ================================================ */
async function handlePasswordChange(e) {
    e.preventDefault();

    const currentPassword = document.getElementById('current-password')?.value;
    const newPassword = document.getElementById('new-password')?.value;
    const confirmPassword = document.getElementById('confirm-new-password')?.value;

    if (!currentPassword || !newPassword || !confirmPassword) {
        if (typeof showToast === 'function') {
            showToast('Please fill in all password fields.', 'warning');
        }
        return;
    }

    if (newPassword !== confirmPassword) {
        if (typeof showToast === 'function') {
            showToast('New passwords do not match.', 'error');
        }
        return;
    }

    if (newPassword.length < 8) {
        if (typeof showToast === 'function') {
            showToast('Password must be at least 8 characters.', 'error');
        }
        return;
    }

    console.log('Password change requested');

    // TODO Phase 2: apiPost('/auth/change-password', { current_password: currentPassword, new_password: newPassword })
    //   .then(() => showToast('Password updated successfully!', 'success'))
    //   .catch(err => showToast(err.message, 'error'));

    if (typeof showToast === 'function') {
        showToast('Password changed (demo mode).', 'success');
    }
}
