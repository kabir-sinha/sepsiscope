# CLAUDE.md — SepsiScope project memory

Explainable, alarm-budgeted sepsis early warning (PhysioNet/CinC 2019). Every change must
be explainable line by line: say what you do and why, in plain language.
Personal, machine-specific notes live in the gitignored `CLAUDE.local.md`.

## Priority 1 — privacy and security (overrides everything)
- Read-only, narrowly scoped inspection. Never print env vars wholesale, shell profiles,
  SSH/cloud credentials, gh hosts, OS keychains, browser data, serials or files outside
  this repository.
- Nothing leaves the local machine without maintainer approval: no push, no remote
  creation, no uploads, no sign-ins, no API calls with the maintainer's tokens. GitHub
  settings changes are written up as click-by-click steps for the maintainer.
- Installs only from Homebrew / PyPI via uv / npm, exact names, shown and approved first.
  No sudo, no `curl | sh`, no `brew upgrade` / `brew cleanup`, no global changes.
- Only work inside this repository. No `rm -rf` outside it.
- Never pickle/joblib; `yaml.safe_load` only.
- No personal data in the repository: no usernames, home paths, hostnames, device or
  account details, and no email except `222482936+kabir-sinha@users.noreply.github.com`.
  No personal name in any tracked file (ADR 0023): the copyright and the pyproject author
  are "SepsiScope contributors"; the name is only the git author (commit metadata).
  One exception (ADR 0025): the exact "Built by" + first-name line in the demo header
  (`web/src/App.tsx`), built at run time by the rules from the local file.
- Network services bind to 127.0.0.1 only. Telemetry off (see `_privacy.py`).
- Anything privacy-related that is not covered here: stop and ask.

## Priority 2 — reuse before install
Reuse the installed Python 3.13, Node 26, git and gh. Added for this project: uv 0.12.24
and, on macOS, libomp (keg-only).

## Working rules (maintainer approval required)
Plan first and wait for maintainer approval · verify versions/flags live from official
sources · prove each step with output · critique loop at the end · small conventional
commits, diffs shown before committing, never push without approval · propose
enhancements before adding them · every git command runs with `TZ=UTC`.
Commits: author = noreply address, **no `Co-Authored-By` AI trailer** (the commit-msg hook
rejects it); AI help is disclosed in `docs/ai_assistance.md` and the README instead.

## Invariants
- Patient-level splits only (external A→B and B→A; 60/20/20 inside, seed 42).
- Features at hour t use only hours <= t.
- `feature_schema.json` saved with every model.
- Models as LightGBM text + JSON, never pickle.
- API on 127.0.0.1.
- The official normalized utility (unmodified `evaluate_sepsis_score.py`) is the reference metric.
- No ICULOS / HospAdmTime / Unit1 / Unit2 features (ablation only).
- Telemetry off: `import sepsiscope` before anything that imports mlflow.
- All logic in `src/sepsiscope/`; scripts and notebooks only call it.
- `docs/protocol.md` is frozen; changes need a new ADR.
- Raw values are never overwritten; the dataset and Parquets never enter git.
- Tests never touch the network; only `sepsiscope data download` does, to one host.

## Decisions (see docs/decisions/)
Python 3.13 via uv (`<3.14` for dcurves) · uv `required-version >=0.12.24,<0.13` ·
exact pins + hashed `uv.lock` · pyarrow 25.0.1 (mlflow needs <26) · ruff 0.16.10 ·
no torch / polars / MAPIE · Vite react-ts template pins untouched (TS ~6.0) ·
code Apache-2.0, docs/figures/results CC BY 4.0 (ADR 0026, supersedes 0003) · public demo later
on a Hugging Face static Space · splits stratified by septic flag (ADR 0013) ·
cleaning = out-of-bound values to NaN, never clip or convert units (ADR 0014) ·
Age 90+ is coded 100 by the dataset and stays uncapped.

## Repo map
```
src/sepsiscope/   _privacy.py (imported first) · config.py · cli.py · _smoke.py · logscrub.py ·
                  tracking.py · repro.py (byte check) · reproduce.py (one-command re-run)
                  audit/: rules · denylist · notebook · gitchecks · hooks · history · mask
                  data/: download · io · fingerprint · build · clean · schema · splits ·
                         pipeline · eda · figures
                  features/: causal · pipeline
                  models/: baselines · lgbm · calibration · tuning · pipeline
                  evaluation/: metrics · run · figures · ablation · exploratory · bands ·
                               deferral · budgets
                  trust/: conformal · explain        api/: app · demo · verdict · whatif
configs/          default.yaml (relative paths, seed, alarm budget, label horizon, switches)
tests/            tests for every package area, plus privacy, network guard, README,
                  TRIPOD+AI, attribution and web-layout guards
scripts/          privacy_guard.py (pre-commit hook) · privacy_pass.sh · deep_scan.py ·
                  independent_scan.sh · api_probe.py · byte_check.py · contrast_check.py ·
                  measure.py
docs/             protocol, data_card, datasheet, data_manifest, eda_findings, model_card,
                  tripod_ai, traceability, privacy, ai_assistance, decisions/
docs/internal/    CLAUDE.md (these rules), handoff, ops, plan/, learning/
splits/           hospital_A.json, hospital_B.json (patient IDs; committed)
reports/          results/ (aggregate JSON) · figures/ (PNGs, no metadata) · data/ ·
                  features/ · tuning/ · manifest_c6.json (byte-check reference)
notebooks/        01_eda.ipynb (calls the package only; outputs stripped)
web/              React + TypeScript demo (Vite): replay, explanations, results
third_party/      physionet_eval/ (official scorer, unmodified, BSD-2-Clause)
data/ models/ mlruns/   git-ignored
```

## Commands
```
uv sync --locked --all-extras        # install exactly the lockfile
uv run sepsiscope doctor             # environment + OpenMP + telemetry check
uv run pytest                        # tests (add -m "not data" to skip the real-data test)
uv run sepsiscope data download      # official S3 bucket, resumable, verifies size + MD5
uv run sepsiscope data verify        # fingerprint, 28 checks, fails on mismatch
uv run sepsiscope data build         # raw + clean Parquet, schemas, cleaning report
uv run sepsiscope data splits        # stratified 60/20/20 patient splits
uv run ruff check . && uv run ruff format --check . && uv run mypy src
uv run pre-commit install            # pre-commit, commit-msg and pre-push hooks
uv run pre-commit run --all-files    # all hooks incl. privacy guard
uv run sepsiscope privacy-audit      # strict: tree + full history + offsets, masked output
cd web && npm ci && npm run lint && npm run build
```
