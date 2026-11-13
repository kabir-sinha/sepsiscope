"""MLflow tracking without personal information (ADR 0022, plan B6 / P1).

- Store: a local SQLite file ``mlruns/mlflow.db`` (ignored by git and blocked by the
  privacy guard). No tracking server and no UI are ever started.
- Runs are created with ``MlflowClient.create_run``, which, unlike ``mlflow.start_run``,
  adds **no** automatic context tags. (In MLflow 3.18 the automatic tags would be the OS
  username, the absolute script path and the git remote URL.) Only the allowlisted tags
  below are written: a fixed user, a repository-relative source name, the source type and
  the commit hash.
- Only parameters, metrics and tags are logged; never artifacts.
- The SQLite store records each experiment's artifact location as an absolute local path
  inside the database. Nothing is ever written there; the database never leaves the local
  machine (maintainer decision, ADR 0022 item 4).

Telemetry is off because ``sepsiscope`` (``_privacy``) is imported before mlflow.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping
from pathlib import Path

from sepsiscope.config import REPO_ROOT
from sepsiscope.models.lgbm import git_commit

EXPERIMENT = "sepsiscope"
DB_NAME = "mlflow.db"
ALLOWED_TAG_KEYS = frozenset(
    {
        "mlflow.user",
        "mlflow.source.name",
        "mlflow.source.type",
        "mlflow.source.git.commit",
        "mlflow.runName",
        "sepsiscope.step",
    }
)


def tracking_uri(mlruns_dir: Path) -> str:
    return f"sqlite:///{(mlruns_dir / DB_NAME).as_posix()}"


def safe_tags(source: str, step: str) -> dict[str, str]:
    """The only tags a run ever gets. ``source`` must be repository-relative."""
    if Path(source).is_absolute() or source.startswith("~"):
        raise ValueError("source must be a repository-relative path")
    return {
        "mlflow.user": "sepsiscope",
        "mlflow.source.name": source,
        "mlflow.source.type": "LOCAL",
        "mlflow.source.git.commit": git_commit(),
        "sepsiscope.step": step,
    }


def log_run(
    mlruns_dir: Path,
    run_name: str,
    step: str,
    params: Mapping[str, object],
    metrics: Mapping[str, float],
    source: str = "src/sepsiscope/cli.py",
) -> str:
    """Create one finished run with params, metrics and safe tags; return its ID."""
    from mlflow.entities import Metric, Param, RunTag
    from mlflow.tracking import MlflowClient

    mlruns_dir.mkdir(parents=True, exist_ok=True)
    client = MlflowClient(tracking_uri=tracking_uri(mlruns_dir))
    experiment = client.get_experiment_by_name(EXPERIMENT)
    experiment_id = experiment.experiment_id if experiment else client.create_experiment(EXPERIMENT)
    tags = safe_tags(source, step)
    run = client.create_run(experiment_id, tags=tags, run_name=run_name)
    run_id = str(run.info.run_id)
    client.log_batch(
        run_id,
        metrics=[Metric(k, float(v), 0, 0) for k, v in sorted(metrics.items())],
        params=[Param(k, str(v)) for k, v in sorted(params.items())],
        tags=[RunTag(k, v) for k, v in sorted(tags.items())],
    )
    client.set_terminated(run_id, "FINISHED")
    unexpected = set(client.get_run(run_id).data.tags) - ALLOWED_TAG_KEYS
    if unexpected:
        raise RuntimeError(f"unexpected MLflow tags: {sorted(unexpected)}")
    return run_id


def stored_texts(db_path: Path) -> Iterable[tuple[str, str]]:
    """Every tag, param, metric name and run/experiment name in the store, read-only.

    Used by the privacy tests. Artifact locations are excluded on purpose (see module
    docstring); everything else a run carries is returned.
    """
    queries = {
        "tag": "SELECT key || '=' || value FROM tags",
        "experiment_tag": "SELECT key || '=' || value FROM experiment_tags",
        "param": "SELECT key || '=' || value FROM params",
        "metric": "SELECT DISTINCT key FROM metrics",
        "run_name": "SELECT name FROM runs",
        "experiment_name": "SELECT name FROM experiments",
    }
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as con:
        for kind, sql in queries.items():
            for (text,) in con.execute(sql):
                yield kind, str(text)


def relative_source(path: Path) -> str:
    """A path inside the repository, written relative to its root."""
    return path.resolve().relative_to(REPO_ROOT).as_posix()
