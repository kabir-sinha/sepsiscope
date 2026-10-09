"""pre-commit hook: block personal paths, foreign emails, env files, data and big files.

Usage (pre-commit passes the staged file names): ``python scripts/privacy_guard.py FILE...``
Exit code 1 (commit blocked) if any file violates a rule. Standard library only.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path, PurePosixPath

ALLOWED_EMAIL = "222482936+kabir-sinha@users.noreply.github.com"
# Addresses that are not personal: placeholders and tool/bot identities.
ALLOWED_EMAIL_PATTERNS = (
    re.compile(r"^[\w.+-]+@example\.(com|org|net)$"),
    re.compile(r"^\d+\+[\w-]+\[bot\]@users\.noreply\.github\.com$"),
)
MAX_BYTES = 1_000_000  # 1 MB
DATA_SUFFIXES = {".psv", ".parquet", ".csv"}

# Built from pieces so this file does not trip its own rules.
HOME_PREFIX = "/" + "Users/"
HOME_PREFIX_ENCODINGS = tuple(
    HOME_PREFIX.encode(enc) for enc in ("utf-8", "utf-16-le", "utf-16-be")
)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")


def _email_allowed(addr: str) -> bool:
    if addr.lower() == ALLOWED_EMAIL:
        return True
    return any(p.match(addr) for p in ALLOWED_EMAIL_PATTERNS)


def check_file(name: str) -> list[str]:
    problems: list[str] = []
    path = PurePosixPath(name)

    if path.name == ".env" or path.name.startswith(".env."):
        problems.append("environment file (.env*) must never be committed")
    if path.parts and path.parts[0] == "data" and path.suffix.lower() in DATA_SUFFIXES:
        problems.append(f"data file ({path.suffix}) under data/")
    if path.suffix.lower() in {".psv", ".parquet"}:
        problems.append(f"dataset file type {path.suffix}")

    file = Path(name)
    if not file.is_file():
        return problems
    size = file.stat().st_size
    if size > MAX_BYTES:
        problems.append(f"file is {size:,} bytes (> 1 MB)")
        return problems

    raw = file.read_bytes()
    # UTF-16 text can also be valid UTF-8 (NUL bytes are legal), so always check it.
    if any(enc in raw for enc in HOME_PREFIX_ENCODINGS[1:]):
        problems.append(f"absolute macOS home path ({HOME_PREFIX}...) in UTF-16 content")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        # Binary or non-UTF-8 (e.g. image metadata, UTF-16): scan the raw bytes.
        if any(enc in raw for enc in HOME_PREFIX_ENCODINGS):
            problems.append(f"absolute macOS home path ({HOME_PREFIX}...) in non-UTF-8 content")
        return problems

    for lineno, line in enumerate(text.splitlines(), start=1):
        if HOME_PREFIX in line:
            problems.append(f"line {lineno}: absolute macOS home path ({HOME_PREFIX}...)")
        for match in EMAIL_RE.finditer(line):
            if not _email_allowed(match.group(0)):
                problems.append(f"line {lineno}: email address not allowed: {match.group(0)}")
    return problems


def main(argv: list[str]) -> int:
    failed = False
    for name in argv:
        for problem in check_file(name):
            print(f"privacy-guard: {name}: {problem}")
            failed = True
    if failed:
        print("privacy-guard: commit blocked. Remove the personal data, then re-stage.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
