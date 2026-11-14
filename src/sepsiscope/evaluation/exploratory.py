"""POST-HOC, EXPLORATORY analysis (not pre-registered; the headline model is unchanged).

Question: the cumulative "measurements so far" counts (``<var>__n``) dominate the A2B
explanations, and a cumulative count grows with time in the ICU, so it partly proxies
ICU length of stay (excluded from the main model by protocol section 3). Here each count
is replaced by **measurements per hour of stay**, ``<var>__n / (t + 1)`` (causal: uses
hours <= t only), and LightGBM is retrained with the **same tuned parameters**, Platt-
calibrated on the source calibration split and thresholded on the source validation
split, then evaluated on the target exactly like the headline model.
"""

from __future__ import annotations

from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from sepsiscope.config import Config
from sepsiscope.data.io import LABEL
from sepsiscope.evaluation import metrics as m
from sepsiscope.evaluation import run as run_mod
from sepsiscope.evaluation.run import (
    DIRECTIONS,
    Prepared,
    Scorer,
    _split_pids,
    evaluate_prepared,
    target_context,
    write_json,
)
from sepsiscope.features.causal import KEYS
from sepsiscope.features.pipeline import read_features
from sepsiscope.models import calibration, lgbm
from sepsiscope.models.tuning import tuned_settings
from sepsiscope.trust.explain import mean_abs_contribution

NAME = "exploratory_count_rates"
LABEL_TEXT = (
    "POST-HOC, EXPLORATORY: LightGBM with measurements per hour instead of cumulative counts"
)


def with_rates(frame: pd.DataFrame) -> pd.DataFrame:
    """Replace every ``<var>__n`` by ``<var>__rate`` = count / (hours of stay so far)."""
    out = frame.copy()
    hours = out["t"].to_numpy(dtype=np.float64) + 1.0
    for col in [c for c in out.columns if c.endswith("__n")]:
        rate = (out[col].to_numpy(dtype=np.float64) / hours).astype(np.float32)
        out.insert(list(out.columns).index(col), col[:-3] + "__rate", rate)
        out = out.drop(columns=col)
    return out


class _Calibrated:
    """Raw LightGBM score and its Platt probability for a fixed feature list."""

    def __init__(self, booster: lgb.Booster, features: list[str]) -> None:
        self.booster, self.features = booster, features
        self.platt = calibration.Platt(1.0, 0.0)

    def raw(self, frame: pd.DataFrame) -> np.ndarray:
        x = lgbm.matrix(frame, self.features)
        return np.asarray(self.booster.predict(x, raw_score=True), dtype=np.float64)

    def prob(self, frame: pd.DataFrame) -> np.ndarray:
        return self.platt.predict(self.raw(frame))


def run(
    cfg: Config,
    data_dir: Path,
    splits_dir: Path,
    results_dir: Path,
    tuning_dir: Path,
) -> list[Path]:
    run_mod.MODEL_LABELS[NAME] = LABEL_TEXT
    written: list[Path] = []
    for direction in DIRECTIONS:
        source_h, target_h = DIRECTIONS[direction]
        source = with_rates(read_features(data_dir, source_h))
        features = [c for c in source.columns if c not in KEYS]
        splits = _split_pids(splits_dir, source_h)
        settings = tuned_settings(tuning_dir / f"lgbm_{direction}.json")
        if settings is None:
            raise FileNotFoundError("tuned parameters missing")
        train = source[source["pid"].isin(splits["train"])]
        model = lgbm.train(train, features, direction, source_h, *settings, seed=cfg.seed)
        cal = source[source["pid"].isin(splits["calibration"])]
        scorer_fn = _Calibrated(model.booster, features)
        scorer_fn.platt = calibration.fit_platt(scorer_fn.raw(cal), cal[LABEL].to_numpy())
        prob = scorer_fn.prob
        booster = model.booster
        val = source[source["pid"].isin(splits["val"])]
        threshold, val_rate = m.budget_threshold(prob(val), cfg.alarm_budget)
        fitted = {
            "features": len(features),
            "num_trees": booster.num_trees(),
            "parameters": "main model's tuned parameters (not re-tuned)",
        }
        prepared = Prepared(NAME, Scorer(NAME, prob, prob, fitted), threshold, val_rate)
        del source, train, cal, val
        target = target_context(
            with_rates(read_features(data_dir, target_h)),
            _split_pids(splits_dir, target_h),
            cfg.seed,
        )
        result = evaluate_prepared(prepared, direction, cfg, target)
        alerts = prob(target.full.frame) >= threshold
        mean_abs = mean_abs_contribution(booster, lgbm.matrix(target.full.frame, features), alerts)
        order = np.argsort(-mean_abs, kind="stable")[:10]
        result["status"] = "post-hoc, exploratory"
        result["top10_mean_abs_contribution"] = [
            {"name": features[i], "mean_abs_contribution": float(mean_abs[i])} for i in order
        ]
        path = results_dir / f"{NAME}_{direction}.json"
        write_json(path, result)
        written.append(path)
        del target
    return written
