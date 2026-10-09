# CLAUDE.md — SepsiScope project memory

Explainable, alarm-budgeted sepsis early warning (PhysioNet/CinC 2019). Every change must
be explainable line by line: explain
what you do and why, in plain language.

## Priority 1 — privacy and security (overrides everything)
- Read-only, narrowly scoped inspection. Never print env vars wholesale, shell profiles,
  SSH/cloud credentials, gh hosts, OS keychains, browser data, serials or files outside
  this repository.
- Nothing leaves the local machine without maintainer approval: no push, no remote
  creation, no sign-ins, no API calls with the maintainer's tokens. GitHub settings
  changes are written up as click-by-click steps for the maintainer.
- Installs only from Homebrew / PyPI via uv / npm, exact names, shown and approved first.
  No sudo, no `curl | sh`, no `brew upgrade` / `brew cleanup`, no global changes.
- Only work inside this repository. No `rm -rf` outside it.
- Never pickle/joblib; `yaml.safe_load` only.
- No username/home paths, no email except `222482936+kabir-sinha@users.noreply.github.com`.
- Network services bind to 127.0.0.1 only. Telemetry off (see `_privacy.py`).
- Anything privacy-related that is not covered here: stop and ask.

## Priority 2 — reuse before install
Reuse the installed Python 3.13, Node 26, git and gh. Added for this project: uv 0.12.24
and, on macOS, libomp (keg-only).

## Working rules
Plan first and wait for approval · verify versions/flags live from official sources ·
prove each step with output · critique loop at the end · small conventional commits,
never push without OK · ask before adding enhancements.
Commits: author = noreply address, **no `Co-Authored-By` AI trailer**; instead keep
`docs/ai_assistance.md` (and the README section) updated each phase.

## Invariants
- Patient-level splits only (external A→B and B→A; 60/20/20 inside, seed 42).
- Features at hour t use only hours <= t.
- `feature_schema.json` saved with every model.
- Models as LightGBM text + JSON, never pickle.
- API on 127.0.0.1.
- The official normalized utility (unmodified `evaluate_sepsis_score.py`) is the reference metric.
- No ICULOS / HospAdmTime / Unit1 / Unit2 features (ablation only).
- Telemetry off: `import sepsiscope` before anything that imports mlflow.
- All logic in `src/sepsiscope/`; scripts and notebooks only call it.
- `docs/protocol.md` is frozen; changes need a new ADR.

## Decisions (see docs/decisions/)
Python 3.13 via uv (`<3.14` for dcurves) · uv `required-version >=0.12.24,<0.13` ·
exact pins + hashed `uv.lock` · pyarrow 25.0.1 (mlflow needs <26) · ruff 0.16.10 ·
no torch / polars / MAPIE · Vite react-ts template pins untouched (TS ~6.0) ·
no open-source licence (all rights reserved; ADR 0003) · public demo later
on a Hugging Face static Space.

## Repo map
```
src/sepsiscope/   _privacy.py (imported first) · config.py · cli.py · _smoke.py
                  data/ features/ models/ evaluation/ trust/ api/
configs/          default.yaml (relative paths, seed, alarm budget, label horizon, switches)
tests/            smoke, privacy, config, cli
scripts/          privacy_guard.py (pre-commit hook)
docs/             protocol, privacy, ops, model_card, tripod_ai, decisions/, learning/
web/              Vite react-ts scaffold + research banner
third_party/      vendored code with its own licence
data/ models/ mlruns/   git-ignored
```

## Commands
```
uv sync --locked --all-extras        # install exactly the lockfile
uv run sepsiscope doctor             # environment + OpenMP + telemetry check
uv run pytest                        # tests
uv run ruff check . && uv run ruff format --check . && uv run mypy src
uv run pre-commit run --all-files    # all hooks incl. privacy guard
cd web && npm ci && npm run lint && npm run build
```
