# 0011 — Protocol amendment: citations only

**Date:** 2026-10-10 · **Status:** Accepted

## Context
`docs/protocol.md` is frozen (ADR 0007). Two references in it were imprecise: the SIRS
criteria cited Sepsis-3 without the box number, and the paper's row counts had no
table reference. Neither had been machine-verified when the protocol was frozen.

## Decision
Amend the citations only, still before any data was downloaded:
- SIRS: Singer M, et al., JAMA 2016;315(8):801-810, **Box 1** ("SIRS", credited there to
  Bone et al.). Bone 1992 stays as the original source.
- Row counts 739,663 (A) / 684,508 (B): Reyna MA, et al., challenge manuscript,
  **Table 2**, printed page 11 of `manuscript.pdf` in the official evaluation repository.

No dataset, label, split, metric, threshold, baseline or ablation changed.

## Alternatives
Leave the imprecise citations: rejected, every claim should be traceable for the viva.

## Consequences
Both references were checked against the primary sources on 2026-10-10 (the Sepsis-3
full text via NCBI E-utilities, PMC4968574, and the text of `manuscript.pdf`).

## Sources
[Sepsis-3 on PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC4968574/) ·
[manuscript.pdf](https://github.com/physionetchallenges/evaluation-2019/blob/master/manuscript.pdf)
