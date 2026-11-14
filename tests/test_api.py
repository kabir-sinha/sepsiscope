"""Local demo API: loopback only, local CORS only, serves a precomputed file, no IDs."""

from __future__ import annotations

import json
import re
import shutil
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

RESULTS = REPO_ROOT / "reports" / "results"
DOC = {
    "direction": "B2A",
    "note": "Research prototype, not for clinical use.",
    "lgbm_threshold": 0.05,
    "news2_threshold": 7.0,
    "alarm_budget": 0.05,
    "rules": ["rule"],
    "what_if": {"budgets": [0.05], "lgbm_thresholds": [0.05], "news2_thresholds": [7.0]},
    "vitals": {"HR": {"label": "Heart rate", "unit": "beats/min", "normal": [51, 90]}},
    "patients": [
        {
            "key": "demo-1",
            "label": "Demo patient 1",
            "story": "Septic, caught early",
            "story_note": None,
            "hours": 3,
            "septic": True,
            "onset_hour": 2,
            "window": [0, 2],
            "vitals": {"HR": [80, 95, 120]},
            "news2_alert_hours": [2],
            "compare": {"lr": [0.01, 0.02, 0.03], "news2_prob": [0.01, 0.02, 0.04]},
            "what_if": {
                "sepsiscope": [{"alert_hours": [1, 2], "verdict": {"outcome": "warned"}}],
                "news2": [{"alert_hours": [2], "verdict": {"outcome": "warned"}}],
            },
            "verdict": {"sepsiscope": {"outcome": "warned"}, "news2": {"outcome": "warned"}},
            "banner": "SepsiScope warned 1 h before onset · NEWS2 warned at the onset hour",
            "age_group": "under 65",
            "risk": [0.01, 0.06, 0.2],
            "news2": [2, 5, 8],
            "alert_hours": [1, 2],
            "reasons": [
                [],
                [
                    {
                        "feature": "HR",
                        "label": "heart rate",
                        "value": 120,
                        "unit": "beats/min",
                        "process": False,
                        "contribution": 0.4,
                        "sentence": "Heart rate = 120 beats/min raised the risk.",
                    }
                ],
                [],
            ],
        }
    ],
}


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    path = tmp_path / "demo.json"
    path.write_text(json.dumps(DOC))
    return TestClient(create_app(path, RESULTS))


def test_summary_and_patient(client: TestClient) -> None:
    summary = client.get("/api/summary").json()
    row = summary["patients"][0]
    assert set(row) == {
        "key",
        "label",
        "story",
        "story_note",
        "hours",
        "septic",
        "verdict",
        "what_if",
    }
    assert summary["rules"] == ["rule"] and summary["vitals"]["HR"]["normal"] == [51, 90]
    patient = client.get("/api/patients/demo-1").json()
    assert patient["alert_hours"] == [1, 2] and patient["news2_alert_hours"] == [2]
    assert len(patient["reasons"]) == patient["hours"] == len(patient["vitals"]["HR"])
    assert patient["reasons"][1][0]["sentence"].startswith("Heart rate")
    assert patient["window"] == [0, 2] and patient["banner"].startswith("SepsiScope")
    assert client.get("/api/patients/nope").status_code == 404
    assert client.get("/docs").status_code == 404  # no docs pages
    assert client.post("/api/summary").status_code == 405  # read-only


def test_results_come_from_committed_aggregates(client: TestClient) -> None:
    res = client.get("/api/results").json()
    assert res["alarm_budget"] == 0.05
    assert {(r["model"], r["direction"]) for r in res["rows"]} == {
        (m, d) for m in ("lgbm", "lr", "news2", "sirs", "qsofa") for d in ("A2B", "B2A")
    }
    lgbm = next(r for r in res["rows"] if r["model"] == "lgbm" and r["direction"] == "B2A")
    committed = json.loads((RESULTS / "lgbm_B2A.json").read_text())["strict_external"]
    assert lgbm["alert_rate"] == committed["point"]["alert_rate"]
    assert set(res["criterion"]) == {"A2B", "B2A"}


