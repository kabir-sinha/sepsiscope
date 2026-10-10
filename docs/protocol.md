# SepsiScope evaluation protocol (frozen)

**Status:** frozen on 2026-10-10, before any data was downloaded or any model trained.
Citations were made more precise on 2026-10-10 (ADR 0011); no method changed.
Any change after this date needs a new ADR in `docs/decisions/` that explains why, and
results must be reported under both the old and the new protocol. This exists so results
cannot be cherry-picked after seeing them.

## 1. Dataset

- **Source:** PhysioNet/Computing in Cardiology Challenge 2019, training set v1.0.0
  ([PhysioNet page](https://physionet.org/content/challenge-2019/1.0.0/),
  DOI [10.13026/v64v-d857](https://doi.org/10.13026/v64v-d857)).
- **Licence:** [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/).
- **Paper:** Reyna MA et al. *Early Prediction of Sepsis From Clinical Data: The
  PhysioNet/Computing in Cardiology Challenge 2019.* Critical Care Medicine 2020;48(2):210-217.
  [doi:10.1097/CCM.0000000000004145](https://doi.org/10.1097/CCM.0000000000004145)
  ([open access on PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC6964870/)).
- **Hospital systems** (from the paper): **A** = Beth Israel Deaconess Medical Center,
  **B** = Emory University Hospital. (C was the hidden test set and is not public.)

### Expected fingerprint (checked in Phase 1; a mismatch stops the pipeline)

|                 | A       | B       |
|-----------------|---------|---------|
| Files (patients)| 20,336  | 20,000  |
| Rows (hours)    | 790,215 | 761,995 |
| Septic patients | 1,790   | 1,142   |
| Positive rows   | 17,136  | 10,780  |
| Max stay        | 336 h   | 336 h   |

The file counts match the PhysioNet page. The challenge manuscript reports 739,663 (A) /
684,508 (B) rows: Reyna MA, et al., Critical Care Medicine 2020 challenge manuscript,
Table 2 (printed page 11 of
[`manuscript.pdf`](https://github.com/physionetchallenges/evaluation-2019/blob/master/manuscript.pdf)
in the official evaluation repository). The actual files contain 790,215 / 761,995 rows;
**the files are authoritative**, and Phase 1 records the counts it actually finds.

## 2. Label

From the PhysioNet page: for septic patients `SepsisLabel = 1` if `t >= t_sepsis - 6`,
else 0; for non-septic patients it is always 0. Labels are monotone (once 1, they stay 1),
and Phase 1 asserts this per patient.

- Onset used for event metrics: `t_onset = (first row with SepsisLabel = 1) + 6 h`.
- **Special case:** septic patients who are positive from row 0 (expected: 426) have an
  onset that cannot be pinned down. They are reported **separately** and also included
  in the main row-level metrics.

## 3. Features (invariants)

- At hour `t`, features use **only rows with hour <= t** (no look-ahead).
- **Excluded from all main models:** `ICULOS`, `HospAdmTime`, `Unit1`, `Unit2`. They encode
  hospital and ICU process rather than physiology. They are added back only in the
  ablation below.
- Every saved model ships with its `feature_schema.json`.

## 4. Splits

- **External validation in both directions:** train on A, test on B; train on B, test on A.
  The test hospital is never used for fitting, tuning, thresholding or calibration.
- **Inside the training hospital:** split **by patient** into 60 % train / 20 % validation /
  20 % calibration, seed 42. No patient appears in two parts.
- **Hyperparameter tuning:** `GroupKFold(n_splits=5)` grouped by patient, inside the 60 %
  train part only
  ([scikit-learn GroupKFold](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupKFold.html)).

## 5. Metrics (all reported on the external test hospital)

| Metric | Definition |
|---|---|
| AUROC, AUPRC | row level |
| **Official normalized utility** (reference metric) | the official `evaluate_sepsis_score.py` from [physionetchallenges/evaluation-2019](https://github.com/physionetchallenges/evaluation-2019), unmodified (vendored in `third_party/` with its BSD-2-Clause licence). Parameters in that file: `dt_early=-12`, `dt_optimal=-6`, `dt_late=3`, `max_u_tp=1`, `min_u_fn=-2`, `u_fp=-0.05`, `u_tn=0`; normalized as (U - U_inaction) / (U_best - U_inaction) |
| Timely sensitivity | share of septic patients with >= 1 alert in `[t_onset - 12 h, t_onset]` |
| Median lead time | median of `t_onset - first timely alert`, among detected patients |
| False alerts | alerts per 100 non-septic patient-days |
| Calibration | reliability plot (10 quantile bins) and expected calibration error (ECE) |
| Net benefit | decision curve analysis ([Vickers & Elkin 2006](https://doi.org/10.1177/0272989X06295361)) via [dcurves](https://pypi.org/project/dcurves/), against treat-all, treat-none and NEWS2. NEWS2 is turned into a probability by a logistic regression fitted on the **training** hospital |
| Uncertainty | 95 % CIs by **patient-level** bootstrap, 1,000 resamples, seed 42 |
| Subgroups | sex (`Gender`), age < 65 vs >= 65 |

## 6. Thresholds and alarm budget

- The operating threshold is chosen on the **validation** split only, so that the alert
  rate is within the alarm budget (`alarm_budget = 0.05` of patient-hours, see
  `configs/default.yaml`).
- The realised alert rate on the test hospital is always reported next to the budget.

## 7. Baselines

1. **Modified NEWS2:** [RCP NEWS2](https://www.rcp.ac.uk/improving-care/resources/national-early-warning-score-news-2/)
   Chart 1 with SpO2 Scale 1. There is **no consciousness item** (not in the data), so
   the maximum is 17. "On oxygen" is `FiO2 > 0.21`. Cut points are applied
   upper-inclusive: a value belongs to the band whose upper limit it does not exceed
   (for example, a temperature of 35.05 °C scores as 35.1-36.0).
2. **SIRS** (0-4 criteria): temperature > 38 or < 36 °C; heart rate > 90/min;
   respiratory rate > 20/min or PaCO2 < 32 mmHg; WBC > 12 or < 4 ×10³/µL. The
   immature-bands criterion is not used (not in the data). Source: Singer M, et al. "The
   Third International Consensus Definitions for Sepsis and Septic Shock (Sepsis-3)."
   JAMA 2016;315(8):801-810, **Box 1**
   ([doi:10.1001/jama.2016.0287](https://doi.org/10.1001/jama.2016.0287)). Original SIRS
   source: [Bone et al. 1992](https://doi.org/10.1378/chest.101.6.1644).
3. **Modified qSOFA** (0-2): respiratory rate >= 22/min; systolic BP <= 100 mmHg. Altered
   mentation is not in the data, so the maximum is 2
   ([Seymour et al. 2016](https://doi.org/10.1001/jama.2016.0288)).
4. **Logistic regression** on the same features as the main model.

## 8. Ablations

1. Without measurement-process features (missingness indicators, time since last measurement).
2. Vitals only.
3. ICU-time features (`ICULOS`, `HospAdmTime`, `Unit1`, `Unit2`) **added back**, to show
   how much they inflate results.

## 9. Reporting

Results follow [TRIPOD+AI](https://doi.org/10.1136/bmj-2023-078378) (see
`docs/tripod_ai.md`) and are summarised in `docs/model_card.md`.
