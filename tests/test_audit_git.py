"""Commit checks: commit-msg rules, identities, +0000 offsets, pre-push and CI ranges.

Each test builds a throwaway repository in tmp_path with global/system git config
disabled, so the developer's own git settings and hooks never take part.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from sepsiscope.audit.denylist import ALLOWED_EMAIL, DENYLIST_FILE
from sepsiscope.audit.gitchecks import (
    ZERO_SHA,
    check_commit,
    check_message,
    outgoing_rev_args,
    read_commits,
)
from sepsiscope.audit.hooks import main as hooks_main

GIT = shutil.which("git") or "git"
BOT = "49699333+dependabot[bot]@users.noreply.github.com"
FOREIGN = "zq" + "@" + "mail.example-domain.net"


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("TZ", "UTC")
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)
    subprocess.run([GIT, "init", "-q", "-b", "main"], check=True)
    return root


def commit(
    message: str, *, tz: str = "UTC", email: str = ALLOWED_EMAIL, committer: str | None = None
) -> str:
    env = {
        **os.environ,
        "TZ": tz,
        "GIT_AUTHOR_NAME": "Maintainer",
        "GIT_AUTHOR_EMAIL": email,
        "GIT_COMMITTER_NAME": "Maintainer",
        "GIT_COMMITTER_EMAIL": committer or email,
    }
    subprocess.run([GIT, "commit", "-q", "--allow-empty", "-m", message], check=True, env=env)
    return subprocess.run(
        [GIT, "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()


# --- commit messages -----------------------------------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        "feat(audit): add a check",
        "docs: mention Claude Code in the AI-assistance notes",  # subject, not a trailer
        "fix: thing\n\nBody text.\n# Please enter the commit message (git comment)",
        f"build(deps): bump x\n\nCo-authored-by: dependabot[bot] <{BOT}>",
        "build(deps): bump x\n\nSigned-off-by: dependabot[bot] <" + "support" + "@github.com>",
    ],
)
def test_clean_messages(message: str) -> None:
    assert check_message(message) == []


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("feat: x\n\nCo-Authored-By: Someone <a" + "@example.com>", "Co-Authored-By"),
        ("feat: x\n\nco-authored-by: AI <noreply" + "@anthropic.com>", "Co-Authored-By"),
        ("feat: x\n\nClaude-Session: abc123", "AI tool trailer"),
        ("feat: x\n\nAssisted-by: ChatGPT", "AI tool trailer"),
        ("feat: x\n\nGenerated with Claude Code", "'generated with' AI line"),
        ("feat: x\n\nsee https://claude" + ".ai/chat/abc", "chat session URL"),
        (f"feat: x\n\nmail {FOREIGN}", "email address not allowed: z****@"),
        ("feat: wait for the Student " + "Pack", "account-tier wording"),
    ],
)
def test_blocked_messages(message: str, expected: str) -> None:
    problems = check_message(message)
    assert any(expected in p for p in problems), problems


def test_message_denylist_is_masked() -> None:
    problems = check_message("fix: typo\n\nThanks Zorblax", ("Zorblax",))
    assert problems == ["message line 3: personal value from the local denylist (Z****)"]


# --- identities and offsets ----------------------------------------------------------


def test_utc_commit_is_clean(repo: Path) -> None:
    commit("feat: one")
    (c,) = read_commits(repo, ["HEAD"])
    assert (c.author_offset, c.committer_offset) == ("+0000", "+0000")
    assert c.message.strip() == "feat: one"
    assert check_commit(c) == []


def test_local_offset_is_flagged_and_masked(repo: Path) -> None:
    commit("feat: one", tz="ABC-1")  # POSIX TZ "ABC-1" = UTC+01:00
    (c,) = read_commits(repo, ["HEAD"])
    assert c.author_offset == "+0100"
    assert check_commit(c) == [
        "author offset +0*** is not +0000",
        "committer offset +0*** is not +0000",
    ]


def test_foreign_identity_is_flagged_and_masked(repo: Path) -> None:
    commit("feat: one", email=FOREIGN)
    (c,) = read_commits(repo, ["HEAD"])
    problems = check_commit(c)
    assert "author email not allowed: z****@mail.example-domain.net" in problems
    assert "committer email not allowed: z****@mail.example-domain.net" in problems


def test_bot_commits_are_exempt_from_the_offset_rule(repo: Path) -> None:
    commit("build(deps): bump", tz="ABC-1", email=BOT, committer="noreply" + "@github.com")
    (c,) = read_commits(repo, ["HEAD"])
    assert check_commit(c) == []


def test_outgoing_rev_args() -> None:
    assert outgoing_rev_args("a" * 40, "b" * 40) == [f"{'a' * 40}..{'b' * 40}"]
    assert outgoing_rev_args(ZERO_SHA, "b" * 40) == ["b" * 40, "--not", "--remotes"]
    assert outgoing_rev_args("", "b") == ["b", "--not", "--remotes"]


# --- hook entry points ---------------------------------------------------------------


def test_commit_msg_hook(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    good = repo / "good.txt"
    good.write_text("feat: fine\n")
    bad = repo / "bad.txt"
    bad.write_text("feat: x\n\nCo-Authored-By: AI <a" + "@example.com>\n")
    assert hooks_main(["commit-msg", str(good)]) == 0
    assert hooks_main(["commit-msg", str(bad)]) == 1
    assert "commit blocked" in capsys.readouterr().out


def test_commit_msg_hook_uses_local_denylist(repo: Path) -> None:
    (repo / DENYLIST_FILE).write_text("Zorblax\n")
    msg = repo / "msg.txt"
    msg.write_text("fix: thanks zorblax\n")
    assert hooks_main(["commit-msg", str(msg)]) == 1


def test_pre_push_checks_only_outgoing_commits(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    old = commit("feat: legacy", tz="ABC-1")  # already pushed in this scenario
    new = commit("feat: new")
    monkeypatch.setenv("PRE_COMMIT_FROM_REF", old)
    monkeypatch.setenv("PRE_COMMIT_TO_REF", new)
    assert hooks_main(["pre-push"]) == 0
    assert "1 commit(s) checked, all clean" in capsys.readouterr().out

    bad = commit("feat: local time", tz="ABC-1")
    monkeypatch.setenv("PRE_COMMIT_TO_REF", bad)
    assert hooks_main(["pre-push"]) == 1
    out = capsys.readouterr().out
    assert f"{bad[:7]}: author offset +0*** is not +0000" in out
    assert "+0100" not in out


def test_pre_push_new_branch_and_delete(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    head = commit("feat: one", tz="ABC-1")
    monkeypatch.setenv("PRE_COMMIT_FROM_REF", ZERO_SHA)  # new branch: nothing on a remote
    monkeypatch.setenv("PRE_COMMIT_TO_REF", head)
    assert hooks_main(["pre-push"]) == 1
    monkeypatch.setenv("PRE_COMMIT_TO_REF", ZERO_SHA)  # branch deletion pushes no commits
    assert hooks_main(["pre-push"]) == 0


def test_ci_commits_subcommand(repo: Path) -> None:
    base = commit("feat: base", tz="ABC-1")
    head = commit("feat: next\n\nCo-Authored-By: AI <a" + "@example.com>")
    assert hooks_main(["commits", "--from", base, "--to", base]) == 0
    assert hooks_main(["commits", "--from", base, "--to", head]) == 1
