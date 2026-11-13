# Handoff

State of the work, so anyone can pick it up from the repository alone.

## Phase 1 closed; privacy hardening done (2026-10-22, ADR 0016). Next: Phase 2.

## Resume here

**Batch S (security and privacy lockdown) in progress.** Plan approved 2026-11-13. Batch A
(Milestone 3) is queued: its spec is in `docs/plan/batch-a.md`; present its plan only after
Batch S is pushed and CI is green.

- [x] **S1** Homebrew tools upgraded by name (no global upgrade, no cleanup, dependents
  untouched): uv 0.13.8, Python 3.13.18, Node 26.13.1, git 2.56.1, gh 2.104.0,
  ca-certificates 2026-11-05, libomp 23.1.5; gitleaks 8.30.1 and git-filter-repo 2.47.0
  installed.
- [x] **S2** uv `required-version >=0.13.4,<0.14`, `requires-python >=3.13.18,<3.14`
  (lockfile: that line only); `.venv` recreated on 3.13.18; `doctor` PASS and prints only
  the OS family and architecture; Parquets and cleaning report byte-identical on rebuild.
- [ ] **S3** Claude Code sandbox snippet drafted (2026-11-13); waiting for the maintainer to apply it, then run the proofs.
- [x] **S4** Package security fixes (`pip-audit` clean, `npm audit` clean): pillow 13.0.0,
  mlflow 3.18.0 (+ skinny, tracing), certifi 2026.10.23, virtualenv 21.15.6, filelock
  4.2.10, gitpython 3.2.1, pyasn1 0.6.5, soupsieve 4.1, tornado 6.6.1 (`eaf4b0a`). EDA
  figures regenerated: byte-identical. Dependabot PRs applied locally: #3, #5, #6, #7, #9
  (`dc43e63`); #4, #10 (`83b474b`). Those PRs can be closed. Still to add: any extra items
  from the Dependabot alert list, when it arrives.
- [x] **S5** gitleaks: pre-commit hook (system binary, staged changes, redacted; proven to
  block a token-shaped string); CI job downloads the official 8.30.1 release and checks it
  against pinned SHA-256 values for both the tarball and the checksums file; full-history
  scan: 0 findings.
- [x] **S6** CI prints uv, Python, Node and npm versions and fails below uv 0.13.4,
  Python 3.13.18 or Node 26.13.1 (setup-uv reads `required-version` from `pyproject.toml`).
- [x] **S4 follow-up** Dependabot alert list cross-checked; `nbconvert` 7.17.2; security
  floors in `[tool.uv] constraint-dependencies` (ADR 0017 amendment).
- [x] **S7 (part)** History rewritten in a scratch clone (identical HEAD tree, all offsets
  `+0000`, `privacy-audit --strict` and gitleaks clean); `privacy-audit` strict by default.
- [ ] **S7** Batch gate; history rewrite into a new private repository; push after approval.

Older notes (still valid until S7 replaces the repository):

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

## Privacy hardening (2026-10-22, ADR 0016)

- [x] `.gitignore` covers local-only files, MLflow artifacts, SQLite stores, logs, web coverage.
- [x] `CLAUDE.md` is project-neutral; personal notes are in the gitignored `CLAUDE.local.md`.
- [x] Neutral, OS-neutral docs; account-tier wording removed; name only in the copyright
  line, the pyproject author field and the git author.
- [x] Guard rules moved to `src/sepsiscope/audit/`, with new generic rules, the notebook
  check and the optional local denylist (`.privacy-denylist.local`).
- [x] `commit-msg` and `pre-push` hooks; CI checks every pushed commit.
- [x] `sepsiscope privacy-audit` (non-strict until the pre-sharing rewrite).
- [x] All commits from 2026-10-22 on are made with `TZ=UTC` (`+0000`).

## Open items (carried into later phases)

- **Phase 2, first step:** Dependabot PRs #3 (`@types/node` 26.6.5) and #4 (`uv-build`
  range): apply each locally as a squash commit with `TZ=UTC` (never merge in the web
  interface), then let Dependabot close the PRs.
- Phase 2: run the unit-columns-only ablation declared in ADR 0015.
- `pip-audit` (2026-10-22) reports advisories in `pillow` 12.3.0 (fixed in 13.0.0),
  `virtualenv` 21.14.6 (fixed in 21.14.7+) and `certifi` 2026.7.22 (fixed in 2026.10.19);
  `npm audit` is clean. Upgrade after approval, checking `pillow` 13 against matplotlib.
- **Phase 2/3, when the code is written:**
  - MLflow runs set the `mlflow.user` and `mlflow.source.name` tags explicitly (a fixed
    project value and a repository-relative path), record no git remote URL, keep
    `mlruns/`, `mlflow.db` and `mlartifacts/` untracked, and a test fails if any run tag or
    parameter contains a home path. Verify tag names in the MLflow docs first.
  - A logging filter rewrites the home directory to `~` and repository paths to relative
    ones in log files and CLI error output, with a test.
  - The FastAPI host is typed as `Literal["127.0.0.1"]` in the config, with a test.
- **Pre-sharing task (before anyone else gets access):** rewrite history with
  `git filter-repo` locally (text replacements kept outside the repository, commit dates
  converted to `+0000`), push the result to a **new** private repository, archive the old
  one, and decide on a secret scanner (gitleaks). After the history rewrite, switch
  privacy-audit to strict mode by default. Each install and push needs approval.

- Done in Phase 1: the official scorer is vendored in `third_party/physionet_eval/`.
- Branch protection for `main`: pending; the exact rules, to apply when enabled, are in
  `docs/ops.md`.
- Ubuntu runner: CI is pinned to `ubuntu-24.04`; upgrade deliberately later through a
  pull request (see `docs/ops.md`).

## Next

Phase 2 (features and models), once its plan is approved.
