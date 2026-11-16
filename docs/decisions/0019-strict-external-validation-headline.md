# 0019 — Headline result is strict external validation; deployment adaptation is secondary

**Date:** 2026-11-13 · **Status:** Accepted · **Does not change** `docs/protocol.md`
(adds one secondary, clearly labelled analysis)

## Context
Protocol sections 4 and 6 choose the operating threshold on the source hospital's
validation split and never use the test hospital for thresholding. A threshold chosen at
one hospital can give a very different alert rate at another (score distributions shift
between hospitals; `docs/eda_findings.md`). A deployed system could re-set its threshold
from the new hospital's own scores without needing any labels.

## Decision
- **Headline result = strict external validation.** The threshold is fitted on the source
  hospital's **validation** split (alarm budget 5 %) and applied unchanged to every
  patient of the target hospital.
- **Secondary analysis, labelled "deployment adaptation".** The threshold is re-set from
  the target hospital's **unlabelled** scores, using only its **calibration-split**
  patients (`splits/hospital_X.json`), and the result is evaluated only on the target
  hospital's **remaining** patients (train and validation splits). Labels of the target
  hospital are never used to choose the threshold.
- Both results are always reported side by side; the deployment-adaptation numbers are
  never presented as the headline.

## Alternatives
- Report only strict validation: rejected, it hides how much of the alert-rate drift a
  label-free re-threshold removes.
- Re-threshold on all target patients: rejected, the same patients would then be used to
  choose and to evaluate the threshold.

## Consequences
The secondary analysis is evaluated on about 80 % of the target hospital, so its CIs are a
little wider and its numbers are not directly comparable with the headline.

## Sources
`docs/protocol.md` sections 4 and 6 · ADR 0013 (splits) · `docs/internal/plan/batch-a.md` A0.2
