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
        if (access) options.headers['Authorization'] = 'Bearer ' + access;

        let response = await fetch(API_BASE + path.replace(/^\/+/, ''), options);

        // 401 -> try refreshing once, then retry
        if (response.status === 401 && API.getRefresh() && !options._retried) {
            options._retried = true;
            const refreshed = await API.refreshTokens();
            if (refreshed) return API.request(path, options);
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

window.API = API;
window.showAlert = showAlert;