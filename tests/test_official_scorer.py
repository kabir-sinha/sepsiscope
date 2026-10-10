"""The vendored official scorer must be unmodified and reproduce its documented example."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from sepsiscope.config import REPO_ROOT

SCORER = REPO_ROOT / "third_party" / "physionet_eval" / "evaluate_sepsis_score.py"
LICENCE = SCORER.with_name("LICENSE.txt")
SCORER_SHA256 = "26b8b26267ed32e8b7a7a27e45201cfc8c6640e717ba4cdc1f452b32f12b99e5"
LICENCE_SHA256 = "abc6e0bb01abee7aa79502c8c0a344f55ad2826e5ba5b97e73786bd2104859b6"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def scorer() -> ModuleType:
    spec = importlib.util.spec_from_file_location("official_scorer", SCORER)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_vendored_files_are_byte_identical_to_upstream() -> None:
    assert _sha256(SCORER) == SCORER_SHA256
    assert _sha256(LICENCE) == LICENCE_SHA256
    assert "BSD 2-Clause License" in LICENCE.read_text(encoding="utf-8")


def test_readme_records_the_same_hashes() -> None:
    readme = SCORER.with_name("README.md").read_text(encoding="utf-8")
    assert SCORER_SHA256 in readme
    assert LICENCE_SHA256 in readme


def test_documented_example_is_reproduced(scorer: ModuleType) -> None:
    labels = [0, 0, 0, 0, 1, 1]
    predictions = [0, 0, 1, 1, 1, 1]
    assert scorer.compute_prediction_utility(labels, predictions) == 3.388888888888889


def test_default_parameters_match_the_protocol(scorer: ModuleType) -> None:
    defaults = scorer.compute_prediction_utility.__defaults__
    # dt_early, dt_optimal, dt_late, max_u_tp, min_u_fn, u_fp, u_tn, check_errors
    assert defaults == (-12, -6, 3.0, 1, -2, -0.05, 0, True)
