"""C2 uncertainty-based deferral on the unseen hospital (ADR 0020, ADR 0024 items 2-4).

The headline LightGBM (Platt) is prepared exactly as in ``sepsiscope evaluate`` (same
threshold, checked against the committed result file). Conformal thresholds are fitted on
the source hospital's **calibration** split only, then applied to every target hour.

Reported per alpha (0.10 main; 0.05 and 0.20 sensitivity), with patient-level bootstrap
95 % CIs:

- ``deferral_rate``: share of patient-hours deferred;
- ``share_not_deferred``: per class, share of label-0 and label-1 hours **not** deferred
  (ADR 0020 item 2);
- ``coverage``: per class, share of hours whose true label is in the conformal set (a
  different measure, named apart: ADR 0024 item 4);
- protocol metrics on the non-deferred hours (deferred hours cannot alert; utility via
  ``metrics.subset_reference``), always next to the deferral rate.

Per-hour deferral decisions go to the ignored ``data/`` folder so these numbers can be
recomputed (ADR 0020); the committed result files hold aggregates only.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from sepsiscope.config import Config
from sepsiscope.data.io import LABEL
from sepsiscope.evaluation import metrics as m
from sepsiscope.evaluation.run import (
    DIRECTIONS,
    RESAMPLES,
    Cohort,
    _split_pids,
    prepare_models,
    target_context,
    write_json,
)
from sepsiscope.features.pipeline import read_features
from sepsiscope.trust import conformal

ALPHAS: tuple[float, ...] = (0.10, 0.05, 0.20)
MAIN_ALPHA = 0.10
MAX_DEFERRAL = 0.30  # ADR 0024 item 3 (a)
MAX_CLASS_GAP = 0.10  # ADR 0024 item 3 (b)
DECISIONS_DIR = Path("processed") / "deferral"


def _metrics(
    cohort: Cohort,
    scores: np.ndarray,
    probs: np.ndarray,
    alerts: np.ndarray,
    defer: np.ndarray,
    weights: np.ndarray,
) -> dict[str, object]:
    """Deferral measures and the protocol metrics on the non-deferred hours, with CIs."""
    labels, patient = cohort.labels, cohort.patient
    keep = ~defer
    y = labels.astype(bool)
    ranking = m.Ranking.build(scores[keep], labels[keep])
    reference = m.subset_reference(labels, patient, keep)
    parts = m.utility_parts(labels, alerts & keep, patient, reference)
    events = m.patient_events(labels, alerts & keep, patient)

    def stat(w: np.ndarray | None) -> dict[str, float]:
        row_w = np.ones(len(labels)) if w is None else w[patient]
        kw = None if w is None else row_w[keep]
        return {
            "deferral_rate": float(np.dot(row_w, defer) / row_w.sum()),
            "share_not_deferred_label0": float(np.dot(row_w[~y], keep[~y]) / row_w[~y].sum()),
            "share_not_deferred_label1": float(np.dot(row_w[y], keep[y]) / row_w[y].sum()),
            "auroc": ranking.auroc(kw),
            "auprc": ranking.auprc(kw),
            "utility": parts.normalized(w),
            "alert_rate_non_deferred": m.alert_rate(alerts[keep], patient[keep], w),
            **m.event_metrics(events, w),
        }

    point = stat(None)
    samples = m.bootstrap_samples(stat, weights)
    return {
        "non_deferred_rows": int(keep.sum()),
        "point": point,
        "ci95": {k: list(m.percentile_ci(v)) for k, v in samples.items()},
        "ece_non_deferred": m.ece(probs[keep], labels[keep]) if keep.any() else float("nan"),
    }


def criterion(block: dict[str, object], headline_utility: float) -> dict[str, object]:
    """ADR 0024 item 3 for one direction at the main alpha."""
    point = block["point"]
    assert isinstance(point, dict)
    a = float(point["deferral_rate"]) <= MAX_DEFERRAL
    gap = float(point["share_not_deferred_label0"]) - float(point["share_not_deferred_label1"])
    b = gap <= MAX_CLASS_GAP
    c = float(point["utility"]) > headline_utility
    return {
        "a_deferral_rate_at_most_0.30": a,
        "b_label1_not_deferred_within_0.10_of_label0": b,
        "c_utility_non_deferred_above_headline": c,
        "headline_utility": headline_utility,
        "useful": bool(a and b and c),
    }


def _committed(results_dir: Path, direction: str) -> dict[str, object]:
    doc = json.loads((results_dir / f"lgbm_{direction}.json").read_text(encoding="utf-8"))
    strict = doc["strict_external"]
    assert isinstance(strict, dict)
    return strict


def direction_document(
    direction: str,
    cfg: Config,
    data_dir: Path,
    splits_dir: Path,
    results_dir: Path,
    models_dir: Path,
) -> tuple[dict[str, object], pd.DataFrame]:
    source_h, target_h = DIRECTIONS[direction]
    source = read_features(data_dir, source_h)
    splits = _split_pids(splits_dir, source_h)
    (p,) = prepare_models(["lgbm"], direction, cfg, source, splits, models_dir)
    committed = _committed(results_dir, direction)
    if p.threshold != float(committed["threshold"]):  # type: ignore[arg-type]
        raise ValueError(f"lgbm {direction}: threshold differs from the committed one")
    assert p.scorer.probability is not None
    cal = source[source["pid"].isin(splits["calibration"])]
    cal_probs = p.scorer.probability(cal)
    cal_labels = cal[LABEL].to_numpy()
    thresholds = {a: conformal.fit(cal_probs, cal_labels, a) for a in ALPHAS}
    del source, cal  # one hospital in memory at a time

    target = target_context(
        read_features(data_dir, target_h), _split_pids(splits_dir, target_h), cfg.seed
    )
    frame = target.full.frame
    scores = p.scorer.score(frame)
    probs = p.scorer.probability(frame)
    alerts = scores >= p.threshold
    point = committed["point"]
    assert isinstance(point, dict)
    headline_utility = float(point["utility"])

    per_alpha: dict[str, object] = {}
    decisions = pd.DataFrame({"pid": frame["pid"].to_numpy(), "t": frame["t"].to_numpy()})
    for alpha, th in thresholds.items():
        defer = conformal.deferred(probs, th)
        decisions[f"deferred_alpha_{alpha:.2f}"] = defer
        block = _metrics(target.full, scores, probs, alerts, defer, target.full_weights)
        block["thresholds"] = {"q0": th.q0, "q1": th.q1}
        block["calibration_hours"] = {"label0": th.n0, "label1": th.n1}
        block["coverage"] = conformal.coverage(probs, target.full.labels, th)
        block["coverage_on_source_calibration"] = conformal.coverage(cal_probs, cal_labels, th)
        if alpha == MAIN_ALPHA:
            block["adr_0024_item_3"] = criterion(block, headline_utility)
        per_alpha[f"{alpha:.2f}"] = block

    doc: dict[str, object] = {
        "direction": direction,
        "source": source_h,
        "target": target_h,
        "analysis": "C2 class-conditional conformal deferral (ADR 0020, ADR 0024 items 2-4)",
        "model": "lgbm (Platt), headline threshold on non-deferred hours",
        "threshold": p.threshold,
        "nonconformity": "1 - p_hat(y), per-class thresholds from the source calibration split",
        "deferral_rule": "deferred when the prediction set is {0, 1} or empty",
        "names": {
            "share_not_deferred": "per class, share of hours not deferred (ADR 0020 item 2)",
            "coverage": "per class, share of hours whose true label is in the set",
        },
        "main_alpha": MAIN_ALPHA,
        "seed": cfg.seed,
        "bootstrap_resamples": RESAMPLES,
        "headline_utility": headline_utility,
        "alphas": per_alpha,
    }
    return doc, decisions


def run(
    cfg: Config,
    data_dir: Path,
    splits_dir: Path,
    results_dir: Path,
    models_dir: Path,
) -> list[Path]:
    written: list[Path] = []
    out_dir = data_dir / DECISIONS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    for direction in DIRECTIONS:
        doc, decisions = direction_document(
            direction, cfg, data_dir, splits_dir, results_dir, models_dir
        )
        decisions.to_parquet(out_dir / f"deferral_{direction}.parquet", index=False)
        path = results_dir / f"deferral_{direction}.json"
        write_json(path, doc)
        written.append(path)
    return written
