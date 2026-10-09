# 0009 — Dependency pins and exclusions

**Date:** 2026-10-10 · **Status:** Accepted

## Context
Results must be reproducible, and installs must be verifiable.

## Decision
Exact `==` pins in `pyproject.toml`; `uv.lock` records sha256 hashes for every artifact.
Versions were checked live on PyPI on 2026-10-10.
- **pyarrow 25.0.1, not 26.0.0:** mlflow 3.17.0 requires `pyarrow<26`.
- **ruff 0.16.10, not 0.17.0:** 0.17.0 was one day old; a minor ruff release can change rules.
- `types-PyYAML` added to the dev group so mypy strict can type-check `yaml`.
- Optional extra `[xgb]`: xgboost 3.4.1.
- **Excluded:** torch (bundles another OpenMP), polars (2.0 days old), MAPIE (its standard
  conformal mode failed on rare events in earlier testing).

## Alternatives
Ranges (`>=`): rejected for reproducibility.

## Consequences
Upgrades come through Dependabot PRs, which CI must pass.

## Sources
[PyPI JSON API](https://docs.pypi.org/api/json/) ·
[uv lockfile](https://docs.astral.sh/uv/concepts/projects/layout/#the-lockfile)
