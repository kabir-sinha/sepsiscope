# Batch B — Milestone 4: trained model

Status: **approved 2026-11-13 with amendments** (P1–P5, Q1–Q3 below). Decisions are recorded
in ADR 0022. Working mode as in Batch A: one commit per step with `docs/internal/handoff.md`
updated, fast checks per step, the full gate once at the end, then a stop before any
push. Pushes happen from the maintainer's own terminal.

Run times and memory are estimates for the local machine. They are measured in B1, and
any step more than 2× off its estimate is reported. Evaluation loads the source hospital
first, fits, frees it, then loads the target (one hospital at a time where possible).

No new dependency and no download is needed: LightGBM 4.7.0, Optuna 5.0.0, MLflow 3.18.0,
scikit-learn 1.9.1, FastAPI 0.143.0, uvicorn 0.54.0 and httpx 0.28.1 are already pinned.
Anything new needs the maintainer's approval first (P5).

## Order (Q1)

B0 → B1 → B6 → B2 (on the maintainer's "go") → B3 → B4 → B5 → B7 → gate → M4 evidence
report (text only).

## B0. Plan and ADR 0022

This file plus ADR 0022 (decisions 1–7 and Q2). One commit.

## B1. LightGBM model and `sepsiscope train`

- `sepsiscope train --model lgbm --direction {A2B,B2A}` trains on the source **training**
  split only. It saves to the ignored `models/lgbm_{direction}/`:
  - `model.txt`: LightGBM text format, never pickle (ADR 0004);
  - `model.json`: parameters, number of trees, data fingerprint and git commit hash;
  - `feature_schema.json`.
- Reproducibility: `deterministic=True`, `seed=42`, fixed `num_threads`,
  `force_col_wise=True`. No class weighting (ADR 0022). Until B2 finishes, LightGBM default
  parameters are used, with early stopping on an inner patient-grouped split of the
  training data.
- **P2:** the data fingerprint is a SHA-256 of the feature data contents, never paths,
  modification times or hostnames. A test whitelists the fields `model.json` may contain.
- Tests: save and reload give identical predictions; training twice gives byte-identical
  `model.txt`; the model text holds no paths; only training-split patients are used; the
  excluded columns are absent.
- Commit: `feat(models): B1 LightGBM model and sepsiscope train`.
- Estimated run: about 1–3 min per direction, about 2.5–3.5 GiB.

## B6. MLflow tracking and the logging filter (moved before tuning)

- Store: SQLite `mlflow.db` inside the ignored `mlruns/` folder. Telemetry stays off
  (`MLFLOW_DISABLE_TELEMETRY`, `DO_NOT_TRACK`, set in `_privacy.py`; `import sepsiscope`
  first). Never run `mlflow ui` or a tracking server.
- **P1:** override or remove every automatic tag that can hold personal information:
  `mlflow.user` (set to `sepsiscope`), `mlflow.source.name` (repository-relative path), and
  every `mlflow.source.git.*` tag that carries a URL (for example `repoURL`). A commit hash
  is allowed. Tag names are checked in the official MLflow 3.18 documentation before the
  code is written.
- Log parameters, metrics and the tuning summary only. **No artifacts.** Models stay in
  `models/`.
- If MLflow records an absolute path that cannot be avoided anywhere outside the local
  database, stop and ask the maintainer.
- `mlflow.db` and the Optuna journal are in `.gitignore` **and** in a pre-commit check that
  blocks committing them.
- Logging filter: rewrites the home directory to `~` and repository paths to relative paths
  in log files and in CLI error output.
- Privacy tests scan every tag, parameter, metric and any exported summary for the home
  path, username, hostname and GitHub account name; the filter rewrites a planted path.
- Commit: `feat(tracking): B6 MLflow without personal paths; logging filter`.
- Estimated run: seconds.

## B2. Optuna tuning (ADR 0021), started only on the maintainer's "go"

- TPE sampler, seed 42, at most 50 trials, median pruner, `n_jobs=1`.
- Objective: mean row-level AUPRC over `GroupKFold(5)`, grouped by patient, on the source
  **training split only**; the running mean is reported to the pruner after each fold.
  Utility is never optimised.
- Search space, fixed before running: `num_leaves` 15–255 (log), `learning_rate` 0.01–0.2
  (log), `min_child_samples` 20–500 (log), `feature_fraction` 0.5–1.0, `bagging_fraction`
  0.5–1.0 with `bagging_freq` 1, `lambda_l1` and `lambda_l2` 1e-3–10 (log); the number of
  trees by early stopping inside each fold.
- Final model: fitted on the full training split with the best parameters; the number of
  trees is the median of the folds' best rounds.
- Storage: Optuna journal file storage in the ignored `mlruns/` folder, so a run can resume
  after a sleep or a crash.
- Running it: only after the maintainer says "go", with the local machine on power. Ask the
  maintainer before wrapping it in macOS's built-in `caffeinate -i`. If the measured fit
  time projects **more than 6 h per direction**, stop and ask.
- Output: `reports/tuning/lgbm_{direction}.json` (tracked): every trial's parameters, fold
  AUPRCs and pruned flag; numbers only.
- Tests: the folds never share a patient; validation and calibration rows never reach the
  objective; a 3-trial study on synthetic data is reproducible.
- Commits: `feat(models): B2 Optuna tuning per ADR 0021`, `chore(results): tuned parameters`.
- Estimated run: about 1–3 h per direction in the background, about 3 GiB.

## B3. Calibration and per-alert explanations

- Calibrators fitted on the source **calibration** split only: Platt (headline) and
  isotonic (pre-specified sensitivity analysis), from scikit-learn, saved as JSON.
- Explanations: LightGBM's built-in `pred_contrib=True`, computed in chunks, on raw
  log-odds. For an alerting hour: the top features by absolute contribution plus the base
  value. Platt is monotone, so it keeps the ordering of the raw scores.
- Tracked output: aggregate numbers only (mean absolute contribution per feature among
  alerting hours, per direction). Patient-level predictions and explanations are never
  tracked (P3).
- Tests: contributions plus bias equal the raw score to within 1e-9 for every hour; the
  calibrators are monotone and survive a JSON round trip; no target-hospital row reaches a
  calibrator.
- Commits: `feat(models): B3 calibration`, `feat(trust): B3 per-alert explanations from
  pred_contrib`.
- Estimated run: about 1–2 min per direction, at most about 1 GiB extra.

## B4. Evaluate LightGBM against the 4 baselines

- `sepsiscope evaluate --model lgbm --direction …` and `--all-models`, on the unchanged
  Batch A harness: threshold from the source validation split (5 % budget, tie-safe),
  strict external validation as the headline, deployment adaptation as the secondary
  analysis, 1,000 patient-level bootstrap resamples with seed 42.
- **Q3:** the same outputs as Batch A: subgroups, patients positive from their first hour,
  ECE and reliability, decision curves, deployment adaptation; for the uncalibrated model,
  Platt (headline) and isotonic (sensitivity).
- Paired bootstrap 95 % CIs for the difference **LightGBM minus each baseline** in utility,
  AUROC and AUPRC (same resamples).
- Pre-registered success criterion (ADR 0022): LightGBM beats the logistic regression only
  if the paired 95 % CI for the utility difference excludes 0, in each direction.
- Commits: `feat(evaluation): B4 LightGBM in evaluate with paired difference CIs`,
  `chore(results): B4 LightGBM results`.
- Estimated run: about 5–8 min for both directions, about 4 GiB.

## B5. Ablations and drift analysis

| # | Ablation | Source |
|---|---|---|
| 1 | Without the measurement-process features (tests the B→A alert drift) | protocol §8.1 |
| 2 | Vitals only: 8 vitals' last values, shock index, their 6-hour trends and their measurement-process features; no labs, no demographics | protocol §8.2 |
| 3 | ICU-time columns added back: ICULOS, HospAdmTime, Unit1, Unit2 | protocol §8.3 |
| 4 | Unit1 and Unit2 only, added back | ADR 0015 |

- Each ablation reuses the main model's tuned parameters (no re-tuning; a recorded
  limitation, ADR 0022), both directions, strict and adapted, with CIs.
