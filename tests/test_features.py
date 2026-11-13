"""Causal hourly features: no look-ahead, excluded columns absent, deterministic output."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sepsiscope.config import load_config
from sepsiscope.data.io import COLUMNS, MEASUREMENTS
from sepsiscope.features.causal import (
    ICU_TIME,
    KEYS,
    FeatureInputError,
    causal_features,
    feature_specs,
    schema_document,
)
from sepsiscope.features.pipeline import write_features

SWITCHES = load_config().features


def synthetic_frame(n_patients: int = 3, hours: int = 20, seed: int = 0) -> pd.DataFrame:
    """Clean-table layout with random values and about 60 % missing (never real data)."""
    rng = np.random.default_rng(seed)
    rows = []
    for p in range(n_patients):
        for t in range(hours - p):  # unequal stay lengths
            rows.append({"pid": f"p{p:06d}", "hospital": "A", "t": t})
    frame = pd.DataFrame(rows)
    n = len(frame)
    for col in COLUMNS:
        values = rng.normal(50, 20, n).astype(np.float32)
        if col in MEASUREMENTS:
            values[rng.random(n) < 0.6] = np.nan
        frame[col] = values
    frame["Gender"] = rng.integers(0, 2, n).astype(np.float32)
    frame["SepsisLabel"] = 0
    return frame


def test_features_never_look_ahead() -> None:
    base = synthetic_frame()
    before = causal_features(base, SWITCHES)
    rng = np.random.default_rng(1)
    for cut in (0, 3, 7, 12):
        changed = base.copy()
        later = changed["t"] > cut
        for col in MEASUREMENTS:
            # Fill some later gaps, erase some later values, change the rest.
            noise = rng.normal(0, 30, later.sum()).astype(np.float32)
            changed.loc[later, col] = np.where(rng.random(later.sum()) < 0.3, np.nan, noise)
        after = causal_features(changed, SWITCHES)
        upto = before["t"] <= cut
        pd.testing.assert_frame_equal(
            before[upto].reset_index(drop=True), after[upto].reset_index(drop=True)
        )


def test_excluded_columns_absent_unless_ablation() -> None:
    feats = causal_features(synthetic_frame(), SWITCHES)
    assert not set(ICU_TIME) & set(feats.columns)
    assert list(feats.columns[: len(KEYS)]) == list(KEYS)
    ablation = SWITCHES.model_copy(update={"icu_time": True})
    assert set(ICU_TIME) <= set(causal_features(synthetic_frame(), ablation).columns)


def test_features_are_float32_and_match_the_spec() -> None:
    feats = causal_features(synthetic_frame(), SWITCHES)
    names = [s.name for s in feature_specs(SWITCHES)]
    assert list(feats.columns[len(KEYS) :]) == names
    assert all(feats[n].dtype == np.float32 for n in names)
    doc = schema_document(SWITCHES, names)
    assert doc["count"] == len(names)
    assert "ICULOS" not in json.dumps(doc["features"])


def test_output_is_deterministic(tmp_path: Path) -> None:
    frame = synthetic_frame()
    write_features(causal_features(frame, SWITCHES), tmp_path / "a.parquet")
    write_features(causal_features(frame.copy(), SWITCHES), tmp_path / "b.parquet")
    assert (tmp_path / "a.parquet").read_bytes() == (tmp_path / "b.parquet").read_bytes()


def test_hand_computed_values() -> None:
    frame = synthetic_frame(n_patients=2, hours=9)
    first = frame["pid"] == "p000000"
    hr = [80, np.nan, 90, np.nan, np.nan, 100, 110, np.nan, 120]
    frame.loc[first, "HR"] = hr
    frame.loc[first, "SBP"] = [100, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, 60]
    frame.loc[~first, "HR"] = 999.0  # the other patient must never leak in
    f = causal_features(frame, SWITCHES)[first].reset_index(drop=True)
    assert f["HR"].tolist() == [80, 80, 90, 90, 90, 100, 110, 110, 120]
    assert f["HR__hsl"].tolist() == [0, 1, 0, 1, 2, 0, 0, 1, 0]
    assert f["HR__n"].tolist() == [1, 1, 2, 2, 2, 3, 4, 4, 5]
    # Window t-5..t at t=5 holds 80, 90, 100; at t=8 holds 100, 110, 120.
    assert f["HR__mean6"][5] == pytest.approx(90.0)
    assert f["HR__mean6"][8] == pytest.approx(110.0)
    assert f["HR__std6"][8] == pytest.approx(10.0)
    assert np.isnan(f["HR__std6"][0])  # one value: no SD
    assert np.isnan(f["HR__d6"][5]) and f["HR__d6"][8] == pytest.approx(120 - 90)
    assert f["shock_index"][0] == pytest.approx(0.8) and f["shock_index"][8] == pytest.approx(2.0)


def test_unsorted_or_gapped_input_is_rejected() -> None:
    frame = synthetic_frame()
    with pytest.raises(FeatureInputError):
        causal_features(frame.iloc[::-1].reset_index(drop=True), SWITCHES)
    gapped = frame.drop(index=3).reset_index(drop=True)
    with pytest.raises(FeatureInputError):
        causal_features(gapped, SWITCHES)
