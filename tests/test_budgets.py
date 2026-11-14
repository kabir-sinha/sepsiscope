"""C3 on synthetic data: lead-time percentiles, histogram, subgroup CIs (ADR 0024)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from sepsiscope.data.io import LABEL
from sepsiscope.evaluation import budgets
from sepsiscope.evaluation import metrics as m
from sepsiscope.evaluation.run import Cohort


def _cohort() -> Cohort:
    """Four septic patients (onset hour 20 + 6) caught 0, 3, 6 and 12 h early; one clean."""
    rows = []
    for k in range(5):
        hours = 40
        first_pos = 20 if k < 4 else 99
        rows += [{"pid": f"x{k}", "t": t, LABEL: int(t >= first_pos)} for t in range(hours)]
    return Cohort.of(pd.DataFrame(rows))


def test_lead_time_percentiles_and_histogram_by_hand() -> None:
    cohort = _cohort()
    onset = 20 + 6
    alerts = np.zeros(len(cohort.labels), dtype=bool)
    for k, lead in enumerate([0, 3, 6, 12]):
        alerts[k * 40 + onset - lead] = True
    weights = m.bootstrap_weights(cohort.n_patients, 20, 42)
    out = budgets.lead_times(cohort, alerts, weights)
    assert out["detected_patients"] == 4
    assert out["percentiles_hours"]["p50"] == float(np.percentile([0, 3, 6, 12], 50))
    assert out["percentiles_hours"]["p10"] == float(np.percentile([0, 3, 6, 12], 10))
    hist = out["histogram"]
    assert hist["lead_hours"] == list(range(13))
    assert [hist["patients"][h] for h in (0, 3, 6, 12)] == [1, 1, 1, 1]
    assert sum(hist["patients"]) == 4


def test_weighted_percentile_repeats_values() -> None:
    x = np.array([1.0, 5.0])
    assert budgets._wpercentile(x, np.array([3, 1]), 50) == 1.0
    assert np.isnan(budgets._wpercentile(x, np.array([0, 0]), 50))


def test_subgroups_have_cis_and_paired_difference() -> None:
    rng = np.random.default_rng(0)
    rows = []
    for k in range(80):
        first_pos = 15 if k % 3 == 0 else 99
        for t in range(30):
            rows.append(
                {
                    "pid": f"x{k:03d}",
                    "t": t,
                    LABEL: int(t >= first_pos),
                    "Gender": float(k % 2),
                    "Age": 50.0 if k % 4 < 2 else 70.0,
                }
            )
    cohort = Cohort.of(pd.DataFrame(rows))
    good = cohort.labels * 2.0 + rng.normal(0, 1, len(cohort.labels))
    weak = cohort.labels * 0.5 + rng.normal(0, 1, len(cohort.labels))
    scores = {"lgbm": good, "lr": weak}
    th = {k: float(np.quantile(v, 0.9)) for k, v in scores.items()}
    out = budgets.subgroups(cohort, scores, th, seed=42)
    assert set(out) == {"gender_0", "gender_1", "age_lt_65", "age_ge_65"}
    g = out["gender_0"]
    assert g["patients"] == 40
    assert "ci95" in g["models"]["lgbm"] and "auroc" in g["models"]["lgbm"]["ci95"]
    paired = g["paired_lgbm_minus_lr"]["auroc"]
    assert paired["point"] > 0 and paired["ci95"][0] <= paired["point"] <= paired["ci95"][1]
