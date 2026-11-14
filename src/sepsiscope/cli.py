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

app = typer.Typer(
    help="SepsiScope research prototype. Not for clinical use.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,  # plain tracebacks, scrubbed of personal paths
)


@app.callback()
def _setup() -> None:
    """Rewrite personal paths in log records and error tracebacks (B6)."""
    from sepsiscope.logscrub import install

    install()


data_app = typer.Typer(help="Dataset commands.", no_args_is_help=True)
app.add_typer(data_app, name="data")
features_app = typer.Typer(help="Feature commands.", no_args_is_help=True)
app.add_typer(features_app, name="features")
demo_app = typer.Typer(help="Local demo commands.", no_args_is_help=True)
app.add_typer(demo_app, name="demo")

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
    # OS family and CPU architecture only: no OS version, hostname (platform.node()) or model.
    typer.echo(f"platform        {platform.system()} {platform.machine()}")
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


@data_app.command("build")
def data_build() -> None:
    """Build the raw and clean Parquet tables, validate both, write the cleaning report."""
    from sepsiscope.config import load_config
    from sepsiscope.data.pipeline import build_all
    from sepsiscope.data.schema import DataSchemaError

    cfg = load_config()
    try:
        result = build_all(
            _raw_root(), REPO_ROOT / cfg.paths.data_dir, REPO_ROOT / cfg.paths.reports_dir
        )
    except DataSchemaError as exc:
        typer.echo(f"build FAILED schema validation: {str(exc)[:500]}")
        raise typer.Exit(code=1) from exc
    typer.echo(f"rows                  {result.rows:,}")
    typer.echo(f"patients              {result.patients:,}")
    typer.echo(f"raw parquet           {result.raw_path.relative_to(REPO_ROOT)} (schema OK)")
    typer.echo(f"clean parquet         {result.clean_path.relative_to(REPO_ROOT)} (schema OK)")
    typer.echo(f"values set to missing {result.values_set_to_missing:,}")
    typer.echo(f"cleaning report       {result.report_path.relative_to(REPO_ROOT)}")


@data_app.command("splits")
def data_splits() -> None:
    """Write the patient-level 60/20/20 stratified split files for hospitals A and B."""
    from sepsiscope.config import load_config
    from sepsiscope.data.pipeline import write_splits

    cfg = load_config()
    documents = write_splits(
        REPO_ROOT / cfg.paths.data_dir, REPO_ROOT / cfg.paths.splits_dir, cfg.seed
    )
    for hospital, document in documents.items():
        counts = document["counts"]
        assert isinstance(counts, dict)
        for part, c in counts.items():
            rate = c["septic"] / c["patients"]
            typer.echo(
                f"{hospital} {part:<12} patients {c['patients']:>6,}  "
                f"septic {c['septic']:>5,}  rate {rate:.4f}"
            )


@features_app.command("build")
def features_build() -> None:
    """Build causal hourly features per hospital (data/processed) and the feature schema."""
    from sepsiscope.config import load_config
    from sepsiscope.features.pipeline import build_features

    cfg = load_config()
    results = build_features(
        REPO_ROOT / cfg.paths.data_dir, REPO_ROOT / cfg.paths.reports_dir, cfg.features
    )
    for r in results:
        typer.echo(
            f"{r.hospital} rows {r.rows:>9,}  patients {r.patients:>6,}  "
            f"features {r.features}  {r.path.relative_to(REPO_ROOT)}"
        )


