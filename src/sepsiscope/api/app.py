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


def create_app(demo_file: Path) -> FastAPI:
    doc: dict[str, Any] = json.loads(demo_file.read_text(encoding="utf-8"))
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
            "patients": [
                {k: p[k] for k in ("key", "label", "story", "hours", "septic")}
                for p in doc["patients"]
            ],
        }

    @app.get("/api/patients/{key}")
    def patient(key: str) -> dict[str, Any]:
        if key not in by_key:
            raise HTTPException(status_code=404, detail="unknown demo patient")
        result: dict[str, Any] = by_key[key]
        return result

    return app
