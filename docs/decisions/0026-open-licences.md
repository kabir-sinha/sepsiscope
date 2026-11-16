# 0026 — Open licences: Apache-2.0 for code, CC BY 4.0 for documentation and results

**Date:** 2026-11-16 · **Status:** Accepted · **Supersedes** ADR 0003 ·
**Does not change** `docs/protocol.md`
**Amended:** 2026-11-16, before publication: the code licence changed from MIT (first
draft of this ADR, commit `36d97a9`, never pushed) to Apache-2.0.

## Context
ADR 0003 kept all rights reserved while the project was being assessed and noted that an
open licence could be added later. The maintainer now prepares the repository for a public
release and wants others to be able to reuse the code and cite the work.

## Decision
- **Code** (everything not listed below): Apache License 2.0. `LICENSE` holds the official
  text, byte-identical to <https://www.apache.org/licenses/LICENSE-2.0.txt> (11,358 bytes,
  appendix left as published). `NOTICE` carries the copyright line "Copyright 2026
  SepsiScope contributors" (ADR 0023: no personal name in a tracked file; the git history
  records who wrote what) and the third-party and data attributions.
- **Documentation, figures and result files** (`docs/`, `README.md`, `reports/`):
  Creative Commons Attribution 4.0 International (CC BY 4.0).
- **Third-party material keeps its own licence:** the official PhysioNet scorer in
  `third_party/physionet_eval/` stays BSD-2-Clause; the IBM Plex fonts in
  `web/public/fonts/` stay under the SIL Open Font License 1.1. Both are named in `NOTICE`.
- **Data:** not in the repository; it stays with PhysioNet under CC BY 4.0. The README,
  `NOTICE`, model card and demo footer keep the attribution and the citations.
- `CITATION.cff` tells people how to cite the software (and the dataset).
- `pyproject.toml` declares `license = "Apache-2.0"` and ships `LICENSE` and `NOTICE`.
- Medical disclaimer: the software is provided "AS IS" (Apache-2.0 sections 7 and 8) and
  is a research prototype, not for clinical use and not a medical device.

## Why Apache-2.0 rather than MIT
- **Patent grant** (section 3): every contributor licenses any patents their contribution
  needs, and that licence ends for anyone who sues over patents in the work. MIT says
  nothing about patents, which matters for health-related software.
- **Trademark clause** (section 6): the licence does not grant use of the project's name,
  so a fork cannot present itself as SepsiScope.
- **Change notices** (section 4b): redistributed modified files must say that they were
  changed, so altered copies of a clinical-risk model are recognisable as altered.
- It stays permissive and compatible with the BSD-2-Clause scorer and the OFL fonts.

## Alternatives
- **MIT** (first draft of this ADR): shorter, but without the patent grant, the trademark
  clause or change notices.
- **Keep all rights reserved:** rejected; the repository is meant to be reused and cited.
- **CC BY 4.0 for the code too:** rejected; Creative Commons advises against CC licences for
  software.

## Consequences
- Anyone may reuse, change and redistribute the code under Apache-2.0 (keeping `LICENSE`
  and `NOTICE`, and marking changed files), and the documents and results with attribution.
- No change to the code, results or privacy rules.

## Sources
[Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0) ·
[Apache: applying the licence and NOTICE](https://www.apache.org/legal/apply-license.html) ·
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) ·
[Creative Commons FAQ: software](https://creativecommons.org/faq/#can-i-apply-a-creative-commons-license-to-software) ·
[Citation File Format](https://citation-file-format.github.io/) ·
[PhysioNet/CinC Challenge 2019 (CC BY 4.0)](https://physionet.org/content/challenge-2019/1.0.0/)
