"""Every `sepsiscope ...` command written in the README exists in the CLI."""

from __future__ import annotations

import re
from pathlib import Path

from typer.testing import CliRunner

from sepsiscope.cli import app

README = Path(__file__).resolve().parents[1] / "README.md"
COMMAND = re.compile(r"uv run sepsiscope ((?:[a-z][a-z-]*)(?: [a-z][a-z-]*)?)")


def _commands() -> list[str]:
    return sorted(set(COMMAND.findall(README.read_text(encoding="utf-8"))))


def test_readme_names_the_reproduction_commands() -> None:
    names = _commands()
    assert "reproduce" in names
    assert "data download" in names


def test_every_readme_command_has_help() -> None:
    runner = CliRunner()
    for cmd in _commands():
        result = runner.invoke(app, [*cmd.split(), "--help"])
        assert result.exit_code == 0, f"`sepsiscope {cmd}` is not a command"
