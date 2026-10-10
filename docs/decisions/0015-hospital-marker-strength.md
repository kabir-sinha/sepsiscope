# 0015 — Measured strength of the hospital markers; unit columns to be revisited

**Date:** 2026-10-10 · **Status:** Accepted · **Does not change** `docs/protocol.md`

## Context
The protocol keeps `ICULOS`, `HospAdmTime`, `Unit1` and `Unit2` out of all main models
because they describe hospital process rather than physiology, and adds them back only in
an ablation. Before Phase 1 the unit columns were expected to act as a strong hospital
fingerprint. Phase 1 measured how strong each marker actually is.

## Evidence (clean table, 40,336 patients)

"One-rule accuracy" is how often a single counting rule guesses a patient's hospital
correctly; it is a count from a 2×2 table, not a trained model. The baseline is always
guessing hospital A: **50.4 %** (20,336 of 40,336).

| Marker | A | B | One-rule accuracy |
|---|---|---|---|
| Unit columns missing for the patient | 9,522 of 20,336 (46.8 %) | 6,095 of 20,000 (30.5 %) | **58.1 %** |
| Unit columns missing, share of rows | 48.9 % | 29.6 % | |
| `ICULOS` starts at 1 | 12,839 (63.1 %) | 18,704 (93.5 %) | **65.0 %** |

Within a patient the unit columns are either always missing or never missing (0 patients
are mixed). `HospAdmTime` also shifts between hospitals (Jensen-Shannon divergence 0.176,
`docs/eda_findings.md`).

## Decision
- `ICULOS` and `HospAdmTime` **stay excluded** from the main models, as the protocol says.
  `ICULOS` is the stronger hospital marker, and because septic records are truncated
  shortly after onset, time in the ICU also carries label information.
- `Unit1` and `Unit2` **stay excluded for now**, as the protocol says, but the reason is
  weaker than assumed: on their own they identify the hospital only 7.7 points better than
  the baseline. **Revisit in Phase 2 with an ablation** that adds the unit columns back
  on their own, separately from `ICULOS` and `HospAdmTime`, to measure their effect on
  external (A→B, B→A) performance.
- The protocol's existing ablation 3 (all four columns added back) is unchanged. Any change
  to the main feature set would need its own ADR after that ablation.

## Alternatives
- Include the unit columns now: rejected, the protocol was frozen before the data was
  seen and the ablation has not been run.
- Treat 58.1 % as proof the unit columns are harmless: rejected, a weak marginal signal can
  still combine with other features to identify the hospital.

## Consequences
Phase 2 has one extra, pre-declared ablation (unit columns only). Nothing else changes.

## Sources
`docs/eda_findings.md` section 7 · `uv run sepsiscope data verify` (unit missing share) ·
`docs/protocol.md` sections 3 and 8
