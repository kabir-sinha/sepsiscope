"""Fingerprint counts on a synthetic fixture, and the real data when present."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import WritePatient

from sepsiscope.config import REPO_ROOT, load_config
from sepsiscope.data.fingerprint import EXPECTED, compare, compute_fingerprints
from sepsiscope.data.io import RawDataError, iter_patient_files, read_psv, training_dir


def test_fingerprint_on_tiny_dataset(tiny_dataset: Path) -> None:
    fp = compute_fingerprints(tiny_dataset, workers=2)
    a, b, both = fp["A"], fp["B"], fp["A+B"]
    assert (a.files, a.rows, a.septic_patients, a.positive_rows) == (3, 12, 2, 6)
    assert (a.positive_from_row0, a.max_rows, a.iculos_starts_at_1) == (1, 5, 2)
    assert (b.files, b.rows, b.septic_patients, b.positive_rows) == (2, 8, 1, 1)
    assert (b.fio2_present, b.fio2_outside) == (2, 1)
    assert (b.unit_missing, b.hospadmtime_missing) == (2, 1)
    assert both.files == 5
    assert both.rows == 20
    assert both.max_rows == 6
    assert both.non_monotone_patients == 0
    assert both.iculos_step_violations == 0
    assert both.unit_both_one == 0
    assert both.unit_missing_mismatch == 0
    assert both.gender_other == 0


def test_fingerprint_detects_violations(raw_root: Path, write_patient: WritePatient) -> None:
    write_patient("A", 1, [0, 1, 0])  # label goes back to 0
    write_patient("A", 2, [0, 0, 0], overrides={"ICULOS": [1, 2, 4]})  # ICULOS jumps
    write_patient("B", 1, [0, 0], overrides={"Unit1": [1, "NaN"], "Unit2": [1, 0]})
    write_patient("B", 2, [0, 0], overrides={"Gender": [2, "NaN"]})
    both = compute_fingerprints(raw_root, workers=1)["A+B"]
    assert both.non_monotone_patients == 1
    assert both.iculos_step_violations == 1
    assert both.unit_both_one == 1
    assert both.unit_missing_mismatch == 1
    assert both.gender_other == 2


def test_compare_flags_mismatch(tiny_dataset: Path) -> None:
    observed = compute_fingerprints(tiny_dataset, workers=1)
    checks = compare(observed, {"A": {"files": 3, "rows": 999}})
    assert [c.ok for c in checks] == [True, False]


def test_bad_header_is_rejected(raw_root: Path) -> None:
    path = training_dir(raw_root) / "training_setA" / "p000001.psv"
    path.write_text("HR|SepsisLabel\n80|0\n", encoding="utf-8")
    with pytest.raises(RawDataError, match="header"):
        read_psv(path)


def test_missing_folder_is_reported(tmp_path: Path) -> None:
    with pytest.raises(RawDataError, match="download"):
        list(iter_patient_files(tmp_path))


@pytest.mark.data
def test_real_data_fingerprint_matches_protocol() -> None:
    """Runs only when the real dataset has been downloaded (never in CI)."""
    raw = REPO_ROOT / load_config().paths.data_dir / "raw"
    if not (training_dir(raw) / "training_setA").is_dir():
        pytest.skip("real PhysioNet data not present")
    checks = compare(compute_fingerprints(raw), EXPECTED)
    assert [c for c in checks if not c.ok] == []
