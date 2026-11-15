"""Positive control for the three history scanners (deep_scan.py, independent_scan.sh,
gitleaks): fake personal values are planted in a throwaway repository, deleted again, and
must still be found in history. Fake values only; each one is assembled at run time so this
file itself never trips the scanners when they scan the real repository.
"""

from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FAKE_ENV = {"HOME": "/fakehome/ctrl-user", "USER": "ctrl-user"}
GIT = shutil.which("git") or "git"
ZSH = shutil.which("zsh") or "zsh"
GITLEAKS = shutil.which("gitleaks") or "gitleaks"


def _env(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env |= {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", **FAKE_ENV}
    return env | extra


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


@pytest.fixture
def planted(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args: str, **extra: str) -> None:
        subprocess.run([GIT, *args], cwd=repo, check=True, env=_env(**extra))

    git("init", "-q", "--template=")
    text = "\n".join(
        [
            "path " + FAKE_ENV["HOME"] + "/x",
            "user " + FAKE_ENV["USER"],
            "mail someone" + "@" + "gmail.com",
            "ip 10.1" + ".2.3 mac " + ":".join(["00", "11", "22", "33", "44", "55"]),
            "Mac" + "Book Pro 16 G" + "B RAM",
            "Claude " + "Max" + " plan",
            "p0" + "12345",
            "Fake" + "name Q",
        ]
    )
    (repo / "a.txt").write_text(text + "\n")
    (repo / "k.py").write_text('TOKEN = "gh' + 'p_aB3dE6gH9jK2mN5pQ8sT1vW4yZ7cF0hJ3lP6"\n')
    header = b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0))
    (repo / "f.png").write_bytes(header + _chunk(b"tEXt", b"Author\x00x") + _chunk(b"IEND", b""))
    who = ("-c", "user.name=t", "-c", "user.email=t@example.com")
    date = "2026-01-02T10:00:00-0700"  # a non-UTC offset, to be counted
    git("add", "a.txt", "k.py", "f.png")
    git(*who, "commit", "-q", "-m", "c", GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
    git("rm", "-q", "a.txt")
    git(*who, "commit", "-q", "-m", "rm")
    (tmp_path / "deny").write_text("Fake" + "name\n" + "allow-author-name: t\n")
    return repo


def test_deep_scan_finds_every_planted_category(planted: Path) -> None:
    deny = planted.parent / "deny"
    r = subprocess.run(
        [sys.executable, "-I", str(ROOT / "scripts" / "deep_scan.py"), str(planted), str(deny)],
        capture_output=True,
        text=True,
        env=_env(),
    )
    assert r.returncode == 0, r.stderr
    for category in [
        "denylist#1",
        "device",
        "email(other)",
        "home-path",
        "ipv4(non-loopback)",
        "mac",
        "patient-id",
        "plan-names",
        "png-meta:tEXt",
        "secret-pattern",
        "username",
    ]:
        assert f"  {category}:" in r.stdout, category
    assert "denylist#2" not in r.stdout  # the allow-author-name line is not a search value
    assert "gmail" not in r.stdout and "Fake" + "name" not in r.stdout  # counts, never values


@pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh not installed")
def test_independent_scan_counts_planted_values(planted: Path) -> None:
    script = ROOT / "scripts" / "independent_scan.sh"
    r = subprocess.run([ZSH, str(script), str(planted)], capture_output=True, text=True, env=_env())
    assert r.returncode == 0, r.stderr
    first = r.stdout.split()
    counts = dict(zip(first[::2], first[1::2], strict=False))
    assert counts["home"] != "0/0" and counts["emails"] == "1"
    assert counts["secrets"] != "0" and counts["non-UTC"] == "1"


@pytest.mark.skipif(shutil.which("gitleaks") is None, reason="gitleaks not installed")
def test_gitleaks_finds_the_planted_token(planted: Path) -> None:
    r = subprocess.run(
        [GITLEAKS, "git", "--no-banner", "--redact", "--log-opts=--all", str(planted)],
        capture_output=True,
        text=True,
    )
    assert r.returncode != 0
    assert "leaks found: 1" in r.stdout + r.stderr


def test_deep_scan_allows_the_attribution_in_its_file_only(tmp_path: Path) -> None:
    """ADR 0025: the exact attribution in web/src/App.tsx is not counted; elsewhere it is."""
    repo = tmp_path / "repo"
    (repo / "web" / "src").mkdir(parents=True)
    first = "Ctrl" + "first"
    line = '<p className="byline">Built by ' + first + "</p>\n"

    def git(*args: str) -> None:
        subprocess.run([GIT, *args], cwd=repo, check=True, env=_env())

    git("init", "-q", "--template=")
    (repo / "web" / "src" / "App.tsx").write_text(line)
    git("add", ".")
    git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", "c")
    deny = tmp_path / "deny"
    deny.write_text(first + "\nallow-author-name: " + first + " Q\n")
    cmd = [sys.executable, "-I", str(ROOT / "scripts" / "deep_scan.py"), str(repo), str(deny)]
    r = subprocess.run(cmd, capture_output=True, text=True, env=_env())
    assert r.returncode == 0, r.stderr
    assert "denylist#1" not in r.stdout
    (repo / "web" / "src" / "Other.tsx").write_text("// copy\n" + line)
    git("add", ".")
    git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", "d")
    r = subprocess.run(cmd, capture_output=True, text=True, env=_env())
    assert "  denylist#1: 1 paths: web/src/Other.tsx" in r.stdout
