# Data card: PhysioNet/CinC Challenge 2019 (training sets A and B)

Every number here was recomputed from the downloaded files on 2026-10-10 with
`uv run sepsiscope data verify`, `data build` and the EDA functions. The dataset is not in
this repository.

## Source and citation

- **Dataset:** Early Prediction of Sepsis from Clinical Data: The PhysioNet/Computing in
  Cardiology Challenge 2019, version 1.0.0.
  [PhysioNet page](https://physionet.org/content/challenge-2019/1.0.0/),
  DOI [10.13026/v64v-d857](https://doi.org/10.13026/v64v-d857).
- **Paper to cite:** Reyna MA, Josef C, Jeter R, et al. *Early Prediction of Sepsis From
  Clinical Data: The PhysioNet/Computing in Cardiology Challenge 2019.* Critical Care
  Medicine 2020;48(2):210-217.
  [doi:10.1097/CCM.0000000000004145](https://doi.org/10.1097/CCM.0000000000004145).
- **PhysioNet's standard citation**, as requested on the dataset page: Pollard T, Moody BE,
  Lehman L, et al. *PhysioNet as a global platform for biomedical research.* Nature Health
  2026;1(8):792-795.
  [doi:10.1038/s44360-026-00096-z](https://doi.org/10.1038/s44360-026-00096-z). The older
  PhysioNet reference is Goldberger AL, et al. *PhysioBank, PhysioToolkit, and PhysioNet.*
  Circulation 2000;101(23):e215,
  [doi:10.1161/01.CIR.101.23.e215](https://doi.org/10.1161/01.CIR.101.23.e215).
- **Licence:** [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/).
  Attribution used by this project: "PhysioNet/CinC Challenge 2019 (Reyna et al., Critical
  Care Medicine 2020), CC BY 4.0".
- **Download:** the official public bucket; see `docs/data_manifest.md` for file counts and
  the manifest hash.

## Cohorts

ICU patients from two US hospital systems (from the paper): **A** = Beth Israel Deaconess
Medical Center, **B** = Emory University Hospital. A third system, C, was the hidden test
set and is not public. One pipe-separated file per patient, one row per hour.

| | A | B | A + B |
|---|---|---|---|
| Patients (files) | 20,336 | 20,000 | 40,336 |
| Rows (patient-hours) | 790,215 | 761,995 | 1,552,210 |
| Septic patients | 1,790 (8.80 %) | 1,142 (5.71 %) | 2,932 (7.27 %) |
| Positive rows | 17,136 (2.17 %) | 10,780 (1.41 %) | 27,916 (1.80 %) |
| Septic patients positive from row 0 | 203 | 223 | 426 |
| Stay length in rows: median (min – max) | 39 (8 – 336) | 38 (8 – 336) | |
| Median age (years) | 64.7 | 62.0 | |
| Gender = 1 (male) | 58.2 % | 53.7 % | |
| Patient IDs | p000001 – p020643 | p100001 – p120000 | |

The challenge manuscript's Table 2 reports 739,663 (A) and 684,508 (B) rows. The public
files contain 790,215 and 761,995; **the files are authoritative** (`docs/protocol.md`).

## Columns

41 columns per file, in this order: 8 vital signs (`HR`, `O2Sat`, `Temp`, `SBP`, `MAP`,
`DBP`, `Resp`, `EtCO2`), 26 laboratory values, 6 demographics (`Age`, `Gender`, `Unit1`,
`Unit2`, `HospAdmTime`, `ICULOS`) and `SepsisLabel`. Missing values are written as `NaN`.
Our tables add `pid`, `hospital` and `t` (row index from 0) in front and change nothing else.

## Label definition (from the PhysioNet page)

Sepsis follows the Sepsis-3 criteria. Three times are defined per patient:

- **t_suspicion:** clinical suspicion of infection, the earlier of IV antibiotics and blood
  cultures. If antibiotics came first, cultures must follow within 24 hours; if cultures
  came first, antibiotics must be ordered within 72 hours. Antibiotics must be given for at
  least 72 consecutive hours.
- **t_SOFA:** organ dysfunction, a two-point deterioration in SOFA score within 24 hours.
- **t_sepsis:** the earlier of t_suspicion and t_SOFA, provided t_SOFA is no more than
  24 hours before or 12 hours after t_suspicion. Otherwise the patient is not septic.

`SepsisLabel` is 1 from `t_sepsis - 6` hours onwards for septic patients and 0 everywhere
for others. So a positive label means "sepsis onset is at most 6 hours away, or has
happened", not "septic now".

## Quirks (each one re-checked on the files)

| Quirk | Observed |
|---|---|
| Labels are monotone | 0 patients where the label goes from 1 back to 0 |
| `ICULOS` steps | always +1 within a patient (0 violations) |
| `ICULOS` does not always start at 1 | starts at 1 for 31,543 of 40,336 patients (A: 63.1 %, B: 93.5 %) |
| `Gender` | only 0 or 1, never missing. The PhysioNet page defines 0 = female, 1 = male |
| `Age` | never missing; range 14 – 100; 22 patients are under 18 |
| **Age 90 or above is coded as 100** (de-identification; the PhysioNet page says "100 for patients 90 or above") | 392 patients have Age = 100, **all in hospital B**; the highest other age is 89. Hospital A has no age above 89. Age is kept as is and is **not** treated as an outlier or capped |
| `HospAdmTime` | 8 missing values, all in one hospital-A patient; negative for 38,767 patients (admitted to hospital before the ICU), zero for 1,313 and positive for 255 |
| `Unit1` / `Unit2` | never both 1; always missing together; missing in 48.9 % of A's rows and 29.6 % of B's |
| `EtCO2` | **never recorded in hospital A** (0 values; 57,636 in B) |
| `FiO2` | 129,365 values; 395 lie outside 0.21 – 1.0 (examples: −50, 0.0, 0.04, 0.2, 2.0, 4000); none lies between 21 and 100 |
| Records are short and capped | every stay has at least 8 rows and at most 336 (10 patients have exactly 336) |
| **Septic records stop soon after onset** | the last row is at most 9 rows after the first positive label: 1,870 of 2,932 septic patients have exactly 10 rows from the first positive row, 795 have 9, 248 have 8 |
| Values look pre-filtered | observed minimums are exactly 20 for HR, O2Sat, SBP, MAP and DBP and exactly 1 for Resp, which suggests range limits applied before release (an observation; not stated by the source) |

## Units: listed vs observed

The PhysioNet data dictionary and the stored values disagree for some variables. **We
record the difference and do not convert any units.**

| Variable | Listed on the PhysioNet page | Observed values (5th / 50th / 95th percentile) | Reading |
|---|---|---|---|
| FiO2 | "Fraction of inspired oxygen (%)" | 0.35 / 0.50 / 1.00 | stored as a fraction (0.21 – 1.0), not a percentage |
| Lactate | "Lactic acid (mg/dL)" | 0.8 / 1.8 / 7.35 | consistent with mmol/L (for scale: the Sepsis-3 septic-shock criterion is a lactate above 2 mmol/L, which is 18 mg/dL) |
| Magnesium | "(mmol/dL)" | 1.5 / 2.0 / 2.7 | consistent with mg/dL rather than the listed "mmol/dL" (2.0 mmol/dL would be 20 mmol/L) |
| WBC | "count*10^3/µL" | 4.5 / 10.3 / 21.3 | consistent with ×10³/µL as listed |
| Platelets | "count*10^3/µL" | 65 / 181 / 378 | consistent with ×10³/µL as listed |
| Temp | "Deg C" | 35.8 / 37.0 / 38.2 | as listed |

The "Reading" column is our interpretation of the value ranges. It was not confirmed by the
dataset authors.

## Cleaning

One rules table (`src/sepsiscope/data/clean.py`); a value outside its bound becomes missing
in the clean table and the raw table is never changed. 504 values are affected in total.
The bounds are conservative plausibility limits chosen for this project, **not clinical
standards**. Full counts and the observed values next to each bound are in
`docs/decisions/0014-cleaning-plausibility-bounds.md` and `reports/data/cleaning_report.json`.

| Variable | Kept range | Values set to missing (A / B) |
|---|---|---|
| HR | 20 – 300 | 0 / 0 |
| O2Sat | 20 – 100 | 0 / 0 |
| Temp | 25 – 45 °C | 4 / 2 |
| SBP | 20 – 300 | 0 / 0 |
| MAP | 10 – 300 | 0 / 0 |
| DBP | 5 – 250 | 6 / 47 |
| Resp | 1 – 80 | 0 / 50 |
| FiO2 | 0.21 – 1.0 | 321 / 74 |
| pH | 6.5 – 8.0 | 0 / 0 |

## Tables and splits produced

| File | Content | In git? |
|---|---|---|
| `data/raw/…/training_set{A,B}/p*.psv` | the 40,336 original files | no |
| `data/interim/physionet2019_raw.parquet` | all rows, values unchanged (14.7 MB) | no |
| `data/processed/physionet2019_clean.parquet` | after the cleaning rules (13.9 MB) | no |
| `splits/hospital_{A,B}.json` | patient IDs for train / validation / calibration (60/20/20, stratified, seed 42; ADR 0013) | yes |
| `reports/data/cleaning_report.json` | counts per rule and hospital | yes |

Both Parquet tables are validated by pandera schemas (`src/sepsiscope/data/schema.py`)
every time they are built.

## Known limitations

- **Two US hospital systems only.** Results may not transfer to other countries, care
  settings or patient populations.
- **Labels are retrospective.** Sepsis-3 onset is computed afterwards from antibiotic,
  culture and SOFA timing. It is a proxy for the clinical event, and it depends on
  clinicians having acted (ordered cultures and antibiotics).
- **Septic records are truncated** at most 9 rows after the first positive label, so the
  data cannot show what happens later in a septic stay, and stay length itself carries
  information about the label.
- **Mostly missing.** 80.1 % of the 34 vital-sign and laboratory cells are missing; what is
  measured, and how often, reflects clinical decisions and differs by hospital.
- **Hospital-specific recording.** EtCO2 is absent in A; DBP is missing in 48.1 % of A's
  rows against 14.0 % of B's; `ICULOS` start and the unit columns differ by hospital. A model
  can learn the hospital instead of the patient.
- **De-identification effects.** Ages of 90 or above are coded as 100; dates are removed.
- **Unit labels are unreliable** for at least FiO2, Lactate and Magnesium (see above).
- **Research and education use only.** Nothing built on this data here is a medical device.
