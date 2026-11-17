# 0028 — Monthly, grouped Dependabot updates

**Date:** 2026-11-17 · **Status:** Accepted · **Does not change** `docs/protocol.md`

## Context
Weekly Dependabot runs opened one PR per package (nine PRs in the first week), each of
which is applied and tested locally by hand (ADR 0027 workflow).

## Decision
For all three ecosystems (uv, npm in `web/`, github-actions), `.github/dependabot.yml`
checks **monthly** and bundles every **minor and patch** version update into one grouped
PR per ecosystem (`applies-to: version-updates`). Major updates still arrive as separate
PRs; the existing major ignores stay (typescript and `@types/node`; pyarrow and duckdb,
ADR 0027). Security updates are not grouped and still open as soon as an advisory exists.

## Consequences
At most three routine PRs a month, each still gated by the full tests, the API probe and
the byte check before it is applied; security fixes are not delayed.
