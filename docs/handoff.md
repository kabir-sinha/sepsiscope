# Handoff

State of the work, so anyone can pick it up from the repository alone.

## Phase 1 closed; privacy hardening done (2026-10-22, ADR 0016). Next: Phase 2.

## Resume here

**Paused 2026-11-14 (save point, Batch B gate in progress).** 31 commits unpushed (GitHub
`main` at `31bb0c5`), latest = this handoff commit; working tree clean.

**Done this session:**
- (a) Badge wording: no source change (a server started before the last `demo build`).
- Part 1 exhaustive privacy scan: 4 FAILs fixed (scan script blind under zsh, account handle
  in docs/CODEOWNERS, guard not blocking `models/` and `data/demo/`, 500 without security
  headers), real name removed from tracked files (ADR 0023), scan script requires the
  repo's top folder. The 28 unpushed commits were rewritten locally (maintainer approved):
  test fix folded in, author/committer name = the maintainer's first name, dates kept,
  `+0000`; nothing on GitHub touched. Allowed commit name is declared only in the gitignored
  local denylist (`allow-author-name:`). Re-run: **all 11 items PASS on both passes**, positive
  control caught by all three scanners.
- Gate so far: doctor PASS, font SHA-256s OK, `npm audit` 0. **FAIL: `pip-audit`
  CVE-2026-126360 in `opentelemetry-api 1.45.1`** (ReDoS in `traceparent` parsing; reached
  via fastapi/mlflow; not imported by our code; fix 1.45.2).
- Background gate job (unfinished at pause): `uv sync --locked` OK; full pytest: only the
  sandbox-blocked Unix-socket test failed (as before, covered by CI); train A2B 113 trees
  (4.8 s, 2.18 GiB), B2A 234 trees (6.3 s, 2.11 GiB); `evaluate --all-models` was running.
  Its later steps and the byte-identical comparison are **not recorded**: re-run them.

**Next on resume (upgrade APPROVED by the maintainer, with these conditions):**
1. Wait for or re-run the background job (tests once, train, `evaluate --all-models`,
   `ablations`, `exploratory`, `demo build`; tracked outputs must equal HEAD).
2. `uv lock --upgrade-package opentelemetry-api`: only `opentelemetry-api` and
   `opentelemetry-sdk` 1.45.1 → 1.45.2 and `opentelemetry-semantic-conventions`
   0.66b1 → 0.66b2 may change; show the lockfile diff; commit.
3. Real exit codes everywhere (`set -o pipefail`; never read a `tail` exit code), and
   re-check the earlier piped passes with real exit codes.
4. Full gate re-run, then the M4 evidence report (7 parts) + OFFICIAL NUMBERS table.
5. Update handoff and resume note, commit, double privacy check, STOP with the push command.
   The maintainer pushes from their own terminal.

Also for the maintainer: run `git config --local user.name` once with the allowed first name from `.privacy-denylist.local` (the sandbox
blocks `.git/config` writes; commits so far set the name through environment variables).

**Rules:** no push; no sandbox changes; ask before any download; double privacy check
(`sepsiscope privacy-audit` + `scripts/independent_scan.sh`); long runs in the background
under `caffeinate -i`, no polling.

