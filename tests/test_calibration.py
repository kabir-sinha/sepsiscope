"""Calibrators: monotone, JSON round trip, isotonic JSON equals scikit-learn."""

from __future__ import annotations

import json
import warnings

import numpy as np
from sklearn.isotonic import IsotonicRegression

from sepsiscope.models.calibration import fit_isotonic, fit_platt, from_json, to_json


def data(seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    raw = rng.normal(-3, 1.5, 4000)
    labels = (rng.random(4000) < 1 / (1 + np.exp(-(1.3 * raw + 1.0)))).astype(int)
    return raw, labels


def test_platt_recovers_slope_and_is_increasing() -> None:
    raw, labels = data()
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # no deprecation or convergence warnings
        platt = fit_platt(raw, labels)
    assert 1.0 < platt.coef < 1.6
    grid = np.linspace(-8, 3, 50)
    assert np.all(np.diff(platt.predict(grid)) > 0)


def test_isotonic_json_equals_sklearn_and_is_monotone() -> None:
    raw, labels = data()
    iso = fit_isotonic(raw, labels)
    ref = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(raw, labels)
    grid = np.linspace(-12, 6, 500)  # includes points beyond both ends
    np.testing.assert_allclose(iso.predict(grid), ref.predict(grid), atol=1e-12)
    assert np.all(np.diff(iso.predict(grid)) >= 0)


def test_json_round_trip() -> None:
    raw, labels = data()
    platt, iso = fit_platt(raw, labels), fit_isotonic(raw, labels)
    p2, i2 = from_json(json.loads(json.dumps(to_json(platt, iso))))
    np.testing.assert_array_equal(p2.predict(raw), platt.predict(raw))
    np.testing.assert_array_equal(i2.predict(raw), iso.predict(raw))
