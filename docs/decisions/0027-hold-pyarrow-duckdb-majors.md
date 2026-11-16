# 0027 — Hold major upgrades of pyarrow and duckdb

**Date:** 2026-11-16 · **Status:** Accepted · **Does not change** `docs/protocol.md`

## Context
Dependabot opened pyarrow 25.0.1 → 26.0.1 (#5) and duckdb 1.5.6 → 2.0.0 (#3), both major
versions. pyarrow reads and writes every Parquet file the pipeline builds; the committed
byte-check manifest (`reports/manifest_c6.json`, 91 files) proves that a re-run gives
byte-identical result files. duckdb is a declared dependency that only the smoke test
imports today. (mlflow 3.18 accepts `pyarrow<27`, so mlflow no longer blocks pyarrow 26.)

## Decision
- Keep pyarrow 25.0.1 and duckdb 1.5.6 for now; #5 and #3 are not merged.
- `.github/dependabot.yml` ignores **major** updates of both (minor and patch updates
  still come).
- A major upgrade is done deliberately in its own change: run `sepsiscope reproduce` and
  `scripts/byte_check.py --compare reports/manifest_c6.json`; if files differ, explain each
  difference and record a new manifest with an ADR.

## Alternatives
- **Merge now:** rejected; a storage-format library's major release can change how files
  are written, and it would need a full re-run and byte check first.
- **Ignore all updates of both:** rejected; security fixes arrive as minor or patch updates.

## Consequences
- The 2.0 and 26 features are not used until the deliberate upgrade.
- Reproducibility guarantees stay as tested.
