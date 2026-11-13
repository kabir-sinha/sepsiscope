"""Metrics library (protocol sections 5 and 6). Pure functions, no file or network access.

Data layout used throughout: one row per patient-hour, rows grouped by patient in
consecutive order. ``patient`` is an integer array (0..P-1, one value per row) built by
:func:`patient_index`; ``labels`` are 0/1 per row; ``alerts`` are booleans per row.

Bootstrap CIs resample **patients** (with replacement). A resample is represented by how
often each patient was drawn; every row then carries its patient's count as a weight. A
weighted metric with integer weights equals the metric on the resampled (duplicated) rows,
so one pass per resample is enough and nothing is copied.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from types import ModuleType

import numpy as np
import pandas as pd

from sepsiscope.config import REPO_ROOT

SCORER = REPO_ROOT / "third_party" / "physionet_eval" / "evaluate_sepsis_score.py"
ONSET_OFFSET_HOURS = 6  # protocol section 2: onset = first positive row + 6 h
TIMELY_WINDOW_HOURS = 12  # alerts in [onset - 12 h, onset] are timely
# Utility parameters exactly as in the official evaluate_sepsis_score() (protocol section 5).
DT_EARLY, DT_OPTIMAL, DT_LATE = -12, -6, 3


# --- grouping ---------------------------------------------------------------------------


def patient_index(pids: np.ndarray) -> np.ndarray:
    """0..P-1 per row, in order of first appearance; rows of a patient must be contiguous."""
    pids = np.asarray(pids)
    if len(pids) == 0:
        return np.zeros(0, dtype=np.int64)
    new = np.r_[True, pids[1:] != pids[:-1]]
    index = np.cumsum(new) - 1
    if len(np.unique(pids)) != int(new.sum()):
        raise ValueError("rows of each patient must be contiguous")
    return index.astype(np.int64)


def _starts(patient: np.ndarray) -> np.ndarray:
    return np.flatnonzero(np.r_[True, patient[1:] != patient[:-1]])


# --- official utility -------------------------------------------------------------------


@lru_cache(maxsize=1)
def official_scorer() -> ModuleType:
    """The vendored, unmodified official scorer, loaded as a module (never edited)."""
    spec = importlib.util.spec_from_file_location("official_scorer", SCORER)
    if spec is None or spec.loader is None:
        raise ImportError("official scorer not found")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _best_predictions(labels: np.ndarray) -> np.ndarray:
    """The official 'best' predictions for one patient (copied logic, same parameters)."""
    best = np.zeros(len(labels))
    if np.any(labels):
        t_sepsis = int(np.argmax(labels)) - DT_OPTIMAL
        best[max(0, t_sepsis + DT_EARLY) : min(t_sepsis + DT_LATE + 1, len(labels))] = 1
    return best


@dataclass(frozen=True)
class UtilityParts:
    """Per-patient utilities; the official normalised utility is a ratio of their sums."""

    observed: np.ndarray
    best: np.ndarray
    inaction: np.ndarray

    def normalized(self, weights: np.ndarray | None = None) -> float:
        w = np.ones(len(self.observed)) if weights is None else weights
        o, b, i = (float(np.dot(w, x)) for x in (self.observed, self.best, self.inaction))
        return (o - i) / (b - i) if b != i else float("nan")  # undefined without septic patients


def reference_utilities(labels: np.ndarray, patient: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Best and inaction utility per patient (depend on labels only; compute once)."""
    score = official_scorer().compute_prediction_utility
    bounds = np.r_[_starts(patient), len(labels)]
    best, inaction = np.zeros(len(bounds) - 1), np.zeros(len(bounds) - 1)
    for k in range(len(bounds) - 1):
        y = labels[bounds[k] : bounds[k + 1]]
        best[k] = score(y, _best_predictions(y))
        inaction[k] = score(y, np.zeros(len(y)))
    return best, inaction


def utility_parts(
    labels: np.ndarray,
    alerts: np.ndarray,
    patient: np.ndarray,
    reference: tuple[np.ndarray, np.ndarray] | None = None,
) -> UtilityParts:
    """Per-patient utilities with the official ``compute_prediction_utility``."""
    score = official_scorer().compute_prediction_utility
    best, inaction = reference if reference is not None else reference_utilities(labels, patient)
    bounds = np.r_[_starts(patient), len(labels)]
    observed = np.zeros(len(bounds) - 1)
    preds = alerts.astype(np.int64)
    for k in range(len(bounds) - 1):
        observed[k] = score(labels[bounds[k] : bounds[k + 1]], preds[bounds[k] : bounds[k + 1]])
    return UtilityParts(observed, best, inaction)


# --- ranking metrics --------------------------------------------------------------------


