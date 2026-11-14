"""Local demo server (plan B7, P4; demo hardening v3): API plus the built web app.

- Bound to 127.0.0.1 only (the host is typed ``Literal["127.0.0.1"]`` in the config).
- CORS allows only the local development page's origins.
- No model, no training and no outside calls at request time: the JSON files are read once.
- One process serves the built web app (``web/dist``) and the API, so one command runs the
  demo. Every response, a 500 error included, carries security headers: a
  Content-Security-Policy that allows only this origin, ``nosniff``, ``no-referrer`` and no
  framing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import RequestResponseEndpoint

LOCAL_ORIGINS = ["http://127.0.0.1:5173", "http://localhost:5173"]
RESULT_MODELS = ("lgbm", "lr", "news2", "sirs", "qsofa")
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; "
    "form-action 'none'; frame-ancestors 'none'"
)
SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}
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
                    "auroc_ci": ci["auroc"],
                    "auprc_ci": ci["auprc"],
                    "timely_sensitivity_ci": ci["timely_sensitivity"],
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


def create_app(demo_file: Path, results_dir: Path, static_dir: Path | None = None) -> FastAPI:
    doc: dict[str, Any] = json.loads(demo_file.read_text(encoding="utf-8"))
    results = results_summary(results_dir)
    by_key = {p["key"]: p for p in doc["patients"]}
    app = FastAPI(title="SepsiScope local demo", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(
        CORSMiddleware, allow_origins=LOCAL_ORIGINS, allow_methods=["GET"], allow_headers=[]
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        return response

    # An unexpected error is answered by Starlette's outermost error layer, which runs outside
    # the middleware above, so this handler sets the same headers itself. The body is fixed
    # text: no exception message, path or traceback ever reaches the browser.
    @app.exception_handler(Exception)
    async def server_error(request: Request, exc: Exception) -> Response:
        return PlainTextResponse("Internal Server Error", status_code=500, headers=SECURITY_HEADERS)

    @app.get("/api/summary")
    def summary() -> dict[str, Any]:
        return {
            "direction": doc["direction"],
            "note": doc["note"],
            "lgbm_threshold": doc["lgbm_threshold"],
            "news2_threshold": doc["news2_threshold"],
            "alarm_budget": doc["alarm_budget"],
            "rules": doc["rules"],
            "what_if": doc["what_if"],
            "vitals": doc["vitals"],
            "patients": [
                {
                    k: p[k]
                    for k in (
                        "key",
                        "label",
                        "story",
                        "story_note",
                        "hours",
                        "septic",
                        "verdict",
                        "what_if",
                    )
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

    if static_dir is not None:
        # Mounted last, so /api/* routes win; html=True serves index.html at "/".
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="web")
    return app
