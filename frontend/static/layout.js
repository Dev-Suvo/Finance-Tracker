/*
 * FinanceTracker — shared app layout: sidebar, auth guard, wallet chip.
 * Each app page sets <body data-page="..."> to highlight the active link.
 * Pages needing a selected wallet also require .require-wallet on body.
 */

function buildSidebar(active) {
    const links = [
        { page: 'home',            href: 'home.html',            icon: 'bi-house-fill',      label: 'Home' },
        { page: 'create-transaction', href: 'create-transaction.html', icon: 'bi-arrow-left-right', label: 'Create Transaction', wallet: true },
        { page: 'dashboard',       href: 'dashboard.html',       icon: 'bi-graph-up',        label: 'Dashboard', wallet: true },
        { page: 'budgets',         href: 'budgets.html',         icon: 'bi-wallet2',         label: 'Budgets', wallet: true },
        { page: 'savings-goals',   href: 'savings-goals.html',   icon: 'bi-bullseye',        label: 'Savings Goals', wallet: true },
        { page: 'select-wallet',   href: 'select-wallet.html',   icon: 'bi-list-ul',         label: 'Select Wallet' },
    ];

    let html = `
    <div class="sidebar">
        <div class="sidebar-top">
            <a href="home.html" style="text-decoration:none;color:inherit;">
            <div class="sidebar-logo">
                <div class="logo-icon"><i class="bi bi-coin"></i></div>
                FinanceTracker
            </div>
            </a>
            <div class="sidebar-menu">
                ${links.map(function (l) {
                    return `<a href="${l.href}" ${l.page === active ? 'class="active"' : ''}>
                        <i class="bi ${l.icon}"></i> ${l.label}</a>`;
                }).join('')}
            </div>
        </div>
        <div class="sidebar-menu">
            <a href="#" id="logout-link"><i class="bi bi-box-arrow-right"></i> Logout</a>
        </div>
    </div>
    <button class="mobile-menu-btn" id="mobile-menu-btn" aria-label="Open menu"><i class="bi bi-list"></i></button>
    <div class="sidebar-overlay" id="sidebar-overlay"></div>`;
    return html;
}

document.addEventListener('DOMContentLoaded', async function () {
    const layoutEl = document.getElementById('app-layout');
    if (!layoutEl) return;

    const active = document.body.dataset.page || '';
    layoutEl.insertAdjacentHTML('afterbegin', buildSidebar(active));

    // Mobile menu (hamburger → slide-in sidebar)
    const menuBtn = document.getElementById('mobile-menu-btn');
    const menuOverlay = document.getElementById('sidebar-overlay');
    const sidebarEl = document.querySelector('.sidebar');
    function closeMobileMenu() {
        if (sidebarEl) sidebarEl.classList.remove('mobile-open');
        if (menuOverlay) menuOverlay.classList.remove('show');
    }
    if (menuBtn && sidebarEl && menuOverlay) {
        menuBtn.addEventListener('click', function () {
            sidebarEl.classList.toggle('mobile-open');
            menuOverlay.classList.toggle('show');
        });
        menuOverlay.addEventListener('click', closeMobileMenu);
        sidebarEl.addEventListener('click', function (e) {
            if (e.target.closest('a')) closeMobileMenu();
        });
    }

    // Auth guard
    const me = await API.requireAuth();
    if (!me) return;

    // If the page needs a wallet but none selected, go choose one
    if (document.body.dataset.requireWallet) {
        if (!API.getWalletId()) {
            window.location.href = 'select-wallet.html';
            return;
        }
    }

    // Wallet chip (rendered by pages as [data-wallet-chip])
    const chips = document.querySelectorAll('[data-wallet-chip]');
    if (chips.length) {
        const name = API.getWalletName();
        chips.forEach(function (chip) {
            if (name) chip.insertAdjacentHTML('afterbegin', '<i class="bi bi-wallet2"></i> ' + name);
            else chip.insertAdjacentHTML('afterbegin', '<i class="bi bi-wallet2"></i> Select Wallet');
        });
    }

    // Logout
    const logoutLink = document.getElementById('logout-link');
    if (logoutLink) {
        logoutLink.addEventListener('click', function (e) {
            e.preventDefault();
            API.logout();
        });
    }
});