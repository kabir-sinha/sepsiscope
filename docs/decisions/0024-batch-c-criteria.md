# 0024 — Batch C: pre-registered criteria for the shortcut check, deferral and budgets

**Date:** 2026-11-14 · **Status:** Accepted · **Does not change** `docs/protocol.md`
(adds analyses; fixed before any Batch C result exists)

## Context
Batch C checks whether the headline model relies on a time-in-ICU shortcut, adds an
uncertainty-based deferral layer (ADR 0020) and reports alarm-budget sensitivity, lead-time
distributions and subgroup CIs. Each of these can be made to look good after seeing results,
so the rules are fixed here first. The plan is the internal Batch C plan.

## Decision
1. **Shortcut check (C1).** Rows are grouped by their hour's time since ICU admission:
   0–24, 24–48, 48–96 and 96+ h. `ICULOS` is used only for this grouping, never as a
   feature (protocol section 3). LightGBM is said to **collapse within bands** if, in either
   direction, any band has an AUROC whose 95 % CI upper bound is below 0.60, or a point AUROC
   more than 0.10 below the model's overall AUROC in that direction. A collapse is reported
   as evidence of a time shortcut. The paired LightGBM − LR utility difference per band is
   reported next to it, without a pass/fail rule.
2. **Utility within a subset of hours** (C1 bands, C2 non-deferred hours). The unmodified
   official scorer is called with alerts outside the subset set to "no alert", for the
   observed, best and inaction predictions alike; the normalised utility of the subset is
   (observed − inaction) / (best − inaction) of those sums. Because the official utility is
   a sum over rows, this is exactly the subset's share.
3. **Deferral (C2).** Class-conditional split conformal on the Platt probability, with
   nonconformity 1 − p̂(y) and per-class thresholds from the source **calibration** split
   only (the split Platt used). An hour is deferred when its prediction set is {0, 1} or
   empty; other hours keep the headline threshold. α = 0.10 is the main analysis; 0.05 and
   0.20 are sensitivity analyses. Deferral is called **useful** only if, in **each**
   direction at α = 0.10: (a) the deferral rate is at most 30 % of patient-hours; (b) the
   share of label-1 hours not deferred is at most 0.10 below the share of label-0 hours not
   deferred; and (c) the utility on non-deferred hours is above the headline utility. A
   "no" is reported as such.
4. **Names (C2).** "Share not deferred" is ADR 0020's per-class measure; "coverage" is the
   conformal one (share of hours whose true label is in the prediction set). They are never
   used for each other.
5. **Budgets (C3).** Alarm budgets 2, 5 and 10 % of patient-hours, thresholds from the
   source **validation** split (protocol section 6), for LightGBM, LR and NEWS2. The 5 %
   budget must reproduce the committed thresholds exactly. No budget is called "best".
6. **Lead times and subgroups (C3).** Lead-time percentiles (10th–90th) and a 0–12 h
   histogram among timely detected patients; subgroup CIs by patient bootstrap within each
   group (sex, age < 65 / ≥ 65), 1,000 resamples, seed 42, with the paired LightGBM − LR
   difference. Subgroup results are descriptive; no subgroup claim is pre-registered.
7. **Reproducibility check.** Byte-identical comparisons ignore only the `git_commit` key in
   `model.json`, which records HEAD by design.

## Alternatives
- Bands by each patient's total length of stay: rejected, it uses the future (the stay's
  end) to group an hour.
- Defer only on empty sets: rejected, with two classes an empty set is rare and an ambiguous
  set {0, 1} is the real "unsure" case.
- Conformal thresholds from a separate half of the calibration split: rejected; Platt has
  only two parameters, and halving the split makes the positive-class quantile unstable.

## Limitations
- Conformal coverage is guaranteed only for exchangeable data. Neither the hospital shift
  nor the hours within one patient are exchangeable, so target-hospital coverage is
  measured, not guaranteed.
- With about 2 % positive hours, class-conditional sets may include label 1 for most hours,
  which would give a high deferral rate.
- Narrow bands (96+ h) and small subgroups give wide CIs.

## Consequences
Batch C results are judged by items 1 and 3, fixed before any result. Per-hour deferral
decisions are written to the ignored `data/` folder so the ADR 0020 metrics can be
recomputed; only aggregates are committed.

## Sources
Batch C plan (internal) · `docs/protocol.md` sections 3, 5, 6 · ADR 0019 (strict external
headline) · ADR 0020 (deferral metrics) · ADR 0022 (calibration split, Platt headline) ·
Vovk V. et al., *Algorithmic Learning in a Random World* (2005), Mondrian conformal
prediction · Angelopoulos A.N., Bates S., *A Gentle Introduction to Conformal Prediction*
(2021), arXiv:2107.07511
