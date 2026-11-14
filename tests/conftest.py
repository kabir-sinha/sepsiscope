"""Shared test helpers: tiny synthetic patient files (never real data)."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest

from sepsiscope.audit.denylist import ALLOWED_EMAIL
from sepsiscope.data.download import LOCAL_SUBDIR
from sepsiscope.data.io import COLUMNS, HOSPITAL_DIRS

WritePatient = Callable[..., Path]


def psv_text(
    labels: Sequence[int],
    *,
    iculos_start: int = 1,
    overrides: dict[str, Sequence[float | str]] | None = None,
) -> str:
    """Build the text of one synthetic patient file with plausible values."""
    n = len(labels)
    base: dict[str, list[str]] = {name: ["NaN"] * n for name in COLUMNS}
    base["HR"] = [str(70 + i) for i in range(n)]
    base["O2Sat"] = ["97"] * n
    base["Temp"] = ["36.8"] * n
    base["SBP"] = ["120"] * n
    base["MAP"] = ["85"] * n
    base["DBP"] = ["65"] * n
    base["Resp"] = ["16"] * n
    base["Age"] = ["60.5"] * n
    base["Gender"] = ["1"] * n
    base["Unit1"] = ["1"] * n
    base["Unit2"] = ["0"] * n
    base["HospAdmTime"] = ["-5.2"] * n
    base["ICULOS"] = [str(iculos_start + i) for i in range(n)]
    base["SepsisLabel"] = [str(v) for v in labels]
    for name, values in (overrides or {}).items():
        assert len(values) == n, name
        base[name] = [str(v) for v in values]
    lines = ["|".join(COLUMNS)]
    lines += ["|".join(base[name][i] for name in COLUMNS) for i in range(n)]
    return "\n".join(lines) + "\n"


class NetworkBlockedError(AssertionError):
    """A test tried to use the network."""


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Safety net: no test may look up a hostname or open a real network connection.

    Socket-level, standard library only. Unix-domain sockets (AF_UNIX) stay allowed
    because local tooling uses them and they never leave the machine.
    """
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def connect(self: socket.socket, address: Any) -> None:
        if self.family == socket.AF_UNIX:
            return real_connect(self, address)
        raise NetworkBlockedError(f"test tried to connect to {address!r}")

    def connect_ex(self: socket.socket, address: Any) -> int:
        if self.family == socket.AF_UNIX:
            return real_connect_ex(self, address)
        raise NetworkBlockedError(f"test tried to connect to {address!r}")

    def getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
        raise NetworkBlockedError(f"test tried to resolve the hostname {host!r}")

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)


@pytest.fixture
def raw_root(tmp_path: Path) -> Path:
    root = tmp_path / "raw"
    for dirname in HOSPITAL_DIRS.values():
        (root / LOCAL_SUBDIR / dirname).mkdir(parents=True)
    return root


@pytest.fixture
def write_patient(raw_root: Path) -> WritePatient:
    def _write(hospital: str, number: int, labels: Sequence[int], **kwargs: object) -> Path:
        offset = 0 if hospital == "A" else 100_000
        path = raw_root / LOCAL_SUBDIR / HOSPITAL_DIRS[hospital] / f"p{offset + number:06d}.psv"
        path.write_text(psv_text(labels, **kwargs), encoding="utf-8")  # type: ignore[arg-type]
        return path

    return _write


@pytest.fixture
def tiny_dataset(raw_root: Path, write_patient: WritePatient) -> Path:
    """Five patients across two hospitals with known counts."""
    write_patient("A", 1, [0, 0, 0, 0])  # non-septic
    write_patient("A", 2, [0, 0, 1, 1, 1])  # septic, onset mid-stay
    write_patient("A", 3, [1, 1, 1], iculos_start=4)  # septic from row 0, ICULOS starts late
    write_patient("B", 1, [0, 0, 0, 0, 0, 0])
    write_patient(
        "B",
        2,
        [0, 1],
        overrides={
            "FiO2": [0.5, 4000],
            "Unit1": ["NaN", "NaN"],
            "Unit2": ["NaN", "NaN"],
            "HospAdmTime": ["NaN", -1.0],
        },
    )
    return raw_root


# --- throwaway git repositories (privacy-audit and hook tests) -------------------------

GIT = shutil.which("git") or "git"


@pytest.fixture
def git_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty repository; global/system git config (and thus user hooks) disabled."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("TZ", "UTC")
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)
    subprocess.run([GIT, "init", "-q", "-b", "main"], check=True)
    return root


def git_commit(
    message: str,
    *,
    tz: str = "UTC",
    email: str = ALLOWED_EMAIL,
    committer: str | None = None,
    date: str | None = None,
    add_all: bool = False,
    name: str = "Maintainer",
) -> str:
    """Commit in the current directory with a chosen timezone, identity and date."""
    env = {
        **os.environ,
        "TZ": tz,
        "GIT_AUTHOR_NAME": name,
        "GIT_AUTHOR_EMAIL": email,
        "GIT_COMMITTER_NAME": name,
        "GIT_COMMITTER_EMAIL": committer or email,
    }
    if date:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date
    if add_all:
        subprocess.run([GIT, "add", "-A"], check=True)
    subprocess.run([GIT, "commit", "-q", "--allow-empty", "-m", message], check=True, env=env)
    return subprocess.run(
        [GIT, "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
