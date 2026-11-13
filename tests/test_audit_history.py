"""``sepsiscope privacy-audit``: tree, history blobs, messages, offsets, refs; masking;
known (pre-cutoff) versus blocking findings; strict mode.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from conftest import GIT, git_commit
from typer.testing import CliRunner

from sepsiscope.audit.denylist import DENYLIST_FILE, load_denylist
from sepsiscope.audit.history import format_report, run_audit
from sepsiscope.cli import app
from sepsiscope.config import REPO_ROOT

OLD = "2026-10-01T10:00:00"  # before the UTC cutoff (2026-10-22)
NEW = "2026-10-23T10:00:00"
FOREIGN = "zq" + "@" + "mail.example-domain.net"


def _areas(root: Path, strict: bool = False) -> tuple[set[str], set[str]]:
    report = run_audit(root)
    return (
        {f"{f.area}:{f.problem}" for f in report.blocking(strict)},
        {f"{f.area}:{f.problem}" for f in report.known(strict)},
    )


def test_clean_repository(git_repo: Path) -> None:
    (git_repo / "README.md").write_text("hello\n")
    git_commit("docs: readme", date=NEW, add_all=True)
    report = run_audit(git_repo)
    assert report.findings == []
    assert report.scanned["commits"] == 1
    assert format_report(report)[-1].startswith("result   PASS (strict): 0 blocking")


def test_legacy_problems_are_known_until_strict(git_repo: Path) -> None:
    (git_repo / "notes.md").write_text(f"mail {FOREIGN}\n")
    git_commit("docs: notes", tz="ABC-1", date=OLD, add_all=True)
    (git_repo / "notes.md").write_text("cleaned\n")
    git_commit("docs: clean notes", date=NEW, add_all=True)

    blocking, known = _areas(git_repo)
    assert blocking == set()
    assert "commit:author offset +0*** is not +0000" in known
    assert "history:line 1: email address not allowed: z****@mail.example-domain.net" in known

    strict_blocking, strict_known = _areas(git_repo, strict=True)
    assert strict_known == set()
    assert strict_blocking == known


def test_new_commits_must_be_clean(git_repo: Path) -> None:
    git_commit("feat: local time", tz="ABC-1", date=NEW)
    (git_repo / "tmp.md").write_text(f"mail {FOREIGN}\n")
    git_commit("docs: add", date=NEW, add_all=True)
    (git_repo / "tmp.md").unlink()
    git_commit("docs: remove", date=NEW, add_all=True)  # history-only, but after the cutoff
    blocking, _ = _areas(git_repo)
    assert "commit:author offset +0*** is not +0000" in blocking
    assert "history:line 1: email address not allowed: z****@mail.example-domain.net" in blocking


def test_tree_messages_and_refs(git_repo: Path) -> None:
    (git_repo / DENYLIST_FILE).write_text("Zorblax\n")
    (git_repo / "a.md").write_text("by Zorblax\n")
    git_commit("docs: a\n\nCo-Authored-By: AI <x" + "@example.com>", date=NEW)
    subprocess.run([GIT, "add", "a.md"], check=True)
    git_commit("docs: track a", date=NEW)
    subprocess.run([GIT, "branch", "zorblax-notes"], check=True)
    report = run_audit(git_repo)
    lines = "\n".join(format_report(report))
    assert "FAIL     tree     a.md: line 1: personal value from the local denylist (Z****)" in lines
    assert "FAIL     message" in lines
    assert "Co-Authored-By trailer is not allowed" in lines
    assert "FAIL     ref      refs/heads/Z****-notes" in lines
    assert "orblax" not in lines.lower()


def test_png_metadata_in_history(git_repo: Path) -> None:
    png = b"\x89PNG\r\n\x1a\n" + (4).to_bytes(4, "big") + b"tEXtabcd" + b"\x00" * 4
    (git_repo / "fig.png").write_bytes(png)
    git_commit("docs: fig", date=NEW, add_all=True)
    (git_repo / "fig.png").unlink()
    git_commit("docs: drop fig", date=NEW, add_all=True)
    blocking, _ = _areas(git_repo)
    assert any(item.startswith("history:PNG carries metadata chunks") for item in blocking)


def test_cli_on_this_repository_is_masked() -> None:
    result = CliRunner().invoke(app, ["privacy-audit"])
    assert result.exit_code == 0, result.stdout
    assert "result   PASS (strict)" in result.stdout
    for value in load_denylist(REPO_ROOT):  # present only on the maintainer's machine
        assert value.lower() not in result.stdout.lower()


def test_cli_no_strict_lists_known_findings(git_repo: Path) -> None:
    """--no-strict turns legacy findings into 'known'; the default (strict) fails on them."""
    git_commit("docs: legacy", tz="ABC-1", date=OLD)
    git_commit("docs: new", date=NEW)
    report = run_audit(git_repo)
    assert format_report(report)[-1].startswith("result   FAIL (strict): 2 blocking")
    lenient = format_report(report, strict=False)
    assert lenient[-1].startswith("result   PASS (non-strict): 0 blocking, 2 known")
