"""Optional local denylist of personal values (never committed, never read in CI).

``.privacy-denylist.local`` at the repository root: one value per line, ``#`` starts a
comment. It is gitignored, so CI only ever applies the generic patterns in ``rules.py``.
A line ``allow-author-name: <name>`` is not a denied value: it names the one commit
author/committer name that may contain denylist values (commit metadata only, ADR 0023).
Keeping it in this local file keeps the name out of every tracked file.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

DENYLIST_FILE = ".privacy-denylist.local"
ALLOW_AUTHOR_PREFIX = "allow-author-name:"
ALLOWED_EMAIL = "222482936+kabir-sinha@users.noreply.github.com"
# The GitHub handle is part of the allowed noreply address and the repository URL, so it
# is removed from the text before matching; it is not a denylist hit by itself.
HANDLE = ALLOWED_EMAIL.split("+", 1)[1].split("@", 1)[0]

# Lines that carried the maintainer's name before ADR 0023. Since then the name is denied in
# every tracked file; these shapes are accepted only in older history blobs (not rewritten).
COPYRIGHT_RE = re.compile(r"^© \d{4} [^.]+\. All rights reserved\.$")
AUTHOR_RE = re.compile(r'^\s*\{ name = "[^"]+", email = "' + re.escape(ALLOWED_EMAIL) + r'" \}$')


def _entries(root: Path) -> list[str]:
    path = root / DENYLIST_FILE
    if not path.is_file():
        return []
    entries = [line.split("#", 1)[0].strip() for line in path.read_text("utf-8").splitlines()]
    return [e for e in entries if e]


def load_denylist(root: Path) -> tuple[str, ...]:
    """Values from the local denylist, or an empty tuple when the file does not exist."""
    values = [e for e in _entries(root) if not e.lower().startswith(ALLOW_AUTHOR_PREFIX)]
    return tuple(dict.fromkeys(values))


def load_allowed_author_names(root: Path) -> tuple[str, ...]:
    """Names from ``allow-author-name:`` lines (empty when there is no local file)."""
    names = [
        e[len(ALLOW_AUTHOR_PREFIX) :].strip()
        for e in _entries(root)
        if e.lower().startswith(ALLOW_AUTHOR_PREFIX)
    ]
    return tuple(dict.fromkeys(n for n in names if n))


def name_allowed_on(path: str, line: str) -> bool:
    """True for the old README copyright line and pyproject author line (history only)."""
    name = PurePosixPath(path).as_posix()
    if name == "README.md":
        return bool(COPYRIGHT_RE.match(line))
    if name == "pyproject.toml":
        return bool(AUTHOR_RE.match(line))
    return False


def denied_values(text: str, values: tuple[str, ...]) -> list[str]:
    """Denylist values found in ``text`` as whole words (case-insensitive)."""
    if not values:
        return []
    cleaned = re.sub(re.escape(HANDLE), " ", text, flags=re.IGNORECASE)
    found = []
    for value in values:
        if re.search(rf"(?<!\w){re.escape(value)}(?!\w)", cleaned, flags=re.IGNORECASE):
            found.append(value)
    return found