**Batch S and Batch A (Milestone 3) closed 2026-11-13** and pushed by the maintainer from
their own terminal (latest `3e0da73`; CI #11 green on `ce231b2`, 0 open Dependabot alerts).
The Milestone 3 evidence document is done.

**Batch B (Milestone 4: trained model) approved 2026-11-13** with amendments; plan in
`docs/plan/batch-b.md`, decisions in ADR 0022. B0 is done. **Next step: B1** (LightGBM model
and `sepsiscope train`). Order: B1 → B6 → B2 → B3 → B4 → B5 → B7 → gate.
**B2 tuning waits for the maintainer's explicit "go".** Pushes happen from the
maintainer's own terminal.

### Batch B

- [x] **B0** Plan `docs/plan/batch-b.md` and ADR 0022.
- [x] **B1** LightGBM model and `sepsiscope train` (`models/lgbm.py`, `models/pipeline.py`):
  text + whitelisted JSON + feature schema in the ignored `models/lgbm_{direction}/`;
  deterministic, no class weights; data fingerprint = SHA-256 of contents. Default
  parameters (placeholder until B2): early stopping picks 19 trees (A2B) and 3 trees (B2A),
  because the default learning rate 0.1 overfits within a few rounds (inner hold-out AP
  peaks early; at 0.03 it keeps improving). Fit 3.9 s / 2.5 s, peak 2.45 GiB.
  Measured 0.033-0.093 s per boosting round on a fold-sized set (num_leaves 15-255).
- [x] **B6** MLflow tracking (`tracking.py`): local SQLite `mlruns/mlflow.db`; runs created
  with `MlflowClient.create_run`, which adds no automatic context tags (checked in the
  installed MLflow 3.18 source: `mlflow.start_run` would add the OS username, the absolute
  script path and the git remote URL); only six allowlisted tags; no artifacts. The SQLite
  store keeps an absolute artifact location inside the DB only (allowed by ADR 0022 item
  4; nothing is written there). `sepsiscope train` logs each run (`--no-track` to skip).
  Logging filter and scrubbed tracebacks (`logscrub.py`). Privacy guard blocks `.db`,
  `.sqlite`, `.sqlite3`, `.journal` and `mlruns/`. Real DB scan: 53 texts, 0 personal hits.
- [x] **B2** Optuna tuning per ADR 0021 (`models/tuning.py`, `sepsiscope tune --direction`),
  run 2026-11-13 under `caffeinate -i` after the maintainer's "go": 50 trials per direction,
  not resumed, no guard exit. A2B: 0.23 h, 27 pruned, best mean AUPRC 0.1220 (trial 36),
  final model 113 trees. B2A: 0.25 h, 32 pruned, best 0.1235 (trial 25), 234 trees.
  Results in `reports/tuning/lgbm_{A2B,B2A}.json` (numbers only); journal, status JSON and
  log in the ignored `mlruns/tuning/`. Pruned trials show a partial mean (folds seen so far),
  not comparable with complete trials. Resumability: the same command continues from the
  journal; TPE state restarts on resume, so a resumed run is not byte-identical.
- [x] **B3a** Calibration (`models/calibration.py`): Platt (headline, unpenalised) and isotonic
  (sensitivity) on raw log-odds, JSON only; fitted on the source calibration split in B4.
- [x] **B3b** Per-alert explanations (`trust/explain.py`): LightGBM `pred_contrib` on raw
  log-odds, chunked; contributions + base = raw score (tested to 1e-9).
- [x] **B4** `sepsiscope evaluate --all-models`: LightGBM (Platt headline, isotonic, raw) vs the
  4 baselines, both directions; paired difference CIs (`paired_*.json`), aggregate
  explanations (`explanations_*.json`); Batch A baseline files byte-identical; source
  hospital released before the target is loaded. `train` uses the committed tuned params.
- [x] **B5** `sepsiscope ablations`: 4 ablations both ways (main tuned params, not re-tuned),
  `ablation_*.json` and `drift.json`; 280 s, peak 4.32 GiB. Ablation features live in the
  ignored `features_{A,B}_ablation.parquet` (134 columns); main files untouched.
- [x] **B7c** Demo data v2: explicit verdict rules (`api/verdict.py`: onset = first septic hour
  + 6 h; window [onset - 12 h, onset], both ends included; lead = onset - first alert in the
  window; non-septic alerts = false alarms), per-hour vitals, both systems' alerts, top-5
  contributions for every hour with plain-English sentences and units, process features
  tagged; patient 6 renamed "Septic on admission (onset at hour 6)" with a labelling note;
  `/api/results` from committed aggregate JSONs. The dashed LightGBM line is the committed
  B2A strict threshold 0.049641 (4.96 %), not the 5 % budget.
- [x] **B7d** Dashboard redesign (`web/src`, plain React + SVG, no new packages): tabs "How it
  works" (4 steps, glossary, why an unseen hospital), "Patient replay" (cards with verdict
  badges, verdict banner, play/pause + hour slider, risk / NEWS2 / 5 vital charts on one
  hour axis with synced crosshair, threshold, onset, early-warning window, normal ranges,
  legends and helper text; "Why did it alert?" bar chart of the top 5 reasons with
  sentences, units and process tags) and "Results" (table, utility chart with CIs, alert
  drift chart, limitations) from committed aggregates. One light theme, Okabe-Ito palette,
  all text colours >= 4.5:1 contrast, keyboard tabs/slider/alert dots. Not visually checked
  in a browser inside the sandbox (no local server); the maintainer runs it.
