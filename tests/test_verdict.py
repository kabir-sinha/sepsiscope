"""Verdict rules for the demo, including the window edges at exactly 12 h and 0 h."""

from __future__ import annotations

import pytest

from sepsiscope.api.verdict import RULES, banner, onset_hour, verdict


def test_onset_is_first_septic_hour_plus_6() -> None:
    assert onset_hour(10) == 16
    assert onset_hour(0) == 6  # septic on admission
    assert onset_hour(None) is None


@pytest.mark.parametrize(
    ("alerts", "outcome", "lead"),
    [
        ([8], "warned", 12),  # exactly 12 h before onset 20: inside the window
        ([7], "too_early_only", None),  # 13 h before: outside
        ([20], "warned", 0),  # exactly at onset: inside, lead 0
        ([21], "too_late_only", None),  # 1 h after onset
        ([3, 15, 22], "warned", 5),  # first alert in the window decides the lead
        ([], "never_warned", None),
    ],
)
def test_septic_window_edges(alerts: list[int], outcome: str, lead: int | None) -> None:
    v = verdict(alerts, onset=20)
    assert v.outcome == outcome and v.lead_hours == lead
    assert v.false_alarm_hours == 0


def test_lead_zero_sentence() -> None:
    assert verdict([20], 20).sentence == "warned at the onset hour"
    assert verdict([8], 20).sentence == "warned 12 h before onset"


def test_on_admission_window_starts_at_hour_zero() -> None:
    v = verdict([0], onset_hour(0))  # onset 6: window [-6, 6], so hour 0 counts
    assert v.outcome == "warned" and v.lead_hours == 6


def test_non_septic_false_alarms() -> None:
    assert verdict([1, 2, 9], None).false_alarm_hours == 3
    assert verdict([], None).outcome == "quiet"


def test_banner_texts() -> None:
    assert banner(verdict([11], 20), verdict([], 20), septic=True) == (
        "SepsiScope warned 9 h before onset · NEWS2 never warned"
    )
    assert banner(verdict([], None), verdict(list(range(30)), None), septic=False) == (
        "Not septic · false alarm hours: SepsiScope 0 vs NEWS2 30"
    )
    assert len(RULES) == 5
