"""Patient-level train / validation / calibration splits inside one hospital.

60 / 20 / 20 by patient, seed 42, stratified by whether the patient is ever septic
(ADR 0013). No patient appears in two parts. The other hospital is never split: it
is the external test set.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np

PARTS: tuple[str, ...] = ("train", "val", "calibration")
FRACTIONS: tuple[float, ...] = (0.6, 0.2, 0.2)


def largest_remainder(n: int, fractions: Sequence[float] = FRACTIONS) -> list[int]:
    """Split ``n`` into whole counts closest to ``n * fractions`` that sum to ``n``."""
    quotas = [n * f for f in fractions]
    counts = [int(q) for q in quotas]
    leftovers = n - sum(counts)
    # Hand out the remaining patients to the largest fractional parts (ties: first part).
    order = sorted(range(len(quotas)), key=lambda i: (-(quotas[i] - counts[i]), i))
    for i in order[:leftovers]:
        counts[i] += 1
    return counts


def split_patients(
    septic_by_pid: Mapping[str, bool], seed: int, fractions: Sequence[float] = FRACTIONS
) -> dict[str, list[str]]:
    """Deterministic stratified split. Returns sorted patient IDs per part."""
    if abs(sum(fractions) - 1.0) > 1e-9 or len(fractions) != len(PARTS):
        raise ValueError("fractions must have three values that sum to 1")
    septic = sorted(pid for pid, flag in septic_by_pid.items() if flag)
    others = sorted(pid for pid, flag in septic_by_pid.items() if not flag)
    total_counts = largest_remainder(len(septic) + len(others), fractions)
    septic_counts = largest_remainder(len(septic), fractions)
    other_counts = [t - s for t, s in zip(total_counts, septic_counts, strict=True)]
    if min(other_counts) < 0:  # only possible for tiny inputs
        raise ValueError("too few non-septic patients to split")

    rng = np.random.default_rng(seed)
    parts: dict[str, list[str]] = {name: [] for name in PARTS}
    for pids, counts in ((septic, septic_counts), (others, other_counts)):
        shuffled = [pids[i] for i in rng.permutation(len(pids))]
        start = 0
        for name, count in zip(PARTS, counts, strict=True):
            parts[name].extend(shuffled[start : start + count])
            start += count
    return {name: sorted(pids) for name, pids in parts.items()}


def split_document(
    hospital: str, septic_by_pid: Mapping[str, bool], seed: int
) -> dict[str, object]:
    parts = split_patients(septic_by_pid, seed)
    return {
        "dataset": "PhysioNet/CinC Challenge 2019 v1.0.0",
        "hospital": hospital,
        "seed": seed,
        "fractions": dict(zip(PARTS, FRACTIONS, strict=True)),
        "stratified_by": "patient ever septic (max SepsisLabel == 1)",
        "counts": {
            name: {
                "patients": len(pids),
                "septic": sum(1 for p in pids if septic_by_pid[p]),
            }
            for name, pids in parts.items()
        },
        **parts,
    }


def write_split(path: Path, document: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")


def read_split(path: Path) -> dict[str, object]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"{path.name}: split file must contain a JSON object")
    return loaded
