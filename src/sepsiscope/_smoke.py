"""Environment smoke checks shared by ``sepsiscope doctor`` and the test suite.

The key risk on macOS: scikit-learn wheels bundle their own ``libomp`` while
LightGBM loads Homebrew's. Two OpenMP runtimes in one process can abort with
"OMP: Error #15". So both libraries are exercised in ONE process here.
"""

from __future__ import annotations

import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

# Where LightGBM's macOS arm64 wheel looks for libomp (its LC_RPATH entries).
LIBOMP_CANDIDATES = (
    Path("/opt/homebrew/opt/libomp/lib/libomp.dylib"),
    Path("/opt/local/lib/libomp/libomp.dylib"),
)


@dataclass(frozen=True)
class SmokeResult:
    logreg_auc: float
    lgbm_auc: float
    max_contrib_error: float
    roundtrip_identical: bool


def libomp_status() -> str:
    """Human-readable libomp status; never prints user-specific paths."""
    if sys.platform != "darwin":
        return "n/a (non-macOS: LightGBM uses the system OpenMP runtime)"
    for candidate in LIBOMP_CANDIDATES:
        if candidate.exists():
            return f"found ({candidate.parent})"
    return "MISSING - run: brew install libomp"


def make_synthetic(
    n: int = 2000, n_features: int = 8, seed: int = 42, nan_rate: float = 0.1
) -> tuple[NDArray[np.float64], NDArray[np.int_]]:
    """Synthetic binary task with NaNs (like sparse ICU labs)."""
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, n_features))
    logits = 1.5 * x[:, 0] - 1.0 * x[:, 1] + 0.5 * x[:, 2] * x[:, 3]
    y = (rng.random(n) < 1.0 / (1.0 + np.exp(-logits))).astype(np.int_)
    x[rng.random(x.shape) < nan_rate] = np.nan
    return x, y


def run_openmp_smoke(seed: int = 42) -> SmokeResult:
    """Fit scikit-learn and LightGBM in the same process and check invariants."""
    import lightgbm as lgb
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.pipeline import make_pipeline

    x, y = make_synthetic(seed=seed)

    logreg = make_pipeline(SimpleImputer(), LogisticRegression(max_iter=1000))
    logreg.fit(x, y)
    logreg_auc = float(roc_auc_score(y, logreg.predict_proba(x)[:, 1]))

    booster = lgb.train(
        {"objective": "binary", "num_leaves": 15, "seed": seed, "verbose": -1},
        lgb.Dataset(x, label=y),
        num_boost_round=10,
    )
    raw = np.asarray(booster.predict(x, raw_score=True), dtype=np.float64)
    contrib = np.asarray(booster.predict(x, pred_contrib=True), dtype=np.float64)
    # SHAP-style additivity: per-feature contributions + bias == raw margin.
    max_contrib_error = float(np.max(np.abs(contrib.sum(axis=1) - raw)))
    lgbm_auc = float(roc_auc_score(y, raw))

    # Text-format save/load (never pickle) must reproduce predictions exactly.
    with tempfile.TemporaryDirectory() as tmp:
        model_path = Path(tmp) / "model.txt"
        booster.save_model(str(model_path))
        reloaded = lgb.Booster(model_file=str(model_path))
    raw_reloaded = np.asarray(reloaded.predict(x, raw_score=True), dtype=np.float64)
    roundtrip_identical = bool(np.array_equal(raw, raw_reloaded))

    return SmokeResult(logreg_auc, lgbm_auc, max_contrib_error, roundtrip_identical)
