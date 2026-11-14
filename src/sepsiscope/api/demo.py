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

from sepsiscope.config import Config
from sepsiscope.data.io import LABEL
from sepsiscope.evaluation.metrics import ONSET_OFFSET_HOURS, TIMELY_WINDOW_HOURS
from sepsiscope.features.pipeline import read_features
from sepsiscope.models import baselines as b
from sepsiscope.models import calibration, lgbm
from sepsiscope.trust.explain import explain_rows

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


def _number(x: float) -> float | None:
    return None if not np.isfinite(x) else round(float(x), 4)


@dataclass(frozen=True)
class Stay:
    pid: str
    hours: int
    septic: bool
    first: int  # first positive row, -1 if never septic
    onset: int | None
    n_alerts: int
    lead: int | None  # onset minus first timely alert; None if not caught

    @property
    def caught(self) -> bool:
        return self.lead is not None


def build(cfg: Config, data_dir: Path, models_dir: Path, results_dir: Path) -> Path:
    model = lgbm.load(models_dir / f"lgbm_{DIRECTION}")
    features = model.booster.feature_name()
    cal = json.loads((models_dir / f"lgbm_{DIRECTION}" / "calibration.json").read_text())
    platt, _ = calibration.from_json(cal)
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
        septic = bool(y.any())
        first = int(np.argmax(y)) if septic else -1
        onset = first + ONSET_OFFSET_HOURS if septic else None
        alerts = np.flatnonzero(g["alert"].to_numpy())
        lead = None
        if onset is not None:
            timely = [int(h) for h in alerts if onset - TIMELY_WINDOW_HOURS <= h <= onset]
            lead = onset - timely[0] if timely else None
        stays.append(Stay(str(pid), len(g), septic, first, onset, len(alerts), lead))
    fits = [s for s in stays if MIN_HOURS <= s.hours <= MAX_HOURS]

    choices: list[tuple[str, Callable[[Stay], bool]]] = [
        ("Septic, caught early", lambda s: s.caught and s.first > 0 and (s.lead or 0) >= 6),
        ("Septic, caught late", lambda s: s.caught and s.first > 0 and (s.lead or 0) < 3),
        ("Septic, missed", lambda s: s.septic and s.first > 0 and not s.caught),
        ("Not septic, false alarms", lambda s: not s.septic and s.n_alerts >= 3),
        ("Not septic, quiet", lambda s: not s.septic and s.n_alerts == 0),
        ("Septic from the first hour", lambda s: s.septic and s.first == 0),
    ]
    patients = []
    for k, (story, rule) in enumerate(choices, start=1):
        # Septic-from-the-first-hour stays are short; allow 8 h and up (all are 8-10 h).
        pool = fits if k < 6 else [s for s in stays if 8 <= s.hours <= MAX_HOURS]
        stay = next((s for s in pool if rule(s)), None)
        if stay is None:
            continue
        g = frame[frame["pid"] == stay.pid].reset_index(drop=True)
        alert_rows = np.flatnonzero(g["alert"].to_numpy())
        x = lgbm.matrix(g, features)
        explanations = explain_rows(model.booster, x[alert_rows], features)
        col = {name: i for i, name in enumerate(features)}
        reasons = {
            int(h): [
                {
                    "feature": r.feature,
                    "label": plain_name(r.feature),
                    "value": _number(float(x[h, col[r.feature]])),
                    "contribution": round(r.contribution, 4),
                }
                for r in e.reasons
            ]
            for h, e in zip(alert_rows, explanations, strict=True)
        }
        patients.append(
            {
                "key": f"demo-{k}",
                "label": f"Demo patient {k}",
                "story": story,
                "hours": stay.hours,
                "septic": stay.septic,
                "onset_hour": stay.onset,
                "age_group": "65 or older" if float(g["Age"].iloc[0]) >= 65 else "under 65",
                "risk": [round(float(v), 5) for v in g["risk"]],
                "news2": [int(v) for v in g["news2"]],
                "alert_hours": [int(h) for h in alert_rows],
                "reasons": reasons,
            }
        )
    doc = {
        "direction": DIRECTION,
        "note": "Research prototype, not for clinical use. Model trained on hospital B; "
        "these hospital-A patients were never used for training, tuning or thresholds.",
        "lgbm_threshold": threshold,
        "news2_threshold": news2_threshold,
        "alarm_budget": cfg.alarm_budget,
        "patients": patients,
    }
    out = data_dir / DEMO_FILE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    return out
