"""C1 shortcut check on synthetic data: bands, subset utility, collapse rule (ADR 0024)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from sepsiscope.data.io import LABEL
from sepsiscope.evaluation import bands
from sepsiscope.evaluation import metrics as m
from sepsiscope.evaluation.run import Cohort


def test_band_edges_are_half_open() -> None:
    iculos = np.array([1, 23, 24, 47, 48, 95, 96, 335])
    assert bands.band_of(iculos).tolist() == [0, 0, 1, 1, 2, 2, 3, 3]
    with pytest.raises(ValueError):
        bands.band_of(np.array([-1]))


def _cohort(seed: int = 0, n: int = 60) -> tuple[Cohort, np.ndarray]:
    """Patients of 20-150 h; a third become septic late in the stay."""
    rng = np.random.default_rng(seed)
    rows = []
    for k in range(n):
        hours = int(rng.integers(20, 150))
        onset = int(rng.integers(5, hours)) if k % 3 == 0 else hours + 100
        rows += [{"pid": f"x{k:04d}", "t": t, LABEL: int(t >= onset)} for t in range(hours)]
    frame = pd.DataFrame(rows)
    cohort = Cohort.of(frame)
    return cohort, frame["t"].to_numpy() + 1  # ICULOS starting at 1


def test_band_utilities_add_up_to_the_total() -> None:
    cohort, iculos = _cohort()
    rng = np.random.default_rng(1)
    alerts = rng.random(len(cohort.labels)) < 0.1
    band = bands.band_of(iculos)
    full_ref = m.reference_utilities(cohort.labels, cohort.patient)
    everything = np.ones(len(band), dtype=bool)
    assert np.allclose(
        m.subset_reference(cohort.labels, cohort.patient, everything)[0], full_ref[0]
    )
    total = m.utility_parts(cohort.labels, alerts, cohort.patient, full_ref)
    obs = best = 0.0
    for i in range(len(bands.BANDS)):
        keep = band == i
        ref = m.subset_reference(cohort.labels, cohort.patient, keep)
        part = m.utility_parts(cohort.labels, alerts & keep, cohort.patient, ref)
        obs += float(np.sum(part.observed - part.inaction))
        best += float(np.sum(part.best - part.inaction))
    assert obs == pytest.approx(float(np.sum(total.observed - total.inaction)))
    assert best == pytest.approx(float(np.sum(total.best - total.inaction)))


def _model_doc(cohort: Cohort, iculos: np.ndarray, scores: np.ndarray) -> dict[str, object]:
    weights = m.bootstrap_weights(cohort.n_patients, 50, 42)
    alerts = scores >= np.quantile(scores, 0.95)
    band = bands.band_of(iculos)
    every = np.ones(len(band), dtype=bool)
    doc: dict[str, object] = {"overall": bands._block(cohort, scores, alerts, every, weights, {})}
    doc["bands"] = {
        name: bands._block(cohort, scores, alerts, band == i, weights, {})
        for i, (name, _, _) in enumerate(bands.BANDS)
    }
    return doc


def test_time_only_score_is_flagged_as_collapse() -> None:
    cohort, iculos = _cohort(seed=2, n=200)
    rng = np.random.default_rng(3)
    # Ranks hours by ICU time only: separates well overall (sepsis comes late), not within bands.
    scores = iculos + rng.random(len(iculos)) * 1e-3
    doc = _model_doc(cohort, iculos, scores)
    assert doc["overall"]["point"]["auroc"] > 0.7  # type: ignore[index]
    check = bands.collapse_check(doc)
    assert check["collapse"] is True


def test_informative_score_does_not_collapse() -> None:
    cohort, iculos = _cohort(seed=4, n=200)
    rng = np.random.default_rng(5)
    scores = cohort.labels * 2.0 + rng.normal(0, 1, len(iculos))
    check = bands.collapse_check(_model_doc(cohort, iculos, scores))
    assert check == {"collapse": False, "flagged_bands": []}
