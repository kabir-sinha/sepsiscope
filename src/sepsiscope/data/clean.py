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
    Rule(
        "HR",
        20,
        300,
        "beats/min",
        "Below 20 is not a sustained rhythm; above 300 is beyond recorded tachyarrhythmias.",
    ),
    Rule(
        "O2Sat",
        20,
        100,
        "%",
        "Saturation cannot exceed 100; pulse oximetry below 20 is a probe artefact.",
    ),
    Rule(
        "Temp",
        25,
        45,
        "deg C",
        "Covers deep hypothermia to extreme hyperpyrexia; outside is a unit or entry error.",
    ),
    Rule("SBP", 20, 300, "mm Hg", "Outside this range a cuff or arterial line is not reading."),
    Rule("MAP", 10, 300, "mm Hg", "Outside this range the line is damped, flushed or zeroing."),
    Rule("DBP", 5, 250, "mm Hg", "Outside this range the line is damped, flushed or zeroing."),
    Rule(
        "Resp",
        1,
        80,
        "breaths/min",
        "Zero is 'not measured' rather than apnoea here; above 80 is an artefact.",
    ),
    Rule(
        "FiO2",
        0.21,
        1.0,
        "fraction",
        "Stored as a fraction: room air is 0.21 and pure oxygen is 1.0; nothing else exists.",
    ),
    Rule("pH", 6.5, 8.0, "pH", "Blood pH outside 6.5-8.0 is not compatible with a measurement."),
)

RULES_BY_COLUMN: dict[str, Rule] = {rule.column: rule for rule in RULES}


def out_of_bounds(values: pd.Series, rule: Rule) -> tuple[pd.Series, pd.Series]:
    """Boolean masks (below, above); missing values are in neither."""
    return values < rule.low, values > rule.high


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
    values = raw[rule.column].dropna().astype("float64")

    def uniq(series: pd.Series, largest: bool) -> list[float]:
        distinct = np.sort(series.unique())
        picked = distinct[-k:][::-1] if largest else distinct[:k]
        return [round(float(v), 4) for v in picked]

    below, above = values[values < rule.low], values[values > rule.high]
    inside = values[(values >= rule.low) & (values <= rule.high)]
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
