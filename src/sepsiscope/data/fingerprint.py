"""Dataset fingerprint: recompute the expected counts from the raw files and compare.

The expected numbers are frozen in ``docs/protocol.md``. A mismatch means the
download is incomplete or the data differs from what the protocol was written for,
so ``sepsiscope data verify`` fails loudly.
"""

from __future__ import annotations

from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, fields
from pathlib import Path

import numpy as np

from sepsiscope.data.io import PatientFile, iter_patient_files, read_psv

FIO2_LOW, FIO2_HIGH = 0.21, 1.0


@dataclass(frozen=True)
class FileStats:
    """Counts for one patient file."""

    rows: int
    positive_rows: int
    septic: bool
    positive_from_row0: bool
    label_monotone: bool
    iculos_steps_ok: bool
    iculos_starts_at_1: bool
    gender_other: int  # rows where Gender is not 0 or 1 (including missing)
    age_missing: int
    hospadmtime_missing: int
    unit_both_one: int
    unit_missing_mismatch: int  # rows where exactly one of Unit1/Unit2 is missing
    unit_missing: int  # rows where both are missing
    fio2_present: int
    fio2_outside: int


@dataclass(frozen=True)
class Fingerprint:
    """Aggregated counts for one hospital (or for both)."""

    files: int = 0
    rows: int = 0
    septic_patients: int = 0
    positive_rows: int = 0
    positive_from_row0: int = 0
    max_rows: int = 0
    non_monotone_patients: int = 0
    iculos_step_violations: int = 0
    iculos_starts_at_1: int = 0
    gender_other: int = 0
    age_missing: int = 0
    hospadmtime_missing: int = 0
    unit_both_one: int = 0
    unit_missing_mismatch: int = 0
    unit_missing: int = 0
    fio2_present: int = 0
    fio2_outside: int = 0

    def __add__(self, other: Fingerprint) -> Fingerprint:
        values = {}
        for f in fields(self):
            a, b = getattr(self, f.name), getattr(other, f.name)
            values[f.name] = max(a, b) if f.name == "max_rows" else a + b
        return Fingerprint(**values)


# Frozen expectations (docs/protocol.md plus the Phase 1 data facts).
EXPECTED: dict[str, dict[str, int]] = {
    "A": {
        "files": 20_336,
        "rows": 790_215,
        "septic_patients": 1_790,
        "positive_rows": 17_136,
        "positive_from_row0": 203,
        "max_rows": 336,
    },
    "B": {
        "files": 20_000,
        "rows": 761_995,
        "septic_patients": 1_142,
        "positive_rows": 10_780,
        "positive_from_row0": 223,
        "max_rows": 336,
    },
    "A+B": {
        "files": 40_336,
        "rows": 1_552_210,
        "septic_patients": 2_932,
        "positive_rows": 27_916,
        "positive_from_row0": 426,
        "max_rows": 336,
        "non_monotone_patients": 0,
        "iculos_step_violations": 0,
        "iculos_starts_at_1": 31_543,
        "gender_other": 0,
        "age_missing": 0,
        "hospadmtime_missing": 8,
        "unit_both_one": 0,
        "unit_missing_mismatch": 0,
        "fio2_present": 129_365,
        "fio2_outside": 395,
    },
}


def stats_from_columns(
    label: np.ndarray,
    iculos: np.ndarray,
    gender: np.ndarray,
    age: np.ndarray,
    hosp_adm_time: np.ndarray,
    unit1: np.ndarray,
    unit2: np.ndarray,
    fio2: np.ndarray,
) -> FileStats:
    """Pure function: per-patient counts from float arrays (NaN = missing)."""
    positive = label == 1
    u1_missing, u2_missing = np.isnan(unit1), np.isnan(unit2)
    fio2_present = ~np.isnan(fio2)
    with np.errstate(invalid="ignore"):
        fio2_outside = fio2_present & ((fio2 < FIO2_LOW) | (fio2 > FIO2_HIGH))
    return FileStats(
        rows=int(label.size),
        positive_rows=int(positive.sum()),
        septic=bool(positive.any()),
        positive_from_row0=bool(positive[0]),
        label_monotone=bool(np.all(np.diff(label) >= 0)),
        iculos_steps_ok=bool(np.all(np.diff(iculos) == 1)),
        iculos_starts_at_1=bool(iculos[0] == 1),
        gender_other=int((~np.isin(gender, (0.0, 1.0))).sum()),
        age_missing=int(np.isnan(age).sum()),
        hospadmtime_missing=int(np.isnan(hosp_adm_time).sum()),
        unit_both_one=int(((unit1 == 1) & (unit2 == 1)).sum()),
        unit_missing_mismatch=int((u1_missing != u2_missing).sum()),
        unit_missing=int((u1_missing & u2_missing).sum()),
        fio2_present=int(fio2_present.sum()),
        fio2_outside=int(fio2_outside.sum()),
    )


def file_stats(path: Path) -> FileStats:
    table = read_psv(path)

    def col(name: str) -> np.ndarray:
        return np.asarray(table.column(name).to_numpy(zero_copy_only=False), dtype=np.float64)

    return stats_from_columns(
        label=col("SepsisLabel"),
        iculos=col("ICULOS"),
        gender=col("Gender"),
        age=col("Age"),
        hosp_adm_time=col("HospAdmTime"),
        unit1=col("Unit1"),
        unit2=col("Unit2"),
        fio2=col("FiO2"),
    )


def aggregate(stats: Iterable[FileStats]) -> Fingerprint:
    total: dict[str, int] = {f.name: 0 for f in fields(Fingerprint)}
    for s in stats:
        total["files"] += 1
        total["rows"] += s.rows
        total["septic_patients"] += int(s.septic)
        total["positive_rows"] += s.positive_rows
        total["positive_from_row0"] += int(s.positive_from_row0)
        total["max_rows"] = max(total["max_rows"], s.rows)
        total["non_monotone_patients"] += int(not s.label_monotone)
        total["iculos_step_violations"] += int(not s.iculos_steps_ok)
        total["iculos_starts_at_1"] += int(s.iculos_starts_at_1)
        for name in (
            "gender_other",
            "age_missing",
            "hospadmtime_missing",
            "unit_both_one",
            "unit_missing_mismatch",
            "unit_missing",
            "fio2_present",
            "fio2_outside",
        ):
            total[name] += getattr(s, name)
    return Fingerprint(**total)


def compute_fingerprints(raw_root: Path, workers: int = 8) -> dict[str, Fingerprint]:
    """Fingerprint per hospital plus the combined 'A+B'."""
    files: list[PatientFile] = list(iter_patient_files(raw_root))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        stats = list(pool.map(lambda f: file_stats(f.path), files))
    result = {
        hospital: aggregate(s for f, s in zip(files, stats, strict=True) if f.hospital == hospital)
        for hospital in ("A", "B")
    }
    result["A+B"] = result["A"] + result["B"]
    return result


@dataclass(frozen=True)
class Check:
    scope: str
    name: str
    expected: int
    observed: int

    @property
    def ok(self) -> bool:
        return self.expected == self.observed


def compare(
    observed: dict[str, Fingerprint], expected: dict[str, dict[str, int]] = EXPECTED
) -> list[Check]:
    return [
        Check(scope, name, value, getattr(observed[scope], name))
        for scope, items in expected.items()
        for name, value in items.items()
    ]
