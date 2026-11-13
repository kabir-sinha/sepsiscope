"""``sepsiscope privacy-audit``: tracked files, every blob in history, commit messages,
identities, timezone offsets and ref names, with masked output.

Strict by default since the history rewrite (ADR 0017): every finding fails the run. With
``strict=False`` (``--no-strict``), findings that exist only in commits made before
``UTC_REQUIRED_FROM`` are listed as *known* instead of failing.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sepsiscope.audit.denylist import load_denylist
from sepsiscope.audit.gitchecks import check_commit, check_message, git, read_commits
from sepsiscope.audit.mask import mask_values
from sepsiscope.audit.rules import check_content, check_line, check_path

# Commits from this moment on must be fully clean (all are made with TZ=UTC).
UTC_REQUIRED_FROM = datetime(2026, 10, 22, tzinfo=UTC)
LINE_PREFIX_RE = re.compile(r"^line \d+: ")


@dataclass(frozen=True)
class Finding:
    area: str  # tree | history | message | commit | ref
    where: str  # file path, short commit SHA or ref name (masked)
    problem: str  # already masked
    known: bool  # only in commits before UTC_REQUIRED_FROM


@dataclass
class AuditReport:
    findings: list[Finding] = field(default_factory=list)
    scanned: dict[str, int] = field(default_factory=dict)

    def blocking(self, strict: bool = True) -> list[Finding]:
        return [f for f in self.findings if strict or not f.known]

    def known(self, strict: bool = True) -> list[Finding]:
        return [] if strict else [f for f in self.findings if f.known]


def _read_blobs(root: Path, shas: list[str]) -> dict[str, bytes]:
    """Contents of the given objects that are blobs, via one ``git cat-file --batch`` call."""
    exe = shutil.which("git") or "git"
    result = subprocess.run(  # noqa: S603 - fixed executable and arguments
        [exe, "cat-file", "--batch"],
        cwd=root,
        input="".join(f"{sha}\n" for sha in shas).encode(),
        capture_output=True,
        check=True,
    )
    out, pos, blobs = result.stdout, 0, {}
    while pos < len(out):
        header_end = out.index(b"\n", pos)
        sha, kind, size = out[pos:header_end].decode().split()
        start = header_end + 1
        if kind == "blob":  # trees and commits are listed by rev-list too
            blobs[sha] = out[start : start + int(size)]
        pos = start + int(size) + 1  # content is followed by a newline
    return blobs


def _tree_blobs(root: Path, rev: str) -> set[str]:
    out = git(root, "ls-tree", "-r", rev)
    return {line.split()[2] for line in out.splitlines() if line.split()[1] == "blob"}


def run_audit(root: Path) -> AuditReport:
    """Scan the repository at ``root``. Read-only; prints nothing."""
    report = AuditReport()
    denylist = load_denylist(root)
    cutoff = int(UTC_REQUIRED_FROM.timestamp())

    # 1. Tracked files in the working tree (what the next commit would contain).
    tracked = [p for p in git(root, "ls-files", "-z").split("\0") if p]
    for name in tracked:
        path = root / name
        problems = check_path(name)
        if path.is_file():
            problems += check_content(name, path.read_bytes(), denylist)
        report.findings += [Finding("tree", name, p, known=False) for p in problems]

    # 2. Every blob in every commit that is no longer in HEAD.
    commits = read_commits(root, ["--all"])
    paths: dict[str, str] = {}
    for line in git(root, "rev-list", "--all", "--objects").splitlines():
        sha, _, name = line.partition(" ")
        if name:
            paths.setdefault(sha, name)
    head = _tree_blobs(root, "HEAD") if commits else set()
    legacy_blobs: set[str] = set()
    for c in commits:
        if c.committed_at < cutoff:
            legacy_blobs |= _tree_blobs(root, c.sha)
    candidates = [sha for sha in paths if sha not in head]
    blobs = _read_blobs(root, candidates) if candidates else {}
    for sha, raw in blobs.items():
        name = paths[sha]
        problems = check_path(name) + check_content(name, raw, denylist)
        known = sha in legacy_blobs
        report.findings += [Finding("history", name, p, known=known) for p in problems]

    # 3. and 4. Commit messages, identities and offsets.
    for c in commits:
        known = c.committed_at < cutoff
        for p in check_message(c.message, denylist):
            report.findings.append(Finding("message", c.sha[:7], p, known=known))
        for p in check_commit(c):
            report.findings.append(Finding("commit", c.sha[:7], p, known=known))

    # 5. Branch and tag names.
    refs = git(root, "for-each-ref", "--format=%(refname)").splitlines()
    for ref in refs:
        for p in check_line("refs", 1, ref, denylist):
            where = mask_values(ref, denylist)
            report.findings.append(Finding("ref", where, p.split(": ", 1)[1], known=False))

    report.scanned = {
        "tracked files": len(tracked),
        "history-only blobs": len(blobs),
        "commits": len(commits),
        "refs": len(refs),
        "denylist entries": len(denylist),
    }
    return report


def format_report(report: AuditReport, strict: bool = True) -> list[str]:
    """Human-readable, masked report lines."""
    lines = ["scanned  " + ", ".join(f"{k} {v}" for k, v in report.scanned.items())]
    lines += [f"FAIL     {f.area:<8} {f.where}: {f.problem}" for f in report.blocking(strict)]
    known = report.known(strict)
    # Known findings are grouped by problem (without the line number) to stay readable.
    grouped: Counter[tuple[str, str]] = Counter()
    places: dict[tuple[str, str], set[str]] = {}
    for f in known:
        key = (f.area, LINE_PREFIX_RE.sub("", f.problem))
        grouped[key] += 1
        places.setdefault(key, set()).add(f.where)
    for (area, problem), count in sorted(grouped.items()):
        examples = sorted(places[(area, problem)])
        shown = ", ".join(examples[:3]) + (" ..." if len(examples) > 3 else "")
        lines.append(f"known    {area:<8} {problem}  (x{count}: {shown})")
    blocking = len(report.blocking(strict))
    mode = "strict" if strict else "non-strict"
    lines.append(
        f"result   {'FAIL' if blocking else 'PASS'} ({mode}): {blocking} blocking, "
        f"{len(known)} known (only in commits before {UTC_REQUIRED_FROM:%Y-%m-%d}, "
        "listed only with --no-strict)"
    )
    return lines
