"""Ablation feature sets and an end-to-end ablation run on synthetic hospitals."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sepsiscope.config import load_config
from sepsiscope.data.io import LABS
from sepsiscope.data.splits import split_document, write_split
from sepsiscope.evaluation import ablation
from sepsiscope.evaluation import run as run_mod
from sepsiscope.features.causal import EXCLUDED, causal_features
from sepsiscope.features.pipeline import ABLATION_SUFFIX, feature_path, write_features

CFG = load_config()


def test_feature_sets() -> None:
    sets = {n: ablation.ablation_features(n, CFG) for n in ablation.ABLATIONS}
    assert len(sets["no_measurement_process"]) == 130 - 68
    assert not any("__hsl" in f or "__n" in f for f in sets["no_measurement_process"])
    vitals = sets["vitals_only"]
    assert len(vitals) == 8 + 1 + 24 + 16
    assert not any(f.split("__")[0] in LABS for f in vitals)
    assert "Age" not in vitals and "Gender" not in vitals and "bun_creatinine" not in vitals
    assert set(EXCLUDED) <= set(sets["icu_time_added"]) and len(sets["icu_time_added"]) == 134
    assert set(sets["units_added"]) - set(sets["icu_time_added"]) == set()
    assert {"Unit1", "Unit2"} <= set(sets["units_added"]) and "ICULOS" not in sets["units_added"]


def test_ablation_run_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from test_evaluate import hospital  # same synthetic generator as the evaluate tests

    monkeypatch.setattr(run_mod, "RESAMPLES", 20)
    full = CFG.features.model_copy(update={"icu_time": True, "unit_columns": True})
    for name, seed in (("A", 1), ("B", 2)):
        frame = hospital(name, 80, seed)
        write_features(causal_features(frame, full), feature_path(tmp_path, name, ABLATION_SUFFIX))
        flags = frame.groupby("pid")["SepsisLabel"].max().astype(bool).to_dict()
        write_split(tmp_path / "splits" / f"hospital_{name}.json", split_document(name, flags, 42))
    best = {"params": {"num_leaves": 7, "min_child_samples": 5}, "median_rounds": 20}
    for direction in ("A2B", "B2A"):
        tuning = tmp_path / "tuning" / f"lgbm_{direction}.json"
        tuning.parent.mkdir(parents=True, exist_ok=True)
        tuning.write_text(json.dumps({"best": best}))
    written = ablation.run(
        CFG,
        tmp_path,
        tmp_path / "splits",
        tmp_path / "results",
        tmp_path / "tuning",
        tmp_path / "models",
    )
    names = {p.name for p in written}
    assert "ablation_vitals_only_B2A.json" in names and "drift.json" in names
    doc = json.loads((tmp_path / "results" / "ablation_units_added_A2B.json").read_text())
    assert doc["fitted"]["features"] == 132
    assert doc["strict_external"]["source_validation_alert_rate"] <= CFG.alarm_budget
    drift = json.loads((tmp_path / "results" / "drift.json").read_text())
    assert {"measurement_process", "icu_time", "unit_columns"} <= set(drift["by_group"])
    for path in written:
        assert '"p1' not in path.read_text() and '"p2' not in path.read_text()
