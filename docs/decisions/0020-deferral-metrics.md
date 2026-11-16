# 0020 — Deferral metrics for the trust layer

**Date:** 2026-11-13 · **Status:** Accepted · **Does not change** `docs/protocol.md`
(adds metrics; implementation in Batch C)

## Context
The trust layer (Batch C) will let the model defer an hour ("I am not sure, ask a
clinician") instead of scoring it. A deferring model can look better simply by deferring
the hard hours, so deferral needs its own metrics, fixed before any result is seen.

## Decision
Every model that can defer reports, on the **unseen (target) hospital**:

1. **Deferral rate:** share of patient-hours deferred.
2. **Per-class coverage:** share of label-0 hours and of label-1 hours that were **not**
   deferred (shows whether deferral hides positive hours).
3. **Performance on the non-deferred hours:** the protocol section 5 metrics, computed
   only on the hours that were not deferred, always next to the deferral rate.

## Alternatives
- Report only performance on the non-deferred hours: rejected, it rewards deferring
  everything difficult.

## Consequences
Batch C must log the deferral decision per hour so these numbers can be recomputed.

## Sources
`docs/protocol.md` section 5 · `docs/internal/plan/batch-a.md` A0.3