- Drift: realised target alert rate against the budget, and per-feature Jensen-Shannon
  divergence between the hospitals, summarised by feature group; numbers only.
- The `icu_time` switch is split into `icu_time` and `unit_columns`; the extra columns go to
  a separate ignored `features_{H}_ablation.parquet`, and the main feature files stay
  unchanged.
- Commits: `feat(features): B5 ablation feature sets`, `chore(results): B5 ablations`.
- Estimated run: about 25–40 min, about 3–4 GiB.

## B7. Demo: API and dashboard (P4)

- FastAPI bound to **127.0.0.1 only** (host typed as `Literal["127.0.0.1"]`), CORS limited
  to localhost origins, no external calls.
- Dashboard (the existing Vite react-ts app): patient timeline, hourly risk, alerts, and the
  top 5 reasons with plain-English labels.
- Data: a few deterministic held-out target-hospital patients, processed locally; demo
  outputs live in an ignored folder; nothing patient-level is tracked.
- Testing here: FastAPI `TestClient` and `vite build` only. No sandbox change is requested
  (no `allowLocalBinding`). The maintainer starts the API and the web dev server from
  their own terminal with commands given in the report.
- Commits: `feat(api): B7 local demo API`, `feat(web): B7 demo dashboard`.

## Gate (as Batch A, plus API tests and a demo smoke test)

`uv sync --locked`, `doctor`, the full test suite once (the Unix-socket test is covered by
CI), ruff, format, mypy, pre-commit on all files, `pip-audit --skip-editable`, `npm audit`,
web build; a byte-identical re-run of `train`, `evaluate --all-models` and the ablations from
the saved best parameters, plus the 3-trial synthetic reproducibility test (tuning itself
is not repeated; a recorded limitation); API tests and a demo smoke test; the double
privacy check (strict `privacy-audit`, gitleaks, independent history scan). Then the M4
evidence report as text, and ask the maintainer before they push.

## Privacy (P1–P5, all steps)

- **P1** MLflow tags overridden or removed as above; no artifacts; no UI or server;
  `mlflow.db` and the Optuna journal ignored and blocked by pre-commit; privacy tests scan
  for the home path, username, hostname and GitHub account name.
- **P2** Data fingerprint = SHA-256 of contents only; `model.json` fields whitelisted.
- **P3** The "no patient IDs in tracked files" test covers the tuning JSON, the
  explanation summary, ablation results and anything from the demo.
- **P4** Demo on 127.0.0.1, CORS localhost only, no external calls, outputs ignored.
- **P5** No new dependencies or downloads without the maintainer's approval.
