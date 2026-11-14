"""Plain verdicts for one patient and one alerting system (demo only).

The rules match the protocol's event metrics (section 5, ``evaluation.metrics``):

- onset = first hour labelled septic + 6 h (dataset labels start 6 h before onset);
- the early-warning window is [onset - 12 h, onset], both ends included;
- lead time = onset - first alert inside that window;
- for a non-septic patient every alerting hour is a false alarm.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass

WINDOW_HOURS = 12
ONSET_OFFSET_HOURS = 6

RULES: tuple[str, ...] = (
    "Sepsis onset = the first hour the dataset labels septic + 6 hours (the dataset starts "
    "its label 6 hours before the clinical onset).",
    "Early-warning window = from 12 hours before onset up to the onset hour, both included.",
    "Warned in time = at least one alert inside the early-warning window; lead time = onset "
    "minus the first alert in the window.",
    "Alerts before the window are too early to count; alerts after onset are too late.",
    "For a patient who never develops sepsis, every alerting hour is a false alarm.",
)


@dataclass(frozen=True)
class Verdict:
    outcome: str  # warned | too_early_only | too_late_only | never_warned | false_alarms | quiet
    badge: str  # short text for a card badge
    sentence: str  # part of the banner, e.g. "warned 9 h before onset"
    lead_hours: int | None
    first_alert_hour: int | None
    alert_hours: int
    false_alarm_hours: int

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def onset_hour(first_septic_hour: int | None) -> int | None:
    return None if first_septic_hour is None else first_septic_hour + ONSET_OFFSET_HOURS


def verdict(alert_hours: Sequence[int], onset: int | None) -> Verdict:
    """Verdict for one system; ``onset`` is None for a patient who never becomes septic."""
    alerts = sorted(int(h) for h in alert_hours)
    first = alerts[0] if alerts else None
    if onset is None:
        if alerts:
            return Verdict(
                "false_alarms",
                f"{len(alerts)} false alarms",
                f"{len(alerts)} false alarm hours",
                None,
                first,
                len(alerts),
                len(alerts),
            )
        return Verdict("quiet", "No false alarms", "no false alarms", None, None, 0, 0)
    in_window = [h for h in alerts if onset - WINDOW_HOURS <= h <= onset]
    if in_window:
        lead = onset - in_window[0]
        text = "warned at the onset hour" if lead == 0 else f"warned {lead} h before onset"
        return Verdict("warned", f"Warned {lead} h early", text, lead, first, len(alerts), 0)
    if any(h > onset for h in alerts):
        return Verdict(
            "too_late_only",
            "Only after onset",
            "warned only after onset",
            None,
            first,
            len(alerts),
            0,
        )
    if alerts:
        return Verdict(
            "too_early_only",
            "Too early only",
            "alerted only before the warning window",
            None,
            first,
            len(alerts),
            0,
        )
    return Verdict("never_warned", "Never warned", "never warned", None, None, 0, 0)


def banner(model: Verdict, news2: Verdict, septic: bool) -> str:
    """E.g. 'SepsiScope warned 9 h before onset · NEWS2 never warned · false alarms 0 vs 30'."""
    if septic:
        return f"SepsiScope {model.sentence} · NEWS2 {news2.sentence}"
    return (
        f"Not septic · false alarm hours: SepsiScope {model.false_alarm_hours} "
        f"vs NEWS2 {news2.false_alarm_hours}"
    )
