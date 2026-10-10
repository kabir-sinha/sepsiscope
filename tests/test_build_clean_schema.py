"""Raw table build, Parquet round-trip, every cleaning rule, and schema rejections."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from conftest import WritePatient

from sepsiscope.data.build import ALL_COLUMNS, build_raw_table, read_parquet, write_parquet
from sepsiscope.data.clean import RULES, RULES_BY_COLUMN, Rule, apply_rules, boundary_evidence
from sepsiscope.data.io import COLUMNS, MEASUREMENTS
from sepsiscope.data.pipeline import build_all, septic_flags, to_frame, to_table
from sepsiscope.data.schema import DataSchemaError, validate_clean, validate_raw


@pytest.fixture
def raw_frame(tiny_dataset: Path) -> pd.DataFrame:
    return to_frame(build_raw_table(tiny_dataset, workers=2))


def test_raw_table_layout(raw_frame: pd.DataFrame) -> None:
    assert tuple(raw_frame.columns) == ALL_COLUMNS
    assert ALL_COLUMNS[:3] == ("pid", "hospital", "t")
    assert ALL_COLUMNS[3:] == COLUMNS
    assert len(COLUMNS) == 41
    assert len(raw_frame) == 20
    assert list(raw_frame["pid"].unique()) == [
        "p000001",
        "p000002",
        "p000003",
        "p100001",
        "p100002",
    ]
    assert raw_frame.loc[raw_frame["pid"] == "p000002", "t"].tolist() == [0, 1, 2, 3, 4]
    assert all(str(raw_frame[c].dtype) == "float32" for c in MEASUREMENTS)
    assert str(raw_frame["SepsisLabel"].dtype) == "int8"
    assert str(raw_frame["ICULOS"].dtype) == "int16"


def test_raw_values_are_copied_unchanged(raw_frame: pd.DataFrame) -> None:
    b2 = raw_frame[raw_frame["pid"] == "p100002"]
    assert b2["FiO2"].tolist() == [0.5, 4000.0]  # the implausible value is kept in raw
    assert np.isnan(b2["HospAdmTime"].iloc[0])
    assert raw_frame["Temp"].iloc[0] == np.float32(36.8)


def test_parquet_round_trip_is_identical(raw_frame: pd.DataFrame, tmp_path: Path) -> None:
    path = tmp_path / "t.parquet"
    write_parquet(to_table(raw_frame), path)
    back = to_frame(read_parquet(path))
    pd.testing.assert_frame_equal(back, raw_frame)
    assert [str(t) for t in back.dtypes] == [str(t) for t in raw_frame.dtypes]


def test_parquet_writing_is_deterministic(raw_frame: pd.DataFrame, tmp_path: Path) -> None:
    write_parquet(to_table(raw_frame), tmp_path / "a.parquet")
    write_parquet(to_table(raw_frame), tmp_path / "b.parquet")
    assert (tmp_path / "a.parquet").read_bytes() == (tmp_path / "b.parquet").read_bytes()


def _frame_with(column: str, values: list[float]) -> pd.DataFrame:
    n = len(values)
    frame = pd.DataFrame({name: np.full(n, np.nan, dtype=np.float32) for name in MEASUREMENTS})
    frame[column] = np.asarray(values, dtype=np.float32)
    frame["hospital"] = ["A"] * (n - 1) + ["B"]
    return frame


@pytest.mark.parametrize("rule", RULES, ids=lambda r: r.column)
def test_each_cleaning_rule(rule: Rule) -> None:
    step = (rule.high - rule.low) * 0.01
    values = [rule.low - step, rule.low, (rule.low + rule.high) / 2, rule.high, rule.high + step]
    raw = _frame_with(rule.column, [*values, float("nan")])
    clean, report = apply_rules(raw, (rule,))
    kept = clean[rule.column].to_numpy()
    assert np.isnan(kept[0])  # below the lower bound -> missing
    assert np.isnan(kept[4])  # above the upper bound -> missing
    np.testing.assert_array_equal(kept[1:4], raw[rule.column].to_numpy()[1:4])  # bounds inclusive
    assert np.isnan(kept[5])  # missing stays missing
    assert raw[rule.column].notna().sum() == 5  # the input frame is not modified
    by_hospital = {r["hospital"]: r for r in report}
    assert by_hospital["A"]["below_low"] == 1
    assert by_hospital["A"]["above_high"] == 1
    assert by_hospital["A"]["set_to_missing"] == 2
    assert by_hospital["A"]["non_missing_before"] == 5
    assert by_hospital["B"]["set_to_missing"] == 0


def test_cleaning_only_touches_rule_columns(raw_frame: pd.DataFrame) -> None:
    clean, report = apply_rules(raw_frame)
    untouched = [c for c in raw_frame.columns if c not in {r.column for r in RULES}]
    pd.testing.assert_frame_equal(clean[untouched], raw_frame[untouched])
    assert sum(int(str(r["set_to_missing"])) for r in report) == 1  # only FiO2 = 4000
    assert np.isnan(clean.loc[clean["pid"] == "p100002", "FiO2"].iloc[1])


def test_fio2_rule_is_drop_not_divide() -> None:
    raw = _frame_with("FiO2", [0.0, 0.04, 0.2, 0.21, 0.5, 1.0, 2.0, 40.0, 4000.0])
    clean, _ = apply_rules(raw)
    kept = clean["FiO2"].notna().tolist()
    assert kept == [False, False, False, True, True, True, False, False, False]


def test_boundary_evidence_lists_values_next_to_bounds() -> None:
    raw = _frame_with("HR", [5, 19, 20, 80, 300, 301, 500])
    evidence = boundary_evidence(raw, RULES[0], k=2)
    assert evidence["highest_below_low"] == [19.0, 5.0]
    assert evidence["lowest_above_high"] == [301.0, 500.0]
    assert evidence["lowest_inside"] == [20.0, 80.0]


def test_schemas_accept_the_fixture(raw_frame: pd.DataFrame) -> None:
    validate_raw(raw_frame)
    clean, _ = apply_rules(raw_frame)
    validate_clean(clean)


def test_clean_schema_rejects_uncleaned_values(raw_frame: pd.DataFrame) -> None:
    with pytest.raises(DataSchemaError):
        validate_clean(raw_frame)  # FiO2 = 4000 is still present


def _broken(raw_frame: pd.DataFrame, how: str) -> pd.DataFrame:
    df = raw_frame.copy()
    first = df.index[0]
    if how == "extra column":
        df["extra"] = 1
    elif how == "missing column":
        df = df.drop(columns=["Lactate"])
    elif how == "column order":
        df = df[[*ALL_COLUMNS[:3], *reversed(ALL_COLUMNS[3:])]]
    elif how == "wrong dtype":
        df["HR"] = df["HR"].astype("float64")
    elif how == "gender":
        df.loc[first, "Gender"] = 2
    elif how == "unit value":
        df.loc[first, "Unit1"] = 3
    elif how == "units both one":
        df.loc[first, ["Unit1", "Unit2"]] = [1, 1]
    elif how == "units missing apart":
        df.loc[first, "Unit1"] = np.nan
    elif how == "label value":
        df.loc[first, "SepsisLabel"] = 2
    elif how == "label goes back":
        idx = df.index[df["pid"] == "p000002"]
        df.loc[idx[-1], "SepsisLabel"] = 0
    elif how == "t gap":
        df.loc[df.index[1], "t"] = 7
    elif how == "iculos jump":
        df.loc[df.index[1], "ICULOS"] = 50
    elif how == "hospital mismatch":
        df.loc[first, "hospital"] = "B"
    elif how == "bad pid":
        df["pid"] = df["pid"].str.replace("p000001", "patient1")
    elif how == "age missing":
        df.loc[first, "Age"] = np.nan
    elif how == "patient not contiguous":
        df = pd.concat([df.iloc[2:], df.iloc[:2]], ignore_index=True)
    else:  # pragma: no cover
        raise AssertionError(how)
    return df


@pytest.mark.parametrize(
    "how",
    [
        "extra column",
        "missing column",
        "column order",
        "wrong dtype",
        "gender",
        "unit value",
        "units both one",
        "units missing apart",
        "label value",
        "label goes back",
        "t gap",
        "iculos jump",
        "hospital mismatch",
        "bad pid",
        "age missing",
        "patient not contiguous",
    ],
)
def test_raw_schema_rejects(raw_frame: pd.DataFrame, how: str) -> None:
    with pytest.raises(DataSchemaError):
        validate_raw(_broken(raw_frame, how))


def test_build_all_writes_both_tables_and_a_counts_only_report(
    tiny_dataset: Path, tmp_path: Path
) -> None:
    data_dir, reports_dir = tmp_path / "data", tmp_path / "reports"
    result = build_all(tiny_dataset, data_dir, reports_dir)
    assert (result.rows, result.patients, result.values_set_to_missing) == (20, 5, 1)
    raw = to_frame(read_parquet(result.raw_path))
    clean = to_frame(read_parquet(result.clean_path))
    validate_raw(raw)
    validate_clean(clean)
    assert raw["FiO2"].max() == 4000.0  # raw is never overwritten
    assert clean["FiO2"].max() <= 1.0
    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert {r["column"] for r in report["counts"]} == {r.column for r in RULES}
    assert "p1" not in json.dumps(report["counts"])  # no patient IDs, counts only
    fio2_b = next(r for r in report["counts"] if r["column"] == "FiO2" and r["hospital"] == "B")
    assert fio2_b["above_high"] == 1


def test_septic_flags(raw_frame: pd.DataFrame) -> None:
    flags = septic_flags(raw_frame)
    assert flags["A"] == {"p000001": False, "p000002": True, "p000003": True}
    assert flags["B"] == {"p100001": False, "p100002": True}


def test_failing_build_writes_nothing(
    raw_root: Path, write_patient: WritePatient, tmp_path: Path
) -> None:
    write_patient("A", 1, [0, 1, 0])  # label goes back: must fail the raw schema
    with pytest.raises(DataSchemaError):
        build_all(raw_root, tmp_path / "data", tmp_path / "reports")
    assert not (tmp_path / "data").exists()


def test_float32_values_exactly_on_a_bound_are_kept() -> None:
    """0.21 stored as float32 is slightly below the float64 0.21; it must not be dropped."""
    raw = _frame_with("FiO2", [0.21, 1.0, 0.2, 1.1])
    assert float(raw["FiO2"].iloc[0]) < 0.21  # the float32 representation really is lower
    clean, _ = apply_rules(raw)
    assert clean["FiO2"].notna().tolist() == [True, True, False, False]
    evidence = boundary_evidence(raw, RULES_BY_COLUMN["FiO2"], k=2)
    assert evidence["highest_below_low"] == [0.2]
    assert evidence["lowest_inside"][0] == 0.21
