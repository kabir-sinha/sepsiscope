# Official PhysioNet/CinC Challenge 2019 scorer (vendored, unmodified)

| | |
|---|---|
| File | `evaluate_sepsis_score.py` |
| Source | <https://github.com/physionetchallenges/evaluation-2019> |
| Source commit | `467c49b514542be7a4a0bafe40fa2c3b064dda2e` (branch `master`, fetched 2026-10-10) |
| SHA-256 of the file | `26b8b26267ed32e8b7a7a27e45201cfc8c6640e717ba4cdc1f452b32f12b99e5` |
| Licence | BSD-2-Clause, see `LICENSE.txt` (SHA-256 `abc6e0bb01abee7aa79502c8c0a344f55ad2826e5ba5b97e73786bd2104859b6`) |

This file is the reference implementation of the challenge's normalized utility score,
which is SepsiScope's reference metric (`docs/protocol.md`). It must stay byte-for-byte
identical to upstream:

- it is excluded from ruff, mypy and the whitespace-fixing pre-commit hooks;
- `tests/test_official_scorer.py` fails if its SHA-256 changes, and checks that
  `compute_prediction_utility` reproduces the example documented in the file
  (labels `[0,0,0,0,1,1]`, predictions `[0,0,1,1,1,1]` → `3.388888888888889`).

It is not covered by the project's Apache-2.0 licence (ADR 0026).
