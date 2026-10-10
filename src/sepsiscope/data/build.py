"""Build one Parquet table from the 40,336 raw patient files.

Layout: ``pid``, ``hospital`` (A/B), ``t`` (row index from 0), then the 41 original
columns in their original order. Values are copied, never altered: measurements are
stored as float32 (the files carry at most a few decimals), and the build checks that
the float32 copy equals the parsed value to within float32 precision.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from sepsiscope.data.io import COLUMNS, LABEL, PatientFile, iter_patient_files, read_psv

RAW_PARQUET = Path("interim") / "physionet2019_raw.parquet"
CLEAN_PARQUET = Path("processed") / "physionet2019_clean.parquet"

# Storage types. Everything that can be missing stays floating point (NaN = missing).
INT_COLUMNS: dict[str, pa.DataType] = {"ICULOS": pa.int16(), LABEL: pa.int8()}
KEY_COLUMNS: tuple[str, ...] = ("pid", "hospital", "t")
ALL_COLUMNS: tuple[str, ...] = (*KEY_COLUMNS, *COLUMNS)


def parquet_schema() -> pa.Schema:
    fields = [
        pa.field("pid", pa.string()),
        pa.field("hospital", pa.string()),
        pa.field("t", pa.int16()),
    ]
    fields += [pa.field(name, INT_COLUMNS.get(name, pa.float32())) for name in COLUMNS]
    return pa.schema(fields)


def patient_table(patient: PatientFile) -> pa.Table:
    """One patient's rows in the output layout (missing values become NaN)."""
    table = read_psv(patient.path)
    n = table.num_rows
    arrays: list[pa.Array] = [
        pa.array([patient.pid] * n, pa.string()),
        pa.array([patient.hospital] * n, pa.string()),
        pa.array(np.arange(n, dtype=np.int16)),
    ]
    for name in COLUMNS:
        values = np.asarray(table.column(name).to_numpy(zero_copy_only=False), dtype=np.float64)
        if name in INT_COLUMNS:
            if np.isnan(values).any() or not np.all(values == np.round(values)):
                raise ValueError(f"{patient.pid}: {name} is not a whole number everywhere")
            arrays.append(pa.array(values.astype(np.int64), INT_COLUMNS[name]))
        else:
            as32 = values.astype(np.float32)
            if not np.allclose(as32, values, rtol=1e-6, atol=0.0, equal_nan=True):
                raise ValueError(f"{patient.pid}: {name} does not fit float32 exactly enough")
            arrays.append(pa.array(as32, pa.float32()))
    return pa.Table.from_arrays(arrays, schema=parquet_schema())


def build_raw_table(raw_root: Path, workers: int = 8) -> pa.Table:
    """All patients, hospital A then B, each sorted by patient ID and row order."""
    patients = list(iter_patient_files(raw_root))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        tables = list(pool.map(patient_table, patients))
    return pa.concat_tables(tables).combine_chunks()


def write_parquet(table: pa.Table, path: Path) -> None:
    """Write deterministically (fixed compression, no creation metadata of ours)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path, compression="zstd", compression_level=9, row_group_size=200_000)


def read_parquet(path: Path) -> pa.Table:
    return pq.read_table(path)
