"""Local demo API: loopback only, local CORS only, serves a precomputed file, no IDs."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from typer.testing import CliRunner

from sepsiscope.api.app import LOCAL_ORIGINS, create_app
from sepsiscope.api.demo import plain_name
from sepsiscope.cli import app as cli_app
from sepsiscope.config import REPO_ROOT, Config, load_config

DOC = {
    "direction": "B2A",
    "note": "Research prototype, not for clinical use.",
    "lgbm_threshold": 0.05,
    "news2_threshold": 7.0,
    "alarm_budget": 0.05,
    "patients": [
        {
            "key": "demo-1",
            "label": "Demo patient 1",
            "story": "Septic, caught early",
            "hours": 3,
            "septic": True,
            "onset_hour": 2,
            "age_group": "under 65",
            "risk": [0.01, 0.06, 0.2],
            "news2": [2, 5, 8],
            "alert_hours": [1, 2],
            "reasons": {
                "1": [{"feature": "HR", "label": "heart rate", "value": 120, "contribution": 0.4}]
            },
        }
    ],
}


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    path = tmp_path / "demo.json"
    path.write_text(json.dumps(DOC))
    return TestClient(create_app(path))


def test_summary_and_patient(client: TestClient) -> None:
    summary = client.get("/api/summary").json()
    assert summary["patients"][0] == {
        "key": "demo-1",
        "label": "Demo patient 1",
        "story": "Septic, caught early",
        "hours": 3,
        "septic": True,
    }
    patient = client.get("/api/patients/demo-1").json()
    assert patient["alert_hours"] == [1, 2] and patient["reasons"]["1"][0]["label"] == "heart rate"
    assert client.get("/api/patients/nope").status_code == 404
    assert client.get("/docs").status_code == 404  # no docs pages
    assert client.post("/api/summary").status_code == 405  # read-only


def test_cors_allows_only_local_origins(client: TestClient) -> None:
    ok = client.get("/api/summary", headers={"Origin": LOCAL_ORIGINS[0]})
    assert ok.headers.get("access-control-allow-origin") == LOCAL_ORIGINS[0]
    other = client.get("/api/summary", headers={"Origin": "https://example.org"})
    assert "access-control-allow-origin" not in other.headers
    assert all(o.startswith(("http://127.0.0.1:", "http://localhost:")) for o in LOCAL_ORIGINS)


def test_config_accepts_only_loopback() -> None:
    raw: dict[str, Any] = load_config().model_dump()
    for host in ("0.0.0.0", "localhost", "192.168.1.2", "::"):  # noqa: S104 - checks it is refused
        raw["api"]["host"] = host
        with pytest.raises(ValidationError):
            Config.model_validate(raw)


def test_serve_binds_loopback_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import uvicorn

    from sepsiscope.api import demo

    seen: dict[str, Any] = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: seen.update(kw))
    path = tmp_path / "data" / demo.DEMO_FILE
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(DOC))
    monkeypatch.setattr("sepsiscope.cli.REPO_ROOT", tmp_path)
    result = CliRunner().invoke(cli_app, ["demo", "serve"])
    assert result.exit_code == 0, result.stdout
    assert seen["host"] == "127.0.0.1"


def test_no_other_host_in_source() -> None:
    text = "\n".join(p.read_text() for p in (REPO_ROOT / "src").rglob("*.py"))
    text += (REPO_ROOT / "web" / "vite.config.ts").read_text()
    assert "0.0.0.0" not in text  # noqa: S104 - checks it is absent


def test_no_patient_ids_in_tracked_web_or_api_files() -> None:
    files = [
        *(REPO_ROOT / "web" / "src").rglob("*.*"),
        *(REPO_ROOT / "src" / "sepsiscope" / "api").rglob("*.py"),
    ]
    for path in files:
        assert not re.search(r"\bp\d{6}\b", path.read_text(errors="ignore")), path.name


def test_plain_names() -> None:
    assert plain_name("HR__n") == "number of heart rate measurements so far"
    assert plain_name("Temp__mean6") == "temperature, average over the last 6 hours"
    assert plain_name("shock_index").startswith("shock index")
