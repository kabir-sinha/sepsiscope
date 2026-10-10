"""Orchestration for `sepsiscope data build` and `sepsiscope data splits`."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd
import pyarrow as pa

from sepsiscope.data.build import (
    CLEAN_PARQUET,
    RAW_PARQUET,
    build_raw_table,
    parquet_schema,
    read_parquet,
    write_parquet,
)
from sepsiscope.data.clean import RULES, apply_rules
from sepsiscope.data.schema import validate_clean, validate_raw
from sepsiscope.data.splits import split_document, write_split

CLEANING_REPORT = Path("data") / "cleaning_report.json"


@dataclass(frozen=True)
class BuildResult:
    rows: int
    patients: int
    raw_path: Path
    clean_path: Path
    report_path: Path
    values_set_to_missing: int


def to_frame(table: pa.Table) -> pd.DataFrame:
    frame: pd.DataFrame = table.to_pandas()
    return frame


def to_table(frame: pd.DataFrame) -> pa.Table:
    table = pa.Table.from_pandas(frame, schema=parquet_schema(), preserve_index=False)
    return table.replace_schema_metadata(None)


def cleaning_report(rows: list[dict[str, object]]) -> dict[str, object]:
    """Counts only: safe to commit (no patient-level values)."""
    return {
        "dataset": "PhysioNet/CinC Challenge 2019 v1.0.0",
        "note": (
            "Values outside [low, high] are set to missing. Bounds are conservative "
            "plausibility limits chosen for this project, not clinical standards."
        ),
        "rules": [asdict(rule) for rule in RULES],
        "counts": rows,
    }


def build_all(raw_root: Path, data_dir: Path, reports_dir: Path) -> BuildResult:
    """Raw files -> raw Parquet -> schema check -> clean Parquet -> schema check -> report."""
    raw_path, clean_path = data_dir / RAW_PARQUET, data_dir / CLEAN_PARQUET
    report_path = reports_dir / CLEANING_REPORT

    raw_table = build_raw_table(raw_root).replace_schema_metadata(None)
    raw_frame = to_frame(raw_table)
    validate_raw(raw_frame)
    write_parquet(raw_table, raw_path)

    clean_frame, rows = apply_rules(raw_frame)
    validate_clean(clean_frame)
    write_parquet(to_table(clean_frame), clean_path)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(cleaning_report(rows), indent=1) + "\n", encoding="utf-8")
    return BuildResult(
        rows=len(raw_frame),
        patients=int(raw_frame["pid"].nunique()),
        raw_path=raw_path,
        clean_path=clean_path,
        report_path=report_path,
        values_set_to_missing=sum(int(str(r["set_to_missing"])) for r in rows),
    )


def septic_flags(frame: pd.DataFrame) -> dict[str, dict[str, bool]]:
    """Per hospital: patient ID -> ever septic."""
    per_patient = frame.groupby("pid", sort=True).agg(
        hospital=("hospital", "first"), label_max=("SepsisLabel", "max")
    )
    flags: dict[str, dict[str, bool]] = {}
    for pid, hospital, label_max in zip(
        per_patient.index, per_patient["hospital"], per_patient["label_max"], strict=True
    ):
        flags.setdefault(str(hospital), {})[str(pid)] = bool(label_max == 1)
    return flags


def write_splits(data_dir: Path, splits_dir: Path, seed: int) -> dict[str, dict[str, object]]:
    frame = read_parquet(data_dir / RAW_PARQUET).select(["pid", "hospital", "SepsisLabel"])
    documents: dict[str, dict[str, object]] = {}
    for hospital, flags in septic_flags(frame.to_pandas()).items():
        document = split_document(hospital, flags, seed)
        write_split(splits_dir / f"hospital_{hospital}.json", document)
        documents[hospital] = document
    return documents


FIGURE_FILES: dict[str, str] = {
    "missingness": "eda_missingness.png",
    "frequency": "eda_measurement_frequency.png",
    "stay_length": "eda_stay_length.png",
    "label_timing": "eda_label_timing.png",
    "shift": "eda_hospital_shift.png",
    "units": "eda_unit_fingerprint.png",
}


def run_eda(data_dir: Path, figures_dir: Path | None = None) -> dict[str, pd.DataFrame]:
    """Compute every EDA summary from the clean table; optionally write the figures."""
    from sepsiscope.data import eda, figures

    frame = to_frame(read_parquet(data_dir / CLEAN_PARQUET))
    patients = eda.patient_table(frame)
    tables = {
        "patients": patients,
        "cohort": eda.cohort_table(patients),
        "missingness": eda.missingness(frame),
        "frequency": eda.measurements_per_patient_day(frame),
        "ever_measured": eda.patients_ever_measured(frame),
        "shift": eda.hospital_shift(frame),
        "units": eda.unit_fingerprint(frame),
        "unit_rule_accuracy": pd.DataFrame({"accuracy": [eda.unit_rule_accuracy(frame)]}),
    }
    if figures_dir is not None:
        made = {
            "missingness": figures.missingness_figure(tables["missingness"]),
            "frequency": figures.frequency_figure(tables["frequency"]),
            "stay_length": figures.stay_length_figure(patients),
            "label_timing": figures.label_timing_figure(patients),
            "shift": figures.shift_figure(tables["shift"]),
            "units": figures.unit_figure(tables["units"]),
        }
        for name, fig in made.items():
            figures.save(fig, figures_dir / FIGURE_FILES[name])
    return tables
