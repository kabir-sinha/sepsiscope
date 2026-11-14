"""Typed project configuration: YAML in, validated pydantic model out."""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Annotated

import yaml
from pydantic import AfterValidator, BaseModel, ConfigDict, Field

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "configs" / "default.yaml"


def _relative_path(value: str) -> str:
    """Reject absolute paths, home-relative paths and '..' escapes."""
    if not value.strip():
        raise ValueError("path must not be empty")
    if value.startswith("~"):
        raise ValueError(f"path must be relative to the repo, got home path {value!r}")
    if PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute():
        raise ValueError(f"path must be relative to the repo, got absolute path {value!r}")
    if ".." in PurePosixPath(value).parts:
        raise ValueError(f"path must stay inside the repo, got {value!r}")
    return value


RelPath = Annotated[str, AfterValidator(_relative_path)]


class _Strict(BaseModel):
    # extra="forbid": a typo'd key fails loudly instead of being ignored.
    # strict=True: no silent coercion (e.g. "42" is not accepted for an int).
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Paths(_Strict):
    data_dir: RelPath
    models_dir: RelPath
    mlruns_dir: RelPath
    reports_dir: RelPath
    splits_dir: RelPath


class FeatureSwitches(_Strict):
    vitals: bool
    labs: bool
    demographics: bool
    measurement_process: bool
    trends: bool
    icu_time: bool
    unit_columns: bool


class Config(_Strict):
    paths: Paths
    seed: int = Field(ge=0)
    alarm_budget: float = Field(gt=0.0, lt=1.0)
    label_horizon_hours: int = Field(ge=1, le=48)
    features: FeatureSwitches


def load_config(path: Path | str = DEFAULT_CONFIG) -> Config:
    """Read a YAML config safely and validate it; raises on any problem."""
    text = Path(path).read_text(encoding="utf-8")
    raw = yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise ValueError(f"config root must be a mapping, got {type(raw).__name__}")
    return Config.model_validate(raw)
