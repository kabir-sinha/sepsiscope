"""Local demo API (plan B7, P4): serves the precomputed demo file, nothing else.

- Bound to 127.0.0.1 only (the host is typed ``Literal["127.0.0.1"]`` in the config).
- CORS allows only the local web page's origins.
- No model, no training and no outside calls at request time: the JSON file is read once.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

LOCAL_ORIGINS = ["http://127.0.0.1:5173", "http://localhost:5173"]
RESULT_MODELS = ("lgbm", "lr", "news2", "sirs", "qsofa")
DIRECTIONS = ("A2B", "B2A")


def results_summary(results_dir: Path) -> dict[str, Any]:
    """Headline numbers from the committed aggregate result files (no patient-level data)."""
    rows = []
    for direction in DIRECTIONS:
        for model in RESULT_MODELS:
            doc = json.loads((results_dir / f"{model}_{direction}.json").read_text("utf-8"))
            strict, adapted = doc["strict_external"], doc["deployment_adaptation"]
            point, ci = strict["point"], strict["ci95"]
            rows.append(
                {
                    "direction": direction,
                    "model": model,
                    "label": doc["model_label"],
                    "utility": point["utility"],
                    "utility_ci": ci["utility"],
                    "auroc": point["auroc"],
                    "auprc": point["auprc"],
                    "alert_rate": point["alert_rate"],
                    "false_alerts_per_100_days": point["false_alerts_per_100_patient_days"],
                    "timely_sensitivity": point["timely_sensitivity"],
                    "rethresholded_alert_rate": adapted["point"]["alert_rate"],
                    "rethresholded_utility": adapted["point"]["utility"],
                }
            )
    paired = {
        d: json.loads((results_dir / f"paired_{d}.json").read_text("utf-8"))["criterion_adr_0022"]
        for d in DIRECTIONS
    }
    budget = json.loads((results_dir / "lgbm_B2A.json").read_text("utf-8"))["alarm_budget"]
    return {"alarm_budget": budget, "rows": rows, "criterion": paired}


def create_app(demo_file: Path, results_dir: Path) -> FastAPI:
    doc: dict[str, Any] = json.loads(demo_file.read_text(encoding="utf-8"))
    results = results_summary(results_dir)
    by_key = {p["key"]: p for p in doc["patients"]}
    app = FastAPI(title="SepsiScope local demo", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(
        CORSMiddleware, allow_origins=LOCAL_ORIGINS, allow_methods=["GET"], allow_headers=[]
    )

    @app.get("/api/summary")
    def summary() -> dict[str, Any]:
        return {
            "direction": doc["direction"],
            "note": doc["note"],
            "lgbm_threshold": doc["lgbm_threshold"],
            "news2_threshold": doc["news2_threshold"],
            "alarm_budget": doc["alarm_budget"],
            "rules": doc["rules"],
            "vitals": doc["vitals"],
            "patients": [
                {
                    k: p[k]
                    for k in ("key", "label", "story", "story_note", "hours", "septic", "verdict")
                }
                for p in doc["patients"]
            ],
        }

    @app.get("/api/results")
    def get_results() -> dict[str, Any]:
        return results

    @app.get("/api/patients/{key}")
    def patient(key: str) -> dict[str, Any]:
        if key not in by_key:
            raise HTTPException(status_code=404, detail="unknown demo patient")
        result: dict[str, Any] = by_key[key]
        return result

    return app
