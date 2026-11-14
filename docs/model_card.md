# Model card: SepsiScope LightGBM (Platt-calibrated)

Structure follows [Mitchell et al. 2019, "Model Cards for Model Reporting"](https://doi.org/10.1145/3287560.3287596).
Every number below is copied from a committed result file (named next to it); nothing is
estimated by hand. **Research prototype, not for clinical use; not a medical device.**

## Model details

- **What:** gradient-boosted trees (LightGBM 4.7.0, binary objective, deterministic, seed
  42), one model per direction: **A2B** (trained on hospital A, 113 trees) and **B2A**
  (trained on hospital B, 234 trees). Output: Platt-calibrated probability that sepsis
  onset is at most 6 hours away (or has happened) for the current ICU hour.
- **Inputs:** 130 causal features per hour, using only hours ≤ t (protocol section 3):
  vitals 9, labs 27, demographics 2 (Age, Gender), measurement process 68 (cumulative
  counts `__n` and hours since last measured `__hsl`), trends 24 (6-hour means and
  standard deviations). `ICULOS`, `HospAdmTime`, `Unit1` and `Unit2` are never features
  (ablation only). Schema: `reports/features/feature_schema.json`.
- **Training:** source hospital's training split only (A: 12,202 patients, 474,382 hours;
  B: 12,000 patients, 457,002 hours); hyperparameters by Optuna TPE, 50 trials, mean AUPRC
  over GroupKFold(5) (ADR 0021; `reports/tuning/lgbm_{A2B,B2A}.json`). Platt scaling on the
  source **calibration** split; alert threshold on the source **validation** split at a 5 %
  alarm budget (ADR 0022, protocol section 6). No class weights.
- **Saved as:** LightGBM text + whitelisted JSON + feature schema (never pickle; ADR 0004),
  in the ignored `models/`; rebuilt by `uv run sepsiscope reproduce`.
- **Licence:** all rights reserved (ADR 0003). Data: PhysioNet/CinC Challenge 2019, CC BY 4.0.

## Intended use

- **Primary use:** research and teaching on early warning, external validation, alarm
  budgets and explanation of tree models on public ICU data.
- **Users:** students, researchers, reviewers.
- **Out of scope:** any decision about a real patient; any clinical setting; any hospital,
  country or population other than the two in the data without new validation.

## Factors

Hospital (strict external validation both ways), sex (`Gender`), age < 65 / ≥ 65 (protocol
section 5), time in the ICU (C1 bands), alarm budget (C3).

## Metrics

Protocol section 5, on the **unseen** hospital, with patient-level bootstrap 95 % CIs
(1,000 resamples, seed 42): official normalised utility (reference metric, unmodified
scorer), AUROC, AUPRC, alert rate, timely sensitivity, lead time, false alerts per 100
non-septic patient-days, calibration (ECE, reliability), decision curves, subgroups.

## Evaluation data

Strict external validation (ADR 0019): A2B is tested on all 20,000 hospital-B patients,
B2A on all 20,336 hospital-A patients. See `docs/data_card.md`.

## Quantitative analyses

| | A→B | B→A | File |
|---|---|---|---|
| Utility | 0.226 [0.204, 0.251] | 0.273 [0.257, 0.290] | `reports/results/lgbm_{A2B,B2A}.json` |
| AUROC | 0.800 [0.790, 0.811] | 0.765 [0.756, 0.774] | same |
| AUPRC | 0.070 [0.063, 0.080] | 0.094 [0.087, 0.103] | same |
| Alert rate (budget 5 %) | 4.8 % | 8.3 % | same |
| Timely sensitivity | 0.402 [0.372, 0.433] | 0.545 [0.519, 0.568] | same |
| ECE | 0.0058 | 0.0041 | same |
| Utility minus logistic regression | +0.040 [+0.021, +0.059] | +0.167 [+0.147, +0.188] | `reports/results/paired_{A2B,B2A}.json` |

- **Pre-registered criterion (ADR 0022 item 10): met** (paired CI excludes 0 both ways).
- **Deployment adaptation** (threshold re-set on the target, secondary): utility 0.232
  (A→B) and 0.225 (B→A), alert rate 5.2 % both ways.
- **Subgroups** (`reports/results/budgets_{A2B,B2A}.json`): LightGBM − LR utility CI above 0
  in every sex and age group, both ways; lowest AUROC B→A age ≥ 65, 0.750 [0.736, 0.763].
- **Alarm budgets 2 / 5 / 10 %** (same file): LightGBM − LR utility A→B −0.009
  [−0.028, 0.009] / +0.040 / +0.077; B→A +0.061 / +0.167 / +0.246.
- **Shortcut check** (`reports/results/bands_{A2B,B2A}.json`, ADR 0024 item 1): **collapse
  within ICU-stay bands in both directions** (96 h+ AUROC 0.565 and 0.587). A→B alerts
  fall almost only on long stays (0.0 % of hours in the first 48 h, 92 % after 96 h).
- **Deferral** (`reports/results/deferral_{A2B,B2A}.json`, ADR 0024 item 3): **not useful**
  in either direction (deferral rate 30.5 % and 44.8 %, above the 30 % limit).

## Ethical considerations

- Sepsis-3 labels are retrospective and depend on clinicians having acted (cultures,
  antibiotics), so the model partly learns care processes, not only physiology.
- What is measured and how often reflects clinical decisions and differs by hospital; the
  model's strongest features are measurement-process features.
- False alerts cost attention: 48 (A→B) and 102 (B→A) per 100 non-septic patient-days at
  the headline threshold.
- Only two US hospital systems; ages ≥ 90 are coded 100; sex is recorded as 0/1 only.

## Caveats and recommendations

- **Cumulative measurement counts partly proxy ICU time.** The `<var>__n` features grow
  with every hour in the ICU, carrying part of the length-of-stay signal that protocol
  section 3 keeps out by excluding `ICULOS`. They are the top contributors to A→B alerts
  (`reports/results/explanations_A2B.json`). The C1 band analysis confirms the concern:
  within-band discrimination drops and A→B alerts concentrate on long stays. A
  **post-hoc, exploratory** model with measurements per hour instead of counts
  (`reports/results/exploratory_count_rates_*.json`) has lower utility (0.129 and 0.192);
  the headline model is unchanged.
- Septic records end at most 9 hours after the first positive label (`docs/data_card.md`),
  so stay length itself carries information about the label.
- The B→A threshold does not keep its alarm budget on the target (8.3 % against 5 %).
- Conformal coverage on the target is below nominal (exchangeability does not hold across
  hospitals); deferral removes only low-risk hours and never changes an alert.
- A vital or lab that was never measured scores 0 in the rule-based baselines (ADR 0018).
- Recommendation: treat the results as evidence about a public benchmark, not about
  bedside performance; any further use needs prospective, multi-site validation and a
  model without time proxies.
