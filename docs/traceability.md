# Traceability: protocol → code → test → result

Every rule in the frozen protocol (`docs/protocol.md`) and every Batch A decision, with the
code that implements it, the test that checks it, and where its result is written. Result
files under `reports/results/` hold numbers only (no patient IDs) and are byte-identical on
a re-run of `uv run sepsiscope evaluate --all-baselines`.

| Protocol / ADR | Rule | Code | Test | Result |
|---|---|---|---|---|
| §1 | Dataset fingerprint (files, rows, septic, max stay) | `data/fingerprint.py` | `tests/test_fingerprint.py` | `sepsiscope data verify` output |
| §2 | Label as published; onset = first positive row + 6 h | `evaluation/metrics.py` (`patient_events`, `ONSET_OFFSET_HOURS`) | `tests/test_metrics.py::test_event_metrics_by_hand` | `*_A2B.json`, `*_B2A.json` → `septic_patients` |
| §2 | Patients positive from row 0 reported separately | `evaluation/metrics.py` (`event_metrics`, `row0_*`) | `tests/test_metrics.py::test_event_metrics_by_hand` | `septic_from_row_zero`, `row0_timely_sensitivity` |
| §3 | Features at hour t use only hours ≤ t | `features/causal.py` | `tests/test_features.py::test_features_never_look_ahead` | `data/processed/features_{A,B}.parquet` (ignored) |
| §3 | No ICULOS / HospAdmTime / Unit1 / Unit2 in main models | `features/causal.py` (`icu_time` switch) | `tests/test_features.py::test_excluded_columns_absent_unless_ablation` | `reports/features/feature_schema.json` |
| §3 | `feature_schema.json` with every model | `evaluation/run.py` (`save_logistic`) | `tests/test_evaluate.py::test_evaluate_is_complete_reproducible_and_has_no_ids` | `models/baselines/lr_*/` (ignored) |
| §4 | External validation both ways; target never used for fitting or thresholds | `evaluation/run.py` (`DIRECTIONS`, `evaluate_model`) | `tests/test_evaluate.py::test_strict_threshold_comes_from_source_validation` | `strict_external` block |
| §4 | 60/20/20 patient splits, seed 42 (ADR 0013) | `data/splits.py` | `tests/test_splits.py` | `splits/hospital_{A,B}.json` |
| §5 | Row-level AUROC, AUPRC | `evaluation/metrics.py` (`Ranking`) | `tests/test_metrics.py::test_ranking_matches_sklearn_with_ties_and_weights` | `point.auroc`, `point.auprc` |
| §5 | Official normalised utility, unmodified scorer | `evaluation/metrics.py` (`utility_parts`, vendored `compute_prediction_utility`) | `tests/test_metrics.py::test_normalized_utility_equals_official_evaluate`, `tests/test_official_scorer.py` | `point.utility` |
| §5 | Timely sensitivity, median lead time | `evaluation/metrics.py` (`event_metrics`) | `tests/test_metrics.py::test_event_metrics_by_hand` | `point.timely_sensitivity`, `point.median_lead_hours` |
| §5 | False alerts per 100 non-septic patient-days | `evaluation/metrics.py` (`event_metrics`) | `tests/test_metrics.py::test_event_metrics_by_hand` | `point.false_alerts_per_100_patient_days` |
| §5 | Reliability (10 quantile bins) and ECE | `evaluation/metrics.py` (`reliability`, `ece`) | `tests/test_metrics.py::test_ece_and_reliability_by_hand` | `ece`, `reliability`; `reports/figures/results/reliability_*.png` |
| §5 | Decision curves via dcurves vs treat-all / treat-none / modified NEWS2 (max 17) | `evaluation/metrics.py` (`decision_curve`), `evaluation/figures.py` | `tests/test_metrics.py::test_decision_curve_has_reference_strategies` | `decision_curve_*.json`, `reports/figures/results/decision_curve_*.png` |
| §5 | Patient-level bootstrap 95 % CIs, 1,000 resamples, seed 42 | `evaluation/metrics.py` (`bootstrap_weights`, `bootstrap_ci`) | `tests/test_metrics.py::test_bootstrap_is_seeded_and_patient_level`, `test_utility_weights_equal_duplicated_patients` | `ci95` blocks |
| §5 | Subgroups: sex, age < 65 / ≥ 65 | `evaluation/run.py` (`_subgroups`) | `tests/test_evaluate.py` (runs it) | `strict_external.subgroups` |
| §6 | Threshold on the validation split within the 5 % budget; realised rate reported | `evaluation/metrics.py` (`budget_threshold`), `evaluation/run.py` | `tests/test_metrics.py::test_budget_threshold_never_splits_ties` | `threshold`, `source_validation_alert_rate`, `point.alert_rate` |
| §7.1, ADR 0018 | Modified NEWS2 (max 17): Chart 1, SpO2 Scale 1, no consciousness item; missing FiO2 = 0; 24 h sensitivity | `models/baselines.py` (`news2`, `on_oxygen`) | `tests/test_baselines.py` (band edges, oxygen rule) | `news2_*.json`, `sensitivity_fio2_carry_24h` |
| §7.2 | SIRS (max 4), all criteria strict; no band criterion; PaCO2 < 32 alternative | `models/baselines.py` (`sirs`) | `tests/test_baselines.py::test_sirs_criteria` | `sirs_*.json` |
| §7.3 | Modified qSOFA (max 2): RR ≥ 22, SBP ≤ 100 (inclusive) | `models/baselines.py` (`qsofa`) | `tests/test_baselines.py::test_qsofa_criteria` | `qsofa_*.json` |
| §7.4 | Logistic regression; imputation and scaling fitted on train only | `models/baselines.py` (`make_logistic`, `LogisticJSON`) | `tests/test_baselines.py::test_imputation_uses_training_rows_only`, `test_logistic_json_matches_sklearn_and_round_trips` | `lr_*.json` |
| §5 | Modified NEWS2 (max 17) as a probability, fitted on the training hospital | `models/baselines.py` (`fit_news2_probability`) | `tests/test_baselines.py::test_news2_probability_is_increasing` | `news2_*.json` → `fitted.news2_probability` |
| ADR 0019 | Deployment adaptation: threshold from target calibration-split scores, evaluated on the rest | `evaluation/run.py` (`target_context`, `evaluate_model`) | `tests/test_evaluate.py::test_strict_threshold_comes_from_source_validation` | `deployment_adaptation` block |
| ADR 0020 | Deferral metrics | Batch C | Batch C | Batch C |
| ADR 0021 | Tuning: Optuna TPE, GroupKFold(5), AUPRC | Batch B | Batch B | Batch B |
| §8 | Ablations | Batch B (switches exist in `configs/default.yaml` and `features/causal.py`) | `tests/test_features.py` (ICU-time switch) | Batch B |

Module paths are relative to `src/sepsiscope/`.
