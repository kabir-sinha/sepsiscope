"""C3: alarm-budget sensitivity, lead-time distribution, subgroup CIs (ADR 0024 items 5-6).

LightGBM (Platt), logistic regression and NEWS2 are prepared exactly as in
``sepsiscope evaluate``. For each alarm budget (2, 5, 10 % of patient-hours) the threshold
is chosen on the source **validation** split (protocol section 6); the 5 % budget must
reproduce the committed headline thresholds exactly. On the target hospital:

- all protocol metrics with patient-level bootstrap 95 % CIs, plus the paired LightGBM -
  LR difference (same resamples);
- the lead-time distribution among timely detected patients: 10th-90th percentiles with
  CIs and a 0-12 h histogram;
- at the headline 5 % budget, subgroup CIs (sex, age < 65 / >= 65) by patient bootstrap
  within each group, with the paired LightGBM - LR difference. Descriptive only.

Result files hold numbers only: no patient IDs, no paths, no timestamps.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from sepsiscope.config import Config
from sepsiscope.evaluation import metrics as m
from sepsiscope.evaluation.run import (
    DIRECTIONS,
    MODEL_LABELS,
    RESAMPLES,
    Cohort,
    _metrics_block,
    _split_pids,
    prepare_models,
    target_context,
    write_json,
)
from sepsiscope.features.pipeline import read_features

MODELS: tuple[str, ...] = ("lgbm", "lr", "news2")
BUDGETS: tuple[float, ...] = (0.02, 0.05, 0.10)
HEADLINE_BUDGET = 0.05
PERCENTILES: tuple[int, ...] = (10, 25, 50, 75, 90)
MAX_LEAD = 12  # the timely window is [onset - 12 h, onset]
PAIRED_KEYS: tuple[str, ...] = ("utility", "auroc", "auprc", "timely_sensitivity")


def _wpercentile(x: np.ndarray, w: np.ndarray, q: float) -> float:
    """Percentile of x where each value is repeated w times (integer bootstrap weights)."""
    values = np.repeat(x, np.asarray(w).astype(np.int64))
    return float(np.percentile(values, q)) if len(values) else float("nan")


def lead_times(cohort: Cohort, alerts: np.ndarray, weights: np.ndarray) -> dict[str, object]:
    """Lead-time percentiles (with CIs) and histogram among timely detected patients."""
    ev = m.patient_events(cohort.labels, alerts, cohort.patient)
    mask = ev.septic & ~ev.from_row_zero & ev.timely  # same patients as the median lead time
    lead = ev.lead[mask]

    def stat(w: np.ndarray | None) -> dict[str, float]:
        ww = np.ones(int(mask.sum())) if w is None else w[mask]
        return {f"p{q}": _wpercentile(lead, ww, q) for q in PERCENTILES}

    samples = m.bootstrap_samples(stat, weights)
    hours = np.arange(MAX_LEAD + 1)
    counts = [int(np.sum(lead == h)) for h in hours]
    return {
        "detected_patients": int(mask.sum()),
        "percentiles_hours": stat(None),
        "ci95": {k: list(m.percentile_ci(v)) for k, v in samples.items()},
        "histogram": {"lead_hours": hours.tolist(), "patients": counts},
    }


def _paired(a: dict[str, np.ndarray], b: dict[str, np.ndarray]) -> dict[str, object]:
    out: dict[str, object] = {}
    for key in PAIRED_KEYS:
        diff = a[key] - b[key]
        out[key] = {
            "point": float(a[f"point_{key}"] - b[f"point_{key}"]),
            "ci95": list(m.percentile_ci(diff)),
            "share_of_resamples_above_0": float(np.nanmean(diff > 0)),
        }
    return out


def _groups(cohort: Cohort) -> dict[str, np.ndarray]:
    first = np.r_[True, cohort.patient[1:] != cohort.patient[:-1]]
    gender = cohort.frame["Gender"].to_numpy()[first]
    age = cohort.frame["Age"].to_numpy()[first]
    return {
        "gender_0": gender == 0,
        "gender_1": gender == 1,
        "age_lt_65": age < 65,
        "age_ge_65": age >= 65,
    }


def subgroups(
    cohort: Cohort,
    scores: dict[str, np.ndarray],
    thresholds: dict[str, float],
    seed: int,
) -> dict[str, object]:
    """Per group: metrics with CIs (bootstrap within the group) and LightGBM - LR."""
    out: dict[str, object] = {}
    for name, keep_patient in _groups(cohort).items():
        rows = keep_patient[cohort.patient]
        sub = Cohort.of(cohort.frame[rows])
        reference = m.reference_utilities(sub.labels, sub.patient)
        weights = m.bootstrap_weights(sub.n_patients, RESAMPLES, seed)
        models: dict[str, object] = {}
        kept: dict[str, dict[str, np.ndarray]] = {}
        for model, s in scores.items():
            keep: dict[str, np.ndarray] = {}
            models[model] = _metrics_block(
                sub, s[rows], thresholds[model], weights, reference, keep
            )
            kept[model] = keep
        out[name] = {
            "patients": sub.n_patients,
            "models": models,
            "paired_lgbm_minus_lr": _paired(kept["lgbm"], kept["lr"]),
        }
    return out


def _committed_threshold(results_dir: Path, model: str, direction: str) -> float:
    doc = json.loads((results_dir / f"{model}_{direction}.json").read_text(encoding="utf-8"))
    return float(doc["strict_external"]["threshold"])


def direction_document(
    direction: str,
    cfg: Config,
    data_dir: Path,
    splits_dir: Path,
    results_dir: Path,
    models_dir: Path,
) -> dict[str, object]:
    source_h, target_h = DIRECTIONS[direction]
    source = read_features(data_dir, source_h)
    splits = _split_pids(splits_dir, source_h)
    prepared = prepare_models(list(MODELS), direction, cfg, source, splits, models_dir)
    val = source[source["pid"].isin(splits["val"])]
    thresholds: dict[float, dict[str, tuple[float, float]]] = {}
    for budget in BUDGETS:
        thresholds[budget] = {
            p.model: m.budget_threshold(p.scorer.score(val), budget) for p in prepared
        }
    del source, val  # one hospital in memory at a time
    for p in prepared:
        headline = thresholds[HEADLINE_BUDGET][p.model][0]
        if headline != p.threshold or headline != _committed_threshold(
            results_dir, p.model, direction
        ):
            raise ValueError(f"{p.model} {direction}: 5 % budget does not reproduce the headline")

    target = target_context(
        read_features(data_dir, target_h), _split_pids(splits_dir, target_h), cfg.seed
    )
    full = target.full
    scores = {p.model: p.scorer.score(full.frame) for p in prepared}
    budgets_doc: dict[str, object] = {}
    for budget in BUDGETS:
        models_doc: dict[str, object] = {}
        kept: dict[str, dict[str, np.ndarray]] = {}
        for model, s in scores.items():
            threshold, val_rate = thresholds[budget][model]
            keep: dict[str, np.ndarray] = {}
            block = _metrics_block(
                full, s, threshold, target.full_weights, target.full_reference, keep
            )
            block["source_validation_alert_rate"] = val_rate
            block["lead_times"] = lead_times(full, s >= threshold, target.full_weights)
            models_doc[model] = block
            kept[model] = keep
        budgets_doc[f"{budget:.2f}"] = {
            "models": models_doc,
            "paired_lgbm_minus_lr": _paired(kept["lgbm"], kept["lr"]),
        }
    headline_th = {model: thresholds[HEADLINE_BUDGET][model][0] for model in scores}
    return {
        "direction": direction,
        "source": source_h,
        "target": target_h,
        "analysis": "C3 alarm budgets, lead times, subgroup CIs (ADR 0024 items 5-6)",
        "models": {model: MODEL_LABELS[model] for model in scores},
        "thresholds": "per budget, chosen on the source validation split (protocol section 6)",
        "seed": cfg.seed,
        "bootstrap_resamples": RESAMPLES,
        "budgets": budgets_doc,
        "subgroups_at_headline_budget": subgroups(full, scores, headline_th, cfg.seed),
    }


def run(
    cfg: Config,
    data_dir: Path,
    splits_dir: Path,
    results_dir: Path,
    models_dir: Path,
) -> list[Path]:
    written: list[Path] = []
    for direction in DIRECTIONS:
        doc = direction_document(direction, cfg, data_dir, splits_dir, results_dir, models_dir)
        path = results_dir / f"budgets_{direction}.json"
        write_json(path, doc)
        written.append(path)
    return written
