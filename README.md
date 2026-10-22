# ChurnWatch AI — Synthetic Banking Analytics MVP

Backend-first FastAPI service over the supplied synthetic package in `Data/churnwatch_v1_mock_data/`. It joins customer profiles, monthly snapshots, and historical outcomes. Risk is a transparent point-based rule assessment, not a trained model or churn probability. Groq explains the supplied structured assessment; Python computes all dashboard statistics and retrospective comparisons.

All data and outputs are synthetic/demo. They are not real banking data or evidence of real-world performance. Synthetic scenario/reason fields, future labels, outcome fields, and identifiers are not risk-assessment evidence. Historical labels are returned separately only when their horizon is marked observed. The LLM prompt never includes future labels or synthetic scenario/reason fields.

## Data validation and rules

The loader requires all seven package files and reports missing names instead of creating replacements. It validates required columns, IDs, snapshot dates, duplicate customer/date pairs, and label-observation consistency. The joined package currently contains 5,000 profiles, 70,575 snapshots, and 5,000 outcomes. The 30-day horizon has 70,575 eligible snapshots; the 90-day horizon has 62,066. Missing 90-day labels are expected when `label_observed_90d=0`.

Rule points add only when documented thresholds are crossed: transaction decline at least 20% (2), digital-days decline at least 20% (1), 7 or fewer active digital days (1), balance decline at least 20% (1), failed transaction rate at least 10% (1), 3+ card declines (1), 5+ app crashes (1), 5+ failed logins (1), 3+ tickets (1), any unresolved ticket (2), repeat same-issue contact (1), 2+ complaints (1), median resolution at least 72 hours (1), missed salary (2), 3+ bank fees (1), 5+ overdraft days (1), external-transfer growth at least 50% (1), NPS 4 or lower (1), and tenure under 12 months with at most one active product (1). Low is 0–2 points, Medium 3–5, High 6+. External transfers do not prove competitor use; balances or missed salary do not establish intent. Age and income are excluded from rule evidence and the Groq prompt. Unavailable fields are omitted, not fabricated. Points are an ordinal screening heuristic and are never converted to probabilities.

Historical evaluation filters separately on `label_observed_30d` and `label_observed_90d`. It compares Medium/High as an alert against eligible labels and reports descriptive confusion counts, precision, recall, and F1. Snapshots repeat customers and are not independent; results are synthetic retrospective descriptions, not prospective performance estimates. No ML model is trained or loaded.

## Setup (PowerShell / VS Code)

```powershell
cd C:\Users\razan\ChurnAI
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Set `DATABASE_URL` in the root `.env` to the PostgreSQL connection string from your Supabase project. Keep `.env` private; it is ignored by Git. `GROQ_API_KEY` is optional for the main API. `GROQ_MODEL` defaults to `openai/gpt-oss-120b`. Existing `.vscode/.env` values named `GROQ_API_KEY` or legacy `API-KEY` are loaded in memory if root `GROQ_API_KEY` is not set. No secret is printed or rewritten.

The main API allows local frontend development origins on ports 3000 and 5173 by default. Set `FRONTEND_ORIGINS` to a comma-separated allowlist of exact origins for the frontend deployment; do not include paths.

### Apply the Supabase schema

1. In the Supabase Dashboard, open **SQL Editor** and run the complete contents of `monitoring/migrations/001_initial.sql`.
2. In a second SQL Editor query, run `monitoring/migrations/002_enable_rls.sql`. The first migration creates request, LLM response, latency/token, safe error, and churn-evaluation tables. The second enables row-level security; no browser policy is created, so keep database access on the backend.
3. Open **Connect** in the project dashboard and copy the PostgreSQL connection string. Supabase documents the available connection modes [here](https://supabase.com/docs/guides/database/connecting-to-postgres). For an IPv4-only development network, select the **Session pooler** string. Use the host, port, and username exactly as Supabase provides them.
4. Put the connection string in the root `.env` as `DATABASE_URL=...`. Replace its password placeholder locally, retain `sslmode=require` if present, and URL-encode reserved characters in the password. Never commit or share the resulting URL.
5. Start Monitoring and request `GET http://127.0.0.1:8010/api/monitoring/health`. It reports `database: connected` only after an actual connection succeeds. No connection is assumed before that check.

