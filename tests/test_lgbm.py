"""LightGBM main model: reproducible, text + whitelisted JSON, training split only."""

from __future__ import annotations

import getpass
import json
import socket
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sepsiscope.config import REPO_ROOT, load_config
from sepsiscope.data.io import COLUMNS, MEASUREMENTS
from sepsiscope.data.splits import split_document, write_split
from sepsiscope.features.causal import EXCLUDED, causal_features, schema_document
from sepsiscope.features.pipeline import feature_path, write_features
from sepsiscope.models import lgbm
from sepsiscope.models.pipeline import train_direction

CFG = load_config()
SMALL = {"num_leaves": 7, "min_child_samples": 5}


def hospital(name: str, n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for k in range(n):
        hours = int(rng.integers(10, 30))
        first = int(rng.integers(0, hours - 2)) if k % 4 == 0 else hours
        rows += [
            {"pid": f"p{seed}{k:05d}", "hospital": name, "t": t, "y": int(t >= first)}
            for t in range(hours)
        ]
    frame = pd.DataFrame(rows)
    m = len(frame)
    for col in COLUMNS:
        frame[col] = rng.normal(50, 10, m).astype(np.float32)
    frame["HR"] = (80 + 30 * frame["y"] + rng.normal(0, 10, m)).astype(np.float32)
    for col in MEASUREMENTS:
        if col != "HR":
            frame.loc[rng.random(m) < 0.7, col] = np.nan
    frame["Gender"] = np.float32(1)
    frame["SepsisLabel"] = frame.pop("y").astype(np.int8)
    return frame


def features_frame() -> pd.DataFrame:
    return causal_features(hospital("A", 120, 1), CFG.features)


def names(frame: pd.DataFrame) -> list[str]:
    return [c for c in frame.columns if c not in ("pid", "hospital", "t", "SepsisLabel")]


def test_training_is_byte_reproducible_and_round_trips(tmp_path: Path) -> None:
    frame = features_frame()
    feats = names(frame)
    a = lgbm.train(frame, feats, "A2B", "A", SMALL)
    b = lgbm.train(frame, feats, "A2B", "A", SMALL)
    assert a.booster.model_to_string() == b.booster.model_to_string()
    lgbm.save(a, tmp_path / "m", schema_document(CFG.features, feats))
    loaded = lgbm.load(tmp_path / "m")
    np.testing.assert_array_equal(
        lgbm.predict_proba(loaded, frame, feats), lgbm.predict_proba(a, frame, feats)
    )


def test_saved_files_hold_no_paths_and_only_whitelisted_fields(tmp_path: Path) -> None:
    frame = features_frame()
    feats = names(frame)
    model = lgbm.train(frame, feats, "A2B", "A", SMALL)
    folder = lgbm.save(model, tmp_path / "m", schema_document(CFG.features, feats))
    info = json.loads((folder / "model.json").read_text())
    assert set(info) == lgbm.MODEL_JSON_FIELDS
    assert len(info["data_sha256"]) == 64
    for path in folder.iterdir():
        text = path.read_text(encoding="utf-8")
        for secret in (str(Path.home()), str(REPO_ROOT), getpass.getuser(), socket.gethostname()):
            assert secret not in text, path.name
    schema = json.loads((folder / "feature_schema.json").read_text())
    assert not set(EXCLUDED) & {f["name"] for f in schema["features"]}


def test_data_fingerprint_depends_on_contents_only() -> None:
    x = np.arange(6, dtype=np.float32).reshape(3, 2)
    y = np.array([0, 1, 0])
    assert lgbm.data_sha256(x, y, ["a", "b"]) == lgbm.data_sha256(x.copy(), y.copy(), ["a", "b"])
    x2 = x.copy()
    x2[0, 0] = 99
    assert lgbm.data_sha256(x2, y, ["a", "b"]) != lgbm.data_sha256(x, y, ["a", "b"])


def test_class_weighting_is_refused() -> None:
    for bad in ({"is_unbalance": True}, {"scale_pos_weight": 10.0}):
        with pytest.raises(ValueError):
            lgbm.make_params(bad)
    assert "is_unbalance" not in lgbm.make_params() and lgbm.make_params()["deterministic"]


def test_inner_split_is_by_patient() -> None:
    pids = np.repeat(np.array([f"p{i}" for i in range(50)]), 3)
    held = lgbm.inner_split(pids, 42)
    per_patient = pd.Series(held).groupby(pids).nunique()
    assert (per_patient == 1).all()  # a patient is never split
    assert held.sum() == 10 * 3


def test_train_direction_uses_training_split_only(tmp_path: Path) -> None:
    raw = hospital("A", 120, 1)
    write_features(causal_features(raw, CFG.features), feature_path(tmp_path, "A"))
    flags = raw.groupby("pid")["SepsisLabel"].max().astype(bool).to_dict()
    doc = split_document("A", flags, 42)
    write_split(tmp_path / "splits" / "hospital_A.json", doc)
    r = train_direction("A2B", CFG, tmp_path, tmp_path / "splits", tmp_path / "models", SMALL)
    info = json.loads((r.folder / "model.json").read_text())
    train_ids = doc["train"]
    assert isinstance(train_ids, list)
    assert info["train_patients"] == len(train_ids) == r.train_patients
    assert info["train_rows"] == int(raw["pid"].isin(train_ids).sum())
    booster_names = lgbm.load(r.folder).booster.feature_name()
    assert len(booster_names) == info["features"]
    assert "HR" in booster_names and "shock_index" in booster_names
    assert not set(EXCLUDED) & set(booster_names)
