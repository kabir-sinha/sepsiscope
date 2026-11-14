"""Ablations (protocol section 8, ADR 0015, plan B5) and the hospital drift summary.

Each ablation is a LightGBM model on a different feature set, trained with the **main
model's tuned parameters** (no re-tuning; ADR 0022 limitation) on the source training
split, Platt-calibrated on the source calibration split, thresholded on the source
validation split, then evaluated on the target exactly like the main model (strict and
deployment adaptation, 1,000 patient-level bootstrap resamples).

| name                      | feature set                                                    |
|---------------------------|----------------------------------------------------------------|
| no_measurement_process    | main features without "hours since" and "measurements so far"  |
| vitals_only               | 8 vitals' last values, shock index, their trends and their     |
|                           | measurement-process features; no labs, no demographics         |
| icu_time_added            | main + ICULOS, HospAdmTime, Unit1, Unit2                       |
| units_added               | main + Unit1, Unit2                                            |
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd

from sepsiscope.config import Config
from sepsiscope.data.eda import js_divergence
from sepsiscope.data.io import LABEL, VITALS
from sepsiscope.evaluation import metrics as m
from sepsiscope.evaluation.run import (
    DIRECTIONS,
    Prepared,
    Scorer,
    _split_pids,
    evaluate_prepared,
    target_context,
    write_json,
)
from sepsiscope.features.causal import ICU_TIME, UNIT_COLUMNS, FeatureSpec, feature_specs
from sepsiscope.features.pipeline import ABLATION_SUFFIX, read_features
from sepsiscope.models import calibration, lgbm
from sepsiscope.models.tuning import tuned_settings

ABLATIONS: tuple[str, ...] = (
    "no_measurement_process",
    "vitals_only",
    "icu_time_added",
    "units_added",
)
LABELS: dict[str, str] = {
    "no_measurement_process": "LightGBM without measurement-process features (protocol 8.1)",
    "vitals_only": "LightGBM, vitals only (protocol 8.2)",
    "icu_time_added": "LightGBM + ICULOS, HospAdmTime, Unit1, Unit2 (protocol 8.3)",
    "units_added": "LightGBM + Unit1, Unit2 only (ADR 0015)",
}


def _vital_feature(spec: FeatureSpec) -> bool:
    return spec.source in VITALS or spec.name == "shock_index"


def ablation_features(name: str, cfg: Config) -> list[str]:
    main = feature_specs(cfg.features)
    if name == "no_measurement_process":
        return [s.name for s in main if s.group != "measurement_process"]
    if name == "vitals_only":
        keep = {"vitals", "trends", "measurement_process"}
        return [s.name for s in main if s.group in keep and _vital_feature(s)]
    if name == "icu_time_added":
        return [s.name for s in main] + [*ICU_TIME, *UNIT_COLUMNS]
    if name == "units_added":
        return [s.name for s in main] + list(UNIT_COLUMNS)
    raise ValueError(f"unknown ablation {name!r}")


def prepare_ablation(
    name: str,
    direction: str,
    cfg: Config,
    source: pd.DataFrame,
    splits: dict[str, set[str]],
    tuning_dir: Path,
    models_dir: Path,
) -> Prepared:
    features = ablation_features(name, cfg)
    settings = tuned_settings(tuning_dir / f"lgbm_{direction}.json")
    if settings is None:
        raise FileNotFoundError("tuned parameters missing; run B2 first")
    tunable, rounds = settings
    source_h, _ = DIRECTIONS[direction]
    train = source[source["pid"].isin(splits["train"])]
    model = lgbm.train(train, features, direction, source_h, tunable, rounds, cfg.seed)
    folder = models_dir / "ablations" / f"{name}_{direction}"
    lgbm.save(model, folder, {"ablation": name, "features": features})
    booster = model.booster

    def raw(frame: pd.DataFrame) -> np.ndarray:
        return np.asarray(booster.predict(lgbm.matrix(frame, features), raw_score=True))

    cal = source[source["pid"].isin(splits["calibration"])]
    platt = calibration.fit_platt(raw(cal), cal[LABEL].to_numpy())

    def prob(frame: pd.DataFrame) -> np.ndarray:
        return platt.predict(raw(frame))

    fitted = {
        "features": len(features),
        "num_trees": booster.num_trees(),
        "parameters": "main model's tuned parameters (not re-tuned)",
        "platt": {"coef": platt.coef, "intercept": platt.intercept},
    }
    scorer = Scorer(f"ablation_{name}", prob, prob, fitted)
    val = source[source["pid"].isin(splits["val"])]
    threshold, val_rate = m.budget_threshold(prob(val), cfg.alarm_budget)
    return Prepared(f"ablation_{name}", scorer, threshold, val_rate)


def drift_document(data_dir: Path, cfg: Config) -> dict[str, object]:
    """Jensen-Shannon divergence A vs B of every feature (non-missing values), by group."""
    specs = feature_specs(cfg.features.model_copy(update={"icu_time": True, "unit_columns": True}))
    frames = {h: read_features(data_dir, h, ABLATION_SUFFIX) for h in ("A", "B")}
    rows = []
    for spec in specs:
        a = frames["A"][spec.name].to_numpy(dtype=np.float64)
        b = frames["B"][spec.name].to_numpy(dtype=np.float64)
        rows.append(
            {
                "name": spec.name,
                "group": spec.group,
                "js_divergence": js_divergence(a[~np.isnan(a)], b[~np.isnan(b)]),
                "missing_A": float(np.isnan(a).mean()),
                "missing_B": float(np.isnan(b).mean()),
            }
        )
    table = pd.DataFrame(rows)
    by_group = {
        str(g): {
            "features": len(part),
            "mean_js": float(part["js_divergence"].mean()),
            "median_js": float(part["js_divergence"].median()),
            "max_js": float(part["js_divergence"].max()),
        }
        for g, part in table.groupby("group", sort=False)
    }
    return {
        "measure": "Jensen-Shannon divergence (base 2, 50 equal-count pooled bins), A vs B, "
        "all rows, non-missing values",
        "by_group": by_group,
        "features": table.sort_values("js_divergence", ascending=False, kind="stable").to_dict(
            "records"
        ),
    }


def run(
    cfg: Config,
    data_dir: Path,
    splits_dir: Path,
    results_dir: Path,
    tuning_dir: Path,
    models_dir: Path,
    names: tuple[str, ...] = ABLATIONS,
    directions: tuple[str, ...] = tuple(DIRECTIONS),
    progress: Callable[[str], None] = lambda _: None,
) -> list[Path]:
    from sepsiscope.evaluation import run as run_mod

    run_mod.MODEL_LABELS.update({f"ablation_{n}": LABELS[n] for n in ABLATIONS})
    written: list[Path] = []
    for direction in directions:
        source_h, target_h = DIRECTIONS[direction]
        source = read_features(data_dir, source_h, ABLATION_SUFFIX)
        splits = _split_pids(splits_dir, source_h)
        prepared = [
            prepare_ablation(n, direction, cfg, source, splits, tuning_dir, models_dir)
            for n in names
        ]
        del source
        target = target_context(
            read_features(data_dir, target_h, ABLATION_SUFFIX),
            _split_pids(splits_dir, target_h),
            cfg.seed,
        )
        for p in prepared:
            path = results_dir / f"{p.model}_{direction}.json"
            write_json(path, evaluate_prepared(p, direction, cfg, target))
            written.append(path)
            progress(path.name)
        del target
    path = results_dir / "drift.json"
    write_json(path, drift_document(data_dir, cfg))
    written.append(path)
    return written


def summary(results_dir: Path) -> dict[str, dict[str, float]]:
    """Strict alert rate and utility per ablation and direction (for the report)."""
    out: dict[str, dict[str, float]] = {}
    for path in sorted(results_dir.glob("ablation_*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        out[path.stem] = doc["strict_external"]["point"]
    return out
