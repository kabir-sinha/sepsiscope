"""C1 shortcut check: performance within ICU-stay bands (ADR 0024 items 1 and 2).

Question: does the headline model only separate patients by how long they have been in
the ICU? If it did, its ranking would fall apart once hours are compared with other hours
from the same stage of the stay. Rows are grouped by their hour's ``ICULOS`` (hours since
ICU admission, from the clean Parquet). ``ICULOS`` is used only for this grouping, never as
a feature (protocol section 3).

LightGBM, logistic regression and NEWS2 are evaluated exactly as in ``sepsiscope evaluate``
(same fitting, same source-validation thresholds, checked against the committed result
files), on all target patients, per band, with the same patient-level bootstrap weights.
Utility within a band uses ``metrics.subset_reference`` (ADR 0024 item 2).

Result files hold numbers only: no patient IDs, no paths, no timestamps.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from sepsiscope.config import Config
from sepsiscope.data.build import CLEAN_PARQUET
from sepsiscope.evaluation import metrics as m
from sepsiscope.evaluation.run import (
    DIRECTIONS,
    MODEL_LABELS,
    RESAMPLES,
    Cohort,
    _split_pids,
    prepare_models,
    target_context,
    write_json,
)
from sepsiscope.features.pipeline import read_features

MODELS: tuple[str, ...] = ("lgbm", "lr", "news2")
# Half-open ICULOS ranges [from, to); None = no upper end.
BANDS: tuple[tuple[str, int, int | None], ...] = (
    ("0-24h", 0, 24),
    ("24-48h", 24, 48),
    ("48-96h", 48, 96),
    ("96h+", 96, None),
)
COLLAPSE_CI_UPPER = 0.60  # ADR 0024 item 1
COLLAPSE_DROP = 0.10


def band_of(iculos: np.ndarray) -> np.ndarray:
    """Band index 0..3 per row (``ICULOS`` in hours since ICU admission)."""
    out = np.full(len(iculos), -1, dtype=np.int64)
    for i, (_, lo, hi) in enumerate(BANDS):
        upper = np.inf if hi is None else hi
        out[(iculos >= lo) & (iculos < upper)] = i
    if (out < 0).any():
        raise ValueError("ICULOS outside every band")
    return out


def attach_iculos(frame: pd.DataFrame, data_dir: Path, hospital: str) -> np.ndarray:
    """``ICULOS`` for each feature row, joined on (pid, t) from the clean Parquet."""
    table = pq.read_table(
        data_dir / CLEAN_PARQUET,
        columns=["pid", "t", "ICULOS"],
        filters=[("hospital", "=", hospital)],
    ).to_pandas()
    merged = frame[["pid", "t"]].merge(table, on=["pid", "t"], how="left", validate="1:1")
    values = merged["ICULOS"].to_numpy(dtype=np.float64)
    if np.isnan(values).any():
        raise ValueError("rows without ICULOS")
    return values


def _block(
    cohort: Cohort,
    scores: np.ndarray,
    alerts: np.ndarray,
    keep: np.ndarray,
    weights: np.ndarray,
    samples_out: dict[str, np.ndarray],
) -> dict[str, object]:
    """Metrics on the ``keep`` rows of the target cohort, with bootstrap CIs."""
    labels, patient = cohort.labels, cohort.patient
    ranking = m.Ranking.build(scores[keep], labels[keep])
    reference = m.subset_reference(labels, patient, keep)
    parts = m.utility_parts(labels, alerts & keep, patient, reference)
    band_patient = patient[keep]

    def stat(w: np.ndarray | None) -> dict[str, float]:
        row_w = None if w is None else w[band_patient]
        return {
            "auroc": ranking.auroc(row_w),
            "auprc": ranking.auprc(row_w),
            "utility": parts.normalized(w),
            "alert_rate": m.alert_rate(alerts[keep], band_patient, w),
        }

    point = stat(None)
    samples = m.bootstrap_samples(stat, weights)
    samples_out.update(samples)
    samples_out["point_utility"] = np.asarray(point["utility"])
    return {
        "rows": int(keep.sum()),
        "patients": len(np.unique(band_patient)),
        "label1_rows": int(labels[keep].sum()),
        "septic_patients_with_label1_rows": len(np.unique(patient[keep & (labels == 1)])),
        "point": point,
        "ci95": {k: list(m.percentile_ci(v)) for k, v in samples.items()},
    }


def collapse_check(model_doc: dict[str, object]) -> dict[str, object]:
    """ADR 0024 item 1 for one model in one direction."""
    overall = model_doc["overall"]
    assert isinstance(overall, dict)
    overall_auroc = float(overall["point"]["auroc"])
    flagged: list[dict[str, object]] = []
    bands = model_doc["bands"]
    assert isinstance(bands, dict)
    for name, block in bands.items():
        point = float(block["point"]["auroc"])
        upper = float(block["ci95"]["auroc"][1])
        reasons = []
        if upper < COLLAPSE_CI_UPPER:
            reasons.append(f"AUROC CI upper bound {upper:.3f} < {COLLAPSE_CI_UPPER}")
        if point < overall_auroc - COLLAPSE_DROP:
            reasons.append(f"AUROC {point:.3f} more than {COLLAPSE_DROP} below {overall_auroc:.3f}")
        if reasons:
            flagged.append({"band": name, "reasons": reasons})
    return {"collapse": bool(flagged), "flagged_bands": flagged}


def _paired(lgbm: dict[str, np.ndarray], lr: dict[str, np.ndarray]) -> dict[str, object]:
    diff = lgbm["utility"] - lr["utility"]
    point = float(lgbm["point_utility"] - lr["point_utility"])
    return {
        "point": point,
        "ci95": list(m.percentile_ci(diff)),
        "share_of_resamples_above_0": float(np.nanmean(diff > 0)),
    }


def _check_overall(
    overall: dict[str, object], results_dir: Path, model: str, direction: str
) -> None:
    """The all-rows block must reproduce the committed headline AUROC and utility."""
    doc = json.loads((results_dir / f"{model}_{direction}.json").read_text(encoding="utf-8"))
    committed = doc["strict_external"]["point"]
    point = overall["point"]
    assert isinstance(point, dict)
    for key in ("auroc", "utility", "alert_rate"):
        if abs(float(point[key]) - float(committed[key])) > 1e-12:
            raise ValueError(f"{model} {direction}: overall {key} differs from the committed one")


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
        committed = _committed_threshold(results_dir, p.model, direction)
        if p.threshold != committed:
            raise ValueError(f"{p.model} {direction}: threshold differs from the committed one")
    frame = read_features(data_dir, target_h)
    target = target_context(frame, _split_pids(splits_dir, target_h), cfg.seed)
    band = band_of(attach_iculos(target.full.frame, data_dir, target_h))
    weights = target.full_weights
    everything = np.ones(len(band), dtype=bool)

    models_doc: dict[str, object] = {}
    samples: dict[str, dict[str, dict[str, np.ndarray]]] = {}
    for p in prepared:
        scores = p.scorer.score(target.full.frame)
        alerts = scores >= p.threshold
        per: dict[str, dict[str, np.ndarray]] = {}
        overall_samples: dict[str, np.ndarray] = {}
        overall = _block(target.full, scores, alerts, everything, weights, overall_samples)
        _check_overall(overall, results_dir, p.model, direction)
        bands_doc: dict[str, object] = {}
        for i, (name, _, _) in enumerate(BANDS):
            s: dict[str, np.ndarray] = {}
            block = _block(target.full, scores, alerts, band == i, weights, s)
            per[name] = s
            bands_doc[name] = block
        doc: dict[str, object] = {
            "model_label": MODEL_LABELS[p.model],
            "threshold": p.threshold,
            "overall": overall,
            "bands": bands_doc,
        }
        if p.model == "lgbm":
            doc["adr_0024_item_1"] = collapse_check(doc)
        models_doc[p.model] = doc
        samples[p.model] = per

    paired = {name: _paired(samples["lgbm"][name], samples["lr"][name]) for name, _, _ in BANDS}
    return {
        "direction": direction,
        "source": source_h,
        "target": target_h,
        "analysis": "C1 shortcut check: metrics within ICU-stay bands (ADR 0024 items 1-2)",
        "band_variable": "ICULOS (hours since ICU admission), grouping only, never a feature",
        "bands": [{"name": n, "iculos_from": lo, "iculos_to": hi} for n, lo, hi in BANDS],
        "thresholds": "headline thresholds from the source validation split (unchanged)",
        "alarm_budget": cfg.alarm_budget,
        "seed": cfg.seed,
        "bootstrap_resamples": RESAMPLES,
        "collapse_rule": (
            f"LightGBM collapses within bands if any band has an AUROC 95 % CI upper bound "
            f"below {COLLAPSE_CI_UPPER} or a point AUROC more than {COLLAPSE_DROP} below its "
            "overall AUROC in this direction"
        ),
        "models": models_doc,
        "paired_utility_lgbm_minus_lr": paired,
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
        path = results_dir / f"bands_{direction}.json"
        write_json(path, doc)
        written.append(path)
    return written
