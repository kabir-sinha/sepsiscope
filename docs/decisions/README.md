# Architecture Decision Records

One short file per decision: context, decision, alternatives, consequences, sources.
Format after [Michael Nygard's ADRs](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions).
A decision is changed by a new ADR that supersedes it, never by editing history.

| # | Decision | Status |
|---|---|---|
| [0001](0001-reuse-before-install.md) | Reuse existing tools; install only uv and libomp | Accepted |
| [0002](0002-python-313-system-interpreter.md) | Python 3.13 via uv, using the Homebrew interpreter | Accepted |
| [0003](0003-licence-all-rights-reserved.md) | No open-source licence during evaluation | Accepted |
| [0004](0004-models-as-text-never-pickle.md) | Models as LightGBM text + JSON; never pickle/joblib | Accepted |
| [0005](0005-openmp-single-process-smoke.md) | Homebrew libomp + single-process OpenMP smoke test | Accepted |
| [0006](0006-telemetry-off.md) | Telemetry off, enforced in code and tested | Accepted |
| [0007](0007-frozen-evaluation-protocol.md) | Evaluation protocol frozen before data access | Accepted |
| [0008](0008-ci-and-hooks.md) | CI and pre-commit design | Accepted |
| [0009](0009-dependency-choices.md) | Dependency pins and exclusions | Accepted |
| [0010](0010-frontend-scaffold.md) | Vite react-ts template, pins untouched | Accepted |
| [0011](0011-protocol-citation-amendment.md) | Protocol amendment: citations only | Accepted |
| [0012](0012-protocol-qsofa-citation.md) | Protocol amendment: qSOFA citation only | Accepted |
| [0013](0013-stratified-patient-splits.md) | Patient-level splits are stratified by the septic flag | Accepted |
| [0014](0014-cleaning-plausibility-bounds.md) | Cleaning: conservative plausibility bounds | Accepted |
| [0015](0015-hospital-marker-strength.md) | Measured strength of the hospital markers; unit columns to be revisited | Accepted |
| [0016](0016-privacy-hardening.md) | Privacy hardening: UTC commits, local denylist, git hooks, privacy-audit | Accepted |
| [0017](0017-security-lockdown.md) | Security lockdown: patched toolchain, package fixes, gitleaks, sandbox, clean history | Accepted |
| [0018](0018-news2-oxygen-item.md) | Modified NEWS2 (max 17) oxygen item: missing FiO2 scores 0; 24 h carry-forward sensitivity | Accepted |
| [0019](0019-strict-external-validation-headline.md) | Headline = strict external validation; deployment adaptation secondary | Accepted |
| [0020](0020-deferral-metrics.md) | Deferral metrics for the trust layer | Accepted |
| [0021](0021-tuning-protocol.md) | Tuning: Optuna TPE, 50 trials, mean AUPRC over GroupKFold(5) | Accepted |
| [0022](0022-batch-b-model-decisions.md) | Batch B: calibration split, Platt headline, ablations, tracking, no class weights, success criterion | Accepted |
| [0023](0023-no-name-in-tracked-files.md) | No personal name in tracked files (copyright: "SepsiScope contributors") | Accepted |
