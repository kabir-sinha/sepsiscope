"""LightGBM main model (Batch B, ADR 0022): training, saving as text + JSON, loading.

- Trained on the source hospital's **training** split only.
- Reproducible: ``deterministic=True``, fixed seed and thread count, column-wise histograms.
- No class weighting (``is_unbalance`` / ``scale_pos_weight`` are never set; ADR 0022).
- Saved as LightGBM's own text format plus a small JSON file whose fields are fixed
  (``MODEL_JSON_FIELDS``) and hold no paths, times or machine details (ADR 0004, P2).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd

from sepsiscope.config import REPO_ROOT
from sepsiscope.data.io import LABEL

NUM_THREADS = 8  # fixed, so results do not depend on the machine's core count
MAX_ROUNDS = 2000
EARLY_STOPPING_ROUNDS = 50
INNER_VALID_FRACTION = 0.2  # patients of the training split held out for early stopping

BASE_PARAMS: dict[str, Any] = {
    "objective": "binary",
    "metric": "average_precision",
    "deterministic": True,
    "force_col_wise": True,
    "num_threads": NUM_THREADS,
    "seed": 42,
    "verbosity": -1,
}
# LightGBM defaults for the tunable parameters; B2 replaces them with tuned values.
DEFAULT_TUNABLE: dict[str, Any] = {
    "learning_rate": 0.1,
    "num_leaves": 31,
    "min_child_samples": 20,
    "feature_fraction": 1.0,
    "bagging_fraction": 1.0,
    "bagging_freq": 0,
    "lambda_l1": 0.0,
    "lambda_l2": 0.0,
}
FORBIDDEN_PARAMS = frozenset({"is_unbalance", "scale_pos_weight"})
MODEL_JSON_FIELDS = frozenset(
    {
        "model",
        "direction",
        "source_hospital",
        "params",
        "num_trees",
        "rounds_source",
        "features",
        "train_patients",
        "train_rows",
        "data_sha256",
        "git_commit",
        "lightgbm_version",
    }
)


def make_params(tunable: Mapping[str, Any] | None = None, seed: int = 42) -> dict[str, Any]:
    params = {**BASE_PARAMS, **DEFAULT_TUNABLE, **(tunable or {}), "seed": seed}
    bad = FORBIDDEN_PARAMS & set(params)
    if bad:
        raise ValueError(f"class weighting is not allowed (ADR 0022): {sorted(bad)}")
    return params


def matrix(frame: pd.DataFrame, features: Sequence[str]) -> np.ndarray:
    return np.ascontiguousarray(frame[list(features)].to_numpy(dtype=np.float32))


def data_sha256(x: np.ndarray, y: np.ndarray, features: Sequence[str]) -> str:
    """SHA-256 of the training data contents only: names, values and labels (P2)."""
    h = hashlib.sha256()
    h.update("\n".join(features).encode("utf-8"))
    h.update(np.ascontiguousarray(x, dtype=np.float32).tobytes())
    h.update(np.ascontiguousarray(y, dtype=np.int8).tobytes())
    return h.hexdigest()


def inner_split(pids: np.ndarray, seed: int) -> np.ndarray:
    """Boolean mask of rows whose patient is held out for early stopping (by patient)."""
    patients = np.unique(pids)
    rng = np.random.default_rng(seed)
    n_hold = max(1, round(len(patients) * INNER_VALID_FRACTION))
    held = set(rng.choice(patients, size=n_hold, replace=False).tolist())
    return np.fromiter((p in held for p in pids), dtype=bool, count=len(pids))


def fit(
    x: np.ndarray,
    y: np.ndarray,
    params: Mapping[str, Any],
    rounds: int,
    valid: tuple[np.ndarray, np.ndarray] | None = None,
    feature_names: Sequence[str] | None = None,
) -> lgb.Booster:
    """One LightGBM fit; with ``valid`` it stops early on validation average precision."""
    if feature_names is None:
        train_set = lgb.Dataset(x, label=y, free_raw_data=True)
    else:
        train_set = lgb.Dataset(x, label=y, feature_name=list(feature_names), free_raw_data=True)
    callbacks: list[Any] = []
    valid_sets: list[lgb.Dataset] = []
    if valid is not None:
        valid_sets = [lgb.Dataset(valid[0], label=valid[1], reference=train_set)]
        callbacks = [lgb.early_stopping(EARLY_STOPPING_ROUNDS, verbose=False)]
    return lgb.train(
        dict(params), train_set, num_boost_round=rounds, valid_sets=valid_sets, callbacks=callbacks
    )


@dataclass(frozen=True)
class TrainedModel:
    booster: lgb.Booster
    info: dict[str, Any]


def train(
    train_frame: pd.DataFrame,
    features: Sequence[str],
    direction: str,
    source_hospital: str,
    tunable: Mapping[str, Any] | None = None,
    rounds: int | None = None,
    seed: int = 42,
) -> TrainedModel:
    """Fit on the given training rows.

    Without ``rounds`` the number of trees is found by early stopping on a patient-grouped
    inner hold-out of these rows, then the model is refitted on all of them with that many
    trees. With ``rounds`` (from tuning) it is fitted once.
    """
    params = make_params(tunable, seed)
    x, y = matrix(train_frame, features), train_frame[LABEL].to_numpy().astype(np.int8)
    if rounds is None:
        held = inner_split(train_frame["pid"].to_numpy(), seed)
        probe = fit(x[~held], y[~held], params, MAX_ROUNDS, (x[held], y[held]), features)
        rounds = max(1, int(probe.best_iteration))
        source = "early stopping on a patient-grouped 20 % inner hold-out of the training split"
    else:
        source = "given (tuning)"
    booster = fit(x, y, params, rounds, feature_names=features)
    info = {
        "model": "lgbm",
        "direction": direction,
        "source_hospital": source_hospital,
        "params": params,
        "num_trees": booster.num_trees(),
        "rounds_source": source,
        "features": len(features),
        "train_patients": int(train_frame["pid"].nunique()),
        "train_rows": len(train_frame),
        "data_sha256": data_sha256(x, y, features),
        "git_commit": git_commit(),
        "lightgbm_version": version("lightgbm"),
    }
    return TrainedModel(booster, info)


def git_commit() -> str:
    """The current commit hash only (no remote URL, no paths)."""
    try:
        exe = shutil.which("git") or "git"
        out = subprocess.run(  # noqa: S603 - fixed executable and arguments
            [exe, "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    commit = out.stdout.strip()
    return (
        commit if len(commit) == 40 and all(c in "0123456789abcdef" for c in commit) else "unknown"
    )


def save(model: TrainedModel, folder: Path, schema: Mapping[str, object]) -> Path:
    """``model.txt`` (LightGBM text), ``model.json`` (whitelisted fields), feature schema."""
    if set(model.info) != MODEL_JSON_FIELDS:
        raise ValueError("model.json fields differ from the whitelist")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "model.txt").write_text(model.booster.model_to_string(), encoding="utf-8")
    (folder / "model.json").write_text(json.dumps(model.info, indent=1) + "\n", encoding="utf-8")
    (folder / "feature_schema.json").write_text(
        json.dumps(schema, indent=1) + "\n", encoding="utf-8"
    )
    return folder


def load(folder: Path) -> TrainedModel:
    booster = lgb.Booster(model_str=(folder / "model.txt").read_text(encoding="utf-8"))
    info = json.loads((folder / "model.json").read_text(encoding="utf-8"))
    return TrainedModel(booster, info)


def predict_proba(model: TrainedModel, frame: pd.DataFrame, features: Sequence[str]) -> np.ndarray:
    return np.asarray(model.booster.predict(matrix(frame, features)), dtype=np.float64)
