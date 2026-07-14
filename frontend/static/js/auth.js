/**
 * AI BI Platform — Auth JavaScript
 * Login/register form handlers, password visibility, password strength.
 */

document.addEventListener('DOMContentLoaded', () => {
    // ---- Login Form ----
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }

    // ---- Register Form ----
    const registerForm = document.getElementById('register-form');
    if (registerForm) {
        registerForm.addEventListener('submit', handleRegister);
    }
});

/* ================================================
   Login Handler
   ================================================ */
async function handleLogin(e) {
    e.preventDefault();

    const usernameOrEmail = document.getElementById('email')?.value?.trim();
    const password = document.getElementById('password')?.value;
    const errorEl = document.getElementById('login-error');
    const errorText = document.getElementById('login-error-text');
    const btn = document.getElementById('login-btn');
    const btnText = document.getElementById('login-btn-text');
    const btnSpinner = document.getElementById('login-btn-spinner');

    // Basic validation
    if (!usernameOrEmail || !password) {
        showAuthError(errorEl, errorText, 'Please fill in all fields.');
        return;
    }

    // Show loading state
    if (btn) btn.disabled = true;
    if (btnText) btnText.textContent = 'Signing in...';
    if (btnSpinner) btnSpinner.classList.remove('hidden');
    if (errorEl) errorEl.classList.add('hidden');

    try {
        const response = await apiPost('/auth/login', {
            username_or_email: usernameOrEmail,
            password: password
        });

        if (response.ok) {
            const data = await response.json();
            // Set access token in memory cache
            setAccessToken(data.access_token);
            // Optionally, you can store it in sessionStorage for tab persistence
            sessionStorage.setItem('access_token', data.access_token);
            // Redirect to dashboard
            window.location.href = '/dashboard';
        } else {
            const errData = await response.json().catch(() => ({}));
            showAuthError(errorEl, errorText, getErrorMessage(errData.detail, 'Login failed. Invalid credentials.'));
            // Reset button
            if (btn) btn.disabled = false;
            if (btnText) btnText.textContent = 'Sign In';
            if (btnSpinner) btnSpinner.classList.add('hidden');
        }
    } catch (err) {
        console.error(err);
        showAuthError(errorEl, errorText, 'An unexpected error occurred. Please try again.');
        // Reset button
        if (btn) btn.disabled = false;
        if (btnText) btnText.textContent = 'Sign In';
        if (btnSpinner) btnSpinner.classList.add('hidden');
    }
}

/* ================================================
   Register Handler
   ================================================ */
async function handleRegister(e) {
    e.preventDefault();

    const fullName = document.getElementById('full_name')?.value?.trim();
    const email = document.getElementById('reg-email')?.value?.trim();
    const username = document.getElementById('username')?.value?.trim();
    const password = document.getElementById('reg-password')?.value;
    const confirmPassword = document.getElementById('confirm-password')?.value;
    const terms = document.getElementById('terms')?.checked;
    const errorEl = document.getElementById('register-error');
    const errorText = document.getElementById('register-error-text');
    const btn = document.getElementById('register-btn');
    const btnText = document.getElementById('register-btn-text');
    const btnSpinner = document.getElementById('register-btn-spinner');

    // Validation
    if (!fullName || !email || !username || !password || !confirmPassword) {
        showAuthError(errorEl, errorText, 'Please fill in all fields.');
        return;
    }

    if (!isValidEmail(email)) {
        showAuthError(errorEl, errorText, 'Please enter a valid email address.');
        return;
    }

    if (password.length < 8) {
        showAuthError(errorEl, errorText, 'Password must be at least 8 characters.');
        return;
    }

    if (password !== confirmPassword) {
        showAuthError(errorEl, errorText, 'Passwords do not match.');
        return;
    }

    if (!terms) {
        showAuthError(errorEl, errorText, 'You must agree to the Terms of Service.');
        return;
    }

    // Show loading state
    if (btn) btn.disabled = true;
    if (btnText) btnText.textContent = 'Creating account...';
    if (btnSpinner) btnSpinner.classList.remove('hidden');
    if (errorEl) errorEl.classList.add('hidden');

    try {
        const response = await apiPost('/auth/register', {
            email: email,
            username: username,
            password: password,
            full_name: fullName
        });

        if (response.ok) {
            const data = await response.json();
            setAccessToken(data.access_token);
            sessionStorage.setItem('access_token', data.access_token);
            window.location.href = '/dashboard';
        } else {
            const errData = await response.json().catch(() => ({}));
            showAuthError(errorEl, errorText, getErrorMessage(errData.detail, 'Registration failed. Try different credentials.'));
            if (btn) btn.disabled = false;
            if (btnText) btnText.textContent = 'Create Account';
            if (btnSpinner) btnSpinner.classList.add('hidden');
        }
    } catch (err) {
        console.error(err);
        showAuthError(errorEl, errorText, 'An unexpected error occurred. Please try again.');
        if (btn) btn.disabled = false;
        if (btnText) btnText.textContent = 'Create Account';
        if (btnSpinner) btnSpinner.classList.add('hidden');
    }
}

