# 0007 — Evaluation protocol frozen before data access

**Date:** 2026-10-10 · **Status:** Accepted

## Context
Choosing metrics, splits or thresholds after seeing results inflates performance
(researcher degrees of freedom).

## Decision
`docs/protocol.md` fixes the dataset fingerprint, label, external A→B / B→A splits,
metrics (official utility as the reference), thresholds chosen on validation only,
baselines and ablations, before any download.

## Alternatives
Decide as we go: rejected.

## Consequences
Changes need a new ADR, and results are then reported under both versions.

## Sources
[TRIPOD+AI](https://doi.org/10.1136/bmj-2023-078378) ·
[Reyna et al. 2020](https://doi.org/10.1097/CCM.0000000000004145)
