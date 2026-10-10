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


def _raw_root() -> Path:
    from sepsiscope.config import load_config

    return REPO_ROOT / load_config().paths.data_dir / "raw"


@data_app.command("download")
def data_download() -> None:
    """Download PhysioNet/CinC 2019 from the official public S3 bucket (resumable)."""
    from sepsiscope.data.download import DownloadError, download_all

    typer.echo("listing and downloading from the official PhysioNet S3 bucket ...")
    try:
        report, manifest_sha = download_all(_raw_root())
    except DownloadError as exc:
        typer.echo(f"download FAILED: {exc}")
        raise typer.Exit(code=1) from exc
    typer.echo(f"listed files        {report.listed}")
    typer.echo(f"downloaded now      {report.downloaded}")
    typer.echo(f"already present     {report.already_present}")
    typer.echo(f"other keys ignored  {len(report.skipped_keys)}")
    typer.echo(f"not MD5-verifiable  {len(report.unverifiable)}")
    typer.echo(f"seconds             {report.seconds:.1f}")
    typer.echo(f"manifest sha256     {manifest_sha}")


@data_app.command("verify")
def data_verify() -> None:
    """Recompute the dataset fingerprint from the raw files; fail on any mismatch."""
    from sepsiscope.data.fingerprint import compare, compute_fingerprints
    from sepsiscope.data.io import RawDataError

    try:
        observed = compute_fingerprints(_raw_root())
    except RawDataError as exc:
        typer.echo(f"verify FAILED: {exc}")
        raise typer.Exit(code=1) from exc
    checks = compare(observed)
    typer.echo(f"{'scope':<5} {'check':<24} {'expected':>10} {'observed':>10}  result")
    for c in checks:
        result = "ok" if c.ok else "MISMATCH"
        typer.echo(f"{c.scope:<5} {c.name:<24} {c.expected:>10,} {c.observed:>10,}  {result}")
    for scope in ("A", "B"):
        fp = observed[scope]
        typer.echo(f"{scope:<5} unit_missing_share       {fp.unit_missing / fp.rows:>21.4f}  info")
    failed = [c for c in checks if not c.ok]
    typer.echo("fingerprint     " + ("PASS" if not failed else f"FAIL ({len(failed)} mismatches)"))
    if failed:
        raise typer.Exit(code=1)


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
