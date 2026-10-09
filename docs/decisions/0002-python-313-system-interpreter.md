# 0002 — Python 3.13 via uv, using the Homebrew interpreter

**Date:** 2026-10-10 · **Status:** Accepted

## Context
All key packages ship macOS arm64 wheels for CPython 3.13. `dcurves` 1.1.7 declares
`requires-python <3.14`. uv resolves the lockfile for **every** Python allowed by
`requires-python`, so an open-ended `>=3.13` would make resolution fail.

## Decision
- `.python-version` = `3.13` (single source of truth, also read by CI).
- `requires-python = ">=3.13,<3.14"`.
- `[tool.uv] python-preference = "system"`: prefer the Homebrew 3.13.6 already installed;
  CI (which has no system 3.13) may fall back to a uv-managed build.
- `[tool.uv] required-version = ">=0.12.24,<0.13"`: the same uv minor locally and in CI
  (setup-uv reads this), so the lockfile format cannot drift.

## Alternatives
`only-system` (CI would fail without a system 3.13); a uv-managed interpreter locally
(a duplicate download).

## Consequences
`.venv/pyvenv.cfg` points at `/opt/homebrew/opt/python@3.13/bin`. Moving to 3.14 needs a
new ADR once dcurves supports it.

## Sources
[uv: Python version preference](https://docs.astral.sh/uv/concepts/python-versions/#adjusting-python-version-preferences) ·
[uv settings: required-version](https://docs.astral.sh/uv/reference/settings/#required-version) ·
[dcurves on PyPI](https://pypi.org/project/dcurves/)
