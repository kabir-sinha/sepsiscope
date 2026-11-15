"""ADR 0025: the demo attribution appears once, in one file, and the name nowhere else.

The name is read from the header line itself, so it is never written in this file.
"""

from __future__ import annotations

import re
import shutil
import subprocess

import pytest

from sepsiscope.audit.denylist import (
    ALLOWED_EMAIL,
    ATTRIBUTION_FILE,
    ATTRIBUTION_PREFIX,
    HANDLE,
    load_attribution,
    load_denylist,
    strip_attribution,
)
from sepsiscope.audit.rules import check_content, check_line
from sepsiscope.config import REPO_ROOT

GIT = shutil.which("git") or "git"
FAKE_FIRST, FAKE_LAST = "Zorvan", "Quellby"
FAKE_ATTR = (ATTRIBUTION_PREFIX + FAKE_FIRST,)
DENY = (FAKE_FIRST, FAKE_LAST, f"{FAKE_FIRST} {FAKE_LAST}")
LINE = f'            <p className="byline">{ATTRIBUTION_PREFIX}{FAKE_FIRST}</p>'


def _name_in_header() -> str:
    text = (REPO_ROOT / ATTRIBUTION_FILE).read_text(encoding="utf-8")
    found = re.findall(
        r'<p className="byline">' + re.escape(ATTRIBUTION_PREFIX) + r"(\w+)</p>", text
    )
    assert len(found) == 1, "exactly one attribution line in the demo header"
    return found[0]


def _tracked_text() -> dict[str, str]:
    files = subprocess.run(
        [GIT, "ls-files", "-z"], cwd=REPO_ROOT, capture_output=True, check=True, text=True
    ).stdout.split("\0")
    out = {}
    for name in filter(None, files):
        path = REPO_ROOT / name
        if not path.is_file():
            continue
        try:
            out[name] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
    return out


def test_name_appears_only_in_the_one_attribution() -> None:
    name = _name_in_header()
    word = re.compile(rf"(?<!\w){re.escape(name)}(?!\w)", re.IGNORECASE)
    hits = {}
    for path, text in _tracked_text().items():
        cleaned = text.replace(ALLOWED_EMAIL, " ")
        cleaned = re.sub(re.escape(HANDLE), " ", cleaned, flags=re.IGNORECASE)
        if n := len(word.findall(cleaned)):
            hits[path] = n
    assert hits == {ATTRIBUTION_FILE: 1}, sorted(hits)


def test_local_denylist_finds_nothing_in_tracked_files() -> None:
    deny = load_denylist(REPO_ROOT)
    if not deny:
        pytest.skip("no local denylist (CI)")
    attribution = load_attribution(REPO_ROOT)
    assert len(attribution) == 1
    problems = {
        path: p
        for path, text in _tracked_text().items()
        if (p := check_content(path, text.encode("utf-8"), deny, False, attribution))
    }
    assert problems == {}, sorted(problems)


def test_exact_attribution_is_allowed_in_its_file_only() -> None:
    assert check_line(ATTRIBUTION_FILE, 1, LINE, DENY, attribution=FAKE_ATTR) == []
    assert check_line("web/src/Results.tsx", 1, LINE, DENY, attribution=FAKE_ATTR) != []
    assert check_line("README.md", 1, LINE, DENY, attribution=FAKE_ATTR) != []
    assert check_line(ATTRIBUTION_FILE, 1, LINE, DENY) != []  # no local file: no exception


@pytest.mark.parametrize(
    "text",
    [
        f"{ATTRIBUTION_PREFIX}{FAKE_FIRST} {FAKE_LAST}",  # full name
        f"{ATTRIBUTION_PREFIX}{FAKE_FIRST.lower()}",  # not the exact text
        f"built by {FAKE_FIRST}",
        f"{ATTRIBUTION_PREFIX}{FAKE_FIRST} and {FAKE_FIRST}",  # a second mention
        f"{FAKE_FIRST} wrote this",
        f"{ATTRIBUTION_PREFIX}{FAKE_FIRST}-{FAKE_LAST}",
    ],
)
def test_anything_but_the_exact_text_is_denied(text: str) -> None:
    assert check_line(ATTRIBUTION_FILE, 1, text, DENY, attribution=FAKE_ATTR) != []


def test_strip_is_exact_and_file_bound() -> None:
    text = f"x {ATTRIBUTION_PREFIX}{FAKE_FIRST}</p>"
    assert FAKE_FIRST not in strip_attribution(ATTRIBUTION_FILE, text, FAKE_ATTR)
    assert strip_attribution("web/src/ui.tsx", text, FAKE_ATTR) == text
    assert strip_attribution(ATTRIBUTION_FILE, text, ()) == text
