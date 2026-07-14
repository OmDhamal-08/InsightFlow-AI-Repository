/**
 * API Client — Minimal fetch wrapper with JWT auth.
 * 
 * Stores access token in memory, attaches it to requests,
 * and auto-refreshes on 401 responses.
 */

const API_BASE = window.location.origin + '/api/v1';
let _accessToken = null;

/**
 * Set the access token (called after login/register).
 */
function setAccessToken(token) {
    _accessToken = token;
}

/**
 * Get the current access token.
 */
function getAccessToken() {
    return _accessToken;
}

/**
 * Clear the access token (called on logout).
 */
function clearAccessToken() {
    _accessToken = null;
}

/**
 * Make an API request with automatic auth header injection.
 * 
 * @param {string} endpoint - API path (e.g., '/auth/login')
 * @param {object} options - Fetch options (method, body, etc.)
 * @returns {Promise<Response>}
 */
async function apiRequest(endpoint, options = {}) {
    const url = API_BASE + endpoint;
    const headers = {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
    };

    if (_accessToken) {
        headers['Authorization'] = 'Bearer ' + _accessToken;
    }

    const response = await fetch(url, {
        ...options,
        headers,
        credentials: 'include',  // Send cookies (refresh token)
    });

    // Auto-refresh on 401 (except for auth endpoints)
    if (response.status === 401 && !endpoint.includes('/auth/refresh')) {
        const refreshed = await refreshToken();
        if (refreshed) {
            headers['Authorization'] = 'Bearer ' + _accessToken;
            return fetch(url, { ...options, headers, credentials: 'include' });
        }
    }

    return response;
}

/**
 * Attempt to refresh the access token using the refresh cookie.
 */
async function refreshToken() {
    try {
        const resp = await fetch(API_BASE + '/auth/refresh', {
            method: 'POST',
            credentials: 'include',
        });
        if (resp.ok) {
            const data = await resp.json();
            _accessToken = data.access_token;
            return true;
        }
    } catch (e) {
        console.error('Token refresh failed:', e);
    }
    return false;
}

// Convenience methods
async function apiGet(endpoint) {
    return apiRequest(endpoint, { method: 'GET' });
}

async function apiPost(endpoint, body) {
    return apiRequest(endpoint, {
        method: 'POST',
        body: JSON.stringify(body),
    });
}

async function apiPut(endpoint, body) {
    return apiRequest(endpoint, {
        method: 'PUT',
        body: JSON.stringify(body),
    });
}

async function apiDelete(endpoint) {
    return apiRequest(endpoint, { method: 'DELETE' });
}
