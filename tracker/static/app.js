/* FinanceTracker – app.js */

document.addEventListener('DOMContentLoaded', function () {

    /* ── Auto-dismiss alerts ── */
    setTimeout(function () {
        document.querySelectorAll('.alert').forEach(function (el) {
            el.style.transition = 'opacity .5s';
            el.style.opacity = '0';
            setTimeout(function () { el.remove(); }, 500);
        });
    }, 4000);


    /* ── Transaction type toggle buttons ── */
    const typeBtns = document.querySelectorAll('.type-btn');
    const typeInput = document.getElementById('transaction_type');

    if (typeBtns.length && typeInput) {
        typeBtns.forEach(function (btn) {
            btn.addEventListener('click', function () {
                typeBtns.forEach(function (b) { b.classList.remove('active'); });
                btn.classList.add('active');
                typeInput.value = btn.dataset.value;
            });
        });
    }


    /* ── Wallet card cursor pointer for select page ── */
    document.querySelectorAll('.wallet-card').forEach(function (card) {
        card.style.cursor = 'pointer';
    });

});
