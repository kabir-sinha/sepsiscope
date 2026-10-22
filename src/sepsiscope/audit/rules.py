"""File rules: block personal paths, foreign emails, account wording, IDs, env files,
data, big files, PNG metadata, notebook outputs and local denylist values.

Used by the pre-commit hook (``scripts/privacy_guard.py``), CI and ``privacy-audit``.
Messages never contain the matched personal value in clear text.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from sepsiscope.audit.denylist import ALLOWED_EMAIL, denied_values, load_denylist, name_allowed_on
from sepsiscope.audit.mask import mask, mask_email
from sepsiscope.audit.notebook import check_notebook

# Addresses that are not personal: placeholders and tool/bot identities.
ALLOWED_EMAIL_PATTERNS = (
    re.compile(r"^[\w.+-]+@example\.(com|org|net)$"),
    re.compile(r"^\d+\+[\w-]+\[bot\]@users\.noreply\.github\.com$"),
    re.compile(r"^(noreply|support)@github\.com$"),  # GitHub service addresses in bot commits
)
MAX_BYTES = 1_000_000  # 1 MB
DATA_SUFFIXES = {".psv", ".parquet", ".csv"}

# Built from pieces so this file does not trip its own rules.
HOME_PREFIX = "/" + "Users/"
HOME_PREFIX_ENCODINGS = tuple(
    HOME_PREFIX.encode(enc) for enc in ("utf-8", "utf-16-le", "utf-16-be")
)
OTHER_HOME_RES = (
    ("Linux home path", re.compile(r"(?<![\w.-])/" + r"home/[a-z_][a-z0-9_-]*")),
    ("Windows home path", re.compile(r"\b[A-Za-z]:\\+" + r"Users\\+[^\\\s]+", re.IGNORECASE)),
)
# Account-tier wording (plan, payment and verification status) and enrollment-ID shapes.
# Each pattern is split in two strings so this file does not match itself.
TIER = "account-tier wording"
WORDING_RES = (
    (TIER, re.compile(r"\bstudent\s+(developer\s+)?" + r"pack\b", re.I)),
    (TIER, re.compile(r"\bgithub\s+(free|pro|team)\s+" + r"(plan|account|tier)\b", re.I)),
    (TIER, re.compile(r"\bplan\s+(is|was|treated\s+as)\s+\W*" + r"(free|pro|team)\b", re.I)),
    (TIER, re.compile(r"\b" + "bill" + r"ing\b", re.I)),
    (TIER, re.compile(r"\b(student|education)\s+" + r"(verification|benefits?)\b", re.I)),
    ("enrollment-ID shape", re.compile(r"\b[A-Z]\d{2}[A-Z]{3,5}" + r"\d{3,6}\b")),
)
# Lockfiles hold hashes and package names: wording and ID shapes would only false-alarm.
WORDING_EXEMPT = {"uv.lock", "web/package-lock.json"}
# PNG chunks that can carry text, EXIF data or a timestamp.
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_METADATA_CHUNKS = {"tEXt", "iTXt", "zTXt", "eXIf", "tIME"}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")


def _email_allowed(addr: str) -> bool:
    if addr.lower() == ALLOWED_EMAIL:
        return True
    return any(p.match(addr) for p in ALLOWED_EMAIL_PATTERNS)


def png_chunk_types(data: bytes) -> set[str]:
    """Chunk type names of a PNG file's bytes."""
    types: set[str] = set()
    pos = 8
    while pos + 8 <= len(data):
        length = int.from_bytes(data[pos : pos + 4], "big")
        types.add(data[pos + 4 : pos + 8].decode("latin-1"))
        pos += 12 + length
    return types


def check_path(name: str) -> list[str]:
    """Rules that depend only on the file name."""
    problems: list[str] = []
    path = PurePosixPath(name)
    if path.name == ".env" or path.name.startswith(".env."):
        problems.append("environment file (.env*) must never be committed")
    if path.parts and path.parts[0] == "data" and path.suffix.lower() in DATA_SUFFIXES:
        problems.append(f"data file ({path.suffix}) under data/")
    if path.suffix.lower() in {".psv", ".parquet"}:
        problems.append(f"dataset file type {path.suffix}")
    return problems


def check_line(name: str, lineno: int, line: str, denylist: tuple[str, ...]) -> list[str]:
    """Text rules for one line. Messages are masked."""
    problems: list[str] = []
    where = f"line {lineno}"
    if HOME_PREFIX in line:
        problems.append(f"{where}: absolute macOS home path ({HOME_PREFIX}...)")
    for label, pattern in OTHER_HOME_RES:
        if pattern.search(line):
            problems.append(f"{where}: {label}")
    for match in EMAIL_RE.finditer(line):
        if not _email_allowed(match.group(0)):
            problems.append(f"{where}: email address not allowed: {mask_email(match.group(0))}")
    if PurePosixPath(name).as_posix() not in WORDING_EXEMPT:
        for label, pattern in WORDING_RES:
            if pattern.search(line):
                problems.append(f"{where}: {label}")
    if denylist and not name_allowed_on(name, line):
        for value in denied_values(line, denylist):
            problems.append(f"{where}: personal value from the local denylist ({mask(value)})")
    return problems


def check_content(name: str, raw: bytes, denylist: tuple[str, ...] = ()) -> list[str]:
    """Content rules for a file's bytes (used for the working tree and for history)."""
    problems: list[str] = []
    if len(raw) > MAX_BYTES:
        return [f"file is {len(raw):,} bytes (> 1 MB)"]
    if raw[:8] == PNG_SIGNATURE:
        bad = sorted(png_chunk_types(raw) & PNG_METADATA_CHUNKS)
        if bad:
            problems.append(f"PNG carries metadata chunks {bad}; save it without metadata")
    if name.endswith(".ipynb"):
        problems.extend(check_notebook(raw))
    # UTF-16 text can also be valid UTF-8 (NUL bytes are legal), so always check it.
    if any(enc in raw for enc in HOME_PREFIX_ENCODINGS[1:]):
        problems.append(f"absolute macOS home path ({HOME_PREFIX}...) in UTF-16 content")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        # Binary or non-UTF-8 (e.g. image metadata, UTF-16): scan the raw bytes.
        if any(enc in raw for enc in HOME_PREFIX_ENCODINGS):
            problems.append(f"absolute macOS home path ({HOME_PREFIX}...) in non-UTF-8 content")
        lowered = raw.lower()
        for value in denylist:
            if value.lower().encode("utf-8") in lowered:
                problems.append(f"personal value from the local denylist ({mask(value)})")
        return problems
    for lineno, line in enumerate(text.splitlines(), start=1):
        problems.extend(check_line(name, lineno, line, denylist))
    return problems


def check_file(name: str, denylist: tuple[str, ...] = ()) -> list[str]:
    """All rules for one file on disk."""
    problems = check_path(name)
    file = Path(name)
    if not file.is_file():
        return problems
    size = file.stat().st_size
    if size > MAX_BYTES:
        return [*problems, f"file is {size:,} bytes (> 1 MB)"]
    return problems + check_content(name, file.read_bytes(), denylist)


def main(argv: list[str]) -> int:
    """pre-commit entry point: check the given files; the local denylist is optional."""
    denylist = load_denylist(Path.cwd())
    failed = False
    for name in argv:
        for problem in check_file(name, denylist):
            print(f"privacy-guard: {name}: {problem}")
            failed = True
    if failed:
        print("privacy-guard: commit blocked. Remove the personal data, then re-stage.")
    return 1 if failed else 0
