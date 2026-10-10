"""Splits: deterministic, disjoint, complete, right proportions, septic rate preserved."""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sepsiscope.data.splits import (
    FRACTIONS,
    PARTS,
    largest_remainder,
    read_split,
    split_document,
    split_patients,
    write_split,
)


def _cohort(n: int, n_septic: int) -> dict[str, bool]:
    return {f"p{i:06d}": i < n_septic for i in range(n)}


def test_largest_remainder_examples() -> None:
    assert largest_remainder(10) == [6, 2, 2]
    assert largest_remainder(20_336) == [12_202, 4_067, 4_067]
    assert largest_remainder(1_790) == [1_074, 358, 358]
    assert largest_remainder(1) == [1, 0, 0]


@given(st.integers(min_value=0, max_value=50_000))
def test_largest_remainder_is_within_one(n: int) -> None:
    counts = largest_remainder(n)
    assert sum(counts) == n
    assert all(abs(c - n * f) < 1 for c, f in zip(counts, FRACTIONS, strict=True))


@given(st.integers(min_value=30, max_value=3_000), st.floats(min_value=0.02, max_value=0.5))
def test_split_properties(n: int, septic_share: float) -> None:
    cohort = _cohort(n, max(1, int(n * septic_share)))
    parts = split_patients(cohort, seed=42)
    everyone = [pid for name in PARTS for pid in parts[name]]
    assert len(everyone) == len(set(everyone)) == n  # disjoint and complete
    assert set(everyone) == set(cohort)
    n_septic = sum(cohort.values())
    for name, fraction in zip(PARTS, FRACTIONS, strict=True):
        assert abs(len(parts[name]) - n * fraction) < 1  # totals within 1 patient
        septic_here = sum(cohort[p] for p in parts[name])
        assert abs(septic_here - n_septic * fraction) < 1  # septic count within 1 patient
        assert parts[name] == sorted(parts[name])


def test_split_is_deterministic_and_seed_dependent() -> None:
    cohort = _cohort(1_000, 80)
    assert split_patients(cohort, seed=42) == split_patients(cohort, seed=42)
    assert split_patients(dict(reversed(cohort.items())), seed=42) == split_patients(cohort, 42)
    assert split_patients(cohort, seed=43) != split_patients(cohort, seed=42)


def test_septic_rate_is_preserved() -> None:
    cohort = _cohort(20_336, 1_790)
    parts = split_patients(cohort, seed=42)
    overall = 1_790 / 20_336
    for name in PARTS:
        rate = sum(cohort[p] for p in parts[name]) / len(parts[name])
        assert abs(rate - overall) < 0.001


def test_bad_fractions_are_rejected() -> None:
    with pytest.raises(ValueError, match="sum to 1"):
        split_patients(_cohort(10, 2), seed=42, fractions=(0.5, 0.2, 0.2))


def test_document_round_trip(tmp_path: Path) -> None:
    cohort = _cohort(50, 5)
    document = split_document("A", cohort, seed=42)
    assert document["counts"] == {
        "train": {"patients": 30, "septic": 3},
        "val": {"patients": 10, "septic": 1},
        "calibration": {"patients": 10, "septic": 1},
    }
    path = tmp_path / "splits" / "hospital_A.json"
    write_split(path, document)
    assert read_split(path) == document
    assert set(document) >= {"hospital", "seed", "fractions", "stratified_by", *PARTS}