@pytest.fixture
def web_client(tmp_path: Path) -> TestClient:
    path = tmp_path / "demo.json"
    path.write_text(json.dumps(DOC))
    web = tmp_path / "dist"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text("<!doctype html><title>demo</title>")
    (web / "assets" / "app.js").write_text("console.log(1)")
    return TestClient(create_app(path, RESULTS, web))


def test_one_process_serves_web_and_api(web_client: TestClient) -> None:
    assert "<title>demo</title>" in web_client.get("/").text
    assert web_client.get("/assets/app.js").status_code == 200
    assert web_client.get("/api/summary").json()["what_if"]["budgets"] == [0.05]


@pytest.mark.parametrize("path", ["/", "/assets/app.js", "/api/summary", "/api/patients/nope"])
def test_security_headers_on_every_response(web_client: TestClient, path: str) -> None:
    headers = web_client.get(path).headers
    csp = headers["content-security-policy"]
    assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert "http" not in csp  # no external origins at all
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "no-referrer"
    assert headers["x-frame-options"] == "DENY"


def test_built_bundle_has_no_ids_paths_or_source_maps() -> None:
    dist = REPO_ROOT / "web" / "dist"
    if not (dist / "index.html").is_file():
        pytest.skip("web/dist not built (run npm run build)")
    files = [p for p in dist.rglob("*") if p.is_file()]
    assert not [p for p in files if p.suffix == ".map"]
    home = str(Path.home())
    for p in files:
        if p.suffix in {".js", ".css", ".html", ".svg"}:
            text = p.read_text(errors="ignore")
            assert "sourceMappingURL" not in text, p.name
            assert home not in text and "/" + "Users/" not in text, p.name
            assert not re.search(r"\bp\d{6}\b", text), p.name
            assert "fonts.googleapis" not in text and "cdn." not in text, p.name


def test_built_fonts_are_same_origin_and_served_with_csp(tmp_path: Path) -> None:
    dist = REPO_ROOT / "web" / "dist"
    if not (dist / "index.html").is_file():
        pytest.skip("web/dist not built (run npm run build)")
    css = "".join(p.read_text() for p in (dist / "assets").glob("*.css"))
    urls = re.findall(r"url\(([^)]*)\)", css)
    assert urls and all(u.strip("'\"").startswith(("/fonts/", "data:")) for u in urls)
    path = tmp_path / "demo.json"
    path.write_text(json.dumps(DOC))
    client = TestClient(create_app(path, RESULTS, dist))
    font = client.get("/fonts/IBMPlexSans-Regular-Latin1.woff2")
    assert font.status_code == 200 and font.content[:4] == b"wOF2"
    assert "font-src 'self'" in font.headers["content-security-policy"]


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
    shutil.copytree(RESULTS, tmp_path / "reports" / "results")
    (tmp_path / "web" / "dist").mkdir(parents=True)
    (tmp_path / "web" / "dist" / "index.html").write_text("<!doctype html>")
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
    for path in (f for f in files if f.is_file()):
        assert not re.search(r"\bp\d{6}\b", path.read_text(errors="ignore")), path.name


def test_display_values_and_sentences() -> None:
    from sepsiscope.api.demo import display_value, reason_sentence

    assert display_value(37.1667) == "37.2" and display_value(112.0) == "112"
    assert display_value(1.234) == "1.23" and display_value(0.5) == "0.5"
    assert reason_sentence("temperature", 37.1667, "°C", 0.2) == (
        "Temperature = 37.2 °C raised the risk."
    )
    assert "information to the model" not in reason_sentence("lactate", None, "mmol/L", 0.1)


def test_plain_names() -> None:
    assert plain_name("HR__n") == "number of heart rate measurements so far"
    assert plain_name("Temp__mean6") == "temperature, average over the last 6 hours"
    assert plain_name("shock_index").startswith("shock index")
