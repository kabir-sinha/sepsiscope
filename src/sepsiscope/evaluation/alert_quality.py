"""Alert quality at the headline 5 % budget: how trustworthy is an alert, and per patient?

Post-hoc, descriptive (Batch E, after Milestone 5): no new model, threshold or criterion.
For LightGBM, the logistic regression and NEWS2, both directions, at the committed headline
thresholds (checked against ``{model}_{direction}.json``), on every patient of the unseen
hospital, with the same patient-level bootstrap as the protocol (1,000 resamples, seed 42):

- precision per alerting hour (PPV) and its lift over the share of label-1 hours;
- NPV per hour;
- precision per patient (share of alerted patients who are ever septic), its lift over the
  share of septic patients, and the patients alerted per septic patient found;
- sensitivity per patient (septic patients with at least one alert, at any time);
- alerting hours per septic patient found and per timely detection (protocol window).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from sepsiscope.config import Config
from sepsiscope.evaluation import metrics as m
from sepsiscope.evaluation.run import (
    DIRECTIONS,
    MODEL_LABELS,
    RESAMPLES,
    _split_pids,
    prepare_models,
    target_context,
    write_json,
)
from sepsiscope.features.pipeline import read_features

MODELS: tuple[str, ...] = ("lgbm", "lr", "news2")
DEFINITIONS: dict[str, str] = {
    "ppv_hour": "label-1 hours among alerting hours",
    "label1_share_hour": "label-1 hours among all hours",
    "lift_hour": "ppv_hour / label1_share_hour",
    "npv_hour": "label-0 hours among non-alerting hours",
    "precision_patient": "ever-septic patients among patients with at least one alert",
    "septic_share_patient": "ever-septic patients among all patients",
    "lift_patient": "precision_patient / septic_share_patient",
    "patients_alerted_per_septic_found": "1 / precision_patient",
    "sensitivity_patient_any_alert": "septic patients with at least one alert, at any time",
    "timely_sensitivity": "protocol event metric (window onset - 12 h to onset, row-0 "
    "septic patients excluded); equals the committed headline value",
    "alert_hours_per_septic_found": "alerting hours / septic patients with an alert",
    "alert_hours_per_timely_detection": "alerting hours / timely detections",
}


@dataclass(frozen=True)
class PatientCounts:
    """Per-patient sums, so a bootstrap only reweights patients."""

    alert_hours: np.ndarray
    true_alert_hours: np.ndarray  # alerting hours with label 1
    hours: np.ndarray
    label1_hours: np.ndarray
    true_quiet_hours: np.ndarray  # non-alerting hours with label 0
    alerted: np.ndarray  # at least one alert
    septic: np.ndarray  # ever label 1
    timely_main: np.ndarray  # timely detection, row-0 septic excluded
    main: np.ndarray  # septic and not positive from row 0


def patient_counts(labels: np.ndarray, alerts: np.ndarray, patient: np.ndarray) -> PatientCounts:
    n = int(patient.max()) + 1 if len(patient) else 0
    lab = labels.astype(bool)
    al = alerts.astype(bool)
    ev = m.patient_events(labels, al, patient)

    def count(x: np.ndarray) -> np.ndarray:
        return np.bincount(patient, x.astype(np.float64), minlength=n)

    main = ev.septic & ~ev.from_row_zero
    return PatientCounts(
        alert_hours=count(al),
        true_alert_hours=count(al & lab),
        hours=np.bincount(patient, minlength=n).astype(np.float64),
        label1_hours=count(lab),
        true_quiet_hours=count(~al & ~lab),
        alerted=count(al) > 0,
        septic=ev.septic,
        timely_main=ev.timely & main,
        main=main,
    )


def _ratio(a: float, b: float) -> float:
    return a / b if b > 0 else float("nan")


def statistics(c: PatientCounts, w: np.ndarray) -> dict[str, float]:
    """All quantities for one set of patient weights (ones = the point estimate)."""
    alerts = float(w @ c.alert_hours)
    hours = float(w @ c.hours)
    ppv = _ratio(float(w @ c.true_alert_hours), alerts)
    share_h = _ratio(float(w @ c.label1_hours), hours)
    alerted = float(w @ c.alerted)
    found = float(w @ (c.alerted & c.septic))
    septic = float(w @ c.septic)
    precision = _ratio(found, alerted)
    share_p = _ratio(septic, float(w.sum()))
    timely = float(w @ c.timely_main)
    return {
        "ppv_hour": ppv,
        "label1_share_hour": share_h,
        "lift_hour": _ratio(ppv, share_h),
        "npv_hour": _ratio(float(w @ c.true_quiet_hours), hours - alerts),
        "precision_patient": precision,
        "septic_share_patient": share_p,
        "lift_patient": _ratio(precision, share_p),
        "patients_alerted_per_septic_found": _ratio(alerted, found),
        "sensitivity_patient_any_alert": _ratio(found, septic),
        "timely_sensitivity": _ratio(timely, float(w @ c.main)),
        "alert_hours_per_septic_found": _ratio(alerts, found),
        "alert_hours_per_timely_detection": _ratio(alerts, timely),
    }


def block(c: PatientCounts, weights: np.ndarray) -> dict[str, object]:
    """Point estimates, bootstrap 95 % CIs and the raw counts."""
    point = statistics(c, np.ones(len(c.hours)))
    samples = m.bootstrap_samples(lambda w: statistics(c, w), weights)
    return {
        "point": point,
        "ci95": {k: m.percentile_ci(samples[k]) for k in point},
        "counts": {
            "patients": len(c.hours),
            "hours": int(c.hours.sum()),
            "alert_hours": int(c.alert_hours.sum()),
            "patients_alerted": int(c.alerted.sum()),
            "septic_patients": int(c.septic.sum()),
            "septic_patients_alerted": int((c.alerted & c.septic).sum()),
        },
    }


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
    prepared = prepare_models(
        list(MODELS), direction, cfg, source, _split_pids(splits_dir, source_h), models_dir
    )
    del source  # one hospital in memory at a time
    for p in prepared:
        if p.threshold != _committed_threshold(results_dir, p.model, direction):
            raise ValueError(f"{p.model} {direction}: threshold differs from the headline")
    target = target_context(
        read_features(data_dir, target_h), _split_pids(splits_dir, target_h), cfg.seed
    )
    full = target.full
    models: dict[str, object] = {}
    for p in prepared:
        alerts = p.scorer.score(full.frame) >= p.threshold
        counts = patient_counts(full.labels, alerts, full.patient)
        models[p.model] = {
            "model_label": MODEL_LABELS[p.model],
            "threshold": p.threshold,
            **block(counts, target.full_weights),
        }
    return {
        "direction": direction,
        "source": source_h,
        "target": target_h,
        "analysis": "alert quality at the headline 5 % budget (post-hoc, descriptive)",
        "thresholds": "headline thresholds from the source validation split (unchanged)",
        "alarm_budget": cfg.alarm_budget,
        "seed": cfg.seed,
        "bootstrap_resamples": RESAMPLES,
        "definitions": DEFINITIONS,
        "models": models,
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
        path = results_dir / f"alert_quality_{direction}.json"
        write_json(path, doc)
        written.append(path)
    return written
