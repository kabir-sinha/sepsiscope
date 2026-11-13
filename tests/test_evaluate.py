"""End-to-end `evaluate` on two small synthetic hospitals (never real data)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sepsiscope.config import load_config
from sepsiscope.data.figures import FORBIDDEN_PNG_CHUNKS, png_chunk_types
from sepsiscope.data.io import COLUMNS, MEASUREMENTS
from sepsiscope.data.splits import split_document, write_split
from sepsiscope.evaluation import run as run_mod
from sepsiscope.features.causal import causal_features
from sepsiscope.features.pipeline import feature_path, write_features

CFG = load_config()


def hospital(name: str, n: int, seed: int) -> pd.DataFrame:
    """Septic patients have rising HR and Resp before the label turns 1."""
    rng = np.random.default_rng(seed)
    rows = []
    for k in range(n):
        hours = int(rng.integers(12, 40))
        septic = k % 4 == 0
        first_pos = int(rng.integers(0, hours - 2)) if septic else hours
        for t in range(hours):
            rows.append(
                {"pid": f"p{seed}{k:05d}", "hospital": name, "t": t, "lab": int(t >= first_pos)}
            )
    frame = pd.DataFrame(rows)
    m = len(frame)
    for col in COLUMNS:
        frame[col] = rng.normal(50, 10, m).astype(np.float32)
    drift = (frame["lab"] * 1.0 + rng.normal(0, 0.5, m)).astype(np.float32)
    frame["HR"] = (80 + 25 * drift).astype(np.float32)
    frame["Resp"] = (16 + 8 * drift).astype(np.float32)
    frame["Temp"] = (37 + drift).astype(np.float32)
    frame["SBP"] = (120 - 20 * drift).astype(np.float32)
    frame["O2Sat"] = (97 - 3 * drift).astype(np.float32)
    for col in MEASUREMENTS:
        if col not in ("HR", "Resp", "Temp", "SBP", "O2Sat"):
            frame.loc[rng.random(m) < 0.8, col] = np.nan
    frame["FiO2"] = np.where(rng.random(m) < 0.1, 0.4, np.nan).astype(np.float32)
    frame["Gender"] = (frame["pid"].str[-1].astype(int) % 2).astype(np.float32)
    frame["Age"] = np.where(frame["pid"].str[-2].astype(int) % 2 == 0, 50, 70).astype(np.float32)
    frame["SepsisLabel"] = frame.pop("lab").astype(np.int8)
    return frame


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(run_mod, "RESAMPLES", 25)
    for name, seed in (("A", 1), ("B", 2)):
        frame = hospital(name, 80, seed)
        write_features(causal_features(frame, CFG.features), feature_path(tmp_path, name))
        flags = frame.groupby("pid")["SepsisLabel"].max().astype(bool).to_dict()
        write_split(tmp_path / "splits" / f"hospital_{name}.json", split_document(name, flags, 42))
    return tmp_path


def run_all(root: Path, out: str) -> list[Path]:
    return run_mod.run(
        list(run_mod.MODELS),
        ["A2B", "B2A"],
        CFG,
        root,
        root / "splits",
        root / out / "results",
        root / out / "models",
        root / out / "figures",
    )


def test_evaluate_is_complete_reproducible_and_has_no_ids(workspace: Path) -> None:
    first, second = run_all(workspace, "one"), run_all(workspace, "two")
    names = sorted(p.name for p in first)
    assert "lr_A2B.json" in names and "decision_curve_B2A.json" in names
    assert "reliability_A2B.png" in names
    for a, b in zip(first, second, strict=True):
        assert a.read_bytes() == b.read_bytes(), a.name
    for path in first:
        if path.suffix == ".json":
            text = path.read_text(encoding="utf-8")
            assert '"p1' not in text and '"p2' not in text  # no patient IDs
            json.loads(text)  # strict JSON (no NaN)
        else:
            assert not set(png_chunk_types(path)) & FORBIDDEN_PNG_CHUNKS
    assert (workspace / "one" / "models" / "baselines" / "lr_A2B" / "feature_schema.json").is_file()


def test_strict_threshold_comes_from_source_validation(workspace: Path) -> None:
    run_all(workspace, "out")
    result = json.loads((workspace / "out" / "results" / "news2_A2B.json").read_text())
    strict = result["strict_external"]
    assert strict["source_validation_alert_rate"] <= CFG.alarm_budget
    assert strict["patients"] == 80  # every target patient
    adapted = result["deployment_adaptation"]
    assert adapted["target_calibration_alert_rate"] <= CFG.alarm_budget
    assert adapted["patients"] == 64  # target train + validation splits only (80 %)
    assert "sensitivity_fio2_carry_24h" in result
    assert set(strict["ci95"]) >= {"auroc", "auprc", "utility", "timely_sensitivity"}
