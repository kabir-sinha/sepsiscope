# 0013 — Patient-level splits are stratified by the septic flag

**Date:** 2026-10-10 · **Status:** Accepted · **Amends:** `docs/protocol.md` section 4

## Context
The protocol fixes a 60/20/20 train / validation / calibration split **by patient**,
seed 42, inside the training hospital. It does not say how patients are assigned. Septic
patients are rare (A: 1,790 of 20,336 = 8.80 %; B: 1,142 of 20,000 = 5.71 %), so a plain
random split lets the septic rate drift between parts by chance. The calibration part
then sees a different base rate from the training part, which matters for calibration
and for choosing the alarm threshold.

## Decision
Assign patients **stratified by one patient-level flag: ever septic (max SepsisLabel = 1)**.
- Whole counts per part come from the largest-remainder method, first for all patients,
  then for septic patients; non-septic counts are the difference. Totals and septic
  counts are therefore each within one patient of 60/20/20.
- Inside each stratum, sorted patient IDs are shuffled with `numpy.random.default_rng(42)`
  (septic stratum first, then non-septic) and cut in order: train, validation, calibration.
- The files `splits/hospital_A.json` and `splits/hospital_B.json` hold patient IDs only
  and are committed. Patient IDs are the public file names of the dataset.

Result (from `uv run sepsiscope data splits`):

| Hospital | Part | Patients | Septic | Septic rate |
|---|---|---|---|---|
| A | train | 12,202 | 1,074 | 8.80 % |
| A | validation | 4,067 | 358 | 8.80 % |
| A | calibration | 4,067 | 358 | 8.80 % |
| B | train | 12,000 | 685 | 5.71 % |
| B | validation | 4,000 | 229 | 5.73 % |
| B | calibration | 4,000 | 228 | 5.70 % |

Nothing else in the protocol changes: the split is still by patient, 60/20/20, seed 42;
the other hospital is still never split; tuning still uses GroupKFold(5) inside the
60 % part only.

## Alternatives
- Plain random split: rejected, the septic rate would differ between parts by chance.
- Stratifying also by stay length, age or sex: rejected, more strata with few septic
  patients each, and no evidence yet that it is needed.
- `sklearn.model_selection.StratifiedGroupKFold`: built for folds, not a fixed 60/20/20.

## Consequences
The split was fixed **before** any model was trained and uses only the label's
patient-level maximum, which is also what the fingerprint counts. Tests check that the
split is deterministic, disjoint, complete, within one patient of the target sizes and
keeps the septic rate; one test checks the committed files themselves.

## Sources
[scikit-learn: cross-validation iterators for grouped and stratified data](https://scikit-learn.org/stable/modules/cross_validation.html) ·
[NumPy `default_rng`](https://numpy.org/doc/stable/reference/random/generator.html)
