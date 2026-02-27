import math
import os
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "smartloan360-dev-secret")


class FallbackModel:
    def predict(self, X):
        monthly_income, loan_amount, credit_score = X[0]
        income_gate = monthly_income >= (loan_amount / 120)
        credit_gate = credit_score >= 650
        return np.array([1 if income_gate and credit_gate else 0])

    def predict_proba(self, X):
        monthly_income, loan_amount, credit_score = X[0]
        score = 0.22
        score += min(max((credit_score - 500) / 360, 0), 0.53)
        score += min(max((monthly_income - (loan_amount / 120)) / 120000, 0), 0.2)
        approved = min(max(score, 0.05), 0.95)
        return np.array([[1 - approved, approved]])


def load_model():
    model_path = Path(__file__).resolve().parent / "model.pkl"
    if model_path.exists():
        return joblib.load(model_path)
    app.logger.warning("model.pkl not found. Falling back to rules-based model.")
    return FallbackModel()


model = load_model()

USERS = {
    "admin": {
        "password": generate_password_hash("smartloan360"),
        "name": "Platform Admin",
    },
    "analyst": {
        "password": generate_password_hash("loanmarket123"),
        "name": "Credit Analyst",
    },
}

BANKS = {
    "Home": [
        {"name": "SBI", "base_rate": 8.35, "min_credit": 680, "max_foir": 0.55, "processing_fee": 0.6},
        {"name": "HDFC", "base_rate": 8.55, "min_credit": 710, "max_foir": 0.52, "processing_fee": 0.75},
        {"name": "Axis", "base_rate": 8.72, "min_credit": 695, "max_foir": 0.54, "processing_fee": 0.7},
        {"name": "ICICI", "base_rate": 8.68, "min_credit": 700, "max_foir": 0.53, "processing_fee": 0.8},
    ],
    "Education": [
        {"name": "SBI", "base_rate": 8.95, "min_credit": 650, "max_foir": 0.58, "processing_fee": 0.5},
        {"name": "Bank of Baroda", "base_rate": 9.1, "min_credit": 640, "max_foir": 0.59, "processing_fee": 0.4},
        {"name": "Axis", "base_rate": 9.25, "min_credit": 655, "max_foir": 0.57, "processing_fee": 0.65},
    ],
    "Personal": [
        {"name": "HDFC", "base_rate": 11.2, "min_credit": 730, "max_foir": 0.48, "processing_fee": 1.3},
        {"name": "ICICI", "base_rate": 11.45, "min_credit": 725, "max_foir": 0.5, "processing_fee": 1.1},
        {"name": "Axis", "base_rate": 11.8, "min_credit": 710, "max_foir": 0.5, "processing_fee": 1.2},
    ],
    "Business": [
        {"name": "HDFC", "base_rate": 10.45, "min_credit": 700, "max_foir": 0.55, "processing_fee": 1.0},
        {"name": "ICICI", "base_rate": 10.8, "min_credit": 695, "max_foir": 0.56, "processing_fee": 1.1},
        {"name": "Kotak", "base_rate": 10.95, "min_credit": 690, "max_foir": 0.57, "processing_fee": 0.95},
    ],
}

EMPLOYMENT_STABILITY = {
    "salaried": 1.0,
    "self_employed": 0.85,
    "freelancer": 0.75,
}


def login_required():
    return "username" in session


def emi(principal, annual_rate, months):
    monthly_rate = annual_rate / 12 / 100
    if monthly_rate == 0:
        return principal / months
    factor = (1 + monthly_rate) ** months
    return principal * monthly_rate * factor / (factor - 1)


def profile_risk(credit_score, foir, stability):
    risk_score = 100

    if credit_score >= 760:
        risk_score -= 35
    elif credit_score >= 700:
        risk_score -= 22
    elif credit_score >= 650:
        risk_score -= 10

    if foir <= 0.35:
        risk_score -= 25
    elif foir <= 0.45:
        risk_score -= 15
    elif foir <= 0.55:
        risk_score -= 5
    else:
        risk_score += 20

    if stability >= 0.95:
        risk_score -= 12
    elif stability < 0.8:
        risk_score += 10

    risk_score = max(5, min(95, risk_score))

    if risk_score <= 35:
        return "Low", risk_score
    if risk_score <= 60:
        return "Medium", risk_score
    return "High", risk_score


def explain_profile(data, decision_confidence, risk_label):
    reasons = []
    cautions = []

    if data["credit_score"] >= 740:
        reasons.append("Strong credit profile increases lender trust.")
    elif data["credit_score"] < 670:
        cautions.append("Credit score is below preferred range for premium offers.")

    if data["foir"] <= 0.4:
        reasons.append("Healthy FOIR indicates manageable repayment capacity.")
    elif data["foir"] > 0.55:
        cautions.append("FOIR is high; lenders may reduce sanction amount.")

    if data["disposable_income"] >= (0.35 * data["monthly_income"]):
        reasons.append("Disposable income supports stable EMI servicing.")

    if decision_confidence < 55:
        cautions.append("Eligibility confidence is moderate; terms may vary by lender.")

    if risk_label == "High" and not cautions:
        cautions.append("Overall profile is sensitive to higher loan burden.")

    return reasons, cautions


