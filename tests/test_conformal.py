"""Class-conditional conformal deferral on synthetic data (ADR 0020, ADR 0024)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from sepsiscope.evaluation import deferral
from sepsiscope.trust import conformal


def test_quantile_rank_and_infinite_threshold() -> None:
    scores = np.arange(1, 10, dtype=float)  # n = 9: rank ceil(10 * 0.9) = 9 -> the maximum
    assert conformal._quantile(scores, 0.10) == 9.0
    assert conformal._quantile(scores[:8], 0.10) == math.inf  # rank 9 > n = 8
    assert conformal._quantile(np.array([]), 0.10) == math.inf


@pytest.mark.parametrize("alpha", [0.05, 0.10, 0.20])
def test_per_class_coverage_holds_on_exchangeable_data(alpha: float) -> None:
    rng = np.random.default_rng(42)
    n = 40_000
    p = rng.beta(0.5, 8.0, n)  # skewed like a rare outcome
    y = (rng.random(n) < p).astype(int)
    cal, test = slice(0, n // 2), slice(n // 2, n)
    th = conformal.fit(p[cal], y[cal], alpha)
    cov = conformal.coverage(p[test], y[test], th)
    assert cov["label0"] >= 1 - alpha - 0.02
    assert cov["label1"] >= 1 - alpha - 0.03  # fewer positive hours, more noise


def test_deferral_rule_both_or_empty() -> None:
    th = conformal.ClassThresholds(alpha=0.1, q0=0.3, q1=0.5, n0=1, n1=1)
    p = np.array([0.1, 0.4, 0.6, 0.45])
    has0, has1 = conformal.prediction_sets(p, th)
    # 0.1: {0}; 0.4: {} (0.4 > q0, 0.6 > q1); 0.6: {1}; 0.45: {} -> deferred
    assert has0.tolist() == [True, False, False, False]
    assert has1.tolist() == [False, False, True, False]
    assert conformal.deferred(p, th).tolist() == [False, True, False, True]
    both = conformal.ClassThresholds(alpha=0.1, q0=0.9, q1=0.9, n0=1, n1=1)
    assert conformal.deferred(np.array([0.5]), both).tolist() == [True]  # {0, 1}


def test_criterion_needs_all_three_parts() -> None:
    def block(rate: float, s0: float, s1: float, util: float) -> dict[str, object]:
        return {
            "point": {
                "deferral_rate": rate,
                "share_not_deferred_label0": s0,
                "share_not_deferred_label1": s1,
                "utility": util,
            }
        }

    assert deferral.criterion(block(0.2, 0.8, 0.75, 0.30), 0.27)["useful"] is True
    assert deferral.criterion(block(0.31, 0.8, 0.75, 0.30), 0.27)["useful"] is False
    assert deferral.criterion(block(0.2, 0.8, 0.65, 0.30), 0.27)["useful"] is False
    assert deferral.criterion(block(0.2, 0.8, 0.75, 0.27), 0.27)["useful"] is False
