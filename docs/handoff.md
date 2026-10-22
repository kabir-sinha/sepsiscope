# Handoff

State of the work, so anyone can pick it up from the repository alone.

## Phase 1 closed. M2 evidence report delivered (2026-10-10). Next: Phase 2.

- Repository `kabir-sinha/sepsiscope` is **private**; default branch `main`.
- First CI run is green: run `38003153138` (jobs `python` and `web`). After the four
  follow-up tasks, CI is green on `df74bd2`: run `38004614423`, on `ubuntu-24.04`.
- Commit `1e7b118` (`docs(ops): record repository state after first push`) is
  pushed.
- Branch protection: pending; rules in `docs/ops.md`, to apply when enabled.

## Pending tasks

- [x] **Task 1:** pushed `1e7b118` and `bceb8db` after a clean privacy scan.
- [x] **Task 2:** `ignore` rule for `typescript` semver-major updates added and pushed
  (`ba3152f`); PR #1 answered with `@dependabot ignore this major version`.
- [x] **Task 3:** runtime is Node 26 (`web/.nvmrc`, read by CI via `node-version-file`);
  `@types/node` moved from major 24 to 26.6.4 by merging PR #2 (`56a5bdb`, authored by
  `dependabot[bot]`); local `npm ci`, lint and build pass.
- [x] **Task 4:** both CI jobs pinned to `runs-on: ubuntu-24.04` (26e9efe); upgrade note in
  `docs/ops.md`.

All four are done and pushed. Open pull requests: none (#1 closed, #2 merged).

## Phase 0 close-out

- [x] **Close-out 1:** fetched; local `main` was 0 behind `origin/main` (`dfad15b`) and
  contains the PR #2 merge `56a5bdb`; no fast-forward needed.
- [x] **Close-out 2:** citations amended (c2c2892, ADR 0011): Sepsis-3 Box 1 verified in the
  full text; row counts verified in Table 2 of `manuscript.pdf`, on printed page 11
  (an earlier note said page 10).
- [x] **Close-out 3:** `ignore` rule for `@types/node` semver-major updates added (0c1b915).
- [x] **Close-out 4:** state table in `docs/ops.md` refreshed (e82bbf1).
- [x] **Close-out 5:** Definition of Done re-run on 2026-10-10, all green: `uv sync --locked`;
  `doctor` PASS (OpenMP OK, telemetry off, nothing personal printed); pytest 48 passed, three
  runs in a row; ruff and mypy clean; `pre-commit run --all-files` clean; web `npm ci`, lint
  and build clean; pip-audit and npm audit report no vulnerabilities; full-history privacy
  scan (100 blobs, 28 commits) clean. No files changed.
- [x] **Close-out 6:** "Open items" section added; ten commits pushed after a clean privacy
  scan (`dfad15b..c92c9c5`); CI green on `c92c9c5`: run `38028938070` (jobs `python` and `web`).

## Phase 1 checklist

No models are trained in this phase.

- [x] **P1-1:** downloader (`sepsiscope data download`): S3 listing, resumable, size + MD5 checks, manifest summary. All 40,336 files downloaded and verified by size and MD5 (code fc39560, manifest summary 45159b6).
- [x] **P1-2:** verify (`sepsiscope data verify`): recompute the fingerprint, fail loudly on mismatch. Real data: all 28 checks match (code 8af0c9b).
- [x] **P1-3:** build (`sepsiscope data build`): raw Parquet with pid, hospital, t + 41 original columns. Real data: 1,552,210 rows, 40,336 patients, 14.7 MB, byte-identical on rebuild (b4ac7f6, 6e3365b).
- [x] **P1-4:** cleaning rules table, clean Parquet, `reports/data/cleaning_report.json`. Real data: 504 values set to missing; report and ADR 0014 (1db5443, fcced96).
- [x] **P1-5:** pandera schemas for raw and clean, validated in `data build`. Both Parquets validate in `data build` (b4ac7f6).
- [x] **P1-6:** splits (`sepsiscope data splits`): 60/20/20 by patient, seed 42, stratified; ADR. Split files committed, septic rate preserved, ADR 0013 (1e75e03, 2dcc210).
- [x] **P1-7:** data card (`docs/data_card.md`) (92a3d19).
- [x] **P1-8:** EDA notebook, figures, `docs/eda_findings.md`. Notebook runs on real data with 0 errors; six figures, byte-identical on re-run (6ce5480, 1ad25e2).
- [x] **P1-9:** vendor the official scorer into `third_party/physionet_eval/` with licence and example test (e5fec2d).
- [x] **P1-10:** tests (mocked HTTP, fixture fingerprint, cleaning, schema, splits, Parquet round-trip, `data` marker). 136 tests plus one real-data test; network blocked in tests (8526542).
- [x] **P1-11:** qSOFA Box 4 citation added (2387c6d, ADR 0012). `ruff format` counts
  Markdown files as well as Python files (it formats Python code blocks in Markdown), which
  explains the higher count; nothing unintended is included, no config change.
- [x] **P1-12:** close the build: full Definition of Done, no data in git, push after scan, CI. Definition of Done green (137 tests ×3, clean clone 136 passed and 1 skipped, ruff, mypy, pre-commit, web build, audits); full-history scan clean; no data in git; 27 commits pushed (`52e271d..f71483a`); CI green on `f71483a`: run `38070758706`.
- [x] **P1-13:** Milestone 2 evidence report, Parts A-F, delivered outside the repository (no files). Delivered on 2026-10-10, Parts A to F; no files were created for it.

## Phase 1 critique log

- An old Phase 0 test (`test_stubs`) still invoked `sepsiscope data download` after the
  command became real, so a test run started the approved download early. It wrote only
  inside `data/raw/` (git-ignored). Fixed: the test no longer calls it; `tests/conftest.py`
  has an autouse socket-level guard that fails any test opening a real connection (no new
  package); every run of the downloader re-checks the size and MD5 of every file, including
  those fetched early, and removes stale temp files.

## Open items (carried into later phases)

- Phase 2: run the unit-columns-only ablation declared in ADR 0015.

- Done in Phase 1: the official scorer is vendored in `third_party/physionet_eval/`.
- Branch protection for `main`: pending; the exact rules, to apply when enabled, are in
  `docs/ops.md`.
- Ubuntu runner: CI is pinned to `ubuntu-24.04`; upgrade deliberately later through a
  pull request (see `docs/ops.md`).

## Next

Phase 2 (features and models), once its plan is approved.
