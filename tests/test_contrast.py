"""WCAG 2.2 contrast of the demo's colour tokens in both themes (scripts/contrast_check.py)."""

from __future__ import annotations

import importlib.util

from sepsiscope.config import REPO_ROOT


def test_all_tokens_meet_wcag_contrast() -> None:
    spec = importlib.util.spec_from_file_location(
        "contrast_check", REPO_ROOT / "scripts" / "contrast_check.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = module.check(module.CSS.read_text(encoding="utf-8"))
    assert {r[0] for r in rows} == {"light", "dark"}
    failed = [f"{theme} {pair} {ratio:.2f}" for theme, pair, _, ratio, _, ok in rows if not ok]
    assert not failed, failed
