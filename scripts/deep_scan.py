"""Exhaustive privacy scan of every blob in git history, binary metadata and commit messages.

Third check next to ``sepsiscope privacy-audit`` and ``scripts/independent_scan.sh``. It is
deliberately **independent of the sepsiscope package** (standard library only), so a bug in
the package's rules cannot hide a finding here. Prints counts and repository-relative paths
only, never a matched value.

Usage (from anywhere): ``python -I scripts/deep_scan.py REPO DENYLIST``
DENYLIST is the gitignored local file (one value per line; ``#`` comments and
``allow-author-name:`` lines are skipped). Personal values are read from it at run time and
never written into this file. Patterns below are written so that their own source text
cannot match them (for example ``mac(?:)book``), because this file is scanned too.
"""

from __future__ import annotations

import os
import re
import socket
import struct
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ALLOW_PREFIX = "allow-author-name:"
# ADR 0025: the one allowed demo attribution ("Built by " + first word of the allowed author
# name, built at run time) is removed before counting, in this one file only.
ATTRIBUTION_FILE = "web/src/App.tsx"
ATTRIBUTION_PREFIX = "Built by "

REGEX: dict[str, bytes] = {
    "email(other)": rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "ipv4(non-loopback)": rb"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])",
    "mac": rb"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b",
    "users-path": rb"/" + rb"Users/[A-Za-z0-9_.-]+|/" + rb"home/[A-Za-z0-9_.-]+|C:\\\\" + rb"Users",
    "device": (
        rb"(?i)mac(?:)book|i(?:)mac\b|mac ?mini|mac(?:) studio|apple m[1-9]"
        rb"|\bm[1-9] (?:pro|max|ultra)\b|\d+ ?gb (?:ram|memory|unified)"
        rb"|hardware(?:) uuid|serial(?:) number|\budid\b|platform(?:) uuid"
    ),
    "os-version": (
        rb"(?i)macos (?:1[0-9]|2[0-9])|darwin 2[0-9]"
        rb"|\b(?:sono(?:)ma|seq(?:)uoia|tah(?:)oe|vent(?:)ura)\b"
    ),
    "plan-names": (
        rb"(?i)claude (?:pro|max)\b|\bmax (?:plan|5x|20x)\b|\bpro(?:) plan\b"
        rb"|usage(?:) limit|session(?:) limit|rate[- ]limit(?:ed)? on claude"
    ),
    "wifi": rb"(?i)\bssid\b|wi-?fi name",
    "location/tz": (
        rb"(?i)asia(?:)/|\+05(?:)30|\bkolkata\b|\bdelhi\b|\bnoida\b|\bmumbai\b"
        rb"|\bbangalore\b|\bbengaluru\b"
    ),
    "patient-id": rb"\bp[01]\d{5}\b",
    "secret-pattern": (
        rb"gh(?:)p_[A-Za-z0-9]{20,}|github(?:)_pat_|gh(?:)o_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}"
        rb"|sk-[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY|xox[bp]-"
    ),
}
# Not personal: GitHub noreply addresses, placeholders and the AI-trailer address once
# found in old messages (built in pieces so the guard does not read it as an address).
OK_EMAIL = re.compile(
    rb"^(?:[^@]+@users\.noreply\.github\.com|noreply@github\.com|[^@]+@example\.(?:com|org)"
    rb"|noreply" + rb"@" + rb"anthropic\.com)$"
)
MESSAGE_WORDS = re.compile(rb"(?i)co-authored|generated with|claude|anthropic")


def git(*args: str, data: bytes | None = None) -> bytes:
    return subprocess.run(["git", *args], input=data, capture_output=True, check=True).stdout


def denylist(path: str) -> list[str]:
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        value = line.split("#", 1)[0].strip()
        if value and not value.lower().startswith(ALLOW_PREFIX):
            out.append(value)
    return out


def attribution(path: str) -> list[bytes]:
    names = [
        line.split("#", 1)[0].strip()[len(ALLOW_PREFIX) :].strip()
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip().lower().startswith(ALLOW_PREFIX)
    ]
    return [(ATTRIBUTION_PREFIX + n.split()[0]).encode() for n in names if n]


def without_attribution(blob: bytes, allowed: list[bytes]) -> bytes:
    for a in allowed:  # exact and case-sensitive; a following word is still counted
        blob = re.sub(rb"(?<!\w)" + re.escape(a) + rb"(?![\w-])(?![ \t]+\w)", b" ", blob)
    return blob


def literals(deny: list[str]) -> dict[str, str]:
    lit = {f"denylist#{i + 1}": v for i, v in enumerate(deny)}
    user = os.environ.get("USER") or ""
    if not user:
        user = subprocess.run(["id", "-un"], capture_output=True, text=True).stdout.strip()
    lit |= {
        "username": user,
        "hostname": socket.gethostname().split(".")[0],
        "home-path": str(Path("~").expanduser()),
    }
    return {k: v for k, v in lit.items() if v}


