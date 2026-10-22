import pandas as pd
import pytest

from monitoring.evaluation import evaluate_snapshots


@pytest.fixture
def snapshots():
    return pd.DataFrame(
        [
            ("C1", "2025-01-01", 1, 1, 1, 1),
            ("C2", "2025-01-01", 0, 1, None, 0),
            ("C3", "2025-01-01", 1, 1, 0, 1),
            ("C4", "2025-01-01", 0, 1, None, 0),
            ("C5", "2025-01-01", 0, 1, 0, 1),
            ("C6", "2025-01-01", 1, 1, None, 0),
        ],
        columns=[
            "customer_id",
            "snapshot_date",
            "churn_within_30d",
            "label_observed_30d",
            "churn_within_90d",
            "label_observed_90d",
        ],
    )


def test_evaluation_uses_observed_labels_and_high_only_metrics(snapshots):
    categories = pd.Series(["High", "High", "Medium", "Medium", "Low", "Low"])

    result = evaluate_snapshots(snapshots, categories, "30d")

    assert result["evaluated_records"] == 6
    assert result["unavailable_outcome_records"] == 0
    assert result["high_risk_records"] == 2
    assert result["high_risk_churned"] == 1
    assert result["churned_records"] == 3
    assert result["high_risk_precision"] == pytest.approx(0.5)
    assert result["high_risk_recall"] == pytest.approx(1 / 3)
    assert [row["churn_rate"] for row in result["risk_categories"]] == [0.5, 0.5, 0.5]


def test_90_day_evaluation_excludes_unobserved_outcomes(snapshots):
    categories = pd.Series(["High", "High", "Medium", "Medium", "Low", "Low"])

    result = evaluate_snapshots(snapshots, categories, "90d")

    assert result["evaluated_records"] == 3
    assert result["unavailable_outcome_records"] == 3
    assert result["unobserved_records"] == 3
    assert result["missing_outcome_records"] == 3
    assert result["high_risk_precision"] == 1
    assert result["high_risk_recall"] == 1


def test_evaluation_rejects_duplicate_customer_snapshot_pairs(snapshots):
    duplicate = pd.concat([snapshots, snapshots.iloc[[0]]], ignore_index=True)
    categories = pd.Series(["High"] * len(duplicate))

    with pytest.raises(ValueError, match="must be unique"):
        evaluate_snapshots(duplicate, categories, "30d")
