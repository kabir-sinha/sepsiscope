"""Singular or plural wording for counts the demo shows ("1 hour", "2 hours").

The demo file (``data/demo/demo_B2A.json``) is a byte-checked build output, so the text
stored in it is left exactly as built. The API corrects the count wording when it serves
the demo, from the structured fields stored next to the text (counts, values, units):

- verdicts with false alarms: "1 false alarm", "1 false alarm hour";
- reasons: the unit after a value shown as 1 ("1 hour", "1 measurement"), both in the
  sentence and in the ``unit`` field the web app shows next to the bar.
"""

from __future__ import annotations

from typing import Any

# Plural units used by the reasons, and their singular form.
SINGULAR_UNITS: dict[str, str] = {"hours": "hour", "measurements": "measurement"}


def reason_sentence(label: str, value: float | None, unit: str, contribution: float) -> str:
    effect = "raised" if contribution > 0 else "lowered"
    if value is None:
        return f"{label[:1].upper()}{label[1:]}: not measured yet; this {effect} the risk."
    shown = f"{display_value(value)} {unit}".strip()
    return f"{label[:1].upper()}{label[1:]} = {shown} {effect} the risk."


def display_value(value: float) -> str:
    """Readable value: 1 decimal from 10 upwards (37.2 not 37.17), else up to 2 decimals."""
    return f"{round(value, 1 if abs(value) >= 10 else 2):g}"


def plural(n: float, singular: str, plural_form: str | None = None) -> str:
    """'0 hours', '1 hour', '2 hours'; ``plural_form`` for irregular nouns."""
    shown = display_value(float(n))
    word = singular if shown == "1" else (plural_form or f"{singular}s")
    return f"{shown} {word}"


def unit_for(value: float | None, unit: str) -> str:
    """The unit as shown after ``value``: singular when the value is shown as 1."""
    if value is not None and display_value(value) == "1":
        return SINGULAR_UNITS.get(unit, unit)
    return unit


def verdict_for_display(v: dict[str, Any]) -> dict[str, Any]:
    if v["outcome"] != "false_alarms":
        return v
    n = v["false_alarm_hours"]
    return {**v, "badge": plural(n, "false alarm"), "sentence": plural(n, "false alarm hour")}


def reason_for_display(r: dict[str, Any]) -> dict[str, Any]:
    unit = unit_for(r["value"], r["unit"])
    if unit == r["unit"]:
        return r
    sentence = reason_sentence(r["label"], r["value"], unit, r["contribution"])
    return {**r, "unit": unit, "sentence": sentence}


def patient_for_display(p: dict[str, Any]) -> dict[str, Any]:
    """A copy of one stored demo patient with count wording corrected (input unchanged)."""
    return {
        **p,
        "verdict": {k: verdict_for_display(v) for k, v in p["verdict"].items()},
        "what_if": {
            k: [{**w, "verdict": verdict_for_display(w["verdict"])} for w in ws]
            for k, ws in p["what_if"].items()
        },
        "reasons": [[reason_for_display(r) for r in hour] for hour in p["reasons"]],
    }
