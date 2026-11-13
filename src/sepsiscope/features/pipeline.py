"""Orchestration for `sepsiscope features build`: clean Parquet -> per-hospital features."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from sepsiscope.config import FeatureSwitches
from sepsiscope.data.build import CLEAN_PARQUET, read_parquet, write_parquet
from sepsiscope.features.causal import causal_features, schema_document

FEATURE_DIR = Path("processed")
SCHEMA_FILE = Path("features") / "feature_schema.json"
HOSPITALS: tuple[str, ...] = ("A", "B")


def feature_path(data_dir: Path, hospital: str) -> Path:
    return data_dir / FEATURE_DIR / f"features_{hospital}.parquet"


@dataclass(frozen=True)
class FeatureResult:
    hospital: str
    rows: int
    patients: int
    features: int
    path: Path


def write_features(frame: pd.DataFrame, path: Path) -> None:
    """Parquet without pandas metadata, so the same table always gives the same bytes."""
    table = pa.Table.from_pandas(frame, preserve_index=False).replace_schema_metadata(None)
    write_parquet(table, path)


def build_features(
    data_dir: Path, reports_dir: Path, switches: FeatureSwitches
) -> list[FeatureResult]:
    clean = read_parquet(data_dir / CLEAN_PARQUET).to_pandas()
    results: list[FeatureResult] = []
    names: list[str] = []
    for hospital in HOSPITALS:
        part = clean[clean["hospital"] == hospital].reset_index(drop=True)
        feats = causal_features(part, switches)
        path = feature_path(data_dir, hospital)
        write_features(feats, path)
        names = list(feats.columns[4:])
        results.append(
            FeatureResult(hospital, len(feats), int(feats["pid"].nunique()), len(names), path)
        )
        del part, feats
    schema_path = reports_dir / SCHEMA_FILE
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    document = schema_document(switches, names)
    schema_path.write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    return results


def read_features(data_dir: Path, hospital: str) -> pd.DataFrame:
    path = feature_path(data_dir, hospital)
    if not path.is_file():
        raise FileNotFoundError(f"{path.name} not found; run `sepsiscope features build` first")
    frame: pd.DataFrame = pq.read_table(path).to_pandas()
    return frame
