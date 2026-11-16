# Changelog

Notable changes per phase. Dates are ISO 8601. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Public readiness, Batch E (2026-11-16)

### Added
- `LICENSE` (Apache-2.0, official text) and `NOTICE` for the code, CC BY 4.0 for
  documentation, figures and results, and `CITATION.cff` (ADR 0026, supersedes ADR 0003).
- `sepsiscope analyses alert-quality`: alert precision (PPV), NPV, lift and per-patient
  numbers at the 5 % budget for LightGBM, LR and NEWS2 (`alert_quality_*.json`; a
  reproduce step; byte-check manifest now 91 files).
- "Start here" index of the eight key ADRs.

### Changed
- README rewritten as a project showcase (results table, Mermaid diagram, quick start,
  reproduce, citation, licence).
- Internal working notes (handoff, operations, plans, learning notes) and the AI-assistant
  rules are kept out of the public repository.
- Doc fixes: `privacy.md` states the ADR 0025 byline exception; repo map and handoff
  heading updated.

### Removed
- Dead code (`report_as_dict`, `relative_source`, `stepDecimals`) and the Vite starter
  assets.

## Batch D, demo polish (2026-11-15 to 2026-11-16, tag `v1.0.1`)

### Added
- One exact "Built by" + first-name byline on the demo header, allowed by the privacy
  rules in that file only (ADR 0025, `51f02c3`).
- Results tab section "Robustness checks (Milestone 5)", built from the committed
  band, deferral and budget files (`21c8162`).

### Fixed
- Verdict for alerts before and after the early-warning window but not in it
  (`early_and_late`; `c995dce`).
- In-chart labels placed clear of lines, alert dots and each other on every chart
  (`4d73ae8`, `2b35a1a`).
- Phone layout at 375 px and a meta description (`988308e`); verdict badges wrap inside
  the patient cards (`95fda3e`).

## Milestone 5, Batch C: robustness checks and reporting (2026-11-14 to 2026-11-15, tag `v1.0.0-m5`)

### Added
- Batch C plan and ADR 0024 with pass/fail criteria fixed before any result (`e3da7ef`,
  `e60da3e`).
- `sepsiscope analyses bands`: metrics within ICU-stay bands (`ba4fc65`, `718b2ae`;
  results `e3e21c7`).
- `sepsiscope analyses deferral`: class-conditional conformal deferral (`f1f340a`,
  `2492235`; results `6c19b25`).
- `sepsiscope analyses budgets`: 2/5/10 % alert budgets, lead-time distribution and
  subgroup CIs (`7bf9e1e`, `8a97251`; results `b899d92`).
- `sepsiscope reproduce`: every result from the verified dataset in one command
  (`4c74d4c`); byte-identical re-run check (`0f5c622`) with a committed manifest
  (`77399f9`).
- Model card, datasheet and TRIPOD+AI checklist (`4b9f236`, `1b1fdfa`, `216bda0`).
- In-repository privacy scan helpers and their positive control (`7d0e158`).

### Fixed
- Demo: threshold label clear of the onset and selected-hour lines; LightGBM headline cards
  match the others (`154567d`, `a5d29bc`).

## Milestone 4, Batch B: model, trust layer and demo (2026-11-13 to 2026-11-14)

### Added
- Batch B plan and ADR 0022 (`31bb0c5`).
- LightGBM model and `sepsiscope train` (`559029c`); Optuna tuning per ADR 0021 with the
  tuned parameters committed (`572ae8e`, `c96d96f`).
- Calibration (Platt headline, isotonic sensitivity) and per-alert explanations
  (`5f001c4`, `863ce7d`).
- LightGBM in `sepsiscope evaluate` with paired difference CIs; results and explanation
  summaries (`56fa8e6`, `be8c557`).
- Ablation feature sets, ablation runner and hospital drift summary (`22bc612`,
  `b9d2ac4`); post-hoc exploratory analysis (`103911e`).
- MLflow tracking without personal paths (`12af436`).
- Local demo: data, API on 127.0.0.1 with security headers, verdict rules, what-if
  budgets, and the React dashboard with replay, reasons panel, results, dark mode and
  self-hosted IBM Plex fonts (`d18b415` to `d858e7a`); WCAG 2.2 contrast check
  (`15c9173`).

### Changed
- No personal name in tracked files (ADR 0023, `1d3362b`); commit-name rule (`cce547d`);
  guard blocks `models/` and `data/demo/` (`386b271`).

### Fixed
- opentelemetry-api/sdk 1.45.2 and semantic-conventions 0.66b2 (CVE-2026-126360,
  `ebe8e2f`); 500 errors keep the security headers (`f2b480c`); independent scan fixes
  (`11f98b6`, `807fdaa`).

## Milestone 3, Batch A: features, baselines and evaluation (2026-11-13)

### Added
- ADRs 0018-0021: NEWS2 oxygen item, strict external validation as the headline,
  deferral metrics, tuning protocol (`49e21a8`).
- Causal hourly features with a tracked feature schema (`3dafd89`).
- Baselines: modified NEWS2 (max 17), SIRS, modified qSOFA (max 2) and logistic regression
  (`44f1e1c`, `ca676cd`).
