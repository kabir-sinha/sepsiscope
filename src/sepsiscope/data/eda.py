"""Exploratory summaries of the PhysioNet 2019 table (no feature engineering).

Every function takes the table as a DataFrame and returns a small summary frame, so
the notebook and the figures only call these functions.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from sepsiscope.data.io import DEMOGRAPHICS, MEASUREMENTS

VARIABLES: tuple[str, ...] = (*MEASUREMENTS, *DEMOGRAPHICS)


def patient_table(df: pd.DataFrame) -> pd.DataFrame:
    """One row per patient: hospital, stay length, septic flag and label timing."""
    grouped = df.groupby("pid", sort=True)
    out = pd.DataFrame(
        {
            "hospital": grouped["hospital"].first(),
            "rows": grouped.size(),
            "septic": grouped["SepsisLabel"].max() == 1,
            "positive_rows": grouped["SepsisLabel"].sum(),
            "age": grouped["Age"].first(),
            "gender": grouped["Gender"].first(),
            "first_iculos": grouped["ICULOS"].first(),
        }
    )
    positive = df[df["SepsisLabel"] == 1].groupby("pid", sort=True)
    out["first_positive_t"] = positive["t"].min().reindex(out.index)
    out["first_positive_iculos"] = positive["ICULOS"].min().reindex(out.index)
    out["rows_from_first_positive"] = out["rows"] - out["first_positive_t"]
    return out


def cohort_table(patients: pd.DataFrame) -> pd.DataFrame:
    """Cohort summary per hospital (columns A, B)."""
    rows: dict[str, dict[str, float]] = {}
    for hospital, p in patients.groupby("hospital", sort=True):
        septic = p[p["septic"]]
        rows[str(hospital)] = {
            "patients": len(p),
            "rows (patient-hours)": int(p["rows"].sum()),
            "septic patients": len(septic),
            "septic patients (%)": 100 * len(septic) / len(p),
            "positive rows": int(p["positive_rows"].sum()),
            "positive rows (%)": 100 * p["positive_rows"].sum() / p["rows"].sum(),
            "septic and positive from row 0": int((septic["first_positive_t"] == 0).sum()),
            "median stay (rows)": float(p["rows"].median()),
            "median stay, septic (rows)": float(septic["rows"].median()),
            "median stay, non-septic (rows)": float(p.loc[~p["septic"], "rows"].median()),
            "max stay (rows)": int(p["rows"].max()),
            "median age (years)": float(p["age"].median()),
            "Gender = 1 (%)": 100 * float((p["gender"] == 1).mean()),
            "ICULOS starts at 1 (%)": 100 * float((p["first_iculos"] == 1).mean()),
        }
    return pd.DataFrame(rows)


def missingness(df: pd.DataFrame) -> pd.DataFrame:
    """Share of rows where each variable is missing, per hospital (0-1)."""
    shares = df[list(VARIABLES)].isna().groupby(df["hospital"], sort=True).mean()
    return shares.T.rename_axis("variable")


def measurements_per_patient_day(df: pd.DataFrame) -> pd.DataFrame:
    """Per variable (rows) and hospital (columns A, B): measurements per patient-day."""
    observed = df[list(MEASUREMENTS)].notna()
    per_day = observed.groupby(df["hospital"], sort=True).mean().T * 24
    return per_day.rename_axis("variable")


def patients_ever_measured(df: pd.DataFrame) -> pd.DataFrame:
    """Per variable and hospital: share of patients with at least one measurement."""
    ever = df[list(MEASUREMENTS)].notna().groupby(df["pid"], sort=True).any()
    hospital_of = df.groupby("pid", sort=True)["hospital"].first()
    return ever.groupby(hospital_of, sort=True).mean().T.rename_axis("variable")


def js_divergence(a: np.ndarray, b: np.ndarray, bins: int = 50) -> float:
    """Jensen-Shannon divergence (base 2, between 0 and 1) of two samples.

    Both samples are binned on the same edges: equal-count bins of the pooled data,
    so no hospital decides the grid. Missing values must be removed by the caller.
    """
    if a.size == 0 or b.size == 0:
        return float("nan")
    pooled = np.concatenate([a, b])
    edges = np.unique(np.quantile(pooled, np.linspace(0, 1, bins + 1)))
    if edges.size < 2:
        return 0.0
    p = np.histogram(a, bins=edges)[0] / a.size
    q = np.histogram(b, bins=edges)[0] / b.size
    m = (p + q) / 2

    def kl(x: np.ndarray, y: np.ndarray) -> float:
        mask = x > 0
        return float(np.sum(x[mask] * np.log2(x[mask] / y[mask])))

    return max(0.0, 0.5 * kl(p, m) + 0.5 * kl(q, m))


def hospital_shift(df: pd.DataFrame, bins: int = 50) -> pd.DataFrame:
    """Per variable: JS divergence of observed values, and the gap in missingness, A vs B."""
    is_a = (df["hospital"] == "A").to_numpy()
    rows = []
    for name in VARIABLES:
        values = df[name].to_numpy(dtype=np.float64)
        present = ~np.isnan(values)
        rows.append(
            {
                "variable": name,
                "js_values": js_divergence(values[present & is_a], values[present & ~is_a], bins),
                "missing_A": float(1 - present[is_a].mean()),
                "missing_B": float(1 - present[~is_a].mean()),
            }
        )
    out = pd.DataFrame(rows).set_index("variable")
    out["missing_gap"] = (out["missing_A"] - out["missing_B"]).abs()
    return out


def unit_fingerprint(df: pd.DataFrame) -> pd.DataFrame:
    """Per hospital: share of rows with Unit1 = 1, Unit2 = 1, or both missing."""
    state = np.select(
        [df["Unit1"].isna() & df["Unit2"].isna(), df["Unit1"] == 1, df["Unit2"] == 1],
        ["missing", "Unit1 = 1", "Unit2 = 1"],
        default="other",
    )
    table = pd.crosstab(df["hospital"], state, normalize="index")
    return table.reindex(columns=["Unit1 = 1", "Unit2 = 1", "missing", "other"], fill_value=0.0)


def unit_rule_accuracy(df: pd.DataFrame) -> float:
    """How well one rule guesses the hospital from the unit columns alone (patient level).

    Rule: a patient whose unit is missing is assigned to the hospital where missing
    units are more common, and the reverse. This is a count, not a trained model.
    """
    per_patient = df.groupby("pid", sort=True).agg(
        hospital=("hospital", "first"), unit_missing=("Unit1", lambda s: bool(s.isna().all()))
    )
    table = pd.crosstab(per_patient["unit_missing"], per_patient["hospital"])
    return float(table.max(axis=1).sum() / table.to_numpy().sum())