Apply the migrations in order: `001_initial.sql`, then `002_enable_rls.sql`. `.env.example` contains placeholders only.
## Run the separate services

Start the main customer API in one terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Start Monitoring in a second terminal/process:

```powershell
.\.venv\Scripts\python.exe -m uvicorn monitoring.main:app --host 127.0.0.1 --port 8010 --reload
```

Main API Swagger: `http://127.0.0.1:8000/docs`. Monitoring Swagger: `http://127.0.0.1:8010/docs`. If Supabase or Monitoring is unavailable, customer analysis still returns; its `monitoring.delivery_status` reports the failure separately. Monitoring uses its own process and Supabase PostgreSQL schema. No SQLite monitoring storage is used.

## Frontend API contract

All customer-facing routes are under `/api`. Every response marks the dataset synthetic. Request/correlation IDs are returned in `X-Request-ID`.

- `GET /api/health`: app/data readiness, Groq configured flag/model, Monitoring URL; does not claim database connectivity.
- `GET /api/dashboard`: customer totals, historical outcome count/rate, latest-snapshot risk chart arrays, segment rates, descriptive factors, eligible 30/90-day rule evaluation, recent process-local analyses.
- `GET /api/customers?page=1&page_size=50&risk_category=High&customer_segment=Mass&search=CUST_`: paginated latest-snapshot explorer and filters.
- `GET /api/customers/{customer_id}?snapshot_date=2026-09-01`: profile, selected feature snapshot, point-based assessment, eligible historical label values, and process-local analysis history.
- `POST /api/customers/{customer_id}/analyze?snapshot_date=2026-09-01`: same evidence plus validated executive summary, insights, recommendations, LLM metadata, retrospective outcome and Monitoring delivery status. Date is optional; latest snapshot is default.
- `GET /api/metrics`: in-memory API request counts and latency quantiles.
- Monitoring service: `GET /api/monitoring/health`, `/api/monitoring/requests`, `/api/monitoring/summary`.

Risk assessment contains `assessment_type`, `risk_category`, integer `risk_score` and `risk_score_unit: "points (not probability)"`, thresholds, evidence-linked `risk_factors`, and limitations. No `churn_probability_*` fields are returned. LLM response fields are schema-validated. If Groq fails or returns malformed JSON, a clearly identified local rules-based narrative is returned and `llm_metadata.status` is unavailable with a safe error category.

Monitoring stores the request ID/timestamp, provider/model/status, risk assessment type/category, selected synthetic customer key/date, response JSON, measured latency, provider-reported token counts, safe error category, label eligibility and available actual labels. Rule-alert agreement is separate from LLM correctness. LLM correctness remains `not_evaluated` until independently reviewed. Monitoring delivery has a short timeout and does not fail customer analysis.

## Demo, evaluation, and tests

```powershell
python scripts\run_demo.py
python scripts\evaluate_rules.py
pytest -q
```

The demo selects one actual synthetic customer snapshot and makes one optional Groq call. Evaluation is local and makes no LLM call. The old `scripts/train_model.py` entry point is intentionally disabled; no training is performed.

## Limits and next steps

The rule points are hand-set screening indicators, not calibrated risk. The retrospective snapshot metrics reuse repeated customers and cannot establish generalization. The monitoring service records operational events but does not automatically assess LLM correctness. Real outcome validation, access policies/RLS, privacy review, human evaluation, drift analysis, alerting, and durable deployment operations remain future work. The supplied social-impact fields are absent and are not invented.