- [x] **Integrity check v3 (2026-11-14):** after an accidental restart stopped the first
  re-run, no tracked output had changed; models rebuilt from the tuned params are
  byte-identical (A2B 113 trees, B2A 234 trees); full re-run of train, `evaluate
  --all-models`, `ablations` and `exploratory` under `caffeinate -i`: all 46 tracked files
  in `reports/` byte-identical to HEAD. Gate helpers moved out of the scratchpad into
  `scripts/measure.py` and `scripts/independent_scan.sh`.
- [x] **Demo hardening:** `sepsiscope demo serve` serves the built web app (`web/dist`,
  ignored) and the API from one process on 127.0.0.1; every response carries a CSP
  (`default-src 'self'`, no external origins, `frame-ancestors 'none'`), `nosniff`,
  `no-referrer`, `X-Frame-Options: DENY`; no source maps. What-if budgets 1-10 %:
  thresholds from hospital B's validation split only (5 % reproduces the committed
  threshold, checked in the build). Comparison curves: logistic regression and NEWS2 as a
  probability.
- [x] **Dashboard v3** (`web/src`, plain React + SVG, no new packages): one selected hour (Play,
  slider, ←/→, clicks) with hover as a labelled preview; charts drawn at true pixel width
  (axis text >= 12 px); inline no-wrap legends, one shared vitals legend; pointer-following
  tooltip that closes on leave/scroll; "Why" list with full sentences, inline bars, values
  and units; threshold labelled with its true value (4.96 %); Results with AUPRC and timely
  sensitivity CIs; headline strip; what-if budget slider; compare overlay; speed control;
  "Show as table" under every chart; light theme + "ICU monitor" dark mode; PhysioNet data
  credit and citations. Fonts: system stack until the self-hosted IBM Plex files are approved.
- [x] **Fonts:** self-hosted IBM Plex Sans 400/600/700 and Plex Mono 400 (Latin-1 subsets, OFL
  1.1) from `npm pack @ibm/plex-sans@1.1.0 @ibm/plex-mono@2.5.0` (integrity checked, not
  installed); SHA-256s in `web/public/fonts/FONTS.md`; the text-fixing pre-commit hooks skip
  that folder so the licence stays byte-identical.
- [x] **Dashboard v3.1:** page title; a patient opens at the first alert hour (else the
  highest-risk hour); round axis ticks (risk 0/2/4/6 %, hours 0/12/24/36/48); vitals to 1
  decimal; missing-value note shown once; verdict wording "Warned at onset" / "Alerted only
  before the window"; full Pollard et al. citation; glossary "targeted at about 5 %"; value
  labels on the utility bars and solid legend swatches matching the bars.
- [x] **Post-hoc, exploratory** (`sepsiscope exploratory`; not pre-registered, headline model
  unchanged): cumulative "measurements so far" counts replaced by measurements per hour of
  stay, same tuned params. A→B utility 0.129 [0.111, 0.147] (headline 0.226), AUROC 0.790,
  alert rate 2.7 %; B→A utility 0.192 [0.176, 0.207] (headline 0.273), AUROC 0.728, alert
  rate 8.5 %. Note: **cumulative counts partly proxy ICU time** (they grow with every hour
  of stay); without them, "hours since last measured" features rise to the top, which may
  carry a similar time signal. Recorded in `docs/model_card.md`.
  **Next: gate, then M4 evidence report.**
