"""Explanations: contributions add up to the raw score; reasons are ordered; chunking is exact."""

from __future__ import annotations

import lightgbm as lgb
import numpy as np

from sepsiscope.models import lgbm
from sepsiscope.trust import explain


def model() -> tuple[lgb.Booster, np.ndarray, list[str]]:
    rng = np.random.default_rng(0)
    x = rng.normal(size=(3000, 6)).astype(np.float32)
    x[rng.random(x.shape) < 0.2] = np.nan
    y = (rng.random(3000) < 1 / (1 + np.exp(-(np.nan_to_num(x[:, 0]) * 2 - 2)))).astype(int)
    names = [f"f{i}" for i in range(6)]
    params = lgbm.make_params({"num_leaves": 7, "min_child_samples": 10})
    return lgbm.fit(x, y, params, 50, feature_names=names), x, names


def test_contributions_add_up_to_raw_score() -> None:
    booster, x, _ = model()
    assert explain.additivity_error(booster, x, chunk=700) <= 1e-9


def test_chunking_does_not_change_the_mean() -> None:
    booster, x, _ = model()
    rows = np.arange(len(x)) % 3 == 0
    a = explain.mean_abs_contribution(booster, x, rows, chunk=128)
    b = explain.mean_abs_contribution(booster, x, rows, chunk=10_000)
    np.testing.assert_allclose(a, b, rtol=1e-12)
    assert int(np.argmax(a)) == 0  # the only informative feature dominates


def test_reasons_are_ordered_and_consistent() -> None:
    booster, x, names = model()
    exps = explain.explain_rows(booster, x[:20], names, top=3)
    raw = booster.predict(x[:20], raw_score=True)
    for e, r in zip(exps, raw, strict=True):
        mags = [abs(reason.contribution) for reason in e.reasons]
        assert mags == sorted(mags, reverse=True) and len(e.reasons) == 3
        assert abs(e.raw_score - r) <= 1e-9
