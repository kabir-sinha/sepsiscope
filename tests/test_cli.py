"""CLI behaviour, including that `doctor` prints nothing personal."""

from __future__ import annotations

import getpass
import platform
import re
import socket
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sepsiscope import __version__
from sepsiscope.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


@pytest.mark.parametrize("args", [["train"], ["report"]])
def test_stubs(args: list[str]) -> None:
    result = runner.invoke(app, args)
    assert result.exit_code == 0
    assert "not implemented in Phase 0" in result.stdout


def test_evaluate_needs_model_and_direction() -> None:
    result = runner.invoke(app, ["evaluate", "--model", "xgb", "--direction", "A2B"])
    assert result.exit_code == 2
    assert "--all-baselines" in result.stdout


def test_doctor_passes_and_is_not_personal() -> None:
    result = runner.invoke(app, ["doctor"])
    out = result.stdout
    assert result.exit_code == 0, out
    assert "doctor          PASS" in out
    assert "telemetry       OFF" in out
    assert "openmp smoke    OK" in out
    # Nothing personal: no username, home path, hostname, email or /Users path.
    assert getpass.getuser() not in out
    assert str(Path.home()) not in out
    assert "/" + "Users/" not in out
    assert socket.gethostname() not in out
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", out)
    # No OS version either: only the OS family and CPU architecture.
    assert platform.release() not in out
    assert f"platform        {platform.system()} {platform.machine()}\n" in out
