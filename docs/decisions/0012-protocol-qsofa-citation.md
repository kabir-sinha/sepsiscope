# 0012 — Protocol amendment: qSOFA citation only

**Date:** 2026-10-10 · **Status:** Accepted

## Context
`docs/protocol.md` cited only Seymour et al. 2016 for the modified qSOFA baseline. The
criteria themselves are printed in the Sepsis-3 paper.

## Decision
Add the citation Singer M, et al., JAMA 2016;315(8):801-810, **Box 4** ("qSOFA (Quick
SOFA) Criteria": respiratory rate >= 22/min, altered mentation, systolic blood pressure
<= 100 mm Hg) next to Seymour 2016. The baseline itself is unchanged (two of the three
criteria, because mentation is not in the data).

## Alternatives
Leave Seymour 2016 as the only source: rejected; Box 4 is where the thresholds are listed.

## Consequences
None for methods. Verified in the Sepsis-3 full text (PMC4968574, via NCBI E-utilities)
on 2026-10-10.

## Sources
[Sepsis-3 on PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC4968574/) ·
[Seymour et al. 2016](https://doi.org/10.1001/jama.2016.0288)
