/*
 * FinanceTracker — frontend API helper (fetch + JWT)
 * Configure API_BASE to point at your deployed Django backend.
 */
const API_BASE = (window.API_BASE_URL || 'http://localhost:8000') + '/api/';

const API = {
    /* ---- token storage ------------------------------------------------ */
    getAccess()      { return localStorage.getItem('ft_access'); },
    getRefresh()     { return localStorage.getItem('ft_refresh'); },
    setTokens(access, refresh) {
        localStorage.setItem('ft_access', access);
        if (refresh) localStorage.setItem('ft_refresh', refresh);
    },
    clearTokens() {
        localStorage.removeItem('ft_access');
        localStorage.removeItem('ft_refresh');
        localStorage.removeItem('ft_wallet_id');
        localStorage.removeItem('ft_wallet_name');
    },

    /* ---- session / wallet helpers ------------------------------------- */
    async user() {
        const r = await API.request('auth/me/');
        return r.ok ? r.data : null;
    },

    getWalletId()   { return localStorage.getItem('ft_wallet_id') || ''; },
    getWalletName() { return localStorage.getItem('ft_wallet_name') || ''; },
    setWallet(id, name) {
        localStorage.setItem('ft_wallet_id', id);
        localStorage.setItem('ft_wallet_name', name);
    },

    /* ---- core request ------------------------------------------------ */
    async request(path, options = {}) {
        options = Object.assign({}, options);
        options.headers = Object.assign({}, options.headers || {});

        if (options.body && typeof options.body !== 'string') {
            options.body = JSON.stringify(options.body);
            options.headers['Content-Type'] = 'application/json';
        }

        const access = API.getAccess();
        // Auth endpoints must never carry a stored token: a stale one turns a
        // plain login/register into 401 -> refresh -> retry (3 slow round-trips)
        // before the real response arrives. These endpoints don't need it.
        const noAuth = /^auth\/(token\/|register\/|resend-verification\/|password-reset\/)/.test(path);
        if (access && !noAuth) options.headers['Authorization'] = 'Bearer ' + access;

        let response;
        // If a request hangs >6s (classic Render free cold start after idle),
        // tell the user what's happening instead of looking frozen.
        const slowTimer = setTimeout(function () {
            const wrap = document.querySelector('.message-container');
            if (wrap && !document.getElementById('api-slow-toast')) {
                const t = document.createElement('div');
                t.className = 'alert info';
                t.id = 'api-slow-toast';
                t.innerHTML = '<i class="bi bi-hourglass-split"></i> Waking up the server — the first request after idle can take up to a minute. Please wait…';
                wrap.appendChild(t);
                window.scrollTo(0, 0);
            }
        }, 6000);
        try {
            response = await fetch(API_BASE + path.replace(/^\/+/, ''), options);
        } catch (e) {
            // Network/CORS failure — return a normal error object so UI can
            // re-enable buttons and show a message instead of dying silently.
            return { ok: false, status: 0, data: { detail: 'Cannot reach the server. Please try again in a moment.' } };
        } finally {
            clearTimeout(slowTimer);
            const toast = document.getElementById('api-slow-toast');
            if (toast) toast.remove();
        }

        // 401 on a no-auth endpoint = bad credentials (or server error):
        // refreshing/retrying cannot help, so return it immediately.
        if (response.status === 401 && noAuth) {
            return API._parse(response, options.parseAs);
        }

        // 401 -> try refreshing once, then retry
        if (response.status === 401 && !options._retried) {
            options._retried = true;
            if (API.getRefresh()) {
                const refreshed = await API.refreshTokens();
                if (refreshed) return API.request(path, options);
            }
            // Refresh failed or absent: the stored access token is bad
            // (e.g. it references a deleted user -> "User not found").
            // Drop the stale tokens and retry once WITHOUT auth so AllowAny
            // endpoints (register/login) succeed on the first submit.
            if (options.headers['Authorization']) {
                delete options.headers['Authorization'];
                API.clearTokens();
                return API.request(path, options);
            }
        }

        return API._parse(response, options.parseAs);
    },

    async refreshTokens() {
        const refresh = API.getRefresh();
        if (!refresh) return false;
        try {
            const response = await fetch(API_BASE + 'auth/token/refresh/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh }),
            });
            if (!response.ok) {
                API.clearTokens();
                return false;
            }
            const data = await response.json();
            API.setTokens(data.access, data.refresh);
            return true;
        } catch (e) {
            return false;
        }
    },

    async _parse(response, parseAs) {
        if (parseAs === 'blob') {
            const blob = await response.blob();
            return { ok: response.ok, status: response.status, data: null, blob };
        }
        let data = null;
        const text = await response.text();
        if (text) {
            try { data = JSON.parse(text); } catch (e) { data = null; }
        }
        return { ok: response.ok, status: response.status, data };
    },

    get(path, options) { return API.request(path, Object.assign({ method: 'GET' }, options)); },
    post(path, body)   { return API.request(path, { method: 'POST', body }); },
    patch(path, body)  { return API.request(path, { method: 'PATCH', body }); },
    del(path)          { return API.request(path, { method: 'DELETE' }); },

    /* ---- auth helpers ------------------------------------------------- */
    async login(username, password) {
        const r = await API.request('auth/token/', {
            method: 'POST',
            body: { username, password },
        });
        if (r.ok && r.data) API.setTokens(r.data.access, r.data.refresh);
        return r;
    },

    async logout() {
        API.clearTokens();
        window.location.href = 'login.html';
    },

    async requireAuth() {
        if (!API.getAccess() && !API.getRefresh()) {
            window.location.href = 'login.html';
            return null;
        }
        const me = await API.user();
        if (!me) {
            window.location.href = 'login.html';
            return null;
        }
        return me;
    },
};

/* Auto-dismiss alerts */
function showAlert(message, type) {
    const wrap = document.querySelector('.message-container');
    const el = document.createElement('div');
    el.className = 'alert ' + (type || 'info');
    const icon = type === 'success' ? '<i class="bi bi-check-circle-fill"></i>'
        : type === 'error' ? '<i class="bi bi-exclamation-circle-fill"></i>'
        : '<i class="bi bi-info-circle-fill"></i>';
    el.innerHTML = icon + ' ' + message;
    if (wrap) {
        wrap.appendChild(el);
        window.scrollTo(0, 0);
    } else {
        alert(message);
    }
    setTimeout(function () {
        el.style.transition = 'opacity .5s';
        el.style.opacity = '0';
        setTimeout(function () { el.remove(); }, 500);
    }, 4000);
}

/* ---- Password show/hide toggles ---------------------------------------- */
function initPasswordToggles(root) {
    const scope = root || document;
    scope.querySelectorAll('input[type="password"]:not([data-pw-toggle])').forEach(function (input) {
        input.setAttribute('data-pw-toggle', '1');
        const wrap = document.createElement('span');
        wrap.className = 'pw-wrap';
        input.parentNode.insertBefore(wrap, input);
        wrap.appendChild(input);

        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'pw-toggle';
        btn.setAttribute('aria-label', 'Show password');
        btn.innerHTML = '<i class="bi bi-eye"></i>';
        btn.addEventListener('click', function () {
            const show = input.type === 'password';
            input.type = show ? 'text' : 'password';
            btn.innerHTML = show ? '<i class="bi bi-eye-slash"></i>' : '<i class="bi bi-eye"></i>';
            btn.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
            input.focus();
        });
        wrap.appendChild(btn);
    });
}

window.API = API;
window.showAlert = showAlert;
window.initPasswordToggles = initPasswordToggles;

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { initPasswordToggles(); });
} else {
    initPasswordToggles();
}