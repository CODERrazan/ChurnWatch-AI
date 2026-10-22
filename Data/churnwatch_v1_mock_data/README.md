# ChurnWatch AI — Synthetic Banking Mock Data v1

All data is synthetic and for development/testing only. It is not real banking data.
Social influence / social impact features are intentionally excluded in this first version and should be designed as a separate service/data contract later.

## Files
- customers.csv: 5,000 customer profiles.
- monthly_snapshots.csv: monthly feature snapshots, behavioral signals, and forward-looking target labels.
- churn_outcomes.csv: synthetic event outcome, event date, and generated scenario/reason.
- data_dictionary.csv: column names, dtypes, and descriptions.

## Data design
- Up to 15 monthly snapshots per customer, beginning 2025-08-01.
- Synthetic scenarios: stable, declining engagement, service friction, financial outflow, mixed risk, and competitor pressure.
- Features include customer profile, transaction/digital behavior, balances, failed transactions, support issues, satisfaction, salary flow, external transfers, app stability, fees, overdraft, recurring payments, and branch visits.
- Target labels are based on synthetic churn dates and are null if a full prediction horizon is not observable.
- `label_observed_30d` and `label_observed_90d` indicate full outcome-window availability.

## Important caveats
- The data generator is synthetic and intentionally includes patterns; metrics from this dataset do not demonstrate real-world performance.
- `synthetic_scenario`, `synthetic_churn_reason`, and `synthetic_churn_date` are outcome-side fields and must not be used as model features.
- Do not use labels or future information as inputs.
- Group snapshots by customer and use chronological holdout evaluation to reduce leakage.
- External transfers are not proof of competitor use.
- Social impact is not included yet; add it later as a separate signal/service, then evaluate whether it improves predictive performance.

## Recommended first model
Train separate 30-day and 90-day classifiers, filter each target using its `label_observed_*` flag, exclude identifiers/metadata/labels/outcome fields, and report ROC-AUC, PR-AUC, precision, recall, and calibration on a time-based held-out set.
