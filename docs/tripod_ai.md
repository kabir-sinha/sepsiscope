# TRIPOD+AI checklist

Reporting guideline: Collins GS, Moons KGM, Dhiman P, et al. *TRIPOD+AI statement: updated
guidance for reporting clinical prediction models that use regression or machine learning
methods.* BMJ 2024;385:e078378, [doi:10.1136/bmj-2023-078378](https://doi.org/10.1136/bmj-2023-078378).
Checklist version 11 January 2024, from
[tripod-statement.org](https://www.tripod-statement.org/) (52 items). Topics below are short
paraphrases; read the official checklist for the full wording.

This repository develops and evaluates a model (D;E). Status: **done** = addressed in the
file named; **partly** = addressed with a stated gap; **n/a** = not applicable, with the
reason; **not done** = a gap, with the reason. The report that will carry items 1, 2, 25
and 26 in prose is the project report (later); until then the files below hold them.

| Item | Topic (paraphrased) | Where addressed | Status |
|---|---|---|---|
| 1 | Title: development/evaluation, population, outcome | `README.md` (first lines), `docs/model_card.md` | done |
| 2 | Abstract (TRIPOD+AI for Abstracts) | project report (later) | not done: no abstract yet |
| 3a | Healthcare context, rationale, existing models | `docs/protocol.md` §7 (baselines NEWS2, SIRS, qSOFA with sources) | partly: no literature review in the repo |
| 3b | Target population, intended purpose and users | `docs/model_card.md` "Intended use" | done (research use only) |
| 3c | Known health inequalities between groups | `docs/model_card.md` "Ethical considerations"; `docs/data_card.md` "Known limitations" | partly: the data has sex and age only |
| 4 | Objectives (development and/or validation) | `docs/protocol.md`; `docs/internal/plan/batch-b.md`, `batch-c.md` | done |
| 5a | Data sources for development and evaluation, representativeness | `docs/data_card.md` "Source", "Cohorts"; `docs/datasheet.md` | done |
| 5b | Dates of data collection | `docs/datasheet.md` "Collection process" | n/a: dates removed by de-identification |
| 6a | Setting, number and location of centres | `docs/data_card.md` "Cohorts" (two US hospital systems) | done |
| 6b | Eligibility criteria | `docs/data_card.md` "Cohorts", "Quirks"; `docs/protocol.md` §1 | partly: set by the challenge organisers |
| 6c | Treatments received and their handling | `docs/data_card.md` "Known limitations" (labels depend on antibiotics and cultures) | partly: treatments are not in the data |
| 7 | Pre-processing and quality checks, across groups | `docs/data_card.md` "Cleaning"; ADR 0014; `reports/data/cleaning_report.json` | partly: checks by hospital, not by sex or age |
| 8a | Outcome, horizon, assessment, consistency across groups | `docs/protocol.md` §2; `docs/data_card.md` "Label definition" | done |
| 8b | Outcome assessors for subjective outcomes | `docs/data_card.md` "Label definition" (rule-based Sepsis-3) | n/a: computed by rule, no assessors |
| 8c | Blinding of outcome assessment | `docs/protocol.md` §2 | n/a: label computed by the dataset authors |
| 9a | Choice of initial predictors, pre-selection | `docs/protocol.md` §3 (all recorded variables except ICU time and unit columns); ADR 0015; `reports/features/feature_schema.json` | done |
| 9b | Definition and timing of all predictors | `src/sepsiscope/features/causal.py` (one description per feature); `reports/features/feature_schema.json` | done |
| 9c | Predictor assessors for subjective predictors | — | n/a: routine measurements only |
| 10 | Study size and its justification | `docs/data_card.md` "Cohorts"; `docs/protocol.md` §4 | partly: fixed public dataset, no sample size calculation |
| 11 | Missing data handling | `docs/eda_findings.md` §2; `src/sepsiscope/features/causal.py` (last value carried forward within the stay, hours since last measured, counts); values still missing are left missing for LightGBM | done |
| 12a | Use of the data, partitioning | `docs/protocol.md` §4; ADR 0013, 0019, 0022; `splits/` | done |
| 12b | Handling of predictors (form, scaling) | `src/sepsiscope/features/causal.py`; ADR 0018 (NEWS2 items) | done |
| 12c | Model type, rationale, building steps, tuning, internal validation | ADR 0021, 0022; `docs/model_card.md` "Model details"; `reports/tuning/` | done |
| 12d | Heterogeneity across clusters (hospitals) | ADR 0019 (both directions); `reports/results/drift.json` | done |
| 12e | Performance measures and plots, model comparison | `docs/protocol.md` §5; ADR 0020, 0024 | done |
| 12f | Model updating after evaluation | ADR 0019 (deployment adaptation re-sets the threshold only) | done |
| 12g | How predictions were calculated in evaluation | `src/sepsiscope/evaluation/run.py`; `uv run sepsiscope reproduce` | done |
| 13 | Class imbalance methods | ADR 0022 (no class weights; Platt on the calibration split) | done |
| 14 | Approaches to fairness | `docs/protocol.md` §5 (sex and age subgroups); `reports/results/budgets_*.json` | partly: subgroup reporting only, no mitigation |
| 15 | Model output, classification and threshold choice | `docs/protocol.md` §6; ADR 0022; `docs/model_card.md` | done |
| 16 | Differences between development and evaluation data | `docs/eda_findings.md` §6; `reports/results/drift.json`; `docs/data_card.md` "Known limitations" | done |
| 17 | Ethics approval and consent | `docs/datasheet.md` "Collection process" (source paper; public de-identified data) | partly: no new approval needed for public data; not formally stated by an ethics board here |
| 18a | Funding | `docs/datasheet.md` "Motivation" | done (no funding) |
| 18b | Conflicts of interest | project report (later) | not done: to be declared in the report |
| 18c | Protocol access | `docs/protocol.md` (frozen; changes by ADR) | done |
| 18d | Registration | `docs/protocol.md` | not done: not registered (pre-registration by committed ADRs only) |
| 18e | Data availability | `README.md` "Data attribution"; `docs/data_card.md` | done (public, CC BY 4.0) |
| 18f | Code availability | `README.md` | partly: repository public, all rights reserved (ADR 0003) |
| 19 | Patient and public involvement | — | not done: no involvement (student project) |
| 20a | Participant flow, with and without outcome | `docs/data_card.md` "Cohorts"; result files (`patients`, `septic_patients`) | partly: no flow diagram |
| 20b | Characteristics per source, missing data, groups | `docs/data_card.md`; `docs/eda_findings.md` | done |
| 20c | Predictor distribution: evaluation vs development | `reports/results/drift.json`; `docs/eda_findings.md` §6 | done |
| 21 | Participants and events per analysis | `splits/` sizes; result files; `docs/model_card.md` "Model details" | done |
| 22 | Full model specification and access | `docs/model_card.md`; models rebuilt by `sepsiscope reproduce` (not committed) | partly: model files are not distributed |
| 23a | Performance with CIs, including subgroups | `reports/results/lgbm_*.json`, `budgets_*.json`; `docs/model_card.md` | done |
| 23b | Heterogeneity across clusters | both directions; `reports/results/bands_*.json` (ICU-stay bands) | done |
| 24 | Results of model updating | `reports/results/lgbm_*.json` ("deployment_adaptation") | done |
| 25 | Overall interpretation, fairness | `docs/model_card.md` "Caveats and recommendations" | partly: full discussion in the project report |
| 26 | Limitations | `docs/model_card.md`; `docs/data_card.md` "Known limitations"; ADR 0022, 0024 "Limitations" | done |
| 27a | Handling poor or unavailable input data in use | `docs/model_card.md` "Out of scope" | n/a: not for implementation |
| 27b | User interaction and expertise needed | `docs/model_card.md` "Intended use" | n/a: not for implementation |
| 27c | Next steps for research | `docs/model_card.md` "Caveats and recommendations" | done |