def build_offers(profile, prediction, confidence):
    offers = []

    if prediction != 1:
        return offers

    for bank in BANKS[profile["loan_type"]]:
        if profile["credit_score"] < bank["min_credit"]:
            continue

        base_rate = bank["base_rate"]
        credit_adjustment = -0.35 if profile["credit_score"] >= 760 else (-0.15 if profile["credit_score"] >= 720 else 0.2)
        foir_adjustment = -0.1 if profile["foir"] <= 0.4 else (0.25 if profile["foir"] > 0.5 else 0)
        stability_adjustment = -0.1 if profile["stability"] >= 1 else (0.2 if profile["stability"] < 0.8 else 0)

        effective_rate = round(max(base_rate + credit_adjustment + foir_adjustment + stability_adjustment, 7.75), 2)

        monthly_emi = emi(profile["loan_amount"], effective_rate, profile["tenure_months"])
        combined_obligation = profile["existing_emi"] + monthly_emi
        actual_foir = combined_obligation / profile["monthly_income"]

        if actual_foir > bank["max_foir"]:
            continue

        payable = monthly_emi * profile["tenure_months"]
        processing = profile["loan_amount"] * (bank["processing_fee"] / 100)

        bank_fit = 100
        bank_fit -= (effective_rate - bank["base_rate"]) * 10
        bank_fit -= max(actual_foir - 0.35, 0) * 120
        bank_fit += (confidence - 50) * 0.2
        bank_fit = int(max(35, min(98, bank_fit)))

        offers.append(
            {
                "bank": bank["name"],
                "rate": effective_rate,
                "emi": int(round(monthly_emi)),
                "total_payable": int(round(payable + processing)),
                "processing_fee": round(bank["processing_fee"], 2),
                "approval": bank_fit,
                "foir": round(actual_foir * 100, 1),
                "tag": "Best Rate" if effective_rate <= base_rate else "Fast Approval",
            }
        )

    offers.sort(key=lambda x: (x["rate"], -x["approval"], x["emi"]))
    return offers


@app.route("/", methods=["GET", "POST"])
def login():
    if login_required():
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")

        user = USERS.get(username)
        if user and check_password_hash(user["password"], password):
            session["username"] = username
            session["name"] = user["name"]
            return redirect(url_for("dashboard"))

        flash("Invalid credentials. Use admin/smartloan360 for demo access.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if not login_required():
        return redirect(url_for("login"))

    if request.method == "POST":
        try:
            full_name = request.form.get("full_name", "Applicant").strip() or "Applicant"
            age = int(request.form.get("age", 0))
            employment = request.form.get("employment", "salaried")
            monthly_income = float(request.form.get("monthly_income", 0))
            monthly_expenses = float(request.form.get("monthly_expenses", 0))
            existing_emi = float(request.form.get("existing_emi", 0))
            credit_score = int(request.form.get("credit_score", 0))
            loan_amount = float(request.form.get("loan_amount", 0))
            tenure_months = int(request.form.get("tenure_months", 0))
            loan_type = request.form.get("loan_type", "Home")
        except ValueError:
            flash("Invalid numeric input. Please review your profile values.", "error")
            return redirect(url_for("dashboard"))

        if loan_type not in BANKS:
            flash("Unsupported loan type selected.", "error")
            return redirect(url_for("dashboard"))

        if not (21 <= age <= 65):
            flash("Age should be between 21 and 65 years.", "error")
            return redirect(url_for("dashboard"))

        if monthly_income <= 0 or loan_amount <= 0 or tenure_months < 12:
            flash("Income, loan amount, and tenure should be valid positive values.", "error")
            return redirect(url_for("dashboard"))

        if monthly_expenses < 0 or existing_emi < 0:
            flash("Expenses and existing EMI cannot be negative.", "error")
            return redirect(url_for("dashboard"))

        if not (300 <= credit_score <= 900):
            flash("Credit score must be between 300 and 900.", "error")
            return redirect(url_for("dashboard"))

        stability = EMPLOYMENT_STABILITY.get(employment, 0.8)
        disposable_income = max(monthly_income - monthly_expenses - existing_emi, 0)

        baseline_emi = emi(loan_amount, 10.0, tenure_months)
        foir = (existing_emi + baseline_emi) / monthly_income

        X = np.array([[monthly_income, loan_amount, credit_score]])
        prediction = int(model.predict(X)[0])
        confidence = int(round(float(model.predict_proba(X)[0][1] * 100)))

        risk_label, risk_score = profile_risk(credit_score, foir, stability)

        profile = {
            "full_name": full_name,
            "age": age,
            "employment": employment,
            "monthly_income": monthly_income,
            "monthly_expenses": monthly_expenses,
            "existing_emi": existing_emi,
            "credit_score": credit_score,
            "loan_amount": loan_amount,
            "tenure_months": tenure_months,
            "loan_type": loan_type,
            "disposable_income": disposable_income,
            "foir": foir,
            "stability": stability,
            "generated_at": datetime.now().strftime("%d %b %Y, %I:%M %p"),
        }

        offers = build_offers(profile, prediction, confidence)

        if prediction == 1 and offers:
            status = "APPROVED"
        elif prediction == 1:
            status = "CONDITIONAL"
        else:
            status = "REJECTED"

        reasons, cautions = explain_profile(profile, confidence, risk_label)
        best_offer = offers[0] if offers else None

        return render_template(
            "result.html",
            status=status,
            confidence=confidence,
            risk_label=risk_label,
            risk_score=risk_score,
            profile=profile,
            offers=offers,
            best_offer=best_offer,
            reasons=reasons,
            cautions=cautions,
        )

    return render_template("dashboard.html", user_name=session.get("name", "User"))


if __name__ == "__main__":
    app.run(debug=True)
