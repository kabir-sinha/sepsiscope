"""Precompute the local demo data (plan B7, P4). Runs offline; the API only serves the file.

Direction B2A: the model was trained on hospital B, so every hospital-A patient is held
out. Six patients are picked by fixed rules (smallest patient ID that matches, so the
choice is deterministic), and the demo shows failures as well as successes:

1. septic, caught early (first timely LightGBM alert >= 6 h before onset)
2. septic, caught late (first timely alert < 3 h before onset)
3. septic, missed (no LightGBM alert in [onset - 12 h, onset])
4. non-septic, false alarms (at least 3 alerting hours)
5. non-septic, quiet (no alerts)
6. septic from the first hour (onset cannot be pinned down)

Patient IDs are replaced by "Demo patient 1-6". The output lives in the ignored
``data/demo/`` folder and is never tracked.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from sepsiscope.api.verdict import RULES, WINDOW_HOURS, Verdict, banner, onset_hour, verdict
from sepsiscope.config import Config
from sepsiscope.data.io import LABEL
from sepsiscope.features.pipeline import read_features
from sepsiscope.models import baselines as b
from sepsiscope.models import calibration, lgbm
from sepsiscope.trust.explain import Explanation, explain_rows

DIRECTION, TARGET = "B2A", "A"
DEMO_FILE = Path("demo") / "demo_B2A.json"
MIN_HOURS, MAX_HOURS = 24, 120

NAMES: dict[str, str] = {
    "HR": "heart rate",
    "O2Sat": "oxygen saturation",
    "Temp": "temperature",
    "SBP": "systolic blood pressure",
    "MAP": "mean arterial pressure",
    "DBP": "diastolic blood pressure",
    "Resp": "breathing rate",
    "EtCO2": "end-tidal CO2",
    "BaseExcess": "base excess",
    "HCO3": "bicarbonate",
    "FiO2": "inspired oxygen (FiO2)",
    "pH": "blood pH",
    "PaCO2": "arterial CO2 (PaCO2)",
    "SaO2": "arterial oxygen saturation",
    "AST": "liver enzyme AST",
    "BUN": "blood urea nitrogen",
    "Alkalinephos": "alkaline phosphatase",
    "Calcium": "calcium",
    "Chloride": "chloride",
    "Creatinine": "creatinine",
    "Bilirubin_direct": "direct bilirubin",
    "Glucose": "glucose",
    "Lactate": "lactate",
    "Magnesium": "magnesium",
    "Phosphate": "phosphate",
    "Potassium": "potassium",
    "Bilirubin_total": "total bilirubin",
    "TroponinI": "troponin I",
    "Hct": "haematocrit",
    "Hgb": "haemoglobin",
    "PTT": "clotting time (PTT)",
    "WBC": "white blood cell count",
    "Fibrinogen": "fibrinogen",
    "Platelets": "platelet count",
    "Age": "age",
    "Gender": "sex",
    "shock_index": "shock index (heart rate / systolic pressure)",
    "bun_creatinine": "urea / creatinine ratio",
}
SUFFIXES: dict[str, str] = {
    "__hsl": "hours since last {} measurement",
    "__n": "number of {} measurements so far",
    "__mean6": "{}, average over the last 6 hours",
    "__std6": "{}, variability over the last 6 hours",
    "__d6": "{}, change over the last 6 hours",
}


def plain_name(feature: str) -> str:
    for suffix, template in SUFFIXES.items():
        if feature.endswith(suffix):
            return template.format(NAMES.get(feature[: -len(suffix)], feature))
    return NAMES.get(feature, feature)


UNITS: dict[str, str] = {
    "HR": "beats/min",
    "O2Sat": "%",
    "Temp": "°C",
    "SBP": "mm Hg",
    "MAP": "mm Hg",
    "DBP": "mm Hg",
    "Resp": "breaths/min",
    "EtCO2": "mm Hg",
    "FiO2": "fraction",
    "PaCO2": "mm Hg",
    "SaO2": "%",
    "BUN": "mg/dL",
    "Creatinine": "mg/dL",
    "Lactate": "mmol/L",
    "WBC": "\u00d710\u00b3/\u00b5L",
    "Platelets": "\u00d710\u00b3/\u00b5L",
    "Glucose": "mg/dL",
    "Age": "years",
}
# Vitals shown in the replay, with the NEWS2 0-point band as the shaded "normal range"
# (RCP NEWS2 Chart 1; SpO2 Scale 1). Values are the last measured value at each hour.
VITALS_SHOWN: dict[str, dict[str, object]] = {
    "HR": {"label": "Heart rate", "unit": "beats/min", "normal": [51, 90]},
    "Resp": {"label": "Breathing rate", "unit": "breaths/min", "normal": [12, 20]},
    "Temp": {"label": "Temperature", "unit": "°C", "normal": [36.1, 38.0]},
    "SBP": {"label": "Systolic blood pressure", "unit": "mm Hg", "normal": [111, 219]},
    "O2Sat": {"label": "Oxygen saturation", "unit": "%", "normal": [96, 100]},
}
ON_ADMISSION_NOTE = (
    "This patient was already labelled septic in their first ICU hour. The dataset starts "
    "the sepsis label 6 hours before the clinical onset, so the onset is placed at hour 6 "
    "by the same rule as every other patient; the true onset may have been earlier, even "
    "before ICU admission, which the record cannot show."
)


def base_variable(feature: str) -> str:
    for suffix in SUFFIXES:
        if feature.endswith(suffix):
            return feature[: -len(suffix)]
    return feature


def is_process(feature: str) -> bool:
    """Measurement-process features describe how often staff measured, not the value."""
    return feature.endswith(("__hsl", "__n"))


def unit_of(feature: str) -> str:
    if feature.endswith("__hsl"):
        return "hours"
    if feature.endswith("__n"):
        return "measurements"
    if feature.endswith("__std6"):
        return UNITS.get(base_variable(feature), "")
    return UNITS.get(base_variable(feature), "")


def reason_sentence(label: str, value: float | None, unit: str, contribution: float) -> str:
    effect = "raised" if contribution > 0 else "lowered"
    if value is None:
        return f"{label[:1].upper()}{label[1:]} (not measured yet) {effect} the risk."
    shown = f"{value:g} {unit}".strip()
    return f"{label[:1].upper()}{label[1:]} = {shown} {effect} the risk."


def _number(x: float) -> float | None:
    return None if not np.isfinite(x) else round(float(x), 4)


@dataclass(frozen=True)
class Stay:
    pid: str
    hours: int
    first: int | None  # first hour labelled septic, None if never
    model: Verdict


def _reasons_for(
    row: Explanation, values: np.ndarray, col: dict[str, int]
) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for r in row.reasons:
        value = _number(float(values[col[r.feature]]))
        label, unit = plain_name(r.feature), unit_of(r.feature)
        out.append(
            {
                "feature": r.feature,
                "label": label,
                "value": value,
                "unit": unit,
                "process": is_process(r.feature),
                "contribution": round(r.contribution, 4),
                "sentence": reason_sentence(label, value, unit, r.contribution),
            }
        )
    return out


def build(cfg: Config, data_dir: Path, models_dir: Path, results_dir: Path) -> Path:
    model = lgbm.load(models_dir / f"lgbm_{DIRECTION}")
    features = model.booster.feature_name()
    cal = json.loads((models_dir / f"lgbm_{DIRECTION}" / "calibration.json").read_text())
    platt, _ = calibration.from_json(cal)
    # The alert thresholds are read from the committed result files (never re-derived).
    strict = json.loads((results_dir / f"lgbm_{DIRECTION}.json").read_text())["strict_external"]
    news2_doc = json.loads((results_dir / f"news2_{DIRECTION}.json").read_text())
    threshold, news2_threshold = strict["threshold"], news2_doc["strict_external"]["threshold"]

    frame = read_features(data_dir, TARGET)
    raw = np.asarray(model.booster.predict(lgbm.matrix(frame, features), raw_score=True))
    frame["risk"] = platt.predict(raw)
    frame["alert"] = frame["risk"] >= threshold
    frame["news2"] = b.news2(frame)

    stays: list[Stay] = []
    for pid, g in frame.groupby("pid", sort=True):
        y = g[LABEL].to_numpy()
        first = int(np.argmax(y)) if y.any() else None
        alerts = [int(h) for h in np.flatnonzero(g["alert"].to_numpy())]
        stays.append(Stay(str(pid), len(g), first, verdict(alerts, onset_hour(first))))
    fits = [s for s in stays if MIN_HOURS <= s.hours <= MAX_HOURS]

    def later(s: Stay) -> bool:
        return s.first is not None and s.first > 0

    choices: list[tuple[str, Callable[[Stay], bool]]] = [
        ("Septic, caught early", lambda s: later(s) and (s.model.lead_hours or 0) >= 6),
        (
            "Septic, caught late",
            lambda s: later(s) and s.model.outcome == "warned" and (s.model.lead_hours or 0) < 3,
        ),
        ("Septic, missed", lambda s: later(s) and s.model.outcome == "never_warned"),
        ("Not septic, false alarms", lambda s: s.first is None and s.model.alert_hours >= 3),
        ("Not septic, quiet", lambda s: s.first is None and s.model.alert_hours == 0),
        ("Septic on admission (onset at hour 6)", lambda s: s.first == 0),
    ]
    patients = []
    for k, (story, rule) in enumerate(choices, start=1):
        # Septic-on-admission stays in hospital A are all 8-10 h; allow 8 h for that story.
        pool = fits if k < 6 else [s for s in stays if 8 <= s.hours <= MAX_HOURS]
        stay = next((s for s in pool if rule(s)), None)
        if stay is None:
            continue
        g = frame[frame["pid"] == stay.pid].reset_index(drop=True)
        x = lgbm.matrix(g, features)
        col = {name: i for i, name in enumerate(features)}
        explanations = explain_rows(model.booster, x, features)  # every hour
        onset = onset_hour(stay.first)
        news2_alerts = [int(h) for h in np.flatnonzero(g["news2"].to_numpy() >= news2_threshold)]
        news2_v = verdict(news2_alerts, onset)
        patients.append(
            {
                "key": f"demo-{k}",
                "label": f"Demo patient {k}",
                "story": story,
                "story_note": ON_ADMISSION_NOTE if stay.first == 0 else None,
                "hours": stay.hours,
                "septic": stay.first is not None,
                "onset_hour": onset,
                "window": None if onset is None else [max(0, onset - WINDOW_HOURS), onset],
                "age_group": "65 or older" if float(g["Age"].iloc[0]) >= 65 else "under 65",
                "risk": [round(float(v), 5) for v in g["risk"]],
                "news2": [int(v) for v in g["news2"]],
                "vitals": {
                    v: [_number(float(z)) for z in g[v].to_numpy(dtype=np.float64)]
                    for v in VITALS_SHOWN
                },
                "alert_hours": [int(h) for h in np.flatnonzero(g["alert"].to_numpy())],
                "news2_alert_hours": news2_alerts,
                "verdict": {"sepsiscope": stay.model.as_dict(), "news2": news2_v.as_dict()},
                "banner": banner(stay.model, news2_v, stay.first is not None),
                "reasons": [_reasons_for(e, x[h], col) for h, e in enumerate(explanations)],
            }
        )
    doc = {
        "direction": DIRECTION,
        "note": "Research prototype, not for clinical use. Model trained on hospital B; "
        "these hospital-A patients were never used for training, tuning or thresholds.",
        "lgbm_threshold": threshold,
        "lgbm_threshold_source": f"reports/results/lgbm_{DIRECTION}.json strict_external.threshold",
        "news2_threshold": news2_threshold,
        "alarm_budget": cfg.alarm_budget,
        "rules": list(RULES),
        "vitals": VITALS_SHOWN,
        "patients": patients,
    }
    out = data_dir / DEMO_FILE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return out