@dataclass(frozen=True)
class Ranking:
    """Scores grouped into tied buckets, highest first, so weighted metrics are one pass."""

    bucket: np.ndarray  # per row: index of its score among the distinct scores (0 = highest)
    n_buckets: int
    labels: np.ndarray

    @classmethod
    def build(cls, scores: np.ndarray, labels: np.ndarray) -> Ranking:
        uniq, inverse = np.unique(-np.asarray(scores, dtype=np.float64), return_inverse=True)
        return cls(inverse.astype(np.int64), len(uniq), np.asarray(labels, dtype=np.float64))

    def counts(self, weights: np.ndarray | None) -> tuple[np.ndarray, np.ndarray]:
        w = np.ones(len(self.labels)) if weights is None else weights
        pos = np.bincount(self.bucket, w * self.labels, minlength=self.n_buckets)
        neg = np.bincount(self.bucket, w * (1.0 - self.labels), minlength=self.n_buckets)
        return pos, neg

    def auroc(self, weights: np.ndarray | None = None) -> float:
        """Probability a positive row outranks a negative row; ties count one half."""
        pos, neg = self.counts(weights)
        if pos.sum() == 0 or neg.sum() == 0:
            return float("nan")  # undefined with a single class
        neg_below = neg.sum() - np.cumsum(neg)  # negatives with a strictly lower score
        return float(np.sum(pos * (neg_below + 0.5 * neg)) / (pos.sum() * neg.sum()))

    def auprc(self, weights: np.ndarray | None = None) -> float:
        """Average precision (scikit-learn's definition: step-wise, no interpolation)."""
        pos, neg = self.counts(weights)
        if pos.sum() == 0:
            return float("nan")
        tp, fp = np.cumsum(pos), np.cumsum(neg)
        with np.errstate(invalid="ignore", divide="ignore"):
            precision = np.where(tp + fp > 0, tp / (tp + fp), 0.0)
        return float(np.sum(pos * precision) / pos.sum())


# --- threshold and alert metrics --------------------------------------------------------


def budget_threshold(scores: np.ndarray, budget: float) -> tuple[float, float]:
    """Lowest threshold whose alert rate (``score >= threshold``) stays within the budget.

    Tie-safe: tied scores are never split, so all rows with the threshold score alert
    together. If even the highest score alone exceeds the budget there are no alerts
    (threshold = +inf). Returns (threshold, alert rate on these scores).
    """
    s = np.asarray(scores, dtype=np.float64)
    if np.isnan(s).any():
        raise ValueError("scores contain NaN")
    values, counts = np.unique(-s, return_counts=True)  # highest score first
    rate_at_or_above = np.cumsum(counts) / len(s)
    allowed = np.flatnonzero(rate_at_or_above <= budget)
    if len(allowed) == 0:
        return float("inf"), 0.0
    k = int(allowed[-1])
    return float(-values[k]), float(rate_at_or_above[k])


def alert_rate(alerts: np.ndarray, patient: np.ndarray, weights: np.ndarray | None = None) -> float:
    w = _row_weights(patient, weights)
    return float(np.dot(w, alerts) / w.sum())


@dataclass(frozen=True)
class PatientEvents:
    """Per-patient quantities for event metrics (computed once per score/threshold)."""

    septic: np.ndarray  # ever label 1
    from_row_zero: np.ndarray  # label 1 already in the first row (protocol section 2)
    hours: np.ndarray
    alerts: np.ndarray  # number of alerting hours
    timely: np.ndarray  # >= 1 alert in [onset - 12, onset]
    lead: np.ndarray  # onset - first timely alert, NaN if not detected


def patient_events(labels: np.ndarray, alerts: np.ndarray, patient: np.ndarray) -> PatientEvents:
    starts = _starts(patient)
    n_pat = len(starts)
    hour = np.arange(len(labels)) - starts[patient]
    hours = np.bincount(patient, minlength=n_pat).astype(np.float64)
    n_alerts = np.bincount(patient, alerts.astype(np.float64), minlength=n_pat)
    septic = np.bincount(patient, labels.astype(np.float64), minlength=n_pat) > 0
    first_pos = np.full(n_pat, np.inf)
    np.minimum.at(first_pos, patient[labels == 1], hour[labels == 1])
    onset = first_pos + ONSET_OFFSET_HOURS
    in_window = (
        alerts.astype(bool)
        & (hour >= onset[patient] - TIMELY_WINDOW_HOURS)
        & (hour <= onset[patient])
    )
    first_timely = np.full(n_pat, np.inf)
    np.minimum.at(first_timely, patient[in_window], hour[in_window])
    timely = np.isfinite(first_timely)
    with np.errstate(invalid="ignore"):  # inf - inf for undetected patients; masked below
        lead = np.where(timely, onset - first_timely, np.nan)
    return PatientEvents(septic, septic & (first_pos == 0), hours, n_alerts, timely, lead)


