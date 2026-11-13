"""Calibration of LightGBM raw scores (ADR 0022 items 1-2, plan B3).

Both calibrators are fitted on the source hospital's **calibration** split only, on the
model's raw log-odds, and stored as plain JSON numbers (never pickle).

- **Platt scaling** (headline): probability = sigmoid(a * raw + b). With a > 0 it is
  strictly increasing, so it keeps the ordering of the raw scores and the per-alert
  explanations (computed on raw log-odds) stay valid.
- **Isotonic regression** (pre-specified sensitivity analysis): a non-decreasing step-wise
  linear map; it can create ties, which the tie-safe threshold handles.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression


@dataclass(frozen=True)
class Platt:
    coef: float
    intercept: float

    def predict(self, raw: np.ndarray) -> np.ndarray:
        z = self.coef * np.asarray(raw, dtype=np.float64) + self.intercept
        return 1.0 / (1.0 + np.exp(-z))


@dataclass(frozen=True)
class Isotonic:
    x: list[float]
    y: list[float]

    def predict(self, raw: np.ndarray) -> np.ndarray:
        """Linear interpolation between the fitted points; constant beyond both ends."""
        return np.interp(np.asarray(raw, dtype=np.float64), self.x, self.y)


def fit_platt(raw: np.ndarray, labels: np.ndarray) -> Platt:
    """Unpenalised one-feature logistic regression on the raw scores."""
    lr = LogisticRegression(C=np.inf, max_iter=1000)
    lr.fit(np.asarray(raw, dtype=np.float64).reshape(-1, 1), labels)
    return Platt(float(lr.coef_[0][0]), float(lr.intercept_[0]))


def fit_isotonic(raw: np.ndarray, labels: np.ndarray) -> Isotonic:
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0, increasing=True)
    iso.fit(np.asarray(raw, dtype=np.float64), np.asarray(labels, dtype=np.float64))
    return Isotonic([float(v) for v in iso.X_thresholds_], [float(v) for v in iso.y_thresholds_])


def to_json(platt: Platt, isotonic: Isotonic) -> dict[str, object]:
    return {
        "fitted_on": "source calibration split, raw log-odds",
        "platt": asdict(platt),
        "isotonic": asdict(isotonic),
    }


def from_json(doc: dict[str, object]) -> tuple[Platt, Isotonic]:
    p, i = doc["platt"], doc["isotonic"]
    assert isinstance(p, dict) and isinstance(i, dict)
    return Platt(**p), Isotonic(**i)
