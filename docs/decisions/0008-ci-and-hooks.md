# 0008 — CI and pre-commit design

**Date:** 2026-10-10 · **Status:** Accepted

## Context
A workflow that hard-codes a Python version (e.g. 3.11) drifts from the project's
`.python-version` and breaks CI. Separately pinned
pre-commit mirrors can drift from the project's own ruff/mypy versions.

## Decision
- **CI** (`ubuntu-latest`): `actions/checkout@v7` with `persist-credentials: false`,
  `astral-sh/setup-uv@v10` **without** a `python-version` input (uv reads
  `.python-version`), `uv sync --locked`, ruff, mypy, pytest; `actions/setup-node@v7`
  with `node-version-file: web/.nvmrc`, then `npm ci`, lint and build. Top-level
  `permissions: contents: read`, `timeout-minutes: 15` per job, and a concurrency group
  that cancels superseded runs. Telemetry variables are set as workflow `env`.
- **pre-commit:** ruff, ruff-format, mypy and nbstripout are `repo: local` hooks run via
  `uv run --frozen`, so they use exactly the versions in `uv.lock`.
  `language: unsupported` is the pre-commit >= 4.4 name for `system`. Standard hooks
  come from `pre-commit/pre-commit-hooks` v6.0.0. A custom `privacy-guard` hook
  enforces the privacy rules.

## Alternatives
`astral-sh/ruff-pre-commit` mirror: rejected (a second version pin). Matrix of OSes:
out of scope (ubuntu only, as requested).

## Consequences
Hooks need `uv` on PATH. Dependabot does not update `uses:` versions (no
`github-actions` ecosystem was requested); check them manually each phase.

## Sources
[actions/checkout](https://github.com/actions/checkout) ·
[astral-sh/setup-uv](https://github.com/astral-sh/setup-uv) ·
[actions/setup-node](https://github.com/actions/setup-node) ·
[Workflow syntax: concurrency, permissions, timeout-minutes](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax) ·
[pre-commit: repository-local hooks](https://pre-commit.com/#repository-local-hooks) ·
[Ruff: pre-commit integration](https://docs.astral.sh/ruff/integrations/#pre-commit)
