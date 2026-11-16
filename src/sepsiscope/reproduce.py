"""`sepsiscope reproduce`: every result from the verified dataset, in one command.

Runs the pipeline steps in order, each as its own process (one step's memory is freed
before the next), and stops at the first step that fails, returning its exit code.
LightGBM uses the committed tuned parameters (``reports/tuning/``); ``--retune`` repeats
the tuning first (about 30 minutes; a resumed tuning run is not byte-identical, ADR 0022).
The dataset download is not a step: it is the only command that uses the network and is
run on its own first (``sepsiscope data download``).
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

DIRECTIONS = ("A2B", "B2A")

BEFORE_MODELS: tuple[tuple[str, ...], ...] = (
    ("data", "verify"),
    ("data", "build"),
    ("data", "splits"),
    ("features", "build"),
)
AFTER_MODELS: tuple[tuple[str, ...], ...] = (
    ("evaluate", "--all-models"),
    ("ablations",),
    ("exploratory",),
    ("analyses", "bands"),
    ("analyses", "deferral"),
    ("analyses", "budgets"),
    ("analyses", "alert-quality"),
    ("demo", "build"),
)


def steps(retune: bool = False) -> list[tuple[str, ...]]:
    """The commands in order (arguments after ``sepsiscope``)."""
    out = list(BEFORE_MODELS)
    if retune:
        out += [("tune", "--direction", d) for d in DIRECTIONS]
    out += [("train", "--direction", d, "--no-track") for d in DIRECTIONS]
    return out + list(AFTER_MODELS)


def _executable() -> str:
    """The ``sepsiscope`` script of the running environment (never a global one)."""
    return str(Path(sys.executable).parent / "sepsiscope")


def run(
    commands: Sequence[tuple[str, ...]],
    runner: Callable[[list[str]], int] | None = None,
    echo: Callable[[str], None] = print,
) -> int:
    """Run each command; stop at the first non-zero exit code and return it."""
    exe = _executable()

    def default(argv: list[str]) -> int:
        # fixed executable (this environment's script) and arguments from this module
        return subprocess.run(argv, check=False).returncode  # noqa: S603

    call = runner or default
    for i, args in enumerate(commands, 1):
        echo(f"[{i}/{len(commands)}] sepsiscope {' '.join(args)}")
        code = call([exe, *args])
        if code != 0:
            echo(f"stopped: step {i} exited with {code}")
            return code
    echo("all steps finished")
    return 0
