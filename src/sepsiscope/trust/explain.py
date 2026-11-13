"""Per-alert explanations from LightGBM's built-in feature contributions (plan B3).

``booster.predict(x, pred_contrib=True)`` returns, for every hour, one contribution per
feature plus a base value (last column). They are in **raw log-odds** and add up exactly to
the raw score: sum(contributions) + base = raw score. Platt scaling is increasing, so a
feature that pushes the raw score up also pushes the calibrated risk up (ADR 0022).

Rows are processed in chunks so memory stays bounded. Nothing patient-level is written to
tracked files; only aggregates leave this module through the evaluation (P3).
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass

import lightgbm as lgb
import numpy as np

CHUNK_ROWS = 100_000


def contribution_chunks(
    booster: lgb.Booster, x: np.ndarray, chunk: int = CHUNK_ROWS
) -> Iterator[np.ndarray]:
    """(rows, features + 1) arrays of contributions; the last column is the base value."""
    for start in range(0, len(x), chunk):
        part = booster.predict(x[start : start + chunk], pred_contrib=True)
        yield np.asarray(part, dtype=np.float64)


def additivity_error(booster: lgb.Booster, x: np.ndarray, chunk: int = CHUNK_ROWS) -> float:
    """Largest |sum(contributions) + base - raw score| over all rows."""
    worst = 0.0
    for start, contrib in zip(
        range(0, len(x), chunk), contribution_chunks(booster, x, chunk), strict=True
    ):
        raw = np.asarray(booster.predict(x[start : start + chunk], raw_score=True))
        worst = max(worst, float(np.max(np.abs(contrib.sum(axis=1) - raw))))
    return worst


def mean_abs_contribution(
    booster: lgb.Booster, x: np.ndarray, rows: np.ndarray, chunk: int = CHUNK_ROWS
) -> np.ndarray:
    """Mean |contribution| per feature over the selected rows (e.g. alerting hours)."""
    selected = x[np.asarray(rows, dtype=bool)]
    total = np.zeros(x.shape[1])
    for contrib in contribution_chunks(booster, selected, chunk):
        total += np.abs(contrib[:, :-1]).sum(axis=0)
    return total / max(1, len(selected))


@dataclass(frozen=True)
class Reason:
    feature: str
    contribution: float  # raw log-odds; positive raises the risk


@dataclass(frozen=True)
class Explanation:
    base: float
    raw_score: float
    reasons: list[Reason]  # largest |contribution| first


def explain_rows(
    booster: lgb.Booster, x: np.ndarray, features: Sequence[str], top: int = 5
) -> list[Explanation]:
    """Top reasons for each given row (for alerting hours in the local demo only)."""
    out: list[Explanation] = []
    for contrib in contribution_chunks(booster, x):
        for row in contrib:
            values, base = row[:-1], float(row[-1])
            order = np.argsort(-np.abs(values), kind="stable")[:top]
            reasons = [Reason(features[i], float(values[i])) for i in order]
            out.append(Explanation(base, float(values.sum() + base), reasons))
    return out
