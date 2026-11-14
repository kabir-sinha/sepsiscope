"""docs/tripod_ai.md maps every TRIPOD+AI item (checklist of 11 January 2024) exactly once."""

from __future__ import annotations

import re
from pathlib import Path

DOC = Path(__file__).resolve().parents[1] / "docs" / "tripod_ai.md"
ITEMS = (
    ["1", "2", "3a", "3b", "3c", "4", "5a", "5b", "6a", "6b", "6c", "7", "8a", "8b", "8c"]
    + ["9a", "9b", "9c", "10", "11"]
    + [f"12{c}" for c in "abcdefg"]
    + ["13", "14", "15", "16", "17"]
    + [f"18{c}" for c in "abcdef"]
    + ["19", "20a", "20b", "20c", "21", "22", "23a", "23b", "24", "25", "26", "27a", "27b", "27c"]
)
STATUS = re.compile(r"^(done|partly|n/a|not done)\b")


def _rows() -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for line in DOC.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 4 and re.fullmatch(r"\d{1,2}[a-g]?", cells[0]):
            assert cells[0] not in rows, f"item {cells[0]} listed twice"
            rows[cells[0]] = cells
    return rows


def test_every_item_has_exactly_one_row() -> None:
    assert len(ITEMS) == 52
    assert list(_rows()) == ITEMS


def test_every_row_has_a_place_and_a_status() -> None:
    for item, (_, topic, where, status) in _rows().items():
        assert topic and where, item
        assert STATUS.match(status), f"item {item}: status {status!r}"
