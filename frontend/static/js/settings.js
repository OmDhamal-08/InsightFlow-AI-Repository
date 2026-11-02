/**
 * AI BI Platform — Settings page.
 * Loads the real profile, saves it via PUT /users/profile and changes the
 * password via POST /auth/change-password.
 */

document.addEventListener('DOMContentLoaded', () => {
    const profileForm = document.getElementById('profile-form');
    if (!profileForm) return;
    profileForm.addEventListener('submit', handleProfileSave);
    document.getElementById('password-form')?.addEventListener('submit', handlePasswordChange);
    loadProfile();
});

/* ---------- Tabs ---------- */

function switchSettingsTab(tabName) {
    document.querySelectorAll('.settings-tab').forEach(tab => {
        tab.classList.remove('text-white', 'bg-white/[0.08]');
        tab.classList.add('text-gray-400');
    });
    const activeTab = document.getElementById(`tab-${tabName}`);
    if (activeTab) {
        activeTab.classList.remove('text-gray-400');
        activeTab.classList.add('text-white', 'bg-white/[0.08]');
    }
    document.querySelectorAll('.settings-panel').forEach(panel => panel.classList.add('hidden'));
    const activePanel = document.getElementById(`panel-${tabName}`);
    if (activePanel) {
        activePanel.classList.remove('hidden');
        activePanel.style.animation = 'fadeIn 0.3s ease-out forwards';
    }
}

/* ---------- Profile ---------- */

async function loadProfile() {
    const resp = await apiGet('/auth/me');
    if (!resp.ok) return;
    const me = await resp.json();
    const profile = me.profile || {};
    const set = (id, value) => { const el = document.getElementById(id); if (el) el.value = value || ''; };
    set('settings-email', me.email);
    set('settings-username', me.username);
    set('settings-name', profile.full_name);
    set('settings-company', profile.company);
    set('settings-role', profile.role);
    set('settings-bio', profile.bio);
}

async function handleProfileSave(e) {
    e.preventDefault();
    const value = id => document.getElementById(id)?.value?.trim() ?? '';
    const body = {
        full_name: value('settings-name'),
        company: value('settings-company'),
        role: value('settings-role'),
        bio: value('settings-bio'),
    };
    const resp = await apiPut('/users/profile', body);
    if (resp.ok) {
        showToast('Profile saved.', 'success');
        if (typeof hydrateUserProfile === 'function') hydrateUserProfile();
    } else {
        showToast(await settingsError(resp, 'Could not save profile'), 'error');
    }
}

/* ---------- Password ---------- */

async function handlePasswordChange(e) {
    e.preventDefault();
    const current = document.getElementById('current-password')?.value;
    const next = document.getElementById('new-password')?.value;
    const confirm = document.getElementById('confirm-new-password')?.value;

    if (!current || !next || !confirm) return showToast('Please fill in all password fields.', 'warning');
    if (next !== confirm) return showToast('New passwords do not match.', 'error');
    if (next.length < 8) return showToast('Password must be at least 8 characters.', 'error');

    const resp = await apiPost('/auth/change-password', { current_password: current, new_password: next });
    if (resp.ok) {
        const data = await resp.json();
        setAccessToken(data.access_token);
        sessionStorage.setItem('access_token', data.access_token);
        e.target.reset();
        showToast('Password changed. Other devices have been signed out.', 'success');
    } else {
        showToast(await settingsError(resp, 'Could not change password'), 'error');
    }
}

/** Readable message from a FastAPI error (string or validation list). */
async function settingsError(resp, fallback) {
    const data = await resp.json().catch(() => ({}));
    if (typeof data.detail === 'string') return data.detail;
    if (Array.isArray(data.detail)) return data.detail.map(d => (d.msg || '').replace('Value error, ', '')).join('. ');
    return fallback;
}
