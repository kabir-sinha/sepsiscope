"""EDA summaries on the synthetic fixture, and reproducible metadata-free figures."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sepsiscope.config import REPO_ROOT
from sepsiscope.data import eda, figures
from sepsiscope.data.build import build_raw_table
from sepsiscope.data.pipeline import to_frame


@pytest.fixture
def frame(tiny_dataset: Path) -> pd.DataFrame:
    return to_frame(build_raw_table(tiny_dataset, workers=1))


def test_js_divergence_bounds_and_symmetry() -> None:
    rng = np.random.default_rng(0)
    a, b = rng.normal(0, 1, 5_000), rng.normal(0.5, 1, 5_000)
    assert eda.js_divergence(a, a) == 0.0
    assert eda.js_divergence(np.zeros(100), np.ones(100)) == pytest.approx(1.0)
    assert 0.0 < eda.js_divergence(a, b) < 1.0
    assert eda.js_divergence(a, b) == pytest.approx(eda.js_divergence(b, a))
    assert np.isnan(eda.js_divergence(np.array([]), a))
    assert eda.js_divergence(np.ones(10), np.ones(20)) == 0.0


def test_patient_and_cohort_tables(frame: pd.DataFrame) -> None:
    patients = eda.patient_table(frame)
    assert len(patients) == 5
    assert patients.loc[
        "p000002", ["rows", "first_positive_t", "rows_from_first_positive"]
    ].tolist() == [5, 2, 3]
    assert patients.loc["p000003", "first_positive_t"] == 0
    assert patients.loc["p000003", "first_positive_iculos"] == 4
    assert np.isnan(patients.loc["p000001", "first_positive_t"])
    cohort = eda.cohort_table(patients)
    assert cohort.loc["patients"].tolist() == [3, 2]
    assert cohort.loc["septic patients"].tolist() == [2, 1]
    assert cohort.loc["positive rows", "A"] == 6
    assert cohort.loc["septic and positive from row 0", "A"] == 1
    assert cohort.loc["positive rows (%)", "A"] == pytest.approx(50.0)


def test_missingness_and_frequency(frame: pd.DataFrame) -> None:
    missing = eda.missingness(frame)
    assert list(missing.columns) == ["A", "B"]
    assert len(missing) == 40
    assert missing.loc["HR", "A"] == 0.0
    assert missing.loc["Lactate", "A"] == 1.0
    assert missing.loc["FiO2", "B"] == pytest.approx(6 / 8)
    assert eda.measurements_per_patient_day(frame).loc["HR", "A"] == pytest.approx(24.0)
    assert eda.patients_ever_measured(frame).loc["FiO2", "B"] == pytest.approx(0.5)


def test_hospital_shift_and_unit_fingerprint(frame: pd.DataFrame) -> None:
    shift = eda.hospital_shift(frame, bins=5)
    assert len(shift) == 40
    assert shift.loc["Temp", "js_values"] == 0.0  # identical constant in both hospitals
    assert shift.loc["Unit1", "missing_gap"] == pytest.approx(2 / 8)
    units = eda.unit_fingerprint(frame)
    assert units.loc["A", "Unit1 = 1"] == 1.0
    assert units.loc["B", "missing"] == pytest.approx(2 / 8)
    assert 0.5 <= eda.unit_rule_accuracy(frame) <= 1.0


def _all_figures(frame: pd.DataFrame, out: Path) -> list[Path]:
    patients = eda.patient_table(frame)
    return [
        figures.save(figures.missingness_figure(eda.missingness(frame)), out / "missingness.png"),
        figures.save(
            figures.frequency_figure(eda.measurements_per_patient_day(frame).replace(0, np.nan)),
            out / "frequency.png",
        ),
        figures.save(figures.stay_length_figure(patients), out / "stay.png"),
        figures.save(figures.label_timing_figure(patients), out / "timing.png"),
        figures.save(figures.shift_figure(eda.hospital_shift(frame, bins=5)), out / "shift.png"),
        figures.save(figures.unit_figure(eda.unit_fingerprint(frame)), out / "units.png"),
    ]


def test_figures_are_byte_identical_and_have_no_metadata(
    frame: pd.DataFrame, tmp_path: Path
) -> None:
    first = _all_figures(frame, tmp_path / "one")
    second = _all_figures(frame, tmp_path / "two")
    for a, b in zip(first, second, strict=True):
        assert a.read_bytes() == b.read_bytes(), a.name
        chunks = figures.png_chunk_types(a)
        assert chunks[0] == b"IHDR"
        assert chunks[-1] == b"IEND"
        assert not figures.FORBIDDEN_PNG_CHUNKS & set(chunks), a.name


def test_png_chunk_reader_sees_text_chunks(tmp_path: Path) -> None:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(1, 1))
    ax.plot([0, 1])
    path = tmp_path / "with_meta.png"
    fig.savefig(path)  # matplotlib's default adds a "Software" text chunk
    plt.close(fig)
    assert b"tEXt" in figures.png_chunk_types(path)
    with pytest.raises(ValueError, match="not a PNG"):
        (tmp_path / "x.png").write_bytes(b"hello")
        figures.png_chunk_types(tmp_path / "x.png")


def test_committed_pngs_have_no_text_exif_or_time_chunks() -> None:
    pngs = sorted((REPO_ROOT / "reports" / "figures").glob("*.png"))
    pngs += sorted((REPO_ROOT / "web").glob("src/**/*.png"))
    assert pngs, "expected at least one PNG in the repository"
    for path in pngs:
        bad = figures.FORBIDDEN_PNG_CHUNKS & set(figures.png_chunk_types(path))
        assert not bad, f"{path.name} has metadata chunks {sorted(bad)}"
