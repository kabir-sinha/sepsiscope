# 0006 — Telemetry off, enforced in code and tested

**Date:** 2026-10-10 · **Status:** Accepted

## Context
MLflow (>= 3.2) collects anonymous usage data by default. MLflow also turns it off on
its own when it detects CI or pytest, so a naive test would pass even if our code did
nothing.

## Decision
`sepsiscope/_privacy.py` is the first import of the package and `setdefault`s
`MLFLOW_DISABLE_TELEMETRY=true` and `DO_NOT_TRACK=true` (and `MLFLOW_DISABLE_AGENT_HINT=1`,
which stops an import-time log line containing the home path). Child processes inherit
them. CI sets them too. `tests/test_privacy.py` runs in a subprocess with **all** CI and
pytest markers removed, asserts that MLflow's own CI detection is `False`, and then that
`get_telemetry_client()` is `None`.
Homebrew analytics were turned off globally with `brew analytics off` (approved).

## Alternatives
Rely on MLflow's CI detection: rejected (it does not run on the local machine). Hard overwrite
instead of `setdefault`: rejected so that a deliberate shell override stays possible;
`doctor` reports the effective state and fails if telemetry is on.

## Consequences
Any code path that imports `mlflow` must import `sepsiscope` first; scripts and
notebooks only call into `sepsiscope`, so this holds.

## Sources
[MLflow telemetry source (v3.17.0)](https://github.com/mlflow/mlflow/blob/v3.17.0/mlflow/telemetry/utils.py) ·
[Homebrew analytics](https://docs.brew.sh/Analytics)
