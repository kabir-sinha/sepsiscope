"""Phase 0 smoke tests: imports, OpenMP coexistence, explainability, model I/O."""

from __future__ import annotations

import importlib

import numpy as np
import pytest

from sepsiscope._smoke import libomp_status, make_synthetic, run_openmp_smoke

RUNTIME_MODULES = [
    "numpy",
    "pandas",
    "pyarrow",
    "duckdb",
    "sklearn",
    "lightgbm",
    "shap",
    "dcurves",
    "optuna",
    "mlflow",
    "pandera",
    "fastapi",
    "pydantic",
    "uvicorn",
    "typer",
    "httpx",
    "yaml",
    "matplotlib",
]


@pytest.mark.parametrize("module", RUNTIME_MODULES)
def test_runtime_imports(module: str) -> None:
    importlib.import_module(module)


def test_package_imports() -> None:
    for name in ["sepsiscope", "sepsiscope.cli", "sepsiscope.config"] + [
        f"sepsiscope.{sub}" for sub in ("data", "features", "models", "evaluation", "trust", "api")
    ]:
        importlib.import_module(name)


def test_synthetic_data_has_nans() -> None:
    x, y = make_synthetic()
    assert x.shape == (2000, 8)
    assert np.isnan(x).any()
    assert set(np.unique(y)) == {0, 1}


def test_libomp_found() -> None:
    assert not libomp_status().startswith("MISSING")


def test_sklearn_and_lightgbm_in_one_process() -> None:
    """Both OpenMP users fit in this process; an OMP clash would abort pytest."""
    result = run_openmp_smoke()
    assert result.logreg_auc > 0.7
    assert result.lgbm_auc > 0.7


def test_pred_contrib_sums_to_raw_score() -> None:
    assert run_openmp_smoke().max_contrib_error <= 1e-9


def test_text_model_roundtrip_identical() -> None:
    assert run_openmp_smoke().roundtrip_identical
