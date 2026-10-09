"""Telemetry opt-outs, applied before any third-party library is imported.

This module is imported first by ``sepsiscope/__init__.py``. Setting the
variables in ``os.environ`` also makes every subprocess we start inherit them.

* ``MLFLOW_DISABLE_TELEMETRY`` - MLflow's documented opt-out (MLflow >= 3.2).
* ``DO_NOT_TRACK`` - the cross-tool convention; MLflow also honours it.

Not telemetry, but also set here: ``MLFLOW_DISABLE_AGENT_HINT`` stops MLflow
(>= 3.17) logging an absolute site-packages path (which contains the macOS
username) on import when it detects a coding agent.

``setdefault`` keeps an explicit value the user set in their shell, so a
deliberate override stays possible; ``doctor`` reports the effective status.
"""

from __future__ import annotations

import os

TELEMETRY_ENV: dict[str, str] = {
    "MLFLOW_DISABLE_TELEMETRY": "true",
    "DO_NOT_TRACK": "true",
}

QUIET_ENV: dict[str, str] = {
    "MLFLOW_DISABLE_AGENT_HINT": "1",
}


def apply_telemetry_optouts() -> None:
    """Set the opt-out variables unless the user already set them."""
    for key, value in {**TELEMETRY_ENV, **QUIET_ENV}.items():
        os.environ.setdefault(key, value)


def telemetry_env_ok() -> bool:
    """Return True if every opt-out variable is effectively 'true'."""
    return all(os.environ.get(k, "").lower() == "true" for k in TELEMETRY_ENV)


apply_telemetry_optouts()
