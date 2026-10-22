"""Optional local denylist of personal values (never committed, never read in CI).

``.privacy-denylist.local`` at the repository root: one value per line, ``#`` starts a
comment. It is gitignored, so CI only ever applies the generic patterns in ``rules.py``.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

DENYLIST_FILE = ".privacy-denylist.local"
ALLOWED_EMAIL = "222482936+kabir-sinha@users.noreply.github.com"
# The GitHub handle is part of the allowed noreply address and the repository URL, so it
# is removed from the text before matching; it is not a denylist hit by itself.
HANDLE = ALLOWED_EMAIL.split("+", 1)[1].split("@", 1)[0]

# The only places the maintainer's name may appear (decision recorded in ADR 0016).
COPYRIGHT_RE = re.compile(r"^© \d{4} [^.]+\. All rights reserved\.$")
AUTHOR_RE = re.compile(r'^\s*\{ name = "[^"]+", email = "' + re.escape(ALLOWED_EMAIL) + r'" \}$')


def load_denylist(root: Path) -> tuple[str, ...]:
    """Values from the local denylist, or an empty tuple when the file does not exist."""
    path = root / DENYLIST_FILE
    if not path.is_file():
        return ()
    values = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.split("#", 1)[0].strip()
        if value:
            values.append(value)
    return tuple(dict.fromkeys(values))


def name_allowed_on(path: str, line: str) -> bool:
    """True for the README copyright line and the pyproject author line."""
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
