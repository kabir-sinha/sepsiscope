"""Tuning per ADR 0021 on synthetic data: reproducible, guarded, resumable, training only."""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from sepsiscope.config import REPO_ROOT, load_config
from sepsiscope.data.io import COLUMNS, MEASUREMENTS
from sepsiscope.data.splits import split_document, write_split
from sepsiscope.features.causal import KEYS, causal_features
from sepsiscope.features.pipeline import feature_path, write_features
from sepsiscope.models import tuning

CFG = load_config()


def hospital(n: int = 80, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for k in range(n):
        hours = int(rng.integers(10, 25))
        first = int(rng.integers(0, hours - 2)) if k % 3 == 0 else hours
        rows += [
            {"pid": f"p{seed}{k:05d}", "hospital": "A", "t": t, "y": int(t >= first)}
            for t in range(hours)
        ]
    frame = pd.DataFrame(rows)
    m = len(frame)
    for col in COLUMNS:
        frame[col] = rng.normal(50, 10, m).astype(np.float32)
    frame["HR"] = (80 + 25 * frame["y"] + rng.normal(0, 10, m)).astype(np.float32)
    for col in MEASUREMENTS:
        if col != "HR":
            frame.loc[rng.random(m) < 0.8, col] = np.nan
    frame["SepsisLabel"] = frame.pop("y").astype(np.int8)
    return frame


def data() -> tuning.TuneData:
    feats = causal_features(hospital(), CFG.features)
    return tuning.prepare(feats, [c for c in feats.columns if c not in KEYS])


def test_folds_never_share_a_patient() -> None:
    feats = causal_features(hospital(), CFG.features)
    d = tuning.prepare(feats, [c for c in feats.columns if c not in KEYS])
    pids = feats["pid"].to_numpy()
    assert len(d.folds) == tuning.N_FOLDS
    for tr, va in d.folds:
        assert not set(pids[tr]) & set(pids[va])


def test_three_trial_study_is_reproducible(tmp_path: Path) -> None:
    d = data()
    a = tuning.tune(d, "A2B", tmp_path / "s1", tmp_path / "r1.json", n_trials=3)
    b = tuning.tune(d, "A2B", tmp_path / "s2", tmp_path / "r2.json", n_trials=3)
    assert a.state == b.state == "finished" and a.completed_trials == 3
    assert (tmp_path / "r1.json").read_bytes() == (tmp_path / "r2.json").read_bytes()
    doc = json.loads((tmp_path / "r1.json").read_text())
    assert doc["resumed"] is False and doc["completed_trials"] == 3
    text = (tmp_path / "r1.json").read_text()
    assert '"p1' not in text and str(REPO_ROOT) not in text and str(Path.home()) not in text


def test_guard_stops_and_writes_status(tmp_path: Path) -> None:
    ticks = itertools.count(step=3600.0)  # every fold appears to take one hour
    out = tuning.tune(
        data(),
        "A2B",
        tmp_path / "store",
        tmp_path / "result.json",
        n_trials=10,
        guard_after=2,
        budget_hours=6.0,
        clock=lambda: float(next(ticks)),
    )
    assert out.state == "guard_exit" and out.completed_trials == 2
    assert not (tmp_path / "result.json").exists()
    status = json.loads(out.status_path.read_text())
    assert status["state"] == "guard_exit"
    assert status["projected_remaining_hours"] > 6.0
    assert (tmp_path / "store" / "lgbm_A2B.journal").stat().st_size > 0
    assert tuning.GUARD_EXIT_CODE == 3


def test_same_command_resumes_from_the_journal(tmp_path: Path) -> None:
    d = data()
    first = tuning.tune(d, "B2A", tmp_path / "store", tmp_path / "r.json", n_trials=2)
    assert first.completed_trials == 2 and not first.resumed
    second = tuning.tune(d, "B2A", tmp_path / "store", tmp_path / "r.json", n_trials=3)
    assert second.resumed and second.completed_trials == 3
    doc = json.loads((tmp_path / "r.json").read_text())
    assert doc["resumed"] is True and doc["completed_trials"] == 3


def test_load_training_uses_the_training_split_only(tmp_path: Path) -> None:
    raw = hospital()
    write_features(causal_features(raw, CFG.features), feature_path(tmp_path, "A"))
    flags = raw.groupby("pid")["SepsisLabel"].max().astype(bool).to_dict()
    doc = split_document("A", flags, 42)
    write_split(tmp_path / "splits" / "hospital_A.json", doc)
    d = tuning.load_training("A2B", tmp_path, tmp_path / "splits")
    train_ids = doc["train"]
    assert isinstance(train_ids, list)
    assert len(d.y) == int(raw["pid"].isin(train_ids).sum())
