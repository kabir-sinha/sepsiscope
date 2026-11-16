# 0026 — Open licences: MIT for code, CC BY 4.0 for documentation and results

**Date:** 2026-11-16 · **Status:** Accepted · **Supersedes** ADR 0003 ·
**Does not change** `docs/protocol.md`

## Context
ADR 0003 kept all rights reserved while the project was being assessed and noted that an
open licence could be added later. The maintainer now prepares the repository for a public
release and wants others to be able to reuse the code and cite the work.

## Decision
- **Code** (everything not listed below): MIT, in `LICENSE` at the root. The copyright
  holder is "SepsiScope contributors", as in ADR 0023, so no personal name enters a
  tracked file; the git history records who wrote what.
- **Documentation, figures and result files** (`docs/`, `README.md`, `reports/`):
  Creative Commons Attribution 4.0 International (CC BY 4.0).
- **Third-party material keeps its own licence:** the official PhysioNet scorer in
  `third_party/physionet_eval/` stays BSD-2-Clause; the IBM Plex fonts in
  `web/public/fonts/` stay under the SIL Open Font License 1.1.
- **Data:** not in the repository. The PhysioNet/CinC Challenge 2019 data is CC BY 4.0;
  the README, model card and demo footer keep the attribution and the citations.
- `CITATION.cff` at the root tells people how to cite the software (and the dataset).
- `pyproject.toml` declares `license = "MIT"`.

## Alternatives
- **Apache-2.0** (adds an explicit patent grant): rejected as heavier than this small
  research prototype needs; MIT is the shortest well-known permissive licence.
- **Keep all rights reserved:** rejected; the repository is meant to be reused and cited.
- **CC BY 4.0 for the code too:** rejected; Creative Commons advises against CC licences for
  software.

## Consequences
- Anyone may reuse, change and redistribute the code with the MIT notice, and the
  documents and results with attribution.
- No change to the code, results or privacy rules.

## Sources
[MIT licence (OSI)](https://opensource.org/license/mit) ·
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) ·
[Creative Commons FAQ: software](https://creativecommons.org/faq/#can-i-apply-a-creative-commons-license-to-software) ·
[Citation File Format](https://citation-file-format.github.io/) ·
[PhysioNet/CinC Challenge 2019 (CC BY 4.0)](https://physionet.org/content/challenge-2019/1.0.0/)
