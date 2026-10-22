# Changelog

Notable changes per phase. Dates are ISO 8601. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
- Commit `b4ac7f6` ("add cleaning rules table and pandera schemas") also contains
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
