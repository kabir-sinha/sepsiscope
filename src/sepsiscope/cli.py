"""Command-line interface: ``uv run sepsiscope --help``."""

from __future__ import annotations

import os
import platform
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from pathlib import Path

import typer

from sepsiscope import __version__
from sepsiscope._privacy import TELEMETRY_ENV, telemetry_env_ok
from sepsiscope.config import REPO_ROOT

app = typer.Typer(help="SepsiScope research prototype. Not for clinical use.", no_args_is_help=True)
data_app = typer.Typer(help="Dataset commands.", no_args_is_help=True)
app.add_typer(data_app, name="data")

KEY_PACKAGES = (
    "numpy",
    "pandas",
    "scikit-learn",
    "lightgbm",
    "shap",
    "mlflow",
    "pydantic",
    "fastapi",
)

NOT_IMPLEMENTED = "not implemented in Phase 0"


def _describe_interpreter(executable: str) -> str:
    """Path relative to the repo if inside it, otherwise just 'system'.

    Not resolved: .venv/bin/python is a symlink to the base interpreter.
    """
    try:
        return str(Path(executable).absolute().relative_to(REPO_ROOT))
    except ValueError:
        return "system"


def _pkg(name: str) -> str:
    try:
        return pkg_version(name)
    except PackageNotFoundError:
        return "not installed"


@app.command()
def version() -> None:
    """Print the SepsiScope version."""
    typer.echo(__version__)


@app.command()
def doctor() -> None:
    """Check the environment. Prints nothing personal (no username, home path or email)."""
    from sepsiscope._smoke import libomp_status, run_openmp_smoke

    ok = True
    typer.echo(f"sepsiscope      {__version__}")
    typer.echo(f"python          {platform.python_version()}")
    typer.echo(f"interpreter     {_describe_interpreter(sys.executable)}")
    base = getattr(sys, "_base_executable", sys.executable)
    typer.echo(f"base python     {_describe_interpreter(base)}")
    # platform.platform() has OS/arch only; platform.node() (hostname) is never printed.
    typer.echo(f"platform        {platform.platform()}")
    for name in KEY_PACKAGES:
        typer.echo(f"{name:<15} {_pkg(name)}")

    omp = libomp_status()
    typer.echo(f"libomp          {omp}")
    ok &= not omp.startswith("MISSING")

    try:
        r = run_openmp_smoke()
        smoke_ok = r.max_contrib_error <= 1e-9 and r.roundtrip_identical
        typer.echo(
            f"openmp smoke    {'OK' if smoke_ok else 'FAIL'} "
            f"(logreg AUC {r.logreg_auc:.3f}, lightgbm AUC {r.lgbm_auc:.3f}, "
            f"contrib err {r.max_contrib_error:.1e}, text round-trip "
            f"{'identical' if r.roundtrip_identical else 'DIFFERENT'})"
        )
        ok &= smoke_ok
    except Exception as exc:  # pragma: no cover - only on a broken install
        typer.echo(f"openmp smoke    FAIL ({type(exc).__name__})")
        ok = False

    env_ok = telemetry_env_ok()
    import mlflow.telemetry

    client_off = mlflow.telemetry.get_telemetry_client() is None
    flags = ", ".join(f"{k}={os.environ.get(k, '<unset>')}" for k in TELEMETRY_ENV)
    typer.echo(f"telemetry       {'OFF' if env_ok and client_off else 'ON'} ({flags})")
    ok &= env_ok and client_off

    typer.echo("doctor          " + ("PASS" if ok else "FAIL"))
    if not ok:
        raise typer.Exit(code=1)


@data_app.command("download")
def data_download() -> None:
    """Download PhysioNet/CinC 2019 (Phase 1)."""
    typer.echo(NOT_IMPLEMENTED)


@app.command()
def train() -> None:
    """Train models (later phase)."""
    typer.echo(NOT_IMPLEMENTED)


@app.command()
def evaluate() -> None:
    """Evaluate models against the frozen protocol (later phase)."""
    typer.echo(NOT_IMPLEMENTED)


@app.command()
def report() -> None:
    """Build the report (later phase)."""
    typer.echo(NOT_IMPLEMENTED)
