# Batch A — Milestone 3: data and baselines

Status: **approved 2026-11-13, in progress** (Batch S is pushed and CI is green).
Same working mode as Batch S: one plan, one approval,
fast checks per step, a commit per step with `docs/internal/handoff.md` updated, the full gate at
the end, and a stop before the push.

## A0. Decisions to record as ADRs (approved)

1. **Modified NEWS2 (max 17) oxygen item.** Missing FiO2 means "no supplemental oxygen recorded" (0 points).
   Sensitivity analysis: carry FiO2 forward for up to 24 hours.
2. **Headline result = strict external validation.** The threshold comes from the source
   hospital's validation split. A secondary, clearly labelled "deployment adaptation"
   analysis resets the threshold from the target hospital's unlabelled scores, using only
   its calibration-split patients, and evaluates on its remaining patients.
3. **Deferral metrics** (built in Batch C): deferral rate, per-class coverage, and
   performance on the hours that were not deferred, on the unseen hospital.
4. **Tuning** (Batch B): Optuna TPE, seed 42, at most 50 trials, median pruner; objective =
   mean AUPRC over `GroupKFold(5)` on the training split only. Utility is reported, never
   optimised.

## A1. Causal hourly features

Per hospital, float32, written to the gitignored `data/processed/`:

- last value carried forward within the patient
- hours since each variable was last measured
- measurement counts so far
- 6-hour vital-sign trends
- shock index, BUN/creatinine ratio

`ICULOS`, `HospAdmTime`, `Unit1` and `Unit2` are excluded unless an ablation flag is set.
The feature list is saved as a tracked JSON schema (no data).

Tests: changing rows after hour t never changes features at or before t; excluded columns
are absent; output is deterministic.

## A2. Baselines

- **Modified NEWS2 (max 17):** no consciousness item, SpO2 Scale 1 only. Expected bands, to be verified
  against the official RCP NEWS2 chart and quoted before use:
  - respiration rate ≤8 / 9–11 / 12–20 / 21–24 / ≥25
  - SpO2 scale 1 ≤91 / 92–93 / 94–95 / ≥96; supplemental oxygen +2
  - systolic BP ≤90 / 91–100 / 101–110 / 111–219 / ≥220
  - pulse ≤40 / 41–50 / 51–90 / 91–110 / 111–130 / ≥131
  - temperature ≤35.0 / 35.1–36.0 / 36.1–38.0 / 38.1–39.0 / ≥39.1
- **SIRS:** Sepsis-3 Box 1 / Bone 1992, without the band-count criterion; PaCO2 < 32 mmHg
  as the respiratory alternative.
- **Modified qSOFA (max 2):** respiration rate ≥22, systolic BP ≤100 (both inclusive).
- **Logistic regression:** imputation and scaling fitted on the training split only, plus
  missing-value indicators.
- **Modified NEWS2 (max 17) as a probability:** logistic regression on the source hospital's training split.

## A3. Metrics library

Pure functions with hand-computed test fixtures:

- official normalised utility via the vendored scorer
- row-level AUROC and AUPRC
- tie-safe threshold for a 5 % alert budget; realised alert rate
- false alerts per 100 non-septic patient-days
- timely sensitivity in [onset − 12 h, onset] and median lead time; the 426 patients
  positive from row 0 reported separately
- ECE (10 quantile bins) plus reliability data
- vectorised patient-level bootstrap 95 % CIs (1,000 resamples, seed 42)
- decision curves (dcurves)

## A4. Evaluation command

`sepsiscope evaluate --model {news2,sirs,qsofa,lr} --direction {A2B,B2A}` and
`--all-baselines`:

- writes `reports/results/*.json` (numbers only, tracked) and metadata-free, reproducible
  PNG figures
- a re-run gives byte-identical results

## A5. Traceability

`docs/traceability.md`: protocol section → code module → test → result file.

## A6. Milestone 3 evidence report

Delivered as text, not as a file. Parts:

1. results table for both directions with CIs
2. feature summary
3. traceability summary
4. list of figures
5. deviations and decisions
6. run times and peak memory on the local machine
7. Batch B readiness