@app.command()
def tune(
    direction: str = typer.Option(..., help="A2B or B2A."),
) -> None:
    """Tune LightGBM per ADR 0021 (resumable); then fit the final model. Exit 3 = 6 h guard."""
    from sepsiscope.config import load_config
    from sepsiscope.evaluation.run import DIRECTIONS
    from sepsiscope.models import tuning
    from sepsiscope.models.pipeline import train_direction
    from sepsiscope.tracking import log_run

    if direction not in DIRECTIONS:
        typer.echo("give --direction {A2B,B2A}")
        raise typer.Exit(code=2)
    cfg = load_config()
    mlruns = REPO_ROOT / cfg.paths.mlruns_dir
    store = mlruns / tuning.STORE_SUBDIR
    tuning.add_log_file(store / "tuning.log")
    data = tuning.load_training(
        direction, REPO_ROOT / cfg.paths.data_dir, REPO_ROOT / cfg.paths.splits_dir
    )
    result_path = REPO_ROOT / cfg.paths.reports_dir / "tuning" / f"lgbm_{direction}.json"
    outcome = tuning.tune(data, direction, store, result_path)
    del data
    if outcome.state == "guard_exit":
        typer.echo(f"{direction} guard exit after {outcome.completed_trials} trials")
        raise typer.Exit(code=tuning.GUARD_EXIT_CODE)
    assert outcome.best_params is not None and outcome.median_rounds is not None
    r = train_direction(
        direction,
        cfg,
        REPO_ROOT / cfg.paths.data_dir,
        REPO_ROOT / cfg.paths.splits_dir,
        REPO_ROOT / cfg.paths.models_dir,
        tuning.final_tunable(outcome.best_params),
        outcome.median_rounds,
    )
    log_run(
        mlruns,
        run_name=f"tune_lgbm_{direction}",
        step="B2-tune",
        params={**tuning.final_tunable(outcome.best_params), "direction": direction},
        metrics={
            "best_mean_auprc": float(outcome.best_value or 0.0),
            "completed_trials": outcome.completed_trials,
            "final_trees": r.num_trees,
        },
    )
    typer.echo(
        f"{direction} finished: trials {outcome.completed_trials}, best mean AUPRC "
        f"{outcome.best_value:.4f}, final trees {r.num_trees}, resumed {outcome.resumed}"
    )


@app.command()
def ablations() -> None:
    """B5: build the ablation features, run the 4 ablations both ways, write drift."""
    from sepsiscope.config import load_config
    from sepsiscope.evaluation import ablation
    from sepsiscope.features.pipeline import build_ablation_features

    cfg = load_config()
    data_dir = REPO_ROOT / cfg.paths.data_dir
    for r in build_ablation_features(data_dir, cfg.features):
        typer.echo(f"{r.hospital} ablation features {r.features}  {r.path.relative_to(REPO_ROOT)}")
    reports = REPO_ROOT / cfg.paths.reports_dir
    written = ablation.run(
        cfg,
        data_dir,
        REPO_ROOT / cfg.paths.splits_dir,
        reports / "results",
        reports / "tuning",
        REPO_ROOT / cfg.paths.models_dir,
    )
    for path in written:
        typer.echo(f"wrote {path.relative_to(REPO_ROOT)}")


@demo_app.command("build")
def demo_build() -> None:
    """Precompute the demo patients (B2A, 6 held-out hospital-A patients) into data/demo/."""
    from sepsiscope.api.demo import build
    from sepsiscope.config import load_config

    cfg = load_config()
    out = build(
        cfg,
        REPO_ROOT / cfg.paths.data_dir,
        REPO_ROOT / cfg.paths.models_dir,
        REPO_ROOT / cfg.paths.reports_dir / "results",
    )
    typer.echo(f"wrote {out.relative_to(REPO_ROOT)}")


@demo_app.command("serve")
def demo_serve() -> None:
    """Serve the demo API on 127.0.0.1 only (start it from your own terminal)."""
    import uvicorn

    from sepsiscope.api.app import create_app
    from sepsiscope.api.demo import DEMO_FILE
    from sepsiscope.config import load_config

    cfg = load_config()
    app_ = create_app(REPO_ROOT / cfg.paths.data_dir / DEMO_FILE)
    uvicorn.run(app_, host=cfg.api.host, port=cfg.api.port, log_level="warning")


@app.command()
def exploratory() -> None:
    """POST-HOC, EXPLORATORY: LightGBM with measurements per hour instead of counts."""
    from sepsiscope.config import load_config
    from sepsiscope.evaluation import exploratory as ex

    cfg = load_config()
    reports = REPO_ROOT / cfg.paths.reports_dir
    for path in ex.run(
        cfg,
        REPO_ROOT / cfg.paths.data_dir,
        REPO_ROOT / cfg.paths.splits_dir,
        reports / "results",
        reports / "tuning",
    ):
        typer.echo(f"wrote {path.relative_to(REPO_ROOT)}")


@app.command("privacy-audit")
def privacy_audit(
    strict: bool = typer.Option(
        True,
        "--strict/--no-strict",
        help="Fail on every finding (default). --no-strict lists findings that exist only in "
        "commits made before the UTC cutoff as known instead of failing.",
    ),
) -> None:
    """Scan tracked files, all of git history, messages, offsets and refs (masked output)."""
    from sepsiscope.audit.history import format_report, run_audit

    report = run_audit(REPO_ROOT)
    for line in format_report(report, strict=strict):
        typer.echo(line)
    if report.blocking(strict):
        raise typer.Exit(code=1)


