# Phase 0 — what we set up and why (viva notes)

## uv
A fast Python package and project manager. One tool creates the virtual environment
(`.venv`), resolves dependencies, writes the lockfile and runs commands
(`uv run pytest`). Here it reuses the Homebrew Python 3.13 that was already installed,
instead of downloading another one.

## Lockfile with hashes (`uv.lock`)
`pyproject.toml` says *what* we want (for example `lightgbm==4.7.0`). `uv.lock` records
*exactly* what was installed, including every indirect dependency, plus a **sha256 hash**
of each file. `uv sync --locked` refuses to run if the lockfile is out of date, and the
hashes stop a tampered or swapped package from installing. So the same code gives the
same environment on any machine, which makes results reproducible.

## OpenMP and libomp
OpenMP is a library that lets C/C++ code use all CPU cores in parallel. LightGBM uses it
for fast tree building, and on macOS it loads Homebrew's `libomp`. scikit-learn ships
*its own* copy. If two copies load into one Python process, it can crash with
"OMP: Error #15". Our smoke test fits both libraries in **one** process, three runs in
a row, to prove it is safe on the local machine.

## pre-commit
A program that runs checks *before* git accepts a commit. Ours lint and format the code
(ruff), type-check it (mypy), strip notebook outputs (nbstripout), block private keys
and big files, and run our own **privacy guard** that refuses home paths, personal
emails, `.env` files and data files. Mistakes are caught on the local machine, before they
reach GitHub.

## CI (continuous integration)
GitHub Actions re-runs the checks (lint, types, tests, frontend build) on a fresh Linux
machine for every push and pull request. It proves the project works outside the local machine.
It reads the Python version from `.python-version`, so it can't drift from a hard-coded version.

## Telemetry
Some tools send anonymous usage statistics to their makers by default. MLflow does,
since 3.2. We switch it off in code (`_privacy.py`) before MLflow is imported, and a test
proves it is off. Even anonymous metadata should not leave a health-AI project without
consent.

## GitHub noreply email
Every git commit stores an author email, and on a public repo anyone can read it. GitHub
gives each user a private `<ID>+<username>@users.noreply.github.com` address. Using it, and
turning on "Block command line pushes that expose my email", keeps my real email out of
the history for good.

## Frozen protocol
`docs/protocol.md` was written **before** looking at any data. It fixes the splits,
metrics, thresholds and baselines in advance, so I cannot (even unconsciously) pick
whatever makes the model look best. This is the same idea as pre-registering a
clinical trial.

## Five likely viva questions

1. **Why split by patient and not by row?**
   Rows from the same patient are strongly correlated. If one patient's hours are in both
   train and test, the model "recognises" the patient and the scores are inflated
   (leakage). Patient-level splits, plus a completely different hospital for testing,
   give an honest estimate.

2. **Why not use ICULOS / HospAdmTime / Unit1 / Unit2 as features?**
   They describe *where* and *how long* a patient has been in care, not their physiology.
   They reflect each hospital's process, so they don't transfer to another hospital and
   can inflate in-hospital scores. We only add them back in an ablation, to show that effect.

3. **Why is the official utility score the main metric, not AUROC?**
   AUROC ignores *timing*. The challenge utility rewards alerts 12 to 6 hours before
   onset, penalises late or missed detection (−2) and charges a small cost for false
   alarms (−0.05). That matches the clinical goal better. AUROC and AUPRC are still reported.

4. **Why save models as LightGBM text instead of pickle?**
   Loading a pickle can run arbitrary code, so a tampered file could take over the
   machine. LightGBM's text format is just numbers and tree structure: safe to load,
   readable, and our test proves it gives identical predictions after reloading.

5. **How do you know telemetry is really off, not just assumed?**
   MLflow switches telemetry off by itself when it sees pytest or CI, which would make
   a simple test meaningless. Our test starts a fresh Python process with all those
   markers removed, checks that MLflow does **not** think it is in CI, and only then
   checks that the telemetry client is `None`. So the result is caused by our code.
