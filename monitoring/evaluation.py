from __future__ import annotations

from functools import lru_cache
from typing import Literal

import pandas as pd

from app.banking import assess, load_bundle

Horizon = Literal["30d", "90d"]


@lru_cache(maxsize=1)
def _evaluation_source() -> tuple[pd.DataFrame, pd.Series]:
    snapshots = load_bundle().snapshots
    categories = snapshots.apply(
        lambda row: assess(row.to_dict())["risk_category"], axis=1
    )
    return snapshots, categories


def evaluate_snapshots(
    snapshots: pd.DataFrame, categories: pd.Series, horizon: Horizon
) -> dict:
    if horizon not in ("30d", "90d"):
        raise ValueError("horizon must be 30d or 90d")
    if snapshots.duplicated(["customer_id", "snapshot_date"]).any():
        raise ValueError("customer/snapshot records must be unique")

    label = "churn_within_" + horizon
    observed = "label_observed_" + horizon
    eligible_mask = snapshots[observed].eq(1) & snapshots[label].notna()
    evaluated = pd.DataFrame(
        {
            "customer_id": snapshots["customer_id"],
            "risk_category": categories.reindex(snapshots.index),
            "churned": pd.to_numeric(snapshots[label], errors="coerce"),
        },
        index=snapshots.index,
    ).loc[eligible_mask]

    total_churned = int(evaluated["churned"].sum())
    by_category = []
    for category in ("Low", "Medium", "High"):
        group = evaluated[evaluated["risk_category"] == category]
        count = len(group)
        churned = int(group["churned"].sum())
        by_category.append(
            {
                "category": category,
                "evaluated_records": count,
                "churned_records": churned,
                "churn_rate": churned / count if count else None,
            }
        )

    high_records = next(row["evaluated_records"] for row in by_category if row["category"] == "High")
    high_churned = next(row["churned_records"] for row in by_category if row["category"] == "High")
    total_records = len(snapshots)
    return {
        "horizon": horizon,
        "record_unit": "unique customer and snapshot date",
        "total_records": total_records,
        "evaluated_records": len(evaluated),
        "unavailable_outcome_records": total_records - len(evaluated),
        "unobserved_records": int((~snapshots[observed].eq(1)).sum()),
        "missing_outcome_records": int(snapshots[label].isna().sum()),
        "unique_evaluated_customers": int(evaluated["customer_id"].nunique()),
        "high_risk_records": high_records,
        "high_risk_churned": high_churned,
        "churned_records": total_churned,
        "high_risk_precision": high_churned / high_records if high_records else None,
        "high_risk_recall": high_churned / total_churned if total_churned else None,
        "risk_categories": by_category,
        "limitations": [
            "Synthetic retrospective snapshot-level results; not real-world performance.",
            "Risk points are heuristic indicators, not probabilities.",
            "Repeated customers can have multiple distinct monthly snapshots.",
        ],
    }


def prediction_evaluation(horizon: Horizon) -> dict:
    snapshots, categories = _evaluation_source()
    return evaluate_snapshots(snapshots, categories, horizon)
