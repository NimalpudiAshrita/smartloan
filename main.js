(function () {
    const form = document.getElementById("profileForm");
    if (!form) return;

    const incomeEl = form.querySelector("[name='monthly_income']");
    const expensesEl = form.querySelector("[name='monthly_expenses']");
    const existingEmiEl = form.querySelector("[name='existing_emi']");
    const loanAmountEl = form.querySelector("[name='loan_amount']");
    const tenureEl = form.querySelector("[name='tenure_months']");

    const dispEl = document.getElementById("dispIncome");
    const estEmiEl = document.getElementById("estEmi");

    const inr = (n) =>
        `INR ${Math.max(0, Math.round(n)).toLocaleString("en-IN")}`;

    const estimateEmi = (principal, annualRate, months) => {
        if (!principal || !months) return 0;
        const r = annualRate / 12 / 100;
        if (!r) return principal / months;
        const f = Math.pow(1 + r, months);
        return (principal * r * f) / (f - 1);
    };

    const update = () => {
        const income = Number(incomeEl.value || 0);
        const expenses = Number(expensesEl.value || 0);
        const existingEmi = Number(existingEmiEl.value || 0);
        const loanAmount = Number(loanAmountEl.value || 0);
        const tenure = Number(tenureEl.value || 0);

        const disposable = income - expenses - existingEmi;
        const estimated = estimateEmi(loanAmount, 10, tenure);

        dispEl.textContent = inr(disposable);
        estEmiEl.textContent = inr(estimated);
    };

    [incomeEl, expensesEl, existingEmiEl, loanAmountEl, tenureEl].forEach((el) => {
        el.addEventListener("input", update);
    });

    update();
})();
