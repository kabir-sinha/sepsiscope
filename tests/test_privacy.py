"""Telemetry must be off because of OUR code, not because MLflow detected pytest/CI."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

# MLflow auto-disables telemetry when any of these is set (mlflow/telemetry/utils.py),
# which would make an in-process test pass vacuously. Strip them for the child.
CI_MARKERS = {
    "PYTEST_CURRENT_TEST",
    "GITHUB_ACTIONS",
    "CI",
    "CIRCLECI",
    "GITLAB_CI",
    "JENKINS_URL",
    "TRAVIS",
    "TF_BUILD",
    "BITBUCKET_BUILD_NUMBER",
    "CODEBUILD_BUILD_ARN",
    "BUILDKITE",
    "TEAMCITY_VERSION",
    "CLOUD_RUN_EXECUTION",
    "RUNBOT_HOST_URL",
    "RUNBOT_BUILD_NAME",
    "RUNBOT_WORKER_ID",
    "MLFLOW_TESTING_TELEMETRY",
}
OUR_VARS = {"MLFLOW_DISABLE_TELEMETRY", "DO_NOT_TRACK", "MLFLOW_DISABLE_AGENT_HINT"}


def _clean_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k not in CI_MARKERS | OUR_VARS}


def _run(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        env=_clean_env(),
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def test_mlflow_telemetry_client_is_none_after_importing_sepsiscope() -> None:
    proc = _run(
        """
        import sepsiscope  # must come first
        import mlflow.telemetry
        import mlflow.telemetry.utils as u
        # Guard against a vacuous pass: MLflow must NOT think it is in CI/tests.
        assert u._IS_IN_CI_ENV_OR_TESTING is False, "child env still looks like CI"
        assert mlflow.telemetry.get_telemetry_client() is None
        print("TELEMETRY_OFF")
        """
    )
    assert proc.returncode == 0, proc.stderr
    assert "TELEMETRY_OFF" in proc.stdout


def test_optouts_propagate_to_grandchild_processes() -> None:
    proc = _run(
        """
        import os, subprocess, sys
        import sepsiscope
        out = subprocess.run(
            [sys.executable, "-c",
             "import os;print(os.environ['MLFLOW_DISABLE_TELEMETRY'], os.environ['DO_NOT_TRACK'])"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        print(out)
        """
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "true true"


def test_mlflow_import_does_not_log_home_path() -> None:
    proc = _run("import sepsiscope, mlflow")
    assert proc.returncode == 0, proc.stderr
    home = str(Path.home())
    assert home not in proc.stdout + proc.stderr
