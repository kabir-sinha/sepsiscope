"""Cleaning: one table of plausibility rules, applied to a copy of the raw table.

A value outside its rule's closed interval ``[low, high]`` is set to missing (NaN).
Nothing else changes: no units are converted, no values are clipped or imputed, and
the raw Parquet is never overwritten.

These bounds are **conservative plausibility limits chosen for this project, not
clinical reference ranges or standards**. Each one is meant to remove values that
cannot be a real measurement (wrong unit, typing error, sensor artefact) while keeping
every value a living patient could produce. ADR 0014 records, for each rule, the
per-hospital counts and the observed values just outside each bound.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Rule:
    column: str
    low: float
    high: float
    unit: str
    reason: str


RULES: tuple[Rule, ...] = (
    Rule("HR", 20, 300, "beats/min", "Guard only: observed range is 20-280, nothing is removed."),
    Rule("O2Sat", 20, 100, "%", "Guard only: observed range is 20-100, nothing is removed."),
    Rule(
        "Temp",
        25,
        45,
        "deg C",
        "Removes readings near room temperature (20.9-23.6) and two of exactly 50.0; "
        "the lowest value kept is 26.6 and the highest is 42.2.",
    ),
    Rule("SBP", 20, 300, "mm Hg", "Guard only: observed range is 20-300, nothing is removed."),
    Rule("MAP", 10, 300, "mm Hg", "Guard only: observed range is 20-300, nothing is removed."),
    Rule(
        "DBP",
        5,
        250,
        "mm Hg",
        "Removes diastolic readings of 251-300, which are above the 99.99th percentile "
        "(196); in 13 of the 53 rows it is higher than the systolic value on the same row.",
    ),
    Rule(
        "Resp",
        1,
        80,
        "breaths/min",
        "Removes rates of 81-100, above the 99.99th percentile (60); the lower bound "
        "removes nothing (observed minimum is 1).",
    ),
    Rule(
        "FiO2",
        0.21,
        1.0,
        "fraction",
        "Stored as a fraction: room air is 0.21 and pure oxygen is 1.0. Values outside "
        "cannot be inspired-oxygen fractions; no values lie in 21-100, so they are not "
        "percentages and are not divided by 100.",
    ),
    Rule("pH", 6.5, 8.0, "pH", "Guard only: observed range is 6.62-7.93, nothing is removed."),
)

RULES_BY_COLUMN: dict[str, Rule] = {rule.column: rule for rule in RULES}


def out_of_bounds(values: pd.Series, rule: Rule) -> tuple[pd.Series, pd.Series]:
    """Boolean masks (below, above); missing values are in neither.

    The bounds are converted to the column's own type first. The table stores float32,
    where 0.21 is 0.2099999934...; comparing that with a float64 0.21 would wrongly put
    room-air FiO2 values "below" the bound.
    """
    kind = values.to_numpy().dtype.type
    return values < kind(rule.low), values > kind(rule.high)


def apply_rules(
    raw: pd.DataFrame, rules: tuple[Rule, ...] = RULES
) -> tuple[pd.DataFrame, list[dict[str, object]]]:
    """Return (clean copy, report rows). The input frame is not modified."""
    clean = raw.copy()
    report: list[dict[str, object]] = []
    for rule in rules:
        below, above = out_of_bounds(raw[rule.column], rule)
        outside = below | above
        clean[rule.column] = raw[rule.column].where(~outside, np.nan)
        for hospital in sorted(raw["hospital"].unique()):
            in_hospital = raw["hospital"] == hospital
            report.append(
                {
                    "column": rule.column,
                    "low": rule.low,
                    "high": rule.high,
                    "hospital": str(hospital),
                    "non_missing_before": int((raw[rule.column].notna() & in_hospital).sum()),
                    "below_low": int((below & in_hospital).sum()),
                    "above_high": int((above & in_hospital).sum()),
                    "set_to_missing": int((outside & in_hospital).sum()),
                }
            )
    return clean, report


def boundary_evidence(raw: pd.DataFrame, rule: Rule, k: int = 5) -> dict[str, object]:
    """Observed values nearest to each bound, inside and outside (for the ADR)."""
    values = raw[rule.column].dropna()

    def uniq(series: pd.Series, largest: bool) -> list[float]:
        distinct = np.sort(series.unique())
        picked = distinct[-k:][::-1] if largest else distinct[:k]
        return [round(float(v), 4) for v in picked]

    is_below, is_above = out_of_bounds(values, rule)
    below, above, inside = values[is_below], values[is_above], values[~(is_below | is_above)]
    quantiles = values.quantile([0.0001, 0.001, 0.5, 0.999, 0.9999])
    return {
        "column": rule.column,
        "n": int(values.size),
        "highest_below_low": uniq(below, largest=True),
        "lowest_inside": uniq(inside, largest=False),
        "highest_inside": uniq(inside, largest=True),
        "lowest_above_high": uniq(above, largest=False),
        "quantiles": {f"{q:g}": round(float(v), 4) for q, v in quantiles.items()},
    }
