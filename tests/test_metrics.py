"""Metrics library: hand-computed fixtures and agreement with the official scorer / sklearn."""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pytest
from sklearn.metrics import average_precision_score, roc_auc_score

from sepsiscope.evaluation import metrics as m

# Four patients: septic (onset mid-stay), non-septic, septic from row 0, non-septic.
LABELS = [
    [0] * 10 + [1] * 5,
    [0] * 8,
    [1] * 6,
    [0] * 12,
]
ALERTS = [
    [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 1, 1, 0, 0],
    [0, 1, 0, 0, 0, 0, 0, 0],
    [0, 0, 1, 1, 0, 0],
    [0] * 12,
]


def flat(groups: list[list[int]]) -> np.ndarray:
    return np.array([v for g in groups for v in g])


def patient_of(groups: list[list[int]]) -> np.ndarray:
    return np.repeat(np.arange(len(groups)), [len(g) for g in groups])


def write_psv(path: Path, header: str, columns: list[list[float]]) -> None:
    lines = [header] + ["|".join(str(c[i]) for c in columns) for i in range(len(columns[0]))]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_normalized_utility_equals_official_evaluate(tmp_path: Path) -> None:
    labels_dir, preds_dir = tmp_path / "labels", tmp_path / "preds"
    labels_dir.mkdir()
    preds_dir.mkdir()
    for k, (y, a) in enumerate(zip(LABELS, ALERTS, strict=True)):
        write_psv(labels_dir / f"p{k:06d}.psv", "SepsisLabel", [y])
        write_psv(preds_dir / f"p{k:06d}.psv", "PredictedProbability|PredictedLabel", [a, a])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        official = m.official_scorer().evaluate_sepsis_score(str(labels_dir), str(preds_dir))[4]
    parts = m.utility_parts(flat(LABELS), flat(ALERTS).astype(bool), patient_of(LABELS))
    assert parts.normalized() == pytest.approx(official, abs=1e-12)


def test_utility_weights_equal_duplicated_patients() -> None:
    y, a, p = flat(LABELS), flat(ALERTS).astype(bool), patient_of(LABELS)
    weighted = m.utility_parts(y, a, p).normalized(np.array([2.0, 0.0, 1.0, 1.0]))
    groups = [0, 0, 2, 3]
    dup = m.utility_parts(
        flat([LABELS[g] for g in groups]),
        flat([ALERTS[g] for g in groups]).astype(bool),
        patient_of([LABELS[g] for g in groups]),
    ).normalized()
    assert weighted == pytest.approx(dup)


def test_ranking_matches_sklearn_with_ties_and_weights() -> None:
    rng = np.random.default_rng(0)
    scores = rng.integers(0, 6, 500).astype(float)  # many ties, like NEWS2
    labels = (rng.random(500) < 0.1 + scores / 20).astype(int)
    r = m.Ranking.build(scores, labels)
    assert r.auroc() == pytest.approx(roc_auc_score(labels, scores))
    assert r.auprc() == pytest.approx(average_precision_score(labels, scores))
    w = rng.integers(0, 3, 500).astype(float)
    rep = np.repeat(np.arange(500), w.astype(int))
    assert r.auroc(w) == pytest.approx(roc_auc_score(labels[rep], scores[rep]))
    assert r.auprc(w) == pytest.approx(average_precision_score(labels[rep], scores[rep]))


def test_budget_threshold_never_splits_ties() -> None:
    scores = np.array([9, 7, 7, 7, 5, 5, 3, 1, 1, 1], dtype=float)
    assert m.budget_threshold(scores, 0.10) == (9.0, 0.1)
    assert m.budget_threshold(scores, 0.39) == (9.0, 0.1)  # 7 would give 40 %
    assert m.budget_threshold(scores, 0.40) == (7.0, 0.4)
    assert m.budget_threshold(np.ones(10), 0.05) == (float("inf"), 0.0)


def test_event_metrics_by_hand() -> None:
    ev = m.patient_events(flat(LABELS), flat(ALERTS).astype(bool), patient_of(LABELS))
    # Patient 0: first positive row 10 -> onset 16, window [4, 16]; alerts at 5, 10-12.
    assert ev.timely.tolist() == [True, False, True, False]
    assert ev.lead[0] == 16 - 5
    assert ev.from_row_zero.tolist() == [False, False, True, False]
    out = m.event_metrics(ev)
    assert out["timely_sensitivity"] == 1.0  # only patient 0 counts in the main metric
    assert out["median_lead_hours"] == 11.0
    assert out["row0_timely_sensitivity"] == 1.0
    # Non-septic: 1 alert in 8 + 12 = 20 hours -> 1 / (20 / 24) * 100.
    assert out["false_alerts_per_100_patient_days"] == pytest.approx(120.0)


def test_alert_rate_weighted() -> None:
    a, p = flat(ALERTS).astype(bool), patient_of(ALERTS)
    assert m.alert_rate(a, p) == pytest.approx(7 / 41)
    assert m.alert_rate(a, p, np.array([0.0, 1.0, 0.0, 1.0])) == pytest.approx(1 / 20)


def test_ece_and_reliability_by_hand() -> None:
    probs = np.array([0.1, 0.1, 0.9, 0.9])
    labels = np.array([0, 0, 1, 0])
    table = m.reliability(probs, labels, bins=2)
    assert table["rows"].tolist() == [2, 2]
    assert table["observed_rate"].tolist() == [0.0, 0.5]
    assert m.ece(probs, labels, bins=2) == pytest.approx(0.5 * 0.1 + 0.5 * 0.4)


def test_bootstrap_is_seeded_and_patient_level() -> None:
    w1, w2 = m.bootstrap_weights(50, 20, seed=42), m.bootstrap_weights(50, 20, seed=42)
    assert np.array_equal(w1, w2)
    assert (w1.sum(axis=1) == 50).all()
    ci = m.bootstrap_ci(lambda w: {"mean_w": float(w.mean())}, w1)
    assert ci["mean_w"] == (1.0, 1.0)


def test_patient_index_requires_contiguous_rows() -> None:
    assert m.patient_index(np.array(["a", "a", "b"])).tolist() == [0, 0, 1]
    with pytest.raises(ValueError):
        m.patient_index(np.array(["a", "b", "a"]))


def test_decision_curve_has_reference_strategies() -> None:
    labels = np.array([0, 1, 0, 1, 0, 0])
    table = m.decision_curve(
        labels, {"lr": np.array([0.1, 0.8, 0.3, 0.6, 0.2, 0.1])}, np.array([0.2])
    )
    assert set(table["model"]) == {"lr", "all", "none"}
    assert table.loc[table["model"] == "lr", "net_benefit"].item() == pytest.approx(0.25)
