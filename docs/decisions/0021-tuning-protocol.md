# 0021 — Hyperparameter tuning: Optuna TPE, mean AUPRC over GroupKFold(5)

**Date:** 2026-11-13 · **Status:** Accepted · **Does not change** `docs/protocol.md`
(fills in details that section 4 leaves open)

## Context
Protocol section 4 says tuning uses `GroupKFold(n_splits=5)` grouped by patient, inside
the 60 % train split only, but does not fix the search method, budget or objective.
Fixing them now, before Batch B, prevents tuning until the result looks good.

## Decision
- **Search:** Optuna TPE sampler, seed 42, at most **50 trials**, median pruner.
- **Objective:** mean row-level **AUPRC** over `GroupKFold(5)` folds of the training split
  only (validation, calibration and the other hospital are never seen during tuning).
- **The official utility is reported, never optimised.** It depends on a threshold and
  on the alarm budget, and optimising it directly would tune the threshold implicitly.

## Alternatives
- Optimise AUROC: rejected, positives are rare (about 2 % of hours) and AUPRC is more
  sensitive to the ranking of the hours that matter.
- Optimise the utility: rejected, see above.

## Consequences
Batch B has a fixed tuning budget; any extra trials need a new ADR.

## Sources
`docs/protocol.md` section 4 · Batch A plan (internal) A0.4 ·
[Optuna](https://optuna.org/) (pinned 5.0.0 in `pyproject.toml`)
