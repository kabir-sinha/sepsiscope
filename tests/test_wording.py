"""Singular/plural count wording in the demo (api/wording.py): 0, 1 and 2 for every noun."""

from __future__ import annotations

import copy

import pytest

from sepsiscope.api.verdict import verdict
from sepsiscope.api.wording import (
    patient_for_display,
    plural,
    reason_for_display,
    unit_for,
    verdict_for_display,
)


@pytest.mark.parametrize(
    ("noun", "zero", "one", "two"),
    [
        ("hour", "0 hours", "1 hour", "2 hours"),
        ("false alarm", "0 false alarms", "1 false alarm", "2 false alarms"),
        ("alert", "0 alerts", "1 alert", "2 alerts"),
        ("patient", "0 patients", "1 patient", "2 patients"),
        ("measurement", "0 measurements", "1 measurement", "2 measurements"),
    ],
)
def test_plural_zero_one_two(noun: str, zero: str, one: str, two: str) -> None:
    assert (plural(0, noun), plural(1, noun), plural(2, noun)) == (zero, one, two)


def test_plural_follows_the_shown_value() -> None:
    assert plural(1.0, "hour") == "1 hour"
    assert plural(1.004, "hour") == "1 hour"  # shown as "1"
    assert plural(1.5, "hour") == "1.5 hours"
    assert plural(1, "analysis", "analyses") == "1 analysis"
    assert plural(2, "analysis", "analyses") == "2 analyses"


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0.0, "hours"), (1.0, "hour"), (2.0, "hours"), (None, "hours")],
)
def test_unit_hours(value: float | None, expected: str) -> None:
    assert unit_for(value, "hours") == expected


@pytest.mark.parametrize(
    ("value", "expected"), [(0.0, "measurements"), (1.0, "measurement"), (2.0, "measurements")]
)
def test_unit_measurements(value: float, expected: str) -> None:
    assert unit_for(value, "measurements") == expected


def test_other_units_never_change() -> None:
    assert unit_for(1.0, "°C") == "°C" and unit_for(1.0, "fraction") == "fraction"


@pytest.mark.parametrize(
    ("alerts", "badge", "sentence"),
    [
        ([], "No false alarms", "no false alarms"),
        ([4], "1 false alarm", "1 false alarm hour"),
        ([4, 9], "2 false alarms", "2 false alarm hours"),
    ],
)
def test_false_alarm_verdicts(alerts: list[int], badge: str, sentence: str) -> None:
    v = verdict_for_display(verdict(alerts, None).as_dict())
    assert (v["badge"], v["sentence"]) == (badge, sentence)


def test_other_verdicts_unchanged() -> None:
    v = verdict([20], 24).as_dict()  # warned 4 h early
    assert verdict_for_display(v) is v


def _reason(value: float | None, unit: str) -> dict[str, object]:
    return {
        "feature": "pH__hsl",
        "label": "hours since last blood pH measurement",
        "value": value,
        "unit": unit,
        "process": True,
        "contribution": 0.1,
        "sentence": "as built",
    }


@pytest.mark.parametrize(
    ("value", "shown"),
    [(0.0, "= 0 hours raised"), (1.0, "= 1 hour raised"), (2.0, "= 2 hours raised")],
)
def test_reason_sentence_and_unit(value: float, shown: str) -> None:
    r = reason_for_display(_reason(value, "hours"))
    if value == 1.0:
        assert r["unit"] == "hour" and shown in str(r["sentence"])
    else:  # unchanged: the stored text was already right
        assert r["unit"] == "hours" and r["sentence"] == "as built"


def test_patient_for_display_does_not_change_the_input() -> None:
    v1 = verdict([3], None).as_dict()
    patient = {
        "key": "demo-x",
        "verdict": {"sepsiscope": v1, "news2": verdict([], None).as_dict()},
        "what_if": {"sepsiscope": [{"alert_hours": [3], "verdict": v1}], "news2": []},
        "reasons": [[_reason(1.0, "hours")], []],
    }
    before = copy.deepcopy(patient)
    shown = patient_for_display(patient)
    assert patient == before
    assert shown["verdict"]["sepsiscope"]["badge"] == "1 false alarm"
    assert shown["what_if"]["sepsiscope"][0]["verdict"]["badge"] == "1 false alarm"
    assert shown["reasons"][0][0]["unit"] == "hour"
