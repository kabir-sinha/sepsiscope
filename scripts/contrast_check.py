"""WCAG 2.2 contrast check of the demo's colour tokens, in both themes.

Reads the CSS custom properties from ``web/src/index.css`` (light = ``:root``, dark =
``:root[data-theme='dark']``) and checks every text pair against 4.5:1 (SC 1.4.3) and every
chart line / UI component pair against 3:1 (SC 1.4.11). Prints one line per pair.
Usage: ``uv run python scripts/contrast_check.py`` (exit 1 on any failure).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "web" / "src" / "index.css"

TEXT = [  # (foreground, background, where)
    ("text", "bg", "body text"),
    ("text", "surface", "text on cards"),
    ("text", "surface-2", "text on readout / table highlight"),
    ("heading", "surface", "headings"),
    ("heading", "bg", "page heading"),
    ("muted", "bg", "helper text on page"),
    ("muted", "surface", "helper text, ticks, axis labels"),
    ("muted", "surface-2", "helper text on grey"),
    ("accent", "surface", "teal labels, links"),
    ("accent-text", "accent", "primary button"),
    ("raise-text", "surface", "'raises' text"),
    ("raise-text", "bad-bg", "bad badge"),
    ("good-text", "good-bg", "good badge"),
    ("lower", "surface", "'lowers' text"),
    ("window-text", "surface", "window label"),
    ("tip-text", "tip-bg", "tooltip"),
]
GRAPHICS = [
    ("risk", "surface", "SepsiScope risk line"),
    ("compare", "surface", "comparison line"),
    ("news2", "surface", "NEWS2 line"),
    ("raise", "surface", "alert dots, raises bars"),
    ("lower", "surface", "lowers bars"),
    ("threshold", "surface", "threshold line"),
    ("onset", "surface", "onset line"),
    ("text", "surface", "vital-sign lines"),
    ("ok", "surface", "normal-range legend swatch"),
    ("border", "surface", "input and card borders"),
    ("accent", "surface", "selected card / focus ring"),
    ("focus", "bg", "focus ring on page"),
]


def tokens(css: str) -> dict[str, dict[str, str]]:
    blocks = {
        "light": re.search(r":root\s*\{(.*?)\n\}", css, re.S),
        "dark": re.search(r":root\[data-theme='dark'\]\s*\{(.*?)\n\}", css, re.S),
    }
    out: dict[str, dict[str, str]] = {}
    for name, match in blocks.items():
        assert match, name
        out[name] = dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", match.group(1)))
    out["dark"] = {**out["light"], **out["dark"]}
    return out


def luminance(hex_colour: str) -> float:
    rgb = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def check(css: str) -> list[tuple[str, str, str, float, float, bool]]:
    rows = []
    for theme, tok in tokens(css).items():
        for pairs, need in ((TEXT, 4.5), (GRAPHICS, 3.0)):
            for fg, bg, where in pairs:
                r = ratio(tok[fg], tok[bg])
                rows.append((theme, f"{fg} on {bg}", where, r, need, r >= need))
    return rows


def main() -> int:
    rows = check(CSS.read_text(encoding="utf-8"))
    for theme, pair, where, r, need, ok in rows:
        print(f"{theme:5} {pair:26} {r:5.2f} (>= {need}) {'pass' if ok else 'FAIL'}  {where}")
    failed = [r for r in rows if not r[5]]
    print(f"{len(rows) - len(failed)}/{len(rows)} pass")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
