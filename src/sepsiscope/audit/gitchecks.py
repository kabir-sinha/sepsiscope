"""Commit checks: messages (no AI trailers, no personal data), identities and UTC offsets.

Used by the commit-msg and pre-push hooks, the CI commit check and ``privacy-audit``.
Every commit made from the local machine runs with ``TZ=UTC``, so its author and committer
offsets are ``+0000``; any other offset would reveal the local timezone.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from sepsiscope.audit.denylist import ALLOWED_EMAIL, denied_values
from sepsiscope.audit.mask import mask, mask_email, mask_offset
from sepsiscope.audit.rules import check_line

ZERO_SHA = "0" * 40
UTC_OFFSET = "+0000"
BOT_EMAIL_RE = re.compile(r"^\d+\+[\w-]+\[bot\]@users\.noreply\.github\.com$")
# GitHub's own committer identity (web merges, bot commits); not personal.
GITHUB_COMMITTER = "noreply@github.com"

CO_AUTHOR_RE = re.compile(r"^\s*co-authored-by\s*:", re.IGNORECASE)
AI_TOOLS = r"(claude|anthropic|openai|chatgpt|copilot|gemini)"
# Trailer-shaped body lines ("Key: value") that name an AI tool, e.g. "Claude-Session: ...".
AI_TRAILER_RE = re.compile(rf"^\s*[\w-]*{AI_TOOLS}[\w-]*\s*:|^\s*[\w-]+\s*:.*\b{AI_TOOLS}\b", re.I)
GENERATED_RE = re.compile(rf"generated\s+(with|by)\b.*\b{AI_TOOLS}", re.IGNORECASE)
SESSION_URL_RE = re.compile(r"claude\.ai/", re.IGNORECASE)
EMAIL_IN_LINE_RE = re.compile(r"<([^>]+)>")


def check_message(text: str, denylist: tuple[str, ...] = ()) -> list[str]:
    """Problems in a commit message. Lines starting with '#' are git comments."""
    problems: list[str] = []
    lines = [line for line in text.splitlines() if not line.startswith("#")]
    for index, line in enumerate(lines):
        where = f"message line {index + 1}"
        if CO_AUTHOR_RE.match(line):
            email = EMAIL_IN_LINE_RE.search(line)
            if not (email and BOT_EMAIL_RE.match(email.group(1))):
                problems.append(f"{where}: Co-Authored-By trailer is not allowed")
            continue
        if index > 0 and AI_TRAILER_RE.match(line):
            problems.append(f"{where}: AI tool trailer is not allowed")
        if GENERATED_RE.search(line):
            problems.append(f"{where}: 'generated with' AI line is not allowed")
        if SESSION_URL_RE.search(line):
            problems.append(f"{where}: chat session URL is not allowed")
        problems.extend(
            p.replace(f"line {index + 1}:", f"{where}:", 1)
            for p in check_line("COMMIT_EDITMSG", index + 1, line, denylist)
        )
    return problems


@dataclass(frozen=True)
class Commit:
    sha: str
    author_email: str
    author_offset: str
    committer_email: str
    committer_offset: str
    committed_at: int  # Unix time
    message: str
    author_name: str = ""
    committer_name: str = ""


def git(root: Path, *args: str) -> str:
    """Run a read-only git command in ``root`` and return its stdout."""
    exe = shutil.which("git") or "git"
    result = subprocess.run(  # noqa: S603 - fixed executable, arguments built in this module
        [exe, *args], cwd=root, check=True, capture_output=True, text=True
    )
    return result.stdout


def read_commits(root: Path, rev_args: list[str]) -> list[Commit]:
    """Commits selected by ``git log <rev_args>``, with their original timezone offsets."""
    fmt = "%H%x1f%ae%x1f%ad%x1f%ce%x1f%cd%x1f%ct%x1f%an%x1f%cn%x1f%B%x1e"
    out = git(root, "log", f"--format={fmt}", "--date=format:%z", *rev_args, "--")
    commits = []
    for record in out.split("\x1e"):
        record = record.strip("\n")
        if not record:
            continue
        sha, a_email, a_off, c_email, c_off, c_time, a_name, c_name, message = record.split(
            "\x1f", 8
        )
        commits.append(
            Commit(sha, a_email, a_off, c_email, c_off, int(c_time), message, a_name, c_name)
        )
    return commits


def check_commit(
    commit: Commit, denylist: tuple[str, ...] = (), allowed_names: tuple[str, ...] = ()
) -> list[str]:
    """Identity and offset problems of one commit (messages are checked separately).

    A name containing a local denylist value fails unless it is exactly an allowed author
    name (``allow-author-name:`` in the local file). Without a local file (CI) names are
    not checked, because CI knows no personal values.
    """
    problems: list[str] = []
    for role, name in (("author", commit.author_name), ("committer", commit.committer_name)):
        if name not in allowed_names:
            problems += [
                f"{role} name contains a personal value ({mask(v)})"
                for v in denied_values(name, denylist)
            ]
    author_is_bot = bool(BOT_EMAIL_RE.match(commit.author_email))
    if commit.author_email != ALLOWED_EMAIL and not author_is_bot:
        problems.append(f"author email not allowed: {mask_email(commit.author_email)}")
    if commit.committer_email not in {ALLOWED_EMAIL, GITHUB_COMMITTER} and not BOT_EMAIL_RE.match(
        commit.committer_email
    ):
        problems.append(f"committer email not allowed: {mask_email(commit.committer_email)}")
    # Bot commits carry GitHub's timestamps; everything made locally must be UTC.
    if not author_is_bot:
        for role, offset in (
            ("author", commit.author_offset),
            ("committer", commit.committer_offset),
        ):
            if offset != UTC_OFFSET:
                problems.append(f"{role} offset {mask_offset(offset)} is not {UTC_OFFSET}")
    return problems


def outgoing_rev_args(from_ref: str, to_ref: str) -> list[str]:
    """Commits being pushed: from..to, or everything not on any remote for a new branch."""
    if not from_ref or set(from_ref) == {"0"}:
        return [to_ref, "--not", "--remotes"]
    return [f"{from_ref}..{to_ref}"]