def event_metrics(ev: PatientEvents, weights: np.ndarray | None = None) -> dict[str, float]:
    """Timely sensitivity, median lead time, false alerts per 100 non-septic patient-days.

    Main event metrics exclude septic patients positive from row 0 (their onset cannot be
    pinned down); those are reported separately as ``row0_*`` (protocol section 2).
    """
    w = np.ones(len(ev.septic)) if weights is None else weights
    main = ev.septic & ~ev.from_row_zero
    clean = ~ev.septic
    clean_days = float(np.dot(w[clean], ev.hours[clean])) / 24.0
    clean_alerts = float(np.dot(w[clean], ev.alerts[clean]))
    out = {
        "timely_sensitivity": _wmean(ev.timely, w, main),
        "median_lead_hours": _wmedian(ev.lead, w, main & ev.timely),
        "false_alerts_per_100_patient_days": (
            100.0 * clean_alerts / clean_days if clean_days > 0 else float("nan")
        ),
        "row0_timely_sensitivity": _wmean(ev.timely, w, ev.from_row_zero),
    }
    return out


def _wmean(x: np.ndarray, w: np.ndarray, mask: np.ndarray) -> float:
    total = float(w[mask].sum())
    return float(np.dot(w[mask], x[mask])) / total if total > 0 else float("nan")


def _wmedian(x: np.ndarray, w: np.ndarray, mask: np.ndarray) -> float:
    """Median of x where each value is repeated w times (integer bootstrap weights)."""
    values = np.repeat(x[mask], np.asarray(w[mask]).astype(np.int64))
    return float(np.median(values)) if len(values) else float("nan")


def _row_weights(patient: np.ndarray, weights: np.ndarray | None) -> np.ndarray:
    return np.ones(len(patient)) if weights is None else weights[patient]


# --- calibration ------------------------------------------------------------------------


def reliability(probs: np.ndarray, labels: np.ndarray, bins: int = 10) -> pd.DataFrame:
    """Quantile bins: equal numbers of rows per bin after a stable sort by probability."""
    order = np.argsort(np.asarray(probs, dtype=np.float64), kind="stable")
    rows = []
    for idx in np.array_split(order, bins):
        rows.append(
            {
                "rows": len(idx),
                "mean_predicted": float(np.mean(probs[idx])),
                "observed_rate": float(np.mean(labels[idx])),
            }
        )
    return pd.DataFrame(rows)


def ece(probs: np.ndarray, labels: np.ndarray, bins: int = 10) -> float:
    """Expected calibration error over 10 quantile bins (row-weighted |predicted - observed|)."""
    table = reliability(probs, labels, bins)
    gap = (table["mean_predicted"] - table["observed_rate"]).abs()
    return float(np.sum(table["rows"] * gap) / table["rows"].sum())


# --- bootstrap --------------------------------------------------------------------------


def bootstrap_weights(n_patients: int, resamples: int, seed: int) -> np.ndarray:
    """(resamples, n_patients) draw counts; each row sums to n_patients."""
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, n_patients, size=(resamples, n_patients))
    out = np.zeros((resamples, n_patients), dtype=np.int32)
    for r in range(resamples):
        out[r] = np.bincount(draws[r], minlength=n_patients)
    return out


def bootstrap_ci(
    statistic: Callable[[np.ndarray], Mapping[str, float]],
    weights: np.ndarray,
    level: float = 0.95,
) -> dict[str, tuple[float, float]]:
    """Percentile CIs of every statistic returned by ``statistic(patient_weights)``."""
    samples: dict[str, list[float]] = {}
    for w in weights:
        for key, value in statistic(w.astype(np.float64)).items():
            samples.setdefault(key, []).append(value)
    lo, hi = (1 - level) / 2 * 100, (1 + level) / 2 * 100
    out: dict[str, tuple[float, float]] = {}
    for key, v in samples.items():
        arr = np.asarray(v, dtype=np.float64)
        if np.isnan(arr).all():
            out[key] = (float("nan"), float("nan"))
        else:
            out[key] = (float(np.nanpercentile(arr, lo)), float(np.nanpercentile(arr, hi)))
    return out


# --- decision curves --------------------------------------------------------------------


def decision_curve(
    labels: np.ndarray, probabilities: Mapping[str, np.ndarray], thresholds: np.ndarray
) -> pd.DataFrame:
    """Net benefit per model and threshold via dcurves, plus treat-all and treat-none."""
    from dcurves import dca

    data = pd.DataFrame({"outcome": np.asarray(labels, dtype=np.int64)})
    for name, p in probabilities.items():
        data[name] = np.asarray(p, dtype=np.float64)
    result = dca(
        data=data, outcome="outcome", modelnames=list(probabilities), thresholds=thresholds
    )
    table: pd.DataFrame = result[["model", "threshold", "net_benefit"]].reset_index(drop=True)
    return table
