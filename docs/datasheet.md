# Datasheet: PhysioNet/CinC Challenge 2019 training sets A and B (as used here)

Questions follow Gebru T, Morgenstern J, Vecchione B, et al. *Datasheets for Datasets.*
Communications of the ACM 2021;64(12):86-92,
[doi:10.1145/3458723](https://doi.org/10.1145/3458723). We did not create the dataset; the
answers describe the public release as published by its authors and as we found it.
Numbers and checks are in [`data_card.md`](data_card.md), which this page links to rather
than repeats.

## Motivation

- **Purpose:** created for the 2019 PhysioNet/Computing in Cardiology Challenge on early
  prediction of sepsis from routine ICU data (Reyna et al., Critical Care Medicine 2020).
- **Creators and funding:** the challenge organisers (see the paper and the PhysioNet page);
  this project received no funding and did not take part in creating the data.

## Composition

- **Instances:** ICU stays; one file per patient, one row per hour (A: 20,336 patients,
  790,215 hours; B: 20,000 patients, 761,995 hours). Data card, "Cohorts".
- **Per instance:** 8 vital signs, 26 laboratory values, 6 demographic / administrative
  fields and the label. Data card, "Columns".
- **Label:** Sepsis-3 based, shifted 6 hours earlier. Data card, "Label definition".
- **Missing data:** most cells are missing (80.1 % of vital-sign and lab cells); missingness
  reflects clinical practice and differs by hospital. EDA findings, section 2.
- **Subpopulations:** two US hospital systems; sex (0/1) and age are recorded; ages of 90
  or above are coded as 100 (hospital B only).
- **Sensitive data:** de-identified health records; no names or dates. Patient IDs appear
  only in the committed split files (`splits/`), never in results or the demo.
- **Self-contained:** yes; a third hospital (C) was the hidden test set and is not public.

## Collection process

- Collected from the electronic health records of the two hospital systems and released by
  the challenge organisers; details of collection, ethics approval and de-identification are
  in the source paper. This project downloaded the public release from PhysioNet's official
  bucket once, verified file count, sizes and MD5 hashes (`docs/data_manifest.md`), and
  checks a content fingerprint before every build (protocol section 1).

## Preprocessing, cleaning, labelling

- **By the creators:** the label (Sepsis-3 onset minus 6 hours); records appear range-
  filtered and are capped at 336 hours; septic records end at most 9 hours after the first
  positive label. Data card, "Quirks".
- **By this project:** raw values are never overwritten; values outside conservative
  plausibility bounds become missing in a separate clean table (504 values; ADR 0014);
  units are not converted. Data card, "Cleaning" and "Units".
- **Raw data kept:** yes, in the ignored `data/` folder (never in git).

## Uses

- **Here:** strict external validation between the two hospitals, alarm-budgeted early
  warning, explanation and robustness checks (`docs/protocol.md`, ADRs 0019-0024).
- **Not appropriate for:** clinical decisions; claims about other hospitals, countries or
  care settings; estimating sepsis incidence (the selection is the challenge's).
- **Known risks:** a model can learn the hospital or the length of stay instead of the
  patient (data card, "Known limitations"; C1 band analysis in `docs/model_card.md`).

## Distribution

- **Licence:** Creative Commons Attribution 4.0. Attribution used: "PhysioNet/CinC Challenge
  2019 (Reyna et al., Critical Care Medicine 2020), CC BY 4.0".
- **This repository** does not redistribute the data. It holds aggregate results without
  patient IDs, and the split files with patient IDs only.

## Maintenance

- Maintained by PhysioNet (version 1.0.0). This project pins the version and verifies the
  fingerprint; any change in the files stops the pipeline (`sepsiscope data verify`).