- [x] **B7a** Demo data and API: `sepsiscope demo build` writes 6 held-out hospital-A patients
  (B2A; caught early, caught late, missed, false alarms, quiet, septic from the first hour)
  to the ignored `data/demo/`, relabelled "Demo patient 1-6". `sepsiscope demo serve`:
  FastAPI on `Literal["127.0.0.1"]` (config `api`), CORS localhost only, GET only, no docs
  pages, no model at request time. Septic-from-first-hour stays in A are 8-10 h, so that
  story uses a minimum of 8 h (others 24-120 h).
- [x] **B7b** Dashboard (`web/src`): patient list, hourly LightGBM risk and modified NEWS2 (max 17)
  timelines in plain SVG with threshold, alerts and onset, top-5 reasons in plain English;
  no new npm package; lint, build and `npm audit` clean. The maintainer starts it locally.
- [ ] Gate and M4 evidence report (text).

**Sandbox decisions (maintainer, 2026-11-13), kept as they are:**
- Fetch and push stay in the maintainer's own terminal (sandbox proof 6 fails by design;
  no sandbox exclusion for git).
- Unix-socket binding stays off in the sandbox; `test_unix_domain_sockets_still_work`
  fails locally under the sandbox and is covered by CI.
- After the restart: `~/.ssh` read blocked, `uv sync --locked` exit 0, `npm ci` exit 0,
  reading a file in `~/Documents` blocked from both the shell and Claude Code's Read tool.

### Batch A

- [x] **A0** ADRs 0018 (modified NEWS2 (max 17) oxygen item), 0019 (strict external validation headline),
  0020 (deferral metrics), 0021 (tuning protocol).
- [x] **A1** Causal hourly features (`sepsiscope features build`): 130 float32 features per
  hospital in `data/processed/features_{A,B}.parquet` (A 790,215 rows, B 761,995), about 6 s,
  byte-identical on rebuild; schema in `reports/features/feature_schema.json`.
- [x] **A2** Baselines (`sepsiscope.models.baselines`): modified NEWS2 (max 17; bands verified against
  RCP NEWS2 Chart 1 on 2026-11-13), SIRS, modified qSOFA (max 2), logistic regression (median
  imputation + indicators + scaling, fitted on the training split only; stored as JSON),
  modified NEWS2 (max 17) as a probability. Never-measured items score 0 (ADR 0018).
- [x] **A3** Metrics library (`sepsiscope.evaluation.metrics`): official normalised utility
  (per-patient parts from the vendored scorer; equals `evaluate_sepsis_score` in a test),
  tie-aware AUROC/AUPRC (equal sklearn), tie-safe budget threshold, event metrics, ECE,
  weighted patient-level bootstrap, dcurves decision curves.
- [x] **A4** `sepsiscope evaluate --all-baselines`: 10 result JSON files in `reports/results/`
  and 4 figures in `reports/figures/results/`; strict external validation plus the
  deployment-adaptation analysis (ADR 0019); about 215 s and 5.5 GiB peak on the local
  machine; byte-identical on re-run. LR models saved as JSON with `feature_schema.json` in
  the ignored `models/baselines/`.
- [x] **A5** `docs/traceability.md`: protocol section / ADR → code → test → result.
- [x] **A6** Full gate (2026-11-13): `uv sync --locked`, `doctor` PASS, ruff, format, mypy,
  pre-commit (all files), `pip-audit --skip-editable` clean, web `npm ci` / lint / build /
  `npm audit` clean, `privacy-audit` strict PASS, gitleaks 0, independent history scan 0;
  evaluation byte-identical on re-run. pytest: 234 passed, **1 failed**:
  `test_network_guard.py::test_unix_domain_sockets_still_work` cannot bind a Unix socket
  inside the Claude Code sandbox (EPERM); not a code change, it passed before the sandbox.
  Evidence report delivered as text. Pushed by the maintainer at `ce231b2`; CI #11 green
  (the socket test passes in CI).

