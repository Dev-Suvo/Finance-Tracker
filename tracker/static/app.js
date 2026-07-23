document.addEventListener('DOMContentLoaded', function () {

    /* Auto-dismiss alerts */
    setTimeout(function () {
        document.querySelectorAll('.alert').forEach(function (el) {
            el.style.transition = 'opacity .5s';
            el.style.opacity = '0';

            setTimeout(function () {
                el.remove();
            }, 500);
        });
    }, 4000);

    const typeBtns = document.querySelectorAll('.type-btn');
    const typeInput = document.getElementById('transaction_type');
    const categorySelect = document.getElementById('category');

    const incomeCategories = [
        'Salary',
        'Freelance',
        'Stipend',
        'Scholarship',
        'Business Revenue',
        'Other'
    ];

    const expenseCategories = [
        'Food',
        'Transport',
        'Shopping',
        'Bills',
        'Subscription',
        'Other'
    ];

    function loadCategories(categories) {

        if (!categorySelect) return;

        categorySelect.innerHTML =
        '<option value="">Select Category</option>';

        categories.forEach(function (category) {

        let option = document.createElement('option');

        option.value = category;
        option.textContent = category;

        categorySelect.appendChild(option);
    });
}

    if (typeBtns.length && typeInput) {

        typeBtns.forEach(function (btn) {

            btn.addEventListener('click', function () {

                typeBtns.forEach(function (b) {
                    b.classList.remove('active');
                });

                btn.classList.add('active');

                const type = btn.dataset.value;

                typeInput.value = type;

                if (type === 'Income') {
                    loadCategories(incomeCategories);
                } else {
                    loadCategories(expenseCategories);
                }

            });

        });

    }

});