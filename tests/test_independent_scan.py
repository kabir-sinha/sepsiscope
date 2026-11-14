"""Positive control for scripts/independent_scan.sh: planted values must be counted, a clean
repository must give zeros, and a git error must stop the scan instead of reading as "0 hits"."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "independent_scan.sh"
FAKE_HOME = "/fakehome/scan-user"
ZSH = shutil.which("zsh") or "zsh"
GIT = shutil.which("git") or "git"
pytestmark = pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh not installed")


def _env(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env |= {"HOME": FAKE_HOME, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    return env | extra


def _git(repo: Path, *args: str, **extra: str) -> None:
    subprocess.run([GIT, "-C", str(repo), *args], check=True, env=_env(**extra))


def _commit(repo: Path, msg: str, date: str = "2026-01-01T00:00:00+0000") -> None:
    _git(repo, "add", "-A")
    _git(
        repo,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.com",
        "commit",
        "-q",
        "-m",
        msg,
        GIT_AUTHOR_DATE=date,
        GIT_COMMITTER_DATE=date,
    )


def _scan(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([ZSH, str(SCRIPT), str(repo)], capture_output=True, text=True, env=_env())


def _counts(out: str) -> dict[str, str]:
    first = out.splitlines()[0].split()
    return dict(zip(first[::2], first[1::2], strict=True))


def test_clean_repo_scans_to_zero(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    for i in range(3):  # several commits: the bug was one unsplit argument for all of them
        (tmp_path / f"f{i}.txt").write_text(f"plain text {i}\n")
        _commit(tmp_path, f"c{i}")
    r = _scan(tmp_path)
    assert r.returncode == 0, r.stderr
    c = _counts(r.stdout)
    assert (c["home"], c["emails"], c["secrets"], c["data-paths"], c["non-UTC"]) == (
        "0/0",
        "0",
        "0",
        "0",
        "0",
    )


def test_planted_values_are_found_even_after_deletion(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    (tmp_path / "keep.txt").write_text("nothing\n")
    _commit(tmp_path, "first")
    email = "who" + "@" + "gmail.com"  # built at run time, so the guard sees no address
    token = "gh" + "p_" + "aB3dE6gH9jK2mN5pQ8sT1vW4yZ7cF0hJ3lP6"  # fake, built at run time
    (tmp_path / "leak.txt").write_text(f"{FAKE_HOME}/x\n{email}\nTOKEN={token}\n")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "p.psv").write_text("HR\n")
    _commit(tmp_path, "planted", date="2026-01-02T10:00:00-0700")
    (tmp_path / "leak.txt").unlink()
    (tmp_path / "data" / "p.psv").unlink()
    _commit(tmp_path, "removed again")  # still in history, so it must still be found
    r = _scan(tmp_path)
    assert r.returncode == 0, r.stderr
    c = _counts(r.stdout)
    assert c["home"].split("/")[0] != "0"
    assert c["emails"] == "1"
    assert c["secrets"] != "0"
    assert c["data-paths"] != "0"
    assert c["non-UTC"] == "1"
    assert re.search(r"gmail|gh[p]_|fakehome", r.stdout) is None  # counts only, never values


def test_not_a_repository_fails_loudly(tmp_path: Path) -> None:
    r = _scan(tmp_path)
    assert r.returncode == 2
    assert "ERROR" in r.stderr


def test_subfolder_of_a_repository_fails_loudly(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "f.txt").write_text("x\n")
    _commit(tmp_path, "c")
    r = _scan(tmp_path / "sub")
    assert r.returncode == 2
    assert "top folder" in r.stderr
