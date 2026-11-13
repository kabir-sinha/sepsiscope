"""Orchestration for `sepsiscope train`: source hospital only, training split only."""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sepsiscope.config import Config
from sepsiscope.data.splits import read_split
from sepsiscope.evaluation.run import DIRECTIONS
from sepsiscope.features.causal import KEYS, schema_document
from sepsiscope.features.pipeline import read_features
from sepsiscope.models import lgbm


def model_folder(models_dir: Path, direction: str) -> Path:
    return models_dir / f"lgbm_{direction}"


def train_ids(splits_dir: Path, hospital: str) -> set[str]:
    ids = read_split(splits_dir / f"hospital_{hospital}.json")["train"]
    assert isinstance(ids, list)
    return {str(x) for x in ids}


@dataclass(frozen=True)
class TrainResult:
    direction: str
    folder: Path
    num_trees: int
    train_rows: int
    train_patients: int
    seconds: float


def train_direction(
    direction: str,
    cfg: Config,
    data_dir: Path,
    splits_dir: Path,
    models_dir: Path,
    tunable: Mapping[str, Any] | None = None,
    rounds: int | None = None,
) -> TrainResult:
    """Load only the source hospital, keep its training split, fit and save."""
    source, _ = DIRECTIONS[direction]
    frame = read_features(data_dir, source)
    train = frame[frame["pid"].isin(train_ids(splits_dir, source))].reset_index(drop=True)
    del frame
    features = [c for c in train.columns if c not in KEYS]
    start = time.perf_counter()
    model = lgbm.train(train, features, direction, source, tunable, rounds, cfg.seed)
    seconds = time.perf_counter() - start
    folder = lgbm.save(
        model, model_folder(models_dir, direction), schema_document(cfg.features, features)
    )
    return TrainResult(
        direction,
        folder,
        model.booster.num_trees(),
        len(train),
        int(train["pid"].nunique()),
        seconds,
    )
