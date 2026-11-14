"""Git hook entry points: ``python -m sepsiscope.audit.hooks {commit-msg,pre-push,commits}``.

- ``commit-msg FILE``: rejects AI trailers and personal data in the message.
- ``pre-push``: checks every outgoing commit (pre-commit sets ``PRE_COMMIT_FROM_REF`` and
  ``PRE_COMMIT_TO_REF``): message, identities and ``+0000`` offsets.
- ``commits --from SHA --to SHA``: the same check for CI, on the pushed range.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sepsiscope.audit.denylist import load_allowed_author_names, load_denylist
from sepsiscope.audit.gitchecks import (
    ZERO_SHA,
    check_commit,
    check_message,
    outgoing_rev_args,
    read_commits,
)


def commit_msg(path: Path, root: Path) -> int:
    problems = check_message(path.read_text(encoding="utf-8"), load_denylist(root))
    for problem in problems:
        print(f"commit-msg: {problem}")
    if problems:
        print("commit-msg: commit blocked. Edit the message (no AI trailers, nothing personal).")
    return 1 if problems else 0


def check_range(root: Path, from_ref: str, to_ref: str, label: str) -> int:
    if not to_ref or to_ref == ZERO_SHA:  # deleting a remote branch pushes no commits
        return 0
    denylist = load_denylist(root)
    allowed_names = load_allowed_author_names(root)
    commits = read_commits(root, outgoing_rev_args(from_ref, to_ref))
    failed = False
    for commit in commits:
        found = check_commit(commit, denylist, allowed_names)
        for problem in found + check_message(commit.message, denylist):
            print(f"{label}: {commit.sha[:7]}: {problem}")
            failed = True
    if failed:
        print(f"{label}: blocked. Recreate these commits with TZ=UTC and allowed identities.")
    else:
        print(f"{label}: {len(commits)} commit(s) checked, all clean")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sepsiscope.audit.hooks")
    sub = parser.add_subparsers(dest="command", required=True)
    msg = sub.add_parser("commit-msg")
    msg.add_argument("message_file", type=Path)
    sub.add_parser("pre-push")
    rng = sub.add_parser("commits")
    rng.add_argument("--from", dest="from_ref", default="")
    rng.add_argument("--to", dest="to_ref", required=True)
    args = parser.parse_args(argv)
    root = Path.cwd()
    if args.command == "commit-msg":
        return commit_msg(args.message_file, root)
    if args.command == "pre-push":
        return check_range(
            root,
            os.environ.get("PRE_COMMIT_FROM_REF", ""),
            os.environ.get("PRE_COMMIT_TO_REF", ""),
            "pre-push",
        )
    return check_range(root, args.from_ref, args.to_ref, "commit-check")


if __name__ == "__main__":
    sys.exit(main())
