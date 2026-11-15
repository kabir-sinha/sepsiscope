"""Privacy-scan item 9: probe the local demo app (in-process, no server, no network).

Builds the app exactly as ``sepsiscope demo serve`` does (built ``web/dist``, the ignored
demo JSON, committed results), adds two probe-only routes (one that raises, one with an
integer parameter), requests every path below and checks the status code and that every
response carries the security headers. Prints one line; exit 1 on any mismatch, 2 when the
demo data or the web build is missing.

Usage (repository top folder): ``uv run python scripts/api_probe.py``
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

from sepsiscope.api.app import SECURITY_HEADERS, create_app

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "data" / "demo" / "demo_B2A.json"
DIST = ROOT / "web" / "dist"
EXPECTED: tuple[tuple[str, str, int], ...] = (
    ("GET", "/", 200),
    ("GET", "/api/summary", 200),
    ("GET", "/api/results", 200),
    ("GET", "/api/patients/demo-1", 200),
    ("GET", "/fonts/IBMPlexSans-Regular-Latin1.woff2", 200),
    ("GET", "/favicon.svg", 200),
    ("GET", "/api/patients/nope", 404),
    ("GET", "/nope.js", 404),
    ("GET", "/%2e%2e/pyproject.toml", 404),
    ("GET", "/docs", 404),
    ("GET", "/openapi.json", 404),
    ("POST", "/api/summary", 405),
    ("GET", "/api/_boom", 500),
    ("GET", "/api/_int/abc", 422),
)


def main() -> int:
    if not DEMO.is_file() or not (DIST / "index.html").is_file():
        print("ERROR: run `sepsiscope demo build` and `npm run build` in web/ first")
        return 2
    app = create_app(DEMO, ROOT / "reports" / "results", DIST)

    @app.get("/api/_boom")
    def boom() -> None:
        raise RuntimeError("probe")

    @app.get("/api/_int/{n}")
    def integer(n: int) -> dict[str, int]:
        return {"n": n}

    # The built web app is mounted at "/" and would catch these; match the probes first.
    probes = app.router.routes[-2:]
    app.router.routes[:] = probes + app.router.routes[:-2]

    client = TestClient(app, raise_server_exceptions=False)
    parts, bad = [], 0
    for method, path, want in EXPECTED:
        r = client.request(method, path)
        headers_ok = all(r.headers.get(k) == v for k, v in SECURITY_HEADERS.items())
        ok = r.status_code == want and headers_ok
        bad += not ok
        tag = "" if ok else ("!HEADERS" if r.status_code == want else f"!want {want}")
        parts.append(f"{'' if method == 'GET' else method + '='}{path}={r.status_code}{tag}")
    print("[9] " + " ".join(parts) + f" | security headers on all {len(EXPECTED)}: {bad == 0}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
