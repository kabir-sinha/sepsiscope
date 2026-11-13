"""Baselines: modified NEWS2 (max 17) band edges from RCP Chart 1, SIRS, modified qSOFA (max 2)."""

from __future__ import annotations

import json
from dataclasses import asdict

import numpy as np
import pandas as pd
import pytest

from sepsiscope.models.baselines import (
    NEWS2_MAX,
    LogisticJSON,
    band_points,
    fit_logistic,
    fit_news2_probability,
    news2,
    news2_probability,
    on_oxygen,
    qsofa,
    sirs,
)

NAN = np.nan


def rows(**columns: list[float]) -> pd.DataFrame:
    n = len(next(iter(columns.values())))
    base = {c: [NAN] * n for c in ("Resp", "O2Sat", "SBP", "HR", "Temp", "FiO2", "FiO2__hsl")}
    base |= {"PaCO2": [NAN] * n, "WBC": [NAN] * n}
    base |= columns
    return pd.DataFrame(base).astype(np.float32)


@pytest.mark.parametrize(
    ("column", "values", "expected"),
    [
        ("Resp", [8, 9, 11, 12, 20, 21, 24, 25], [3, 1, 1, 0, 0, 2, 2, 3]),
        ("O2Sat", [91, 92, 93, 94, 95, 96, 100], [3, 2, 2, 1, 1, 0, 0]),
        ("SBP", [90, 91, 100, 101, 110, 111, 219, 219.5, 220], [3, 2, 2, 1, 1, 0, 0, 3, 3]),
        ("HR", [40, 41, 50, 51, 90, 91, 110, 111, 130, 131], [3, 1, 1, 0, 0, 1, 1, 2, 2, 3]),
        (
            "Temp",
            [35.0, 35.05, 35.1, 36.0, 36.1, 38.0, 38.1, 39.0, 39.1],
            [3, 1, 1, 1, 0, 0, 1, 1, 2],
        ),
    ],
)
def test_news2_band_edges(column: str, values: list[float], expected: list[int]) -> None:
    assert news2(rows(**{column: values})).tolist() == expected


def test_news2_missing_scores_zero_and_maximum_is_17() -> None:
    assert news2(rows(Resp=[NAN])).tolist() == [0]
    worst = rows(Resp=[30], O2Sat=[85], SBP=[80], HR=[150], Temp=[34], FiO2=[0.6], FiO2__hsl=[0])
    assert news2(worst).tolist() == [NEWS2_MAX] == [17]


def test_band_points_rejects_nothing_and_keeps_nan_at_zero() -> None:
    assert band_points(np.array([NAN, 5.0]), (8,), (3, 0)).tolist() == [0, 3]


def test_oxygen_rule_main_and_24h_sensitivity() -> None:
    f = rows(FiO2=[0.21, 0.4, 0.4, 0.4, 0.4, NAN], FiO2__hsl=[0, 0, 1, 24, 25, NAN])
    assert on_oxygen(f).tolist() == [False, True, False, False, False, False]
    assert on_oxygen(f, carry_hours=24).tolist() == [False, True, True, True, False, False]


def test_sirs_criteria() -> None:
    f = rows(
        Temp=[38.1, 36.0, 35.9, NAN, 38.0],
        HR=[91, 90, NAN, NAN, NAN],
        Resp=[21, 20, NAN, NAN, NAN],
        PaCO2=[NAN, 32, 31, NAN, NAN],
        WBC=[12.1, 4, 3.9, NAN, 12.0],
    )
    assert sirs(f).tolist() == [4, 0, 3, 0, 0]


def test_qsofa_criteria() -> None:
    f = rows(Resp=[22, 21, NAN, 30], SBP=[100, 101, 90, NAN])
    assert qsofa(f).tolist() == [2, 0, 1, 1]


def test_logistic_json_matches_sklearn_and_round_trips() -> None:
    rng = np.random.default_rng(0)
    n = 400
    frame = pd.DataFrame({"a": rng.normal(size=n), "b": rng.normal(size=n), "c": NAN})
    frame.loc[rng.random(n) < 0.3, "a"] = NAN
    frame["y"] = (rng.random(n) < 1 / (1 + np.exp(-2 * frame["b"]))).astype(int)
    pipe, js = fit_logistic(frame, ["a", "b", "c"], "y", seed=42)
    expected = pipe.predict_proba(frame[["a", "b", "c"]].to_numpy())[:, 1]
    np.testing.assert_allclose(js.predict_proba(frame), expected, rtol=1e-12, atol=1e-12)
    again = LogisticJSON(**json.loads(json.dumps(asdict(js))))
    np.testing.assert_array_equal(again.predict_proba(frame), js.predict_proba(frame))


def test_imputation_uses_training_rows_only() -> None:
    train = pd.DataFrame({"a": [1.0, 2.0, 3.0, NAN], "y": [0, 1, 0, 1]})
    _, js = fit_logistic(train, ["a"], "y", seed=42)
    assert js.medians == [2.0]


def test_news2_probability_is_increasing() -> None:
    scores = np.repeat(np.arange(10), 50)
    labels = (np.random.default_rng(0).random(500) < scores / 12).astype(int)
    coef, intercept = fit_news2_probability(scores, labels, seed=42)
    p = news2_probability(np.arange(10), coef, intercept)
    assert coef > 0 and np.all(np.diff(p) > 0)
