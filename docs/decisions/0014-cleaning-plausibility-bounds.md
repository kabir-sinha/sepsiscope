# 0014 — Cleaning: conservative plausibility bounds

**Date:** 2026-10-10 · **Status:** Accepted · **Adds to:** `docs/protocol.md` (no cleaning was defined there)

## Context
The raw files contain a small number of values that cannot be real measurements (an
inspired-oxygen fraction of 4000, a body temperature of 50.0 °C). The protocol did not
define cleaning. Rules had to be fixed before any model is trained, and without removing
values a living patient could produce.

## Decision
One rules table in `src/sepsiscope/data/clean.py`. A value outside its closed interval
`[low, high]` is set to missing in the **clean** table. Nothing is clipped, imputed or
unit-converted, and the raw table is never changed. **These are conservative plausibility
bounds chosen for this project, not clinical reference ranges or standards.**

Counts are from `reports/data/cleaning_report.json` (all 1,552,210 rows). "Just outside"
and "nearest kept" are the observed values next to each bound.

| Variable | Bound | Non-missing A / B | Removed A | Removed B | Observed just outside | Nearest values kept | 0.01 % – 99.99 % quantiles |
|---|---|---|---|---|---|---|---|
| HR (beats/min) | 20 – 300 | 729,026 / 669,785 | 0 | 0 | none | 20 … 280 | 30 – 172.5 |
| O2Sat (%) | 20 – 100 | 695,136 / 654,338 | 0 | 0 | none | 20 … 100 | 38 – 100 |
| Temp (°C) | 25 – 45 | 266,901 / 258,325 | 4 (below) | 2 (above) | 20.9, 21.0, 23.0, 23.6; 50.0, 50.0 | 26.6 … 42.22 | 31.2 – 40.8 |
| SBP (mm Hg) | 20 – 300 | 670,014 / 655,931 | 0 | 0 | none | 20 … 300 | 41 – 242 |
| MAP (mm Hg) | 10 – 300 | 709,357 / 649,583 | 0 | 0 | none | 20 … 300 | 26 – 271 |
| DBP (mm Hg) | 5 – 250 | 409,918 / 655,738 | 6 (above) | 47 (above) | 251, 256, 260 … 300 | 20 … 250 | 22 – 196 |
| Resp (breaths/min) | 1 – 80 | 712,957 / 600,918 | 0 | 50 (above) | 81, 83, 84 … 100 | 1 … 79 | 1 – 60 |
| FiO2 (fraction) | 0.21 – 1.0 | 112,155 / 17,210 | 319 below, 2 above | 46 below, 28 above | 0.2, 0.18, 0.15 … 0.0, −50; 1.1, 1.2 … 2.0, 5.05, 7, 10, 4000 | 0.21 … 1.0 | 0.0 – 2.0 |
| pH | 6.5 – 8.0 | 90,615 / 16,958 | 0 | 0 | none | 6.62 … 7.93 | 6.80 – 7.68 |

**Total: 504 values set to missing out of 8,574,865 non-missing values in these
nine columns (331 in A, 173 in B).**

Why nothing real is cut:
- **Five rules remove nothing** (HR, O2Sat, SBP, MAP, pH). They are guards for future data.
  The observed minimums sit exactly at 20 (HR, O2Sat, SBP, MAP, DBP) and 1 (Resp), which
  suggests the challenge organisers already range-filtered these variables. That is an
  observation from the data, not something the challenge documentation states.
- **Temp:** the four low values (20.9 – 23.6 °C) are at room temperature, far from the
  next value kept (26.6 °C); the two high values are exactly 50.0 °C. Six values in total.
- **DBP:** the 53 removed values (251 – 300 mm Hg) lie above the 99.99th percentile (196);
  in 13 of the 53 rows the diastolic value is higher than the systolic value on the same row.
- **Resp:** the 50 removed values (81 – 100/min) lie above the 99.99th percentile (60); all
  are in hospital B.
- **FiO2:** the column is stored as a fraction (median 0.5; 1,624 values are exactly 0.21,
  room air, and all are kept). 365 values are below 0.21 and 30 are above 1.0. **No value
  lies between 21 and 100**, so the out-of-range values are not percentages and dividing by
  100 would be wrong; they are set to missing instead.

Variables without a rule (all laboratory values except pH and FiO2, EtCO2, and the
demographics) are left untouched in this phase. `Age` is deliberately not capped:
ages of 90 or above are coded as 100 by the dataset (see `docs/data_card.md`).

## Alternatives
- Clip to the bound instead of removing: rejected, it invents a measurement.
- Divide FiO2 values above 1 by 100: rejected, no values look like percentages.
- Statistical outlier removal (z-scores, IQR): rejected, it removes real extreme illness,
  which is exactly what a sepsis model must see.
- Clinical reference ranges: rejected, those describe healthy people, not ICU patients.

## Consequences
The clean table differs from the raw table in 504 cells. A float32 detail matters: the
table stores float32, where 0.21 is slightly below the float64 number 0.21, so bounds are
converted to the column's type before comparing (a test proves room-air values are kept).
Ablations and baselines use the clean table; the raw table stays available to check any
result against uncleaned data.

## Sources
[PhysioNet/CinC Challenge 2019 data description](https://physionet.org/content/challenge-2019/1.0.0/) ·
`reports/data/cleaning_report.json` · `uv run sepsiscope data build`
