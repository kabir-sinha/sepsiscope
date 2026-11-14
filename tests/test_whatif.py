"""What-if alert budgets: thresholds from validation scores, alerts and verdicts per budget."""

from __future__ import annotations

import itertools

import numpy as np

from sepsiscope.api.whatif import BUDGETS, budget_thresholds, patient_what_if
from sepsiscope.evaluation.metrics import budget_threshold


def test_budgets_are_one_to_ten_percent() -> None:
    assert BUDGETS == (0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.1)


def test_thresholds_match_the_evaluation_rule_and_fall_with_budget() -> None:
    scores = np.random.default_rng(0).random(5000)
    thr = budget_thresholds(scores)
    assert thr[4] == budget_threshold(scores, 0.05)[0]  # same rule as the headline
    assert all(a >= b for a, b in itertools.pairwise(thr))  # bigger budget, lower bar
    for t, b in zip(thr, BUDGETS, strict=True):
        assert np.mean(scores >= t) <= b


def test_alerts_and_verdicts_change_with_the_threshold() -> None:
    risk = [0.01, 0.02, 0.04, 0.06, 0.09, 0.12]  # onset at hour 5
    rows = patient_what_if(risk, [0.10, 0.05, 0.03], onset=5)
    assert [r["alert_hours"] for r in rows] == [[5], [3, 4, 5], [2, 3, 4, 5]]
    assert [r["verdict"]["lead_hours"] for r in rows] == [0, 2, 3]
    quiet = patient_what_if([0.01, 0.02], [0.05, 0.015], onset=None)
    assert [r["verdict"]["false_alarm_hours"] for r in quiet] == [0, 1]
