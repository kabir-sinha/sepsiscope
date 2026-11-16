"""Static layout guards for the demo CSS (no browser needed): nothing may force the page or a
card wider than its box. The browser geometry check is recorded in docs/internal/handoff.md."""

from __future__ import annotations

import re

from sepsiscope.config import REPO_ROOT

CSS = (REPO_ROOT / "web" / "src" / "App.css").read_text(encoding="utf-8")


def _rule(selector: str) -> str:
    m = re.search(r"(?m)^" + re.escape(selector) + r" \{(.*?)^\}", CSS, re.S)
    assert m, selector
    return m.group(1)


def test_verdict_badges_wrap_inside_the_card() -> None:
    badge = _rule(".badge")
    assert "white-space: nowrap" not in badge
    assert "white-space: normal" in badge and "overflow-wrap: anywhere" in badge
    assert "max-width: 100%" in badge
    assert "overflow: hidden" not in badge and "text-overflow" not in badge  # no truncation
    assert "flex-wrap: wrap" in _rule(".badges")
    assert "min-width: 0" in _rule(".card")


def test_grid_minimums_never_exceed_the_screen() -> None:
    fixed = re.findall(r"minmax\((\d+px)", CSS)
    assert fixed == [], f"use minmax(min(N px, 100%), 1fr): {fixed}"