### Batch S

- [x] **S1** Homebrew tools upgraded by name (no global upgrade, no cleanup, dependents
  untouched): uv 0.13.8, Python 3.13.18, Node 26.13.1, git 2.56.1, gh 2.104.0,
  ca-certificates 2026-11-05, libomp 23.1.5; gitleaks 8.30.1 and git-filter-repo 2.47.0
  installed.
- [x] **S2** uv `required-version >=0.13.4,<0.14`, `requires-python >=3.13.18,<3.14`
  (lockfile: that line only); `.venv` recreated on 3.13.18; `doctor` PASS and prints only
  the OS family and architecture; Parquets and cleaning report byte-identical on rebuild.
- [x] **S3** Claude Code sandbox applied by the maintainer; proofs run 2026-11-13:
  1. write outside the repository: blocked (pass)
  2. connection to a domain not on the allowlist: blocked by the proxy, HTTP 403 (pass)
  3. read `~/.ssh`: blocked (pass)
  4. `uv sync --locked --all-extras`: exit 0 (pass)
  5. `npm ci` in `web/`: exit 0 (pass; npm notes that `fsevents` install scripts are not
     run, which is expected and harmless)
  6. `git fetch --dry-run origin`: **fails** (exit 128). The repository's credential helper
     (`gh auth git-credential`) must read `~/.config/gh`, which the sandbox denies, so git
     cannot authenticate to the private repository. Consequence: fetch and push run in the
     maintainer's own terminal. Maintainer decision: keep it that way (no sandbox change).
- [x] **S4** Package security fixes (`pip-audit` clean, `npm audit` clean): pillow 13.0.0,
  mlflow 3.18.0 (+ skinny, tracing), certifi 2026.10.23, virtualenv 21.15.6, filelock
  4.2.10, gitpython 3.2.1, pyasn1 0.6.5, soupsieve 4.1, tornado 6.6.1 (`d11a2ee`). EDA
  figures regenerated: byte-identical. Dependabot PRs applied locally: #3, #5, #6, #7, #9
  (`75604a7`); #4, #10 (`28b252e`). Those PRs can be closed. Still to add: any extra items
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
- [x] **S7** Batch gate passed; rewritten history pushed to a new private repository at
  `2811720`; CI green; 0 open Dependabot alerts; the legacy repository was deleted by the
  maintainer and the local backups were removed.

Older notes. Commit hashes below were remapped to the rewritten history on 2026-11-13; CI
run numbers from before that date belong to the legacy repository.

- The maintainer's repository `sepsiscope` is **private**; default branch `main`.
- First CI run is green: run `38003153138` (jobs `python` and `web`). After the four
  follow-up tasks, CI is green on `e78124d`: run `38004614423`, on `ubuntu-24.04`.
- Commit `ce32d9f` (`docs(ops): record repository state after first push`) is
  pushed.
- Branch protection: pending; rules in `docs/ops.md`, to apply when enabled.

## Pending tasks

- [x] **Task 1:** pushed `ce32d9f` and `d8b1dcd` after a clean privacy scan.
- [x] **Task 2:** `ignore` rule for `typescript` semver-major updates added and pushed
  (`3d75240`); PR #1 answered with `@dependabot ignore this major version`.
- [x] **Task 3:** runtime is Node 26 (`web/.nvmrc`, read by CI via `node-version-file`);
  `@types/node` moved from major 24 to 26.6.4 by merging PR #2 (`3c3cb0b`, authored by
  `dependabot[bot]`); local `npm ci`, lint and build pass.
- [x] **Task 4:** both CI jobs pinned to `runs-on: ubuntu-24.04` (89fe95d); upgrade note in
  `docs/ops.md`.

