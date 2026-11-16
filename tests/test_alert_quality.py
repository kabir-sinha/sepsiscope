"""Alert-quality statistics on a hand-checked toy cohort, and the committed files."""

from __future__ import annotations

import json

import numpy as np
import pytest

from sepsiscope.config import REPO_ROOT
from sepsiscope.evaluation.alert_quality import block, patient_counts, statistics

RESULTS = REPO_ROOT / "reports" / "results"

# Three patients, 20 hours each. P0 septic (label from hour 10, so onset at hour 16),
# alerts at hours 12-13 (timely); P1 never septic, alerts at hours 2-3 (false);
# P2 never septic, no alerts.
HOURS = 20
patient = np.repeat(np.arange(3), HOURS)
labels = np.zeros(3 * HOURS, dtype=np.int64)
labels[10:20] = 1
alerts = np.zeros(3 * HOURS, dtype=bool)
alerts[[12, 13, HOURS + 2, HOURS + 3]] = True


def test_toy_cohort_by_hand() -> None:
    s = statistics(patient_counts(labels, alerts, patient), np.ones(3))
    assert s["ppv_hour"] == pytest.approx(2 / 4)
    assert s["label1_share_hour"] == pytest.approx(10 / 60)
    assert s["lift_hour"] == pytest.approx(0.5 / (10 / 60))
    assert s["npv_hour"] == pytest.approx(48 / 56)  # 56 quiet hours, 8 of them label 1
    assert s["precision_patient"] == pytest.approx(1 / 2)
    assert s["septic_share_patient"] == pytest.approx(1 / 3)
    assert s["lift_patient"] == pytest.approx(1.5)
    assert s["patients_alerted_per_septic_found"] == pytest.approx(2.0)
    assert s["sensitivity_patient_any_alert"] == pytest.approx(1.0)
    assert s["timely_sensitivity"] == pytest.approx(1.0)
    assert s["alert_hours_per_septic_found"] == pytest.approx(4.0)
    assert s["alert_hours_per_timely_detection"] == pytest.approx(4.0)


def test_weights_resample_patients() -> None:
    c = patient_counts(labels, alerts, patient)
    s = statistics(c, np.array([0.0, 2.0, 1.0]))  # septic patient left out
    assert s["precision_patient"] == 0.0 and s["ppv_hour"] == 0.0
    out = block(c, np.array([[1, 1, 1], [0, 2, 1], [3, 0, 0]], dtype=np.int32))
    assert out["counts"]["septic_patients_alerted"] == 1
    assert out["point"]["precision_patient"] == pytest.approx(0.5)


@pytest.mark.parametrize("direction", ["A2B", "B2A"])
def test_committed_file_matches_the_headline(direction: str) -> None:
    doc = json.loads((RESULTS / f"alert_quality_{direction}.json").read_text("utf-8"))
    assert set(doc["models"]) == {"lgbm", "lr", "news2"}
    assert doc["bootstrap_resamples"] == 1000 and doc["seed"] == 42
    for model, block_ in doc["models"].items():
        head = json.loads((RESULTS / f"{model}_{direction}.json").read_text("utf-8"))
        strict = head["strict_external"]
        assert block_["threshold"] == strict["threshold"]
        assert block_["point"]["timely_sensitivity"] == pytest.approx(
            strict["point"]["timely_sensitivity"]
        )
        c = block_["counts"]
        assert c["alert_hours"] / c["hours"] == pytest.approx(strict["point"]["alert_rate"])
        lo, hi = block_["ci95"]["precision_patient"]
        assert lo <= block_["point"]["precision_patient"] <= hi