/* ================================================
   Password Visibility Toggle (WORKING)
   ================================================ */
function togglePasswordVisibility(inputId, button) {
    const input = document.getElementById(inputId);
    if (!input) return;

    const eyeOpen = button.querySelector('.eye-open');
    const eyeClosed = button.querySelector('.eye-closed');

    if (input.type === 'password') {
        input.type = 'text';
        if (eyeOpen) eyeOpen.classList.add('hidden');
        if (eyeClosed) eyeClosed.classList.remove('hidden');
    } else {
        input.type = 'password';
        if (eyeOpen) eyeOpen.classList.remove('hidden');
        if (eyeClosed) eyeClosed.classList.add('hidden');
    }
}

/* ================================================
   Password Strength Checker (WORKING)
   ================================================ */
function checkPasswordStrength(password) {
    const bar1 = document.getElementById('strength-bar-1');
    const bar2 = document.getElementById('strength-bar-2');
    const bar3 = document.getElementById('strength-bar-3');
    const bar4 = document.getElementById('strength-bar-4');
    const text = document.getElementById('strength-text');
    const bars = [bar1, bar2, bar3, bar4];

    if (!bars[0] || !text) return;

    // Reset all bars
    bars.forEach(bar => {
        bar.className = 'h-1 flex-1 rounded-full bg-white/[0.08] transition-colors duration-300';
    });

    if (!password) {
        text.textContent = '';
        return;
    }

    // Calculate strength score
    let score = 0;
    if (password.length >= 8) score++;
    if (password.length >= 12) score++;
    if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
    if (/\d/.test(password)) score++;
    if (/[^a-zA-Z0-9]/.test(password)) score++;

    // Map score to level
    let level, color, label;
    if (score <= 1) {
        level = 1; color = 'bg-red-500'; label = 'Weak';
    } else if (score <= 2) {
        level = 2; color = 'bg-orange-500'; label = 'Fair';
    } else if (score <= 3) {
        level = 3; color = 'bg-amber-500'; label = 'Medium';
    } else {
        level = 4; color = 'bg-emerald-500'; label = 'Strong';
    }

    // Fill bars
    for (let i = 0; i < level; i++) {
        bars[i].className = `h-1 flex-1 rounded-full ${color} transition-colors duration-300`;
    }

    // Set label color
    const labelColors = { 'Weak': 'text-red-400', 'Fair': 'text-orange-400', 'Medium': 'text-amber-400', 'Strong': 'text-emerald-400' };
    text.textContent = label;
    text.className = `text-[11px] font-medium ${labelColors[label]}`;
}

/* ================================================
   Validation Helpers
   ================================================ */
function isValidEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function showAuthError(errorEl, errorText, message) {
    if (errorEl && errorText) {
        errorText.textContent = message;
        errorEl.classList.remove('hidden');
    }
}

function getErrorMessage(detail, fallback) {
    if (!detail) return fallback;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
        return detail.map(err => {
            let msg = err.msg || '';
            if (msg.startsWith('Value error, ')) {
                msg = msg.replace('Value error, ', '');
            }
            if (msg) {
                msg = msg.charAt(0).toUpperCase() + msg.slice(1);
            }
            return msg;
        }).filter(Boolean).join('. ');
    }
    if (typeof detail === 'object') {
        return JSON.stringify(detail);
    }
    return String(detail);
}
