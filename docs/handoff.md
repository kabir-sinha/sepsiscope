# Handoff

State of the work, so anyone can pick it up from the repository alone.

## Phase 0 closed. Phase 1 in progress (see the Phase 1 checklist).

- Repository `kabir-sinha/sepsiscope` is **private**; default branch `main`.
- First CI run is green: run `38003153138` (jobs `python` and `web`). After the four
  follow-up tasks, CI is green on `df74bd2`: run `38004614423`, on `ubuntu-24.04`.
- Commit `1e7b118` (`docs(ops): record repository state after first push`) is
  pushed.
- Branch protection: pending; rules in `docs/ops.md`, to apply when enabled.

## Rules for this work

- Show diffs before committing.
- Verify every flag, option and label against official docs first.
- Never push without a clean privacy scan (username, home path, non-noreply emails).
- Never leave a half-applied change; stop only at a clean commit and record where.

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

## Paused on 2026-10-10: exactly where things stand

- **Last code commit before this note:** `8526542` (`test: block DNS and connect_ex in the
  network guard, allow AF_UNIX`). Working tree clean.
- **Download:** 30,651 of 40,336 files on disk when paused (set A 20,336 of 20,336,
  set B 10,315 of 20,000), in the git-ignored `data/raw/`. The background download was
  still running and may finish or be killed; either is fine because it is resumable.
- **Not run yet:** `sepsiscope data verify`, `data build`, `data splits`. No real-data
  result exists yet, so nothing about the fingerprint is confirmed.
- **Phase 1 tasks done:** P1-9 (vendored scorer) and P1-11 (Phase 0 leftovers).
- **Code written, tested on synthetic data and committed, but not yet run on real data**
  (so not ticked): P1-1 downloader, P1-2 verify, P1-3 build, P1-4 cleaning rules,
  P1-5 schemas, P1-6 splits code, most of P1-10 tests, the EDA functions, figure code
  and notebook for P1-8. 133 tests pass with the network blocked.
- **Dependencies added with approval:** `defusedxml==0.7.1` (runtime),
  `types-defusedxml` and `pandas-stubs==3.0.5.260914` (dev).

### Next three steps

1. Re-run `uv run sepsiscope data download`. It resumes, re-checks the size and MD5 of
   every file (including those fetched earlier), removes stale temp files and writes
   `data/raw/MANIFEST.json`. Record the manifest SHA-256 in `docs/data_manifest.md`.
2. Run `uv run sepsiscope data verify` and compare with the expected fingerprint. On any
   mismatch: stop and show expected vs observed.
3. Stage 2 on real data: `data build`; check observed distributions against each cleaning
   bound; ADR 0013 (stratified splits) and ADR 0014 (cleaning bounds, with per-hospital
   counts and the values just outside each bound); `data splits`; then tick P1-1 to P1-6.

### Pending

- **16 local commits are not pushed.** The push waits for the Stage 3 privacy scan.
- Still to write: `docs/data_manifest.md`, `docs/data_card.md` (include Age 90+ coded as
  100 as a de-identification quirk; Age stays uncapped), `docs/eda_findings.md`, the
  figures, a CHANGELOG entry for Phase 1, and the `docs/ai_assistance.md` Phase 1 row.
- Cleaning-rule reasons in `src/sepsiscope/data/clean.py` are provisional until checked
  against the real distributions.
- Commit `b4ac7f6` also contains `build.py`, although its title mentions only cleaning
  and schemas.
- Evidence report (P1-13): Pollard et al. 2026 (Nature Health 1(8):792-795) is verified on
  Crossref and on the PhysioNet page; cite it alongside Goldberger 2000.

## Phase 1 checklist

No models are trained in this phase.

- [x] **P1-1:** downloader (`sepsiscope data download`): S3 listing, resumable, size + MD5 checks, manifest summary. All 40,336 files downloaded and verified by size and MD5 (code fc39560, manifest summary 45159b6).
- [x] **P1-2:** verify (`sepsiscope data verify`): recompute the fingerprint, fail loudly on mismatch. Real data: all 28 checks match (code 8af0c9b).
- [ ] **P1-3:** build (`sepsiscope data build`): raw Parquet with pid, hospital, t + 41 original columns. _Not started._
- [ ] **P1-4:** cleaning rules table, clean Parquet, `reports/data/cleaning_report.json`. _Not started._
- [ ] **P1-5:** pandera schemas for raw and clean, validated in `data build`. _Not started._
- [ ] **P1-6:** splits (`sepsiscope data splits`): 60/20/20 by patient, seed 42, stratified; ADR. _Not started._
- [ ] **P1-7:** data card (`docs/data_card.md`). _Not started._
- [ ] **P1-8:** EDA notebook, figures, `docs/eda_findings.md`. _Not started._
- [x] **P1-9:** vendor the official scorer into `third_party/physionet_eval/` with licence and example test (e5fec2d).
- [ ] **P1-10:** tests (mocked HTTP, fixture fingerprint, cleaning, schema, splits, Parquet round-trip, `data` marker). _Not started._
- [x] **P1-11:** qSOFA Box 4 citation added (2387c6d, ADR 0012). `ruff format` counts
  Markdown files as well as Python files (it formats Python code blocks in Markdown), which
  explains the higher count; nothing unintended is included, no config change.
- [ ] **P1-12:** close the build: full Definition of Done, no data in git, push after scan, CI. _Not started._
- [ ] **P1-13:** Milestone 2 evidence report, Parts A-F, delivered outside the repository (no files). _Not started._

## Phase 1 critique log

- An old Phase 0 test (`test_stubs`) still invoked `sepsiscope data download` after the
  command became real, so a test run started the approved download early. It wrote only
  inside `data/raw/` (git-ignored). Fixed: the test no longer calls it; `tests/conftest.py`
  has an autouse socket-level guard that fails any test opening a real connection (no new
  package); every run of the downloader re-checks the size and MD5 of every file, including
  those fetched early, and removes stale temp files.

## Open items (carried into later phases)

- Vendor the official `evaluate_sepsis_score.py` into `third_party/` together with its
  BSD-2-Clause licence file (`LICENSE.txt` in the upstream repository). Phase 1 or 2.
- Branch protection for `main`: pending. The exact
  rules are in `docs/ops.md`.
- Ubuntu runner: CI is pinned to `ubuntu-24.04`; upgrade deliberately later through a
  pull request (see `docs/ops.md`).

## Next after these

Phase 1 (data download + fingerprint check).