- Metrics library with hand-computed fixtures (`8fe484e`).
- `sepsiscope evaluate`: strict external validation, deployment adaptation and result
  files (`a45a02e`).
- Traceability from the protocol to code, tests and results (`78e90f8`).

## Security lockdown (2026-11-13)

### Changed
- Toolchain minimums: uv 0.13.4, Python 3.13.18, Node 26.13.1; CI prints and enforces them
  (ADR 0017).
- Security upgrades: pillow 13.0.0, mlflow 3.18.0, certifi 2026.10.23, virtualenv 21.15.6,
  filelock 4.2.10, gitpython 3.2.1, pyasn1 0.6.5, soupsieve 4.1, tornado 6.6.1; web:
  react and react-dom 19.3.1, vite 8.3.5, oxlint 1.89.0, @types/node 26.6.5; setup-uv
  v10.3.3; `uv_build <0.14`. EDA figures are byte-identical after the upgrade.
- `sepsiscope doctor` prints only the OS family and CPU architecture.
- `privacy-audit` is strict by default (`--no-strict` for the lenient view; `3564502`).

### Added
- gitleaks: pre-commit hook and a checksum-verified CI job over the full history.
- Milestone 3 spec (internal plan, queued) and ADR 0017.

## Privacy hardening (2026-10-22)

### Added
- `src/sepsiscope/audit/`: one set of privacy rules for the pre-commit guard, the git
  hooks, CI and the new `sepsiscope privacy-audit` command (masked output) (ADR 0016).
- New rules: Linux and Windows home paths, account-tier wording, enrollment-ID shapes,
  notebook outputs and metadata, and an optional gitignored local denylist.
- `commit-msg` hook (no AI trailers, nothing personal) and `pre-push` hook (`+0000`
  offsets, allowed identities); CI checks every pushed commit the same way.
- ADR 0016.

### Changed
- All commits are made with `TZ=UTC` from 2026-10-22 on.
- `CLAUDE.md` holds project-neutral rules only; personal notes moved to a gitignored file.
- Docs reworded to be neutral and OS-neutral; account-tier wording, other-project
  references and machine-specific notes removed. ADRs 0001, 0003, 0006 and 0008 amended
  (privacy wording only; decisions unchanged).
- CI runs the privacy guard after installing the package and checks out full history.
- `.gitignore` covers local-only files, MLflow artifacts, SQLite stores, logs and web coverage.

## Phase 1 — Data (2026-10-10)

### Added
- `sepsiscope data download`: hardened, resumable downloader for the official PhysioNet S3
  bucket (single allowed host, HTTPS only, no redirects or credentials, `defusedxml`
  parsing, 1 MB response cap, path-containment check, size and MD5-vs-ETag verification,
  atomic writes). All 40,336 files downloaded and verified; summary in `docs/data_manifest.md`.
- `sepsiscope data verify`: recomputes the dataset fingerprint (28 checks); all match.
- `sepsiscope data build`: raw and clean Parquet tables, both validated by pandera schemas,
  plus `reports/data/cleaning_report.json` (counts only).
- Cleaning rules table with conservative plausibility bounds (ADR 0014): 504 values set to
  missing, raw values never overwritten.
- `sepsiscope data splits`: stratified 60/20/20 patient-level splits, seed 42, committed in
  `splits/` (ADR 0013).
- EDA functions, six reproducible metadata-free figures, `notebooks/01_eda.ipynb`,
  `docs/eda_findings.md` and `docs/data_card.md`.
- The official challenge scorer vendored unmodified in `third_party/physionet_eval/`
  (BSD-2-Clause) with a hash check and its documented example as a test.
- Test safety net: no test can resolve a hostname or open a network connection.
- Privacy hook: blocks PNG files that carry text, EXIF or time metadata.
- Dependencies: `defusedxml` (runtime, already locked transitively), `types-defusedxml` and
  `pandas-stubs` (dev).

### Changed
- `docs/protocol.md`: citations made precise (Sepsis-3 Box 1 and Box 4, manuscript Table 2;
  ADRs 0011 and 0012). No method changed.
- Config: new `paths.splits_dir`.

### Notes
- Commit `6b50fbc` ("add cleaning rules table and pandera schemas") also contains
  `src/sepsiscope/data/build.py`; its title under-describes it. History was not rewritten.
- ADR 0015 records the measured hospital-marker strength (unit columns 58.1 %, `ICULOS`
  start 65.0 %, baseline 50.4 %) and schedules a unit-columns-only ablation for Phase 2.

### Fixed
- Cleaning bounds are compared in the column's own float type, so room-air FiO2 values
  (0.21 stored as float32) are kept.

## Phase 0 — Foundation (2026-10-10)

### Added
- Project skeleton with uv, exact pins and a hashed lockfile; telemetry opt-outs; typed
  config; CLI with `doctor`; OpenMP smoke test; pre-commit hooks with a privacy guard;
  CI on pinned actions and runner; Vite scaffold with a research banner; frozen evaluation
  protocol; ADRs 0001 to 0010; private GitHub repository with Dependabot.
