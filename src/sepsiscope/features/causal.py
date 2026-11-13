"""Causal hourly features: every value at hour t uses only that patient's rows with hour <= t.

Input is the clean table (``pid``, ``hospital``, ``t`` and the 41 original columns),
sorted by patient and hour, one row per hour. Every operation below looks backwards only:

- forward fill (last value carried forward) within the patient
- running counts and running "hour of the last measurement" within the patient
- 6-hour windows that end at the current hour
- a shift of 6 rows backwards within the patient

so changing a row after hour t can never change a feature at or before t (tested).

Feature groups follow the config switches (``configs/default.yaml``):

==================== ========================================================
vitals               last value of the 8 vital signs; shock index (HR / SBP)
labs                 last value of the 26 laboratory columns; BUN / creatinine
demographics         Age, Gender
measurement_process  hours since last measured, number of measurements so far
trends               6-hour mean, standard deviation and change of each vital
icu_time             ICULOS, HospAdmTime, Unit1, Unit2 (ablation only)
==================== ========================================================
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from sepsiscope.config import FeatureSwitches
from sepsiscope.data.io import LABEL, LABS, VITALS

KEYS: tuple[str, ...] = ("pid", "hospital", "t", LABEL)
ICU_TIME: tuple[str, ...] = ("ICULOS", "HospAdmTime", "Unit1", "Unit2")
DEMOGRAPHICS: tuple[str, ...] = ("Age", "Gender")
WINDOW_HOURS = 6


class FeatureInputError(ValueError):
    """The input table is not sorted by patient and hour with one row per hour."""


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    group: str
    source: str
    description: str


def _measured_columns(switches: FeatureSwitches) -> list[str]:
    return [*(VITALS if switches.vitals else ()), *(LABS if switches.labs else ())]


def feature_specs(switches: FeatureSwitches) -> list[FeatureSpec]:
    """The ordered feature list for a set of switches (this is what the schema file holds)."""
    specs: list[FeatureSpec] = []
    measured = _measured_columns(switches)
    for col in measured:
        group = "vitals" if col in VITALS else "labs"
        specs.append(FeatureSpec(col, group, col, "last value carried forward"))
    if switches.vitals:
        specs.append(FeatureSpec("shock_index", "vitals", "HR,SBP", "HR / SBP, last values"))
    if switches.labs:
        specs.append(
            FeatureSpec("bun_creatinine", "labs", "BUN,Creatinine", "BUN / Creatinine, last values")
        )
    if switches.demographics:
        specs += [FeatureSpec(c, "demographics", c, "as recorded") for c in DEMOGRAPHICS]
    if switches.measurement_process:
        for col in measured:
            specs.append(
                FeatureSpec(f"{col}__hsl", "measurement_process", col, "hours since last measured")
            )
        for col in measured:
            specs.append(
                FeatureSpec(f"{col}__n", "measurement_process", col, "measurements so far")
            )
    if switches.trends and switches.vitals:
        for col in VITALS:
            specs += [
                FeatureSpec(f"{col}__mean6", "trends", col, "mean of values in hours t-5..t"),
                FeatureSpec(f"{col}__std6", "trends", col, "sample SD of values in hours t-5..t"),
                FeatureSpec(f"{col}__d6", "trends", col, "last value now minus at hour t-6"),
            ]
    if switches.icu_time:
        specs += [FeatureSpec(c, "icu_time", c, "as recorded (ablation only)") for c in ICU_TIME]
    return specs


def _check_order(frame: pd.DataFrame) -> None:
    pid = frame["pid"].to_numpy()
    if len(pid) and not (pid[1:] >= pid[:-1]).all():
        raise FeatureInputError("rows must be sorted by patient ID")
    expected = frame.groupby("pid", sort=False).cumcount().to_numpy()
    if not np.array_equal(frame["t"].to_numpy(), expected):
        raise FeatureInputError("t must run 0, 1, 2, ... within each patient (one row per hour)")


def _window(cumulative: np.ndarray, position: np.ndarray, width: int) -> np.ndarray:
    """Sum over the last ``width`` rows of a per-patient cumulative sum (rows t-width+1..t).

    ``position`` is the hour within the patient. When fewer than ``width`` rows exist the
    window starts at the patient's first row, so nothing from another patient is used.
    """
    out = cumulative.copy()
    take = position >= width
    out[take] -= cumulative[np.flatnonzero(take) - width]
    return out


def causal_features(frame: pd.DataFrame, switches: FeatureSwitches) -> pd.DataFrame:
    """Keys plus float32 features, in the order of :func:`feature_specs`."""
    _check_order(frame)
    pid = frame["pid"].to_numpy()
    hour = frame["t"].to_numpy().astype(np.int64)
    measured = _measured_columns(switches)
    values = frame[measured].astype(np.float64)
    observed = values.notna()
    groups = frame["pid"]

    last = values.groupby(groups, sort=False).ffill()
    cols: dict[str, pd.Series | np.ndarray] = {c: last[c] for c in measured}
    if switches.vitals:
        cols["shock_index"] = _ratio(last["HR"], last["SBP"])
    if switches.labs:
        cols["bun_creatinine"] = _ratio(last["BUN"], last["Creatinine"])
    if switches.demographics:
        for c in DEMOGRAPHICS:
            cols[c] = frame[c]
    if switches.measurement_process:
        hour_if_seen = pd.DataFrame(
            np.where(observed.to_numpy(), hour[:, None], np.nan), columns=measured
        )
        last_seen = hour_if_seen.groupby(pid, sort=False).ffill().to_numpy()
        counts = observed.astype(np.int32).groupby(groups, sort=False).cumsum().to_numpy()
        for j, c in enumerate(measured):
            cols[f"{c}__hsl"] = hour - last_seen[:, j]
        for j, c in enumerate(measured):
            cols[f"{c}__n"] = counts[:, j]
    if switches.trends and switches.vitals:
        vit = values[list(VITALS)]
        filled = vit.fillna(0.0)
        seen = vit.notna().astype(np.float64)
        csum = filled.groupby(groups, sort=False).cumsum().to_numpy()
        csq = (filled**2).groupby(groups, sort=False).cumsum().to_numpy()
        ccount = seen.groupby(groups, sort=False).cumsum().to_numpy()
        lagged = last[list(VITALS)].groupby(groups, sort=False).shift(WINDOW_HOURS).to_numpy()
        for j, c in enumerate(VITALS):
            s = _window(csum[:, j], hour, WINDOW_HOURS)
            q = _window(csq[:, j], hour, WINDOW_HOURS)
            n = _window(ccount[:, j], hour, WINDOW_HOURS)
            with np.errstate(invalid="ignore", divide="ignore"):
                mean = np.where(n >= 1, s / n, np.nan)
                var = np.where(n >= 2, (q - s * s / n) / (n - 1), np.nan)
            cols[f"{c}__mean6"] = mean
            cols[f"{c}__std6"] = np.sqrt(np.clip(var, 0.0, None))
            cols[f"{c}__d6"] = last[c].to_numpy() - lagged[:, j]
    if switches.icu_time:
        for c in ICU_TIME:
            cols[c] = frame[c]

    names = [spec.name for spec in feature_specs(switches)]
    out = pd.DataFrame({k: frame[k].to_numpy() for k in KEYS})
    feats = pd.DataFrame(
        {n: np.asarray(cols[n], dtype=np.float64).astype(np.float32) for n in names}
    )
    return pd.concat([out, feats], axis=1)


def _ratio(numerator: pd.Series, denominator: pd.Series) -> np.ndarray:
    num = numerator.to_numpy(dtype=np.float64)
    den = denominator.to_numpy(dtype=np.float64)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, num / den, np.nan)


def schema_document(
    switches: FeatureSwitches, names: Sequence[str] | None = None
) -> dict[str, object]:
    """Tracked description of the feature table (names and meaning only, no data)."""
    specs = feature_specs(switches)
    if names is not None and [s.name for s in specs] != list(names):
        raise ValueError("feature names do not match the specification")
    return {
        "dataset": "PhysioNet/CinC Challenge 2019 v1.0.0",
        "causal": "each feature at hour t uses only the same patient's rows with hour <= t",
        "keys": list(KEYS),
        "dtype": "float32",
        "switches": switches.model_dump(),
        "count": len(specs),
        "features": [
            {"name": s.name, "group": s.group, "source": s.source, "description": s.description}
            for s in specs
        ],
    }
