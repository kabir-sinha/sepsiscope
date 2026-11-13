# 0022 — Batch B: LightGBM training, calibration, ablations and tracking decisions

**Date:** 2026-11-13 · **Status:** Accepted · **Does not change** `docs/protocol.md`
(fixes details before any Batch B result exists)

## Context
Batch B trains the main model (LightGBM), tunes it (ADR 0021), calibrates it, explains its
alerts and runs the ablations of protocol section 8. Several choices could be tuned after
seeing results, so they are fixed here first. The plan is `docs/plan/batch-b.md`.

## Decision
1. **Calibration split.** Calibrators are fitted on the source hospital's **calibration**
   split only. The alert threshold stays on the source **validation** split (protocol
   section 6), so no split does both jobs.
2. **Calibrator.** Platt scaling is the headline; isotonic regression is a pre-specified
   sensitivity analysis. Neither is chosen by looking at results.
3. **Ablations and re-runs.** Ablations reuse the main model's tuned parameters; they are
   not re-tuned. The batch gate re-runs `train`, `evaluate` and the ablations from the
   saved best parameters, plus a 3-trial synthetic test that shows tuning is reproducible;
   the full tuning run is not repeated.
4. **Tracking store.** MLflow uses a local SQLite `mlflow.db` in an ignored folder; no
   artifacts, no UI, no server. If an absolute path cannot be avoided anywhere outside
   that local database, work stops and the maintainer is asked.
5. **Paired comparisons.** LightGBM minus each baseline in utility, AUROC and AUPRC, with
   paired patient-level bootstrap 95 % CIs (the same 1,000 resamples, seed 42).
6. **Vitals-only ablation** = the 8 vitals' last values, the shock index, their 6-hour
   trends and their measurement-process features; no labs and no demographics.
7. **Tuning run.** Tuning starts only on the maintainer's explicit "go", with the local
   machine on power, using Optuna's journal file storage in an ignored folder so it can
   resume. The maintainer is asked before it is wrapped in `caffeinate -i`. If the measured
   fit time projects more than 6 hours per direction, work stops and the maintainer is
   asked.
8. **No class weighting.** `is_unbalance` and `scale_pos_weight` stay off; the class
   balance is left as it is, so scores stay closer to probabilities.
9. **Explanations** are LightGBM's built-in feature contributions (`pred_contrib`) on the
   raw log-odds. Platt scaling is monotone, so it keeps the ordering of the raw scores and
   the explanations stay valid for the calibrated alert.
10. **Pre-registered success criterion.** LightGBM beats the logistic regression only if the
    paired 95 % CI for the utility difference (LightGBM minus logistic regression) excludes
    0, **in each direction** (A→B and B→A).

## Alternatives
- Calibrate on the validation split: workable (calibration does not change ranking), but it
  would make one split serve two purposes; rejected.
- Re-tune every ablation: about 4× the tuning cost, and the comparison would mix feature
  effects with tuning effects; rejected.
- Choose Platt or isotonic by validation log-loss: a choice made after seeing data;
  rejected.
- Class weighting: it distorts probabilities and the threshold already handles the alert
  budget; rejected.

## Limitations
- Ablation results use parameters tuned for the full feature set, so an ablation may be
  slightly disadvantaged.
- The gate does not repeat the full tuning run; reproducibility of tuning is shown only on
  synthetic data plus the saved, versioned tuning results.

## Consequences
Batch B results are judged by criterion 10, fixed before any result. A "no" is reported as
such.

## Sources
`docs/plan/batch-b.md` · `docs/protocol.md` sections 4–8 · ADR 0004 (no pickle) · ADR 0015
(unit columns) · ADR 0021 (tuning)
