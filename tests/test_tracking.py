"""MLflow tracking holds nothing personal; the log scrubber removes personal paths."""

from __future__ import annotations

import getpass
import io
import logging
import socket
import sys
from pathlib import Path

import pytest

from sepsiscope import logscrub, tracking
from sepsiscope.audit.denylist import ALLOWED_EMAIL
from sepsiscope.config import REPO_ROOT

GITHUB_ACCOUNT = ALLOWED_EMAIL.split("+", 1)[1].split("@", 1)[0]


def personal_values() -> list[str]:
    return [
        str(Path.home()),
        str(REPO_ROOT),
        getpass.getuser(),
        socket.gethostname(),
        GITHUB_ACCOUNT,
    ]


def test_stored_run_holds_nothing_personal(tmp_path: Path) -> None:
    mlruns = tmp_path / "mlruns"
    tracking.log_run(
        mlruns, "train_lgbm_A2B", "test", {"learning_rate": 0.05, "seed": 42}, {"auc": 0.7}
    )
    texts = list(tracking.stored_texts(mlruns / tracking.DB_NAME))
    kinds = {kind for kind, _ in texts}
    assert {"tag", "param", "metric", "run_name"} <= kinds
    for kind, text in texts:
        for value in personal_values():
            assert value.lower() not in text.lower(), f"{kind} holds a personal value"
    tag_keys = {t.split("=", 1)[0] for kind, t in texts if kind == "tag"}
    assert tag_keys <= tracking.ALLOWED_TAG_KEYS
    assert "mlflow.source.git.repoURL" not in tag_keys
    assert (
        dict(t.split("=", 1) for kind, t in texts if kind == "tag")["mlflow.user"] == "sepsiscope"
    )


def test_no_artifacts_are_written(tmp_path: Path) -> None:
    mlruns = tmp_path / "mlruns"
    tracking.log_run(mlruns, "run", "test", {"a": 1}, {"m": 1.0})
    assert sorted(p.name for p in mlruns.rglob("*") if p.is_file()) == [tracking.DB_NAME]


def test_safe_tags_refuse_absolute_sources() -> None:
    with pytest.raises(ValueError):
        tracking.safe_tags(str(REPO_ROOT / "src"), "x")
    with pytest.raises(ValueError):
        tracking.safe_tags("~/x.py", "x")
    commit = tracking.safe_tags("src/sepsiscope/cli.py", "x")["mlflow.source.git.commit"]
    assert commit == "unknown" or len(commit) == 40


def test_scrub_rewrites_repo_and_home_paths() -> None:
    home = Path("/fakehome/someone")
    repo = home / "Projects" / "sepsiscope"
    text = f"error in {repo}/src/a.py and {home}/other/b.py; repo is {repo}"
    assert logscrub.scrub(text, home=home, repo=repo) == (
        "error in src/a.py and ~/other/b.py; repo is ."
    )


def test_filter_scrubs_messages_args_and_tracebacks() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(logscrub.ScrubFilter())
    log = logging.getLogger("sepsiscope.test_scrub")
    log.addHandler(handler)
    log.propagate = False
    try:
        try:
            raise FileNotFoundError(str(Path.home() / "secret.txt"))
        except FileNotFoundError:
            log.exception("could not open %s", REPO_ROOT / "data" / "x.parquet")
    finally:
        log.removeHandler(handler)
    out = stream.getvalue()
    assert "data/x.parquet" in out and "~/secret.txt" in out
    assert str(Path.home()) not in out


def test_excepthook_output_is_scrubbed(monkeypatch: pytest.MonkeyPatch) -> None:
    err = io.StringIO()
    monkeypatch.setattr(sys, "stderr", err)
    try:
        raise RuntimeError(str(Path.home() / "x"))
    except RuntimeError as exc:
        logscrub._excepthook(RuntimeError, exc, exc.__traceback__)
    assert "~/x" in err.getvalue()
    assert str(Path.home()) not in err.getvalue()


def test_store_scan_sees_planted_values(tmp_path: Path) -> None:
    """Positive control: the scan really reads tags, params and metric names."""
    mlruns = tmp_path / "mlruns"
    tracking.log_run(mlruns, "run", "PLANTED_STEP", {"PLANTED_PARAM": "v"}, {"PLANTED_METRIC": 1})
    found = " ".join(text for _, text in tracking.stored_texts(mlruns / tracking.DB_NAME))
    for marker in ("PLANTED_STEP", "PLANTED_PARAM", "PLANTED_METRIC"):
        assert marker in found
