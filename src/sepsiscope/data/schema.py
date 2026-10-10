"""pandera schemas for the raw and the clean table.

Both schemas fix the exact columns, their order and types, and the structural rules
of the dataset (per patient: ``t`` counts up from 0, ``ICULOS`` goes up by exactly 1,
and the label never goes back to 0). The clean schema adds the value ranges that the
cleaning rules guarantee.
"""

from __future__ import annotations

import pandas as pd
import pandera.pandas as pa
from pandera.pandas import Check, Column, DataFrameSchema

from sepsiscope.data.build import ALL_COLUMNS
from sepsiscope.data.clean import RULES_BY_COLUMN
from sepsiscope.data.io import MEASUREMENTS


def _same_patient_as_previous(df: pd.DataFrame) -> pd.Series:
    return df["pid"] == df["pid"].shift()


def _t_contiguous_from_zero(df: pd.DataFrame) -> pd.Series:
    return df["t"] == df.groupby("pid", sort=False).cumcount()


def _iculos_steps_by_one(df: pd.DataFrame) -> pd.Series:
    return ~_same_patient_as_previous(df) | (df["ICULOS"].diff() == 1)


def _label_monotone(df: pd.DataFrame) -> pd.Series:
    return ~_same_patient_as_previous(df) | (df["SepsisLabel"].diff() >= 0)


def _each_patient_is_one_block(df: pd.DataFrame) -> bool:
    blocks = int((~_same_patient_as_previous(df)).sum())
    return bool(blocks == df["pid"].nunique())


def _units_never_both_one(df: pd.DataFrame) -> pd.Series:
    return ~((df["Unit1"] == 1) & (df["Unit2"] == 1))


def _units_missing_together(df: pd.DataFrame) -> pd.Series:
    return df["Unit1"].isna() == df["Unit2"].isna()


def _hospital_matches_pid(df: pd.DataFrame) -> pd.Series:
    # A = p0xxxxx, B = p1xxxxx (the official file naming).
    return df["hospital"] == df["pid"].str[1].map({"0": "A", "1": "B"})


FRAME_CHECKS = [
    Check(_t_contiguous_from_zero, error="t must count 0,1,2,... within each patient"),
    Check(_iculos_steps_by_one, error="ICULOS must increase by exactly 1 within a patient"),
    Check(_label_monotone, error="SepsisLabel must never go from 1 back to 0"),
    Check(_each_patient_is_one_block, error="each patient's rows must be contiguous"),
    Check(_units_never_both_one, error="Unit1 and Unit2 must never both be 1"),
    Check(_units_missing_together, error="Unit1 and Unit2 must be missing together"),
    Check(_hospital_matches_pid, error="hospital must match the patient ID prefix"),
]


def _columns(clean: bool) -> dict[str, Column]:
    columns: dict[str, Column] = {
        "pid": Column(str, Check.str_matches(r"^p\d{6}$")),
        "hospital": Column(str, Check.isin(["A", "B"])),
        "t": Column("int16", Check.in_range(0, 335)),
    }
    for name in MEASUREMENTS:
        checks = []
        if clean and name in RULES_BY_COLUMN:
            rule = RULES_BY_COLUMN[name]
            checks.append(Check.in_range(rule.low, rule.high))
        columns[name] = Column("float32", checks, nullable=True)
    columns["Age"] = Column("float32", Check.in_range(0, 120))
    columns["Gender"] = Column("float32", Check.isin([0.0, 1.0]))
    columns["Unit1"] = Column("float32", Check.isin([0.0, 1.0]), nullable=True)
    columns["Unit2"] = Column("float32", Check.isin([0.0, 1.0]), nullable=True)
    columns["HospAdmTime"] = Column("float32", nullable=True)
    columns["ICULOS"] = Column("int16", Check.ge(1))
    columns["SepsisLabel"] = Column("int8", Check.isin([0, 1]))
    assert tuple(columns) == ALL_COLUMNS
    return columns


def _schema(clean: bool) -> DataFrameSchema:
    return DataFrameSchema(
        _columns(clean),
        checks=FRAME_CHECKS,
        strict=True,  # no extra columns
        ordered=True,  # exact column order
        coerce=False,  # wrong types fail instead of being converted
        name="physionet2019_clean" if clean else "physionet2019_raw",
    )


RAW_SCHEMA = _schema(clean=False)
CLEAN_SCHEMA = _schema(clean=True)


class DataSchemaError(ValueError):
    """The table does not match its schema (wraps pandera's error types)."""


def _validate(schema: DataFrameSchema, df: pd.DataFrame) -> pd.DataFrame:
    try:
        return schema.validate(df)
    except (pa.errors.SchemaError, pa.errors.SchemaErrors) as exc:
        raise DataSchemaError(f"{schema.name}: {str(exc)[:2000]}") from exc


def validate_raw(df: pd.DataFrame) -> pd.DataFrame:
    return _validate(RAW_SCHEMA, df)


def validate_clean(df: pd.DataFrame) -> pd.DataFrame:
    return _validate(CLEAN_SCHEMA, df)
