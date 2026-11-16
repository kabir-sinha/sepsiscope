# 0018 — Modified NEWS2 (max 17) oxygen item: missing FiO2 scores 0

**Date:** 2026-11-13 · **Status:** Accepted · **Does not change** `docs/protocol.md`

## Context
The protocol (section 7) scores the modified NEWS2 (max 17) "air or oxygen" item as "on oxygen" when
`FiO2 > 0.21`. FiO2 is a laboratory/ventilator column and is missing in most hours, so the
protocol needs a rule for hours without an FiO2 value. Cleaning keeps FiO2 only as a
fraction in `[0.21, 1.0]` (ADR 0014).

## Decision
- **Main analysis:** an hour without an FiO2 value means "no supplemental oxygen
  recorded" and scores **0** for the oxygen item. Only the FiO2 value measured in that
  hour is used; it is not carried forward.
- **Sensitivity analysis:** FiO2 is carried forward within the patient for up to
  **24 hours** after its last measurement; after that it counts as missing (0 points).
- The other modified NEWS2 items use the last value carried forward within the patient (causal,
  hours `<= t` only); an item that has never been measured scores 0. The modified score
  has no consciousness item, so its maximum is 17 (protocol section 7).

## Alternatives
- Carry FiO2 forward without a limit: rejected as the main rule, because a patient weaned
  off oxygen would keep the +2 points for the rest of the stay.
- Score missing FiO2 as "on oxygen": rejected, it would add 2 points to most hours.

## Consequences
Modified NEWS2 may under-score patients on oxygen whose FiO2 was not charted every hour; the
24-hour sensitivity analysis shows how much this matters.

## Limitations
- **A vital sign or lab that has never been measured scores 0 points** (approved by the
  maintainer, 2026-11-13). Early in a stay, or for a patient whose vitals are charted
  rarely, the score can be lower than the patient's true state; "no data" is treated as
  "normal". This applies to all modified NEWS2 (max 17) items and, by the same rule, to
  SIRS and modified qSOFA (max 2) criteria, which count only when a value meets them.
- Missing FiO2 also scores 0 (see the decision above), so the oxygen item can under-score.

## Sources
`docs/protocol.md` section 7 · `src/sepsiscope/data/clean.py` (FiO2 rule) · ADR 0014 ·
`docs/internal/plan/batch-a.md` A0.1
