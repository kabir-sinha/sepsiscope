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

## Guardrails (pre-commit, git hooks, CI)

The rules live in `src/sepsiscope/audit/` (ADR 0016). `scripts/privacy_guard.py` runs
them on every commit and **blocks**:

- absolute home paths: macOS (`/` + `Users/`, also in UTF-16 and binary content), Linux
  (`/` + `home/<name>`) and Windows (`C:` + `\Users\`)
- any email address other than the noreply address (plus `@example.*` placeholders,
  GitHub `[bot]` noreply addresses and GitHub's own service addresses)
- account-tier wording (plan, payment or verification status) and enrollment-ID shapes
  (lockfiles are exempt from these two)
- `.env` / `.env.*` files
- `*.psv` / `*.parquet` anywhere, and `*.csv` under `data/`
- files over 1 MB (also `check-added-large-files --maxkb=1000`)
- PNG files that carry text, EXIF or time metadata chunks
- notebooks with outputs, execution counts, cell metadata or environment metadata
- values from the optional local denylist (below)

`detect-private-key` blocks committed private keys. Two more hooks (installed by
`uv run pre-commit install`):

- **commit-msg:** no `Co-Authored-By` trailer (GitHub bot co-authors excepted), no AI-tool
  trailers or "generated with" lines, no chat session URLs, nothing personal.
- **pre-push:** every outgoing commit must have `+0000` author and committer offsets, the
  noreply address (or a GitHub bot identity) and a clean message.

CI runs the file rules over every tracked file and the commit check over the pushed range,
so `git commit --no-verify` or `git push --no-verify` still fails CI.

### Local denylist

`.privacy-denylist.local` (gitignored, mode 600) lists personal values, one per line;
`#` starts a comment. It is read only when present, so CI uses generic patterns only.
Matches are whole-word and case-insensitive; the GitHub handle inside the noreply address
and the repository URL is not a hit. The maintainer's name is allowed only on the README
copyright line and the pyproject author line. Output always masks the value.

### Commit timezone

Every commit is made with `TZ=UTC` so it does not record the local timezone. For your own
commits, a repo-local alias helps: `git config --local alias.c '!TZ=UTC git commit'`, then
`git c -m "..."`.

### How to check the guardrails yourself

```bash
uv run pre-commit run --all-files
```

```bash
uv run sepsiscope privacy-audit
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
