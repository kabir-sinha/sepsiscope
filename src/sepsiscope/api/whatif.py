"""What-if alert budgets for the demo (plan v3, D1).

For each budget from 1 % to 10 % of patient-hours, the alert threshold is chosen on the
**training hospital's validation split only** (hospital B for direction B2A), with the same
tie-safe rule as the evaluation (``metrics.budget_threshold``). The demo then shows how each
held-out patient's alerts, false alarms and verdicts change. At 5 % this reproduces the
committed headline threshold exactly (tested in the build).
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from sepsiscope.api.verdict import verdict
from sepsiscope.evaluation.metrics import budget_threshold

BUDGETS: tuple[float, ...] = tuple(round(k / 100, 2) for k in range(1, 11))


def budget_thresholds(
    validation_scores: np.ndarray, budgets: Sequence[float] = BUDGETS
) -> list[float]:
    """One threshold per budget, from the validation-split scores only."""
    return [
        budget_threshold(np.asarray(validation_scores, dtype=np.float64), b)[0] for b in budgets
    ]


def patient_what_if(
    values: Sequence[float] | np.ndarray, thresholds: Sequence[float], onset: int | None
) -> list[dict[str, object]]:
    """Alert hours and verdict of one patient at every threshold."""
    arr = np.asarray(values, dtype=np.float64)
    out: list[dict[str, object]] = []
    for thr in thresholds:
        alerts = [int(h) for h in np.flatnonzero(arr >= thr)]
        out.append({"alert_hours": alerts, "verdict": verdict(alerts, onset).as_dict()})
    return out
