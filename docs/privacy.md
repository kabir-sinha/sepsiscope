# Privacy

## What SepsiScope collects

**Nothing.** The project has no analytics, no accounts and no remote logging. The API
(later phases) binds to `127.0.0.1` only.

**The only network call the project makes** is `sepsiscope data download`, and only when
you run it: anonymous HTTPS GET requests to the official PhysioNet bucket
(`physionet-open.s3.amazonaws.com`) to list and fetch the public dataset. It sends no
credentials and no data about you, refuses any other host, follows no redirects and
ignores proxy and netrc settings from the environment. Tests cannot use the network at
all: `tests/conftest.py` blocks DNS lookups and connections at socket level.

## Where data lives

| Item | Location | In git? |
|---|---|---|
| PhysioNet 2019 data (`*.psv`), derived `*.parquet` | `data/` | No (git-ignored, blocked by the hook) |
| Trained models (LightGBM text + JSON) | `models/` | No |
| MLflow runs (local file store) | `mlruns/` | No |
| Secrets (`.env*`) | none should exist | No (git-ignored, blocked by the hook) |

The dataset is public and de-identified (PhysioNet, CC BY 4.0). It is still never
committed: it is large, and redistribution is PhysioNet's job.

## Telemetry status of every tool

Checked on 2026-10-10 against each tool's own docs or source.

| Tool | Collects by default? | Status here | How |
|---|---|---|---|
| MLflow 3.17 | Yes (anonymous usage, since 3.2) | **Off** | `src/sepsiscope/_privacy.py` sets `MLFLOW_DISABLE_TELEMETRY=true` and `DO_NOT_TRACK=true` before mlflow can be imported; CI sets them too. `tests/test_privacy.py` proves the telemetry client is `None` in a clean subprocess where MLflow's own CI/pytest auto-detection is **not** triggered. ([MLflow source: `mlflow/telemetry/utils.py`](https://github.com/mlflow/mlflow/blob/v3.17.0/mlflow/telemetry/utils.py)) |
| MLflow "agent hint" | Local log line containing an absolute path (username) | **Off** | `MLFLOW_DISABLE_AGENT_HINT=1` in `_privacy.py` and CI |
| Homebrew | Yes (InfluxDB analytics) | **Off** (set 2026-10-10, global) | `brew analytics off`; check with `brew analytics state` ([docs](https://docs.brew.sh/Analytics)) |
| GitHub CLI `gh` 2.101 | Yes | **Off** (set 2026-10-10, global) | `gh config set telemetry disabled`; check with `gh config get telemetry` (from `gh help environment` / `gh config --help`) |
| uv | No telemetry setting exists | n/a | Sends a standard installer User-Agent to PyPI when downloading, like pip |
| npm 11 | No telemetry | n/a | `npm audit` sends the dependency tree (package names/versions, nothing personal) to the npm registry |
| Vite, oxlint, TypeScript | No telemetry | n/a | none |
| JupyterLab 4.6 | No: news/update checks default to **Ask** | Answer **No** when asked | Settings → Notifications → "Fetch official Jupyter news" = Never |
| pre-commit, ruff, mypy, pytest | No telemetry | n/a | none |
| pip-audit | No telemetry | n/a | Sends the dependency list to PyPI/OSV vulnerability databases when run |
| `opentelemetry-*`, `databricks-sdk` (MLflow deps) | Only export if you configure an endpoint / Databricks URI | Not configured | none |

## Public vs private

- **Repository:** private on GitHub until the maintainer makes it public. Nothing is
  pushed without maintainer approval.
- **Commit identity:** the maintainer's name with `222482936+kabir-sinha@users.noreply.github.com`,
  set at repo level. No personal email ever appears in history.
- **Public later:** code, docs, figures and aggregate metrics only. Never the data,
  never patient-level outputs.

## Guardrails (pre-commit)

`scripts/privacy_guard.py` runs on every commit and **blocks**:

- any line containing an absolute macOS home path (`/` + `Users/`)
- any email address other than the noreply address (plus `@example.*` placeholders and
  GitHub `[bot]` noreply addresses, e.g. Dependabot)
- `.env` / `.env.*` files
- `*.psv` / `*.parquet` anywhere, and `*.csv` under `data/`
- files over 1 MB (also `check-added-large-files --maxkb=1000`)
- PNG files that carry text, EXIF or time metadata chunks

`detect-private-key` blocks committed private keys. CI runs the same privacy guard over
every tracked file, so a commit made with `git commit --no-verify` still fails CI.

### How to check the guardrails yourself

```bash
uv run pre-commit run --all-files
```

```bash
git ls-files | grep -E '\.(psv|parquet|csv)$|(^|/)\.env' || echo "clean"
```

```bash
git grep -nI -e "$HOME" -e "$(whoami)" || echo "clean"
```

```bash
git log --format='%ae %ce' | sort -u
```

The last command must print only the noreply address, plus GitHub's own bot identities on
merged Dependabot pull requests (`49699333+dependabot[bot]@users.noreply.github.com` as
author, and GitHub's own web-flow noreply address as committer). Neither is personal.
