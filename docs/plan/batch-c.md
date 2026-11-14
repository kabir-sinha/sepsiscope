# Batch C — Milestone 5: trust layer, robustness checks and reporting

Status: **approved 2026-11-14 with the recommended defaults** (decisions D1–D12 below).
Criteria are recorded in ADR 0024 **before any Batch C result exists**. Working mode as in
Batch B: one commit per step with `docs/handoff.md` updated, fast checks per step with real
exit codes (`set -o pipefail`), the full gate once at the end, then a stop before any push
or tag. Pushes and tags happen from the maintainer's own terminal.

Run times and memory are estimates for the local machine, based on `evaluate --all-models`
(379 s, 5.68 GiB peak); loading the data sets the peak. Any step more than 2× off its
estimate is reported. Long runs go in the background under `caffeinate -i`, without polling.

No new dependency for C0–C4 (class-conditional conformal prediction is written with numpy;
MAPIE stays excluded). C5 may need downloads of source documents; each is shown with its
URL and size and waits for the maintainer's approval.

## Order (D11)

C0 → C4 → C1 → C2 → C3 → C5 → C6 → M5 evidence report (text only).

## C0. Plan and ADR 0024

This file plus ADR 0024 (all pre-registered criteria). Committed before any C1–C3 run, so the
history shows the order. `docs/protocol.md` stays frozen; Batch C adds analyses and does not
change the headline result.

## C4. Small fixes

- `scripts/byte_check.py --write | --compare`: SHA-256 manifest of `reports/`, `models/` and
  the demo JSON. In `model.json` only the `git_commit` key is dropped before hashing (it
  records HEAD by design); every other byte counts. Tests: identical outputs pass, a changed
  `git_commit` passes, any other change fails.
- Demo: the threshold label moves clear of the onset and selected-hour lines (left of any
  vertical line closer than about 60 px, otherwise above or below the threshold line).
- Demo: the LightGBM headline cards use the same card style as the others (`.stat.main`
  loses its accent border; emphasis by text only).
- Fast check: pytest for the new test, web lint and build, contrast 56/56. The visual result
  is checked by the maintainer in a browser (no local server in the sandbox). Under 1 min.

## C1. Shortcut check by ICU-stay band

- Bands by the hour's time since ICU admission: 0–24, 24–48, 48–96, 96+ h (`ICULOS` used
  only to group rows, never as a feature).
- LightGBM, LR and NEWS2, both directions, each at its headline threshold: AUROC, AUPRC,
  utility, alert rate per band with patient-level bootstrap CIs (1,000, seed 42), plus the
  paired LightGBM − LR utility difference per band.
- Utility within a band: the unmodified official scorer with alerts outside the band set to
  "no alert", for observed, best and inaction alike. The official utility is a sum over
  rows, so this gives exactly the band's share of the sum.
- Collapse rule: ADR 0024 item 1. If performance collapses within bands, the report says so.
- `sepsiscope analyses bands` → `reports/results/bands_{A2B,B2A}.json`. Tests: band
  utilities add up to the total on synthetic data; a planted time-only score collapses
  within bands and is flagged. About 6–8 min, 6 GiB.

## C2. Uncertainty-based deferral (ADR 0020)

- Class-conditional (Mondrian) split conformal on the Platt probability: nonconformity
  1 − p̂(y); per-class thresholds from the source **calibration** split only (the same
  split Platt used, D4). Prediction set = labels whose score is within their class
  threshold. Defer when the set is {0, 1} or empty; non-deferred hours keep the headline
  threshold for alerting (D5).
- α = 0.10 main; 0.05 and 0.20 sensitivity (D2).
- Reported on the target hospital: deferral rate; per-class share not deferred (ADR 0020
  item 2, named "share not deferred", D6); conformal coverage per class against 1 − α
  (named "coverage"); protocol metrics on non-deferred hours (utility with the C1 masking)
  always next to the deferral rate.
- Per-hour deferral decisions are written to the ignored `data/` (ADR 0020 consequence);
  only aggregates are committed: `reports/results/deferral_{A2B,B2A}.json`.
- Caveats: coverage is guaranteed only under exchangeability, which holds for neither
  hospital shift nor hours within a patient; with about 2 % positive hours the deferral
  rate may be high. Reported as found.
- Tests: per-class coverage ≥ 1 − α (with tolerance) on synthetic exchangeable data; set
  rules; fixed seed. About 3–5 min, 6 GiB.

## C3. Alarm-budget sensitivity, lead times, subgroup CIs

- Budgets 2 / 5 / 10 %, thresholds from the source validation split (protocol section 6);
  LightGBM, LR and NEWS2 (D7), both directions, all metrics with CIs, paired LightGBM − LR.
- Lead-time distribution among timely detected patients: histogram 0–12 h and the 10th,
  25th, 50th, 75th and 90th percentiles with CIs.
- Subgroup CIs (sex, age < 65 / ≥ 65): patient bootstrap within each group, plus the paired
  LightGBM − LR difference per group.
- `sepsiscope analyses budgets` → `reports/results/budgets_{A2B,B2A}.json`. Tests: the 5 %
  budget reproduces the committed thresholds exactly; percentiles on a known case. About
  8–12 min, 6 GiB.

## C5. Documentation

- Model card (Mitchell et al. 2019), filled from committed JSON only.
- TRIPOD+AI checklist (Collins et al. 2024, BMJ, doi 10.1136/bmj-2023-078378): every item
  mapped to a section or file, or marked not applicable / not done with a reason. A test
  checks that every item has a row.
- Datasheet (Gebru et al. 2021) as a new `docs/datasheet.md`, linked from `data_card.md` (D8).
- README: one-command reproduction with `uv run sepsiscope reproduce` (D9): data verify →
  build → splits → features → train → evaluate → ablations → exploratory → analyses, from
  the committed tuned parameters (`--retune` optional; a resumed tuning run is not
  byte-identical). A test checks the README commands against `--help`.
- Downloads (each needs approval, URL and size shown first): the TRIPOD+AI checklist from
  the BMJ supplement or tripod-statement.org; optionally the papers behind the model card,
  the datasheet and the conformal method, to verify citations.

## C6. Final gate

Full tests 3 times (real exit codes; the Unix-socket test is covered by CI), the usual gate
list, a byte-identical re-run of train, evaluate, ablations, exploratory, the three analyses
and the demo build checked with `scripts/byte_check.py` (about 30 min, 6 GiB, background),
the exhaustive privacy scan (same 11 items, two passes plus the positive control), the M5
evidence report, handoff and resume note. The release tag `v1.0.0-m5` (annotated, unsigned,
D10) is created only after the maintainer says so; the maintainer pushes it.

## Decisions (maintainer, 2026-11-14: recommended defaults approved)

- **D1** C1 collapse rule as ADR 0024 item 1.
- **D2** C2 α = 0.10 main, 0.05 and 0.20 sensitivity.
- **D3** C2 success criterion as ADR 0024 item 3.
- **D4** C2 conformal thresholds on the same calibration split as Platt.
- **D5** C2 non-deferred hours keep the headline threshold.
- **D6** "Share not deferred" (ADR 0020) and "coverage" (conformal) named apart.
- **D7** C3 budgets for LightGBM, LR and NEWS2; paired subgroup differences included.
- **D8** Datasheet as `docs/datasheet.md`.
- **D9** Reproduction as `uv run sepsiscope reproduce`.
- **D10** Tag `v1.0.0-m5`, annotated, unsigned, only on the maintainer's word.
- **D11** C4 moved to second.
- **D12** No new demo views from C1–C3 in this batch.
