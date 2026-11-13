"""Baselines (protocol section 7): modified NEWS2, SIRS, modified qSOFA, logistic regression.

All rule scores read the causal feature table (``sepsiscope.features``): vital signs and
labs are the last value carried forward within the patient, so a score at hour t uses only
hours <= t. A value that has never been measured scores 0 points (ADR 0018).

NEWS2 bands are from RCP NEWS2 Chart 1 (Royal College of Physicians 2017), SpO2 Scale 1,
verified against the official chart on 2026-11-13. They are applied upper-inclusive: a
value belongs to the first band whose upper limit it does not exceed (protocol section 7),
so 35.05 degC scores as 35.1-36.0 and a systolic of 219.5 scores as >= 220.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# (upper limits of every band but the last, points per band); len(points) = len(uppers) + 1
NEWS2_BANDS: dict[str, tuple[tuple[float, ...], tuple[int, ...]]] = {
    "Resp": ((8, 11, 20, 24), (3, 1, 0, 2, 3)),
    "O2Sat": ((91, 93, 95), (3, 2, 1, 0)),  # SpO2 Scale 1
    "SBP": ((90, 100, 110, 219), (3, 2, 1, 0, 3)),
    "HR": ((40, 50, 90, 110, 130), (3, 1, 0, 1, 2, 3)),
    "Temp": ((35.0, 36.0, 38.0, 39.0), (3, 1, 0, 1, 2)),
}
NEWS2_OXYGEN_POINTS = 2
NEWS2_MAX = 17  # 3 + 3 + 2 + 3 + 3 + 3; no consciousness item
ROOM_AIR_FIO2 = np.float32(0.21)  # compared in float32, the storage type of FiO2


def band_points(values: np.ndarray, uppers: Sequence[float], points: Sequence[int]) -> np.ndarray:
    """Points of the first band whose upper limit the value does not exceed; NaN scores 0."""
    v = np.asarray(values, dtype=np.float64)
    idx = np.searchsorted(np.asarray(uppers, dtype=np.float64), np.nan_to_num(v), side="left")
    out = np.asarray(points, dtype=np.int16)[idx]
    out[np.isnan(v)] = 0
    return out


def on_oxygen(features: pd.DataFrame, carry_hours: int | None = None) -> np.ndarray:
    """FiO2 > 0.21. Main rule: only an FiO2 measured in this hour counts (ADR 0018).

    ``carry_hours=24`` is the sensitivity analysis: the last FiO2 counts for up to 24 hours.
    """
    fio2 = features["FiO2"].to_numpy(dtype=np.float32)
    since = features["FiO2__hsl"].to_numpy(dtype=np.float64)
    limit = 0 if carry_hours is None else carry_hours
    usable = ~np.isnan(since) & (since <= limit)
    result: np.ndarray = usable & (np.nan_to_num(fio2) > ROOM_AIR_FIO2)
    return result


def news2(features: pd.DataFrame, carry_hours: int | None = None) -> np.ndarray:
    """Modified NEWS2, 0-17."""
    total = np.zeros(len(features), dtype=np.int16)
    for column, (uppers, points) in NEWS2_BANDS.items():
        total += band_points(features[column].to_numpy(), uppers, points)
    total += np.where(on_oxygen(features, carry_hours), NEWS2_OXYGEN_POINTS, 0).astype(np.int16)
    return total


def _gt(features: pd.DataFrame, column: str, limit: float) -> np.ndarray:
    v = features[column].to_numpy(dtype=np.float64)
    return ~np.isnan(v) & (v > limit)


def _lt(features: pd.DataFrame, column: str, limit: float) -> np.ndarray:
    v = features[column].to_numpy(dtype=np.float64)
    return ~np.isnan(v) & (v < limit)


def _ge(features: pd.DataFrame, column: str, limit: float) -> np.ndarray:
    v = features[column].to_numpy(dtype=np.float64)
    return ~np.isnan(v) & (v >= limit)


def _le(features: pd.DataFrame, column: str, limit: float) -> np.ndarray:
    v = features[column].to_numpy(dtype=np.float64)
    return ~np.isnan(v) & (v <= limit)


def sirs(features: pd.DataFrame) -> np.ndarray:
    """SIRS criteria met, 0-4 (Sepsis-3 Box 1; no immature-band criterion)."""
    criteria = (
        _gt(features, "Temp", 38) | _lt(features, "Temp", 36),
        _gt(features, "HR", 90),
        _gt(features, "Resp", 20) | _lt(features, "PaCO2", 32),
        _gt(features, "WBC", 12) | _lt(features, "WBC", 4),
    )
    return np.sum(criteria, axis=0).astype(np.int16)


def qsofa(features: pd.DataFrame) -> np.ndarray:
    """Modified qSOFA, 0-2 (Sepsis-3 Box 4; no mentation item)."""
    score: np.ndarray = _ge(features, "Resp", 22).astype(np.int16) + _le(features, "SBP", 100)
    return score.astype(np.int16)


RULE_SCORES = {"news2": news2, "sirs": sirs, "qsofa": qsofa}


# --- logistic regression ---------------------------------------------------------------


def make_logistic(seed: int) -> Pipeline:
    """Median imputation with missing-value indicators, scaling, L2 logistic regression.

    Every step is fitted by ``Pipeline.fit``, which the evaluation calls on the source
    hospital's training split only.
    """
    return Pipeline(
        [
            (
                "impute",
                SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
            ),
            ("scale", StandardScaler()),
            ("model", LogisticRegression(max_iter=2000, random_state=seed)),
        ]
    )


@dataclass(frozen=True)
class LogisticJSON:
    """Everything needed to score with a fitted pipeline, as plain JSON-able lists."""

    features: list[str]
    medians: list[float]
    indicator_features: list[int]
    mean: list[float]
    scale: list[float]
    coef: list[float]
    intercept: float

    @classmethod
    def from_pipeline(cls, pipe: Pipeline, features: Sequence[str]) -> LogisticJSON:
        imp, sc, lr = pipe["impute"], pipe["scale"], pipe["model"]
        return cls(
            features=list(features),
            medians=[float(x) for x in imp.statistics_],
            indicator_features=[int(i) for i in imp.indicator_.features_],
            mean=[float(x) for x in sc.mean_],
            scale=[float(x) for x in sc.scale_],
            coef=[float(x) for x in lr.coef_[0]],
            intercept=float(lr.intercept_[0]),
        )

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        x = frame[self.features].to_numpy(dtype=np.float64)
        missing = np.isnan(x)
        filled = np.where(missing, np.asarray(self.medians), x)
        design = np.hstack([filled, missing[:, self.indicator_features].astype(np.float64)])
        z = (design - np.asarray(self.mean)) / np.asarray(self.scale)
        logit = z @ np.asarray(self.coef) + self.intercept
        return 1.0 / (1.0 + np.exp(-logit))


def fit_logistic(
    train: pd.DataFrame, features: Sequence[str], label: str, seed: int
) -> tuple[Pipeline, LogisticJSON]:
    pipe = make_logistic(seed)
    pipe.fit(train[list(features)].to_numpy(dtype=np.float64), train[label].to_numpy())
    return pipe, LogisticJSON.from_pipeline(pipe, features)


def fit_news2_probability(scores: np.ndarray, labels: np.ndarray, seed: int) -> tuple[float, float]:
    """NEWS2 as a probability: one-feature logistic regression on the source training split.

    Returns (coefficient, intercept); probability = sigmoid(coef * score + intercept).
    """
    lr = LogisticRegression(max_iter=1000, random_state=seed)
    lr.fit(np.asarray(scores, dtype=np.float64).reshape(-1, 1), labels)
    return float(lr.coef_[0][0]), float(lr.intercept_[0])


def news2_probability(scores: np.ndarray, coef: float, intercept: float) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-(coef * np.asarray(scores, dtype=np.float64) + intercept)))
