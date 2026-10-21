# ChurnWatch AI: synthetic banking churn backend

Backend-first FastAPI MVP using the supplied synthetic banking customer dataset. Python/scikit-learn computes churn probabilities, evaluations, and feature contributions. Groq optionally turns these structured results into natural-language explanations.

## Dataset and limitations

`Data/churnwatch_synthetic_banking_customers.csv` contains 1,500 synthetic development/demo records. It is not real banking data and does not establish real-world banking performance. The model excludes `customer_id`, `snapshot_date`, `churn_reason_after_exit` (post-exit information), and the target from model inputs. Its preprocessing is fitted only on the stratified training split during evaluation; reported results use the held-out test split. The deployable pipeline is then fitted on all available synthetic development rows.

The baseline is class-weighted logistic regression with median/mode imputation, numeric scaling, and one-hot encoding. Fixed display bands are Low below 0.35, Medium from 0.35 to below 0.65, and High at or above 0.65. These transparent MVP thresholds are not optimized business cutoffs. Feature contributions and observed relationships are associations, not causes or proof that an individual will churn. Retention actions are suggestions to test.

## Setup (Windows PowerShell / VS Code)

```powershell
cd C:\Users\razan\ChurnAI
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

If Python 3.12 is unavailable, use an installed Python 3.10–3.14 version. Edit `.env` locally to set `GROQ_API_KEY`; do not paste it into source code, commit it, or share it in chat. Create a key in the Groq Cloud Console under API Keys. `GROQ_MODEL` defaults to `openai/gpt-oss-120b` and can be changed in `.env`. The key is optional; `/analyze` returns model-derived explanations and explicitly reports LLM unavailability when it is missing or the provider fails. The application loads the root `.env` first. For an existing VS Code setup, it can also read `GROQ_API_KEY` or the legacy `API-KEY` name from `.vscode/.env` and map it into `GROQ_API_KEY` in memory; it never prints or edits that file. Prefer `GROQ_API_KEY` for new configuration.

## Train/evaluate and run

```powershell
python scripts\train_model.py
pytest -q
uvicorn app.main:app --reload
```

The API startup also computes and saves the model artifact at `artifacts/churn_model.joblib`. The training script prints real data quality and held-out metrics. Do not treat results on synthetic data as evidence of production performance.

Swagger: `http://127.0.0.1:8000/docs`; health: `http://127.0.0.1:8000/health`.

## API contract

- `GET /health`: application, model, and configured/unconfigured LLM states.
- `GET /model/info`: model version, features, seed, evaluation metadata, and risk-band rationale.
- `GET /analytics/overview`: aggregate dataset counts/statistics, risk distribution, and holdout metrics; no per-customer records.
- `POST /predict`: `{ "customer": { ...all supported model features... } }`; returns probability, risk category, top positive logistic contributions, association caveat, and actions.
- `POST /predict/batch`: `{ "customers": [{...}, ...] }`; up to 500 records.
- `POST /analyze`: same body as `/predict`; returns ML prediction plus separate `llm` status. If unavailable, `fallback_explanation.source` identifies the local model-contribution explanation.
- `GET /metrics`: Prometheus text format for request counts/statuses, retained-window request latency p50/p95/p99, prediction risk categories, and LLM success/failure counts.

Requests accept `X-Request-ID` or receive a generated ID, returned in the response header. Logs include request ID, route, status, and latency, without customer records or secrets. LLM token usage is returned only when the provider supplies it; model inference and LLM latency are measured locally. Metrics are in-memory and reset on restart. The model is evaluated offline; online outcome tracking, drift detection, production alerts, and durable monitoring are not implemented.

### Example request

```json
{
  "customer": {
    "age": 42,
    "customer_segment": "Mass",
    "monthly_income_sar": 9000,
    "tenure_months": 18,
    "number_of_banks_used": 2,
    "primary_bank_relationship_months": 18,
    "monthly_transaction_count": 22,
    "transaction_count_change_90d_pct": -18.5,
    "active_digital_days_30d": 12,
    "support_tickets_90d": 2,
    "complaints_90d": 1,
    "failed_transaction_rate_pct": 7.2,
    "regular_salary_inflow": 1,
    "autopay_enabled": 0,
    "savings_balance_sar": 12000,
    "balance_change_90d_pct": -12.0,
    "large_withdrawal_30d": 0,
    "large_withdrawal_ratio_of_balance": 0.1,
    "active_products_count": 2,
    "debit_card_active": 1,
    "loan_active": 0,
    "digital_banking_complaint_90d": 0,
    "competitor_offer_signal_90d": 0,
    "days_since_last_branch_visit": 60,
    "nps_score": 5
  }
}
```

A `/predict` response contains `status: success` and a `prediction` object with `churn_probability`, `risk_category`, `risk_signals`, `explanation`, and `recommended_actions`.

## Monitoring roadmap

Next steps for real labeled outcomes: evaluate on future-period samples; track prediction-to-outcome calibration and performance; monitor feature/prediction drift; track Groq cost, reliability, and model changes; add durable dashboards and alerting; implement access controls, privacy reviews, and audit trails. None of those capabilities is claimed as implemented here.