All four are done and pushed. Open pull requests: none (#1 closed, #2 merged).

## Phase 0 close-out

- [x] **Close-out 1:** fetched; local `main` was 0 behind `origin/main` (`a39e37a`) and
  contains the PR #2 merge `3c3cb0b`; no fast-forward needed.
- [x] **Close-out 2:** citations amended (dbbe18b, ADR 0011): Sepsis-3 Box 1 verified in the
  full text; row counts verified in Table 2 of `manuscript.pdf`, on printed page 11
  (an earlier note said page 10).
- [x] **Close-out 3:** `ignore` rule for `@types/node` semver-major updates added (6ebc9c3).
- [x] **Close-out 4:** state table in `docs/ops.md` refreshed (da6652a).
- [x] **Close-out 5:** Definition of Done re-run on 2026-10-10, all green: `uv sync --locked`;
  `doctor` PASS (OpenMP OK, telemetry off, nothing personal printed); pytest 48 passed, three
  runs in a row; ruff and mypy clean; `pre-commit run --all-files` clean; web `npm ci`, lint
  and build clean; pip-audit and npm audit report no vulnerabilities; full-history privacy
  scan (100 blobs, 28 commits) clean. No files changed.
- [x] **Close-out 6:** "Open items" section added; ten commits pushed after a clean privacy
  scan (`a39e37a..93bd3a5`); CI green on `93bd3a5`: run `38028938070` (jobs `python` and `web`).

## Phase 1 checklist

No models are trained in this phase.

- [x] **P1-1:** downloader (`sepsiscope data download`): S3 listing, resumable, size + MD5 checks, manifest summary. All 40,336 files downloaded and verified by size and MD5 (code c02625a, manifest summary 0ab9ff7).
- [x] **P1-2:** verify (`sepsiscope data verify`): recompute the fingerprint, fail loudly on mismatch. Real data: all 28 checks match (code 555723c).
- [x] **P1-3:** build (`sepsiscope data build`): raw Parquet with pid, hospital, t + 41 original columns. Real data: 1,552,210 rows, 40,336 patients, 14.7 MB, byte-identical on rebuild (6b50fbc, 52621f5).
- [x] **P1-4:** cleaning rules table, clean Parquet, `reports/data/cleaning_report.json`. Real data: 504 values set to missing; report and ADR 0014 (d9f44cd, 3d9498e).
- [x] **P1-5:** pandera schemas for raw and clean, validated in `data build`. Both Parquets validate in `data build` (6b50fbc).
- [x] **P1-6:** splits (`sepsiscope data splits`): 60/20/20 by patient, seed 42, stratified; ADR. Split files committed, septic rate preserved, ADR 0013 (fa36e3f, 26a8d29).
- [x] **P1-7:** data card (`docs/data_card.md`) (3cadabc).
- [x] **P1-8:** EDA notebook, figures, `docs/eda_findings.md`. Notebook runs on real data with 0 errors; six figures, byte-identical on re-run (244e805, f501b5d).
- [x] **P1-9:** vendor the official scorer into `third_party/physionet_eval/` with licence and example test (005f60c).
- [x] **P1-10:** tests (mocked HTTP, fixture fingerprint, cleaning, schema, splits, Parquet round-trip, `data` marker). 136 tests plus one real-data test; network blocked in tests (15216fe).
- [x] **P1-11:** qSOFA Box 4 citation added (22bb492, ADR 0012). `ruff format` counts
  Markdown files as well as Python files (it formats Python code blocks in Markdown), which
  explains the higher count; nothing unintended is included, no config change.
- [x] **P1-12:** close the build: full Definition of Done, no data in git, push after scan, CI. Definition of Done green (137 tests ×3, clean clone 136 passed and 1 skipped, ruff, mypy, pre-commit, web build, audits); full-history scan clean; no data in git; 27 commits pushed (`de3870b..aba6c3e`); CI green on `aba6c3e`: run `38070758706`.
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

Batch A (Milestone 3: causal features, baselines, metrics, evaluation), plan in
`docs/plan/batch-a.md`.
