"""Reading the raw PhysioNet 2019 patient files (pipe-separated, one file per patient)."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
from pyarrow import csv as pacsv

from sepsiscope.data.download import LOCAL_SUBDIR

VITALS = ("HR", "O2Sat", "Temp", "SBP", "MAP", "DBP", "Resp", "EtCO2")
LABS = (
    "BaseExcess",
    "HCO3",
    "FiO2",
    "pH",
    "PaCO2",
    "SaO2",
    "AST",
    "BUN",
    "Alkalinephos",
    "Calcium",
    "Chloride",
    "Creatinine",
    "Bilirubin_direct",
    "Glucose",
    "Lactate",
    "Magnesium",
    "Phosphate",
    "Potassium",
    "Bilirubin_total",
    "TroponinI",
    "Hct",
    "Hgb",
    "PTT",
    "WBC",
    "Fibrinogen",
    "Platelets",
)
DEMOGRAPHICS = ("Age", "Gender", "Unit1", "Unit2", "HospAdmTime", "ICULOS")
LABEL = "SepsisLabel"
# The 41 columns of every file, in the official order.
COLUMNS: tuple[str, ...] = (*VITALS, *LABS, *DEMOGRAPHICS, LABEL)
MEASUREMENTS: tuple[str, ...] = (*VITALS, *LABS)

HOSPITAL_DIRS = {"A": "training_setA", "B": "training_setB"}
_PID_RE = re.compile(r"^p\d{6}$")

_READ = pacsv.ReadOptions(use_threads=False)
_PARSE = pacsv.ParseOptions(delimiter="|")
_CONVERT = pacsv.ConvertOptions(
    column_types=dict.fromkeys(COLUMNS, pa.float64()),
    null_values=["NaN"],
    strings_can_be_null=False,
)


class RawDataError(RuntimeError):
    """Raised when a raw file does not look like a PhysioNet 2019 patient file."""


@dataclass(frozen=True)
class PatientFile:
    hospital: str  # "A" or "B"
    pid: str  # e.g. "p000001"
    path: Path


def training_dir(raw_root: Path) -> Path:
    return raw_root / LOCAL_SUBDIR


def iter_patient_files(raw_root: Path) -> Iterator[PatientFile]:
    """Yield every patient file, hospital A then B, sorted by patient ID."""
    for hospital, dirname in HOSPITAL_DIRS.items():
        folder = training_dir(raw_root) / dirname
        if not folder.is_dir():
            raise RawDataError(f"missing folder {dirname}; run `sepsiscope data download` first")
        for path in sorted(folder.glob("p*.psv")):
            if _PID_RE.match(path.stem) is None:
                raise RawDataError(f"unexpected file name: {path.name}")
            yield PatientFile(hospital=hospital, pid=path.stem, path=path)


def read_psv(path: Path) -> pa.Table:
    """Read one patient file as float64 columns; "NaN" becomes null. Checks the header."""
    table = pacsv.read_csv(path, read_options=_READ, parse_options=_PARSE, convert_options=_CONVERT)
    if tuple(table.column_names) != COLUMNS:
        raise RawDataError(f"{path.name}: header does not match the 41 expected columns")
    if table.num_rows == 0:
        raise RawDataError(f"{path.name}: no data rows")
    return table