@app.command()
def train(
    model: str = typer.Option("lgbm", help="Only lgbm (baselines are fitted inside evaluate)."),
    direction: str | None = typer.Option(None, help="A2B or B2A."),
    track: bool = typer.Option(True, "--track/--no-track", help="Log to the local MLflow DB."),
) -> None:
    """Train the LightGBM model on the source hospital's training split; save to models/."""
    from sepsiscope.config import load_config
    from sepsiscope.evaluation.run import DIRECTIONS
    from sepsiscope.models.pipeline import train_direction

    if model != "lgbm" or direction not in DIRECTIONS:
        typer.echo("give --model lgbm and --direction {A2B,B2A}")
        raise typer.Exit(code=2)
    from sepsiscope.models.tuning import tuned_settings

    cfg = load_config()
    tuned = tuned_settings(REPO_ROOT / cfg.paths.reports_dir / "tuning" / f"lgbm_{direction}.json")
    r = train_direction(
        direction,
        cfg,
        REPO_ROOT / cfg.paths.data_dir,
        REPO_ROOT / cfg.paths.splits_dir,
        REPO_ROOT / cfg.paths.models_dir,
        *(tuned if tuned else (None, None)),
    )
    typer.echo("parameters: " + ("tuned (reports/tuning)" if tuned else "LightGBM defaults"))
    typer.echo(
        f"{r.direction} trees {r.num_trees}  rows {r.train_rows:,}  patients {r.train_patients:,}  "
        f"fit {r.seconds:.1f} s  {r.folder.relative_to(REPO_ROOT)}"
    )
    if track:
        import json

        from sepsiscope.tracking import log_run

        info = json.loads((r.folder / "model.json").read_text(encoding="utf-8"))
        run_id = log_run(
            REPO_ROOT / cfg.paths.mlruns_dir,
            run_name=f"train_lgbm_{direction}",
            step="B1-train",
            params={**info["params"], "direction": direction, "data_sha256": info["data_sha256"]},
            metrics={
                "num_trees": r.num_trees,
                "train_rows": r.train_rows,
                "fit_seconds": r.seconds,
            },
        )
        typer.echo(f"tracked run {run_id} in the local MLflow DB")


@app.command()
def evaluate(
    model: str | None = typer.Option(
        None, help="news2 = modified NEWS2 (max 17), sirs, qsofa = modified qSOFA (max 2), lr."
    ),
    direction: str | None = typer.Option(None, help="A2B or B2A."),
    all_baselines: bool = typer.Option(False, "--all-baselines", help="4 baselines, both ways."),
    all_models: bool = typer.Option(
        False, "--all-models", help="Baselines + LightGBM (Platt, isotonic, raw), both ways."
    ),
) -> None:
    """Evaluate baselines under strict external validation; writes reports/results/."""
    from sepsiscope.config import load_config
    from sepsiscope.evaluation.run import ALL_MODELS, DIRECTIONS, MODELS, run

    if all_models:
        models, directions = list(ALL_MODELS), list(DIRECTIONS)
    elif all_baselines:
        models, directions = list(MODELS), list(DIRECTIONS)
    elif model in ALL_MODELS and direction in DIRECTIONS:
        models, directions = [model], [direction]
    else:
        typer.echo(
            "give --model {news2,sirs,qsofa,lr,lgbm,lgbm_isotonic,lgbm_raw} and --direction "
            "{A2B,B2A}, or --all-baselines / --all-models"
        )
        raise typer.Exit(code=2)
    cfg = load_config()
    reports = REPO_ROOT / cfg.paths.reports_dir
    written = run(
        models,
        directions,
        cfg,
        REPO_ROOT / cfg.paths.data_dir,
        REPO_ROOT / cfg.paths.splits_dir,
        reports / "results",
        REPO_ROOT / cfg.paths.models_dir,
        reports / "figures" / "results",
    )
    for path in written:
        typer.echo(f"wrote {path.relative_to(REPO_ROOT)}")


@app.command()
def report() -> None:
    """Build the report (later phase)."""
    typer.echo(NOT_IMPLEMENTED)