def variants(text: str) -> list[bytes]:
    t = text.lower()
    return [t.encode(), t.encode("utf-16-le"), t.encode("utf-16-be")]


def ok_ip(match: bytes) -> bool:
    parts = [int(x) for x in match.split(b".")]
    if any(p > 255 for p in parts):
        return True  # a version number, not an address
    return match == b"0.0.0.0" or parts[0] == 127


def png_chunks(blob: bytes) -> list[str]:
    out, i = [], 8
    while i + 8 <= len(blob):
        n, typ = struct.unpack(">I4s", blob[i : i + 8])
        if typ in (b"tEXt", b"iTXt", b"zTXt", b"eXIf", b"tIME", b"iCCP"):
            out.append(typ.decode())
        i += 12 + n
    return out


def scan(blob: bytes, lit: dict[str, str]) -> dict[str, int]:
    hits: dict[str, int] = {}
    low = blob.lower()
    for key, value in lit.items():
        count = sum(low.count(v) for v in variants(value))
        if count:
            hits[key] = count
    for key, pattern in REGEX.items():
        found = re.findall(pattern, blob)
        if key == "email(other)":
            found = [m for m in found if not OK_EMAIL.match(m)]
        if key == "ipv4(non-loopback)":
            found = [m for m in found if not ok_ip(m)]
        if found:
            hits[key] = len(found)
    if blob.startswith(b"\x89PNG"):
        chunks = png_chunks(blob)
        if chunks:
            hits["png-meta:" + ",".join(sorted(set(chunks)))] = len(chunks)
    if blob[:4] in (b"wOF2", b"wOFF"):
        hits["font(file)"] = 1  # fonts are checked by SHA-256 against FONTS.md instead
    return hits


def blobs(rev_args: list[str]) -> dict[str, set[str]]:
    """Blob SHA -> paths, for all objects reachable from ``rev_args``."""
    paths: dict[str, set[str]] = defaultdict(set)
    for line in git("rev-list", "--objects", *rev_args).decode().splitlines():
        sha, _, path = line.partition(" ")
        if path:
            paths[sha].add(path)
    out = git("cat-file", "--batch-check", data="\n".join(paths).encode()).decode()
    return {
        sha: paths[sha] for sha, typ, _ in (ln.split() for ln in out.splitlines()) if typ == "blob"
    }


def head_blobs() -> dict[str, set[str]]:
    paths: dict[str, set[str]] = defaultdict(set)
    for line in git("ls-tree", "-r", "HEAD").decode().splitlines():
        meta, path = line.split("\t", 1)
        paths[meta.split()[2]].add(path)
    return paths


def report(
    label: str, objects: dict[str, set[str]], lit: dict[str, str], allowed: list[bytes]
) -> None:
    agg: dict[str, set[str]] = defaultdict(set)
    for sha, paths in objects.items():
        blob = git("cat-file", "blob", sha)
        if paths == {ATTRIBUTION_FILE}:
            blob = without_attribution(blob, allowed)
        for key in scan(blob, lit):
            agg[key] |= paths
    print(f"== {label}: {len(objects)} blobs")
    for key in sorted(agg):
        ps = sorted(agg[key])
        more = " …" if len(ps) > 15 else ""
        print(f"  {key}: {len(ps)} paths: {', '.join(ps[:15])}{more}")
    if not agg:
        print("  no hits")


def message_counts(rev_args: list[str], lit: dict[str, str]) -> dict[str, int]:
    text = git("log", *rev_args, "--format=%an%n%ae%n%cn%n%ce%n%B").lower()
    counts = {k: sum(text.count(v) for v in variants(t)) for k, t in lit.items()}
    for key, pattern in REGEX.items():
        if key not in ("email(other)", "ipv4(non-loopback)"):
            counts[key] = len(re.findall(pattern, text))
    counts["trailer/AI words"] = len(MESSAGE_WORDS.findall(text))
    return {k: v for k, v in counts.items() if v}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: deep_scan.py REPO DENYLIST", file=sys.stderr)
        return 2
    lit = literals(denylist(argv[1]))
    allowed = attribution(argv[1])
    os.chdir(argv[0])
    report("HEAD tree", head_blobs(), lit, allowed)
    has_remote = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", "origin/main"], capture_output=True
    )
    if has_remote.returncode == 0:
        report("unpushed origin/main..HEAD", blobs(["origin/main..HEAD"]), lit, allowed)
        print("== unpushed commit metadata+messages:", message_counts(["origin/main..HEAD"], lit))
    report("all history", blobs(["--all"]), lit, allowed)
    print("== commit metadata+messages (all):", message_counts(["--all"], lit) or "no hits")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
