"""Class-conditional (Mondrian) split conformal prediction for deferral (ADR 0020, 0024).

For an hour with calibrated probability p (Platt), the nonconformity of label y is
``1 - p_hat(y)``: ``p`` for label 0 and ``1 - p`` for label 1. For each class separately,
the threshold ``q_y`` is the ceil((n_y + 1)(1 - alpha))-th smallest nonconformity among the
calibration hours **with that label** (Vovk et al. 2005; Angelopoulos & Bates 2021). The
prediction set of an hour holds every label whose nonconformity is at most its class
threshold. Under exchangeability, each class's true label is in the set with probability
at least 1 - alpha.

Deferral rule (ADR 0024 item 3): an hour is **deferred** ("not sure, ask a clinician") when
its set is {0, 1} or empty; otherwise the model decides, with the headline threshold.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ClassThresholds:
    """Per-class conformal thresholds for one alpha."""

    alpha: float
    q0: float  # label 0 is in the set when p <= q0
    q1: float  # label 1 is in the set when 1 - p <= q1
    n0: int
    n1: int


def _quantile(scores: np.ndarray, alpha: float) -> float:
    """The ceil((n + 1)(1 - alpha))-th smallest score; +inf when that rank exceeds n."""
    n = len(scores)
    k = math.ceil((n + 1) * (1 - alpha))
    if n == 0 or k > n:
        return math.inf
    return float(np.sort(scores, kind="stable")[k - 1])


def fit(probs: np.ndarray, labels: np.ndarray, alpha: float) -> ClassThresholds:
    """Thresholds from calibration hours (source hospital's calibration split only)."""
    p = np.asarray(probs, dtype=np.float64)
    y = np.asarray(labels).astype(bool)
    return ClassThresholds(
        alpha=alpha,
        q0=_quantile(p[~y], alpha),  # nonconformity of label 0 = p
        q1=_quantile(1.0 - p[y], alpha),  # nonconformity of label 1 = 1 - p
        n0=int((~y).sum()),
        n1=int(y.sum()),
    )


def prediction_sets(probs: np.ndarray, th: ClassThresholds) -> tuple[np.ndarray, np.ndarray]:
    """(label 0 in set, label 1 in set) per hour."""
    p = np.asarray(probs, dtype=np.float64)
    return p <= th.q0, (1.0 - p) <= th.q1


def deferred(probs: np.ndarray, th: ClassThresholds) -> np.ndarray:
    """True where the set is {0, 1} or empty (ADR 0024 item 3)."""
    has0, has1 = prediction_sets(probs, th)
    return np.asarray(has0 == has1, dtype=bool)


def coverage(probs: np.ndarray, labels: np.ndarray, th: ClassThresholds) -> dict[str, float]:
    """Conformal coverage per class: share of hours whose true label is in the set."""
    has0, has1 = prediction_sets(probs, th)
    y = np.asarray(labels).astype(bool)
    return {
        "label0": float(has0[~y].mean()) if (~y).any() else math.nan,
        "label1": float(has1[y].mean()) if y.any() else math.nan,
    }
