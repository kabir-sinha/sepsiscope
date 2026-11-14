"""Privacy rules shared by the pre-commit guard, CI and ``privacy-audit``.

Personal-looking samples are built from pieces so this file passes its own guard.
"""

from __future__ import annotations

import json
import subprocess
import sys
import zlib
from pathlib import Path

import pytest

from sepsiscope.audit.denylist import (
    ALLOWED_EMAIL,
    DENYLIST_FILE,
    HANDLE,
    denied_values,
    load_denylist,
    name_allowed_on,
)
from sepsiscope.audit.mask import mask, mask_email, mask_offset, mask_values
from sepsiscope.audit.notebook import check_notebook
from sepsiscope.audit.rules import check_content, check_file, check_path, main
from sepsiscope.config import REPO_ROOT

FAKE_NAME = "Zorblax Quint"  # invented; stands in for a real name
MAC_HOME = "/" + "Users/" + "zq/project"
LINUX_HOME = "/" + "home/" + "zq/project"
WIN_HOME = "C:" + "\\" + "Users" + "\\" + "zq"
FOREIGN_EMAIL = "zq" + "@" + "mail.example-domain.net"


def _lines(text: str, name: str = "notes.md", denylist: tuple[str, ...] = ()) -> list[str]:
    return check_content(name, text.encode("utf-8"), denylist)


# --- masking -------------------------------------------------------------------------


def test_masking_helpers() -> None:
    assert mask(FAKE_NAME) == "Z**** Q****"
    assert mask_email(FOREIGN_EMAIL) == "z****@mail.example-domain.net"
    assert mask_offset("+0100") == "+0***"
    assert mask_values(f"by {FAKE_NAME.lower()}", (FAKE_NAME,)) == "by Z**** Q****"


# --- generic patterns ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "label"),
    [
        (f"see {MAC_HOME}/file", "macOS home path"),
        (f"see {LINUX_HOME}", "Linux home path"),
        (f"see {WIN_HOME}\\file", "Windows home path"),
        ("plan treated" + " as Free until later", "account-tier wording"),
        ("waiting for the Student " + "Pack", "account-tier wording"),
        ("the GitHub Pro " + "plan", "account-tier wording"),
        ("bill" + "ing settings", "account-tier wording"),
        ("Student " + "verification pending", "account-tier wording"),
        ("ID E23" + "CSEU0123", "enrollment-ID shape"),
    ],
)
def test_generic_patterns_block(text: str, label: str) -> None:
    problems = _lines(text)
    assert any(label in p for p in problems), problems


@pytest.mark.parametrize(
    "text",
    [
        "Branch protection: pending; rules below, to apply when enabled.",
        "uv run pytest in /usr/local/bin and /tmp/build",
        "the home page and /homepage",
        "a GitHub Actions run on ubuntu-24.04",
        f"contact {ALLOWED_EMAIL} or bot 49699333+dependabot[bot]@users.noreply.github.com",
        "placeholder someone@example.com",
        "hash ABCDEF0123456789",
    ],
)
def test_clean_text_passes(text: str) -> None:
    assert _lines(text) == []


def test_email_is_blocked_and_masked() -> None:
    problems = _lines(f"mail {FOREIGN_EMAIL}")
    assert problems == ["line 1: email address not allowed: z****@mail.example-domain.net"]
    assert FOREIGN_EMAIL not in problems[0]


def test_lockfiles_are_exempt_from_wording_but_not_paths() -> None:
    text = "token E23" + "CSEU0123 at " + MAC_HOME
    problems = check_content("uv.lock", text.encode(), ())
    assert not any("enrollment" in p for p in problems)
    assert any("home path" in p for p in problems)


def test_utf16_and_binary_home_paths() -> None:
    assert any("UTF-16" in p for p in check_content("x.txt", MAC_HOME.encode("utf-16-le")))
    binary = b"\xff\xfe\x00" + MAC_HOME.encode()
    assert any("non-UTF-8" in p for p in check_content("x.bin", binary))


# --- path rules ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        (".env", "environment file"),
        ("web/.env.local", "environment file"),
        ("data/raw/a.csv", "data file"),
        ("notes/p000001.psv", "dataset file type"),
        ("x/table.parquet", "dataset file type"),
        ("mlflow.db", "tracking or tuning store"),
        ("mlruns/mlflow.db", "tracking or tuning store"),
        ("mlruns/optuna/lgbm_A2B.journal", "tracking or tuning store"),
        ("notes/study.sqlite3", "tracking or tuning store"),
        ("models/lgbm_B2A/model.txt", "under models/"),
        ("models/lgbm_A2B/feature_schema.json", "under models/"),
        ("models/baselines/lr_B2A/model.json", "under models/"),
        ("data/demo/demo_B2A.json", "under data/demo/"),
    ],
)
def test_path_rules(name: str, expected: str) -> None:
    assert any(expected in p for p in check_path(name))


def test_ordinary_paths_are_not_stores() -> None:
    assert check_path("docs/plan/batch-b.md") == []
    assert check_path("src/sepsiscope/tracking.py") == []
    assert check_path("src/sepsiscope/models/lgbm.py") == []  # the code package, not outputs
    assert check_path("src/sepsiscope/api/demo.py") == []
    assert check_path("docs/data_card.md") == []


def test_large_file(tmp_path: Path) -> None:
    big = tmp_path / "big.txt"
    big.write_bytes(b"a" * 1_000_001)
    assert any("> 1 MB" in p for p in check_file(str(big)))


# --- PNG and notebook metadata -------------------------------------------------------


def _png(extra_chunk: bytes | None) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data).to_bytes(4, "big")
        return len(data).to_bytes(4, "big") + kind + data + crc

    ihdr = chunk(b"IHDR", (1).to_bytes(4, "big") * 2 + bytes([8, 0, 0, 0, 0]))
    body = chunk(b"IDAT", zlib.compress(b"\x00\x00")) + chunk(b"IEND", b"")
    middle = chunk(b"tEXt", extra_chunk) if extra_chunk else b""
    return b"\x89PNG\r\n\x1a\n" + ihdr + middle + body


def test_png_metadata() -> None:
    assert check_content("a.png", _png(None)) == []
    assert any("tEXt" in p for p in check_content("a.png", _png(b"Software\x00x")))


def _nb(**changes: object) -> bytes:
    nb: dict[str, object] = {
        "cells": [{"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": []}],
        "metadata": {"kernelspec": {"name": "python3"}, "language_info": {"name": "python"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    nb.update(changes)
    return json.dumps(nb).encode()


def test_notebook_clean_and_dirty() -> None:
    assert check_notebook(_nb()) == []
    dirty_cell = {"cell_type": "code", "execution_count": 3, "metadata": {"x": 1}, "outputs": [1]}
    problems = check_notebook(
        _nb(
            cells=[dirty_cell],
            metadata={"language_info": {"name": "python", "version": "3.13"}, "widgets": {}},
        )
    )
    assert len(problems) == 5, problems
    assert check_notebook(b"not json") == ["notebook is not valid JSON"]


def test_committed_notebooks_are_clean() -> None:
    for nb in REPO_ROOT.glob("notebooks/*.ipynb"):
        assert check_notebook(nb.read_bytes()) == [], nb.name


# --- local denylist ------------------------------------------------------------------


def test_denylist_loading(tmp_path: Path) -> None:
    assert load_denylist(tmp_path) == ()
    (tmp_path / DENYLIST_FILE).write_text(
        f"# comment\n{FAKE_NAME}\n\nzq-host  # trailing\nzq-host\n"
    )
    assert load_denylist(tmp_path) == (FAKE_NAME, "zq-host")


def test_denylist_matches_whole_words_and_masks() -> None:
    deny = (FAKE_NAME, "Quint")
    problems = _lines(f"written by {FAKE_NAME.upper()}", denylist=deny)
    assert problems == [
        "line 1: personal value from the local denylist (Z**** Q****)",
        "line 1: personal value from the local denylist (Q****)",
    ]
    assert _lines("a quintessential example", denylist=deny) == []


def test_handle_is_not_a_denylist_hit() -> None:
    first = HANDLE.split("-")[0]
    text = f"git clone https://github.com/{HANDLE}/sepsiscope and @{HANDLE} {ALLOWED_EMAIL}"
    assert denied_values(text, (first,)) == []


def test_name_allowed_only_on_copyright_and_author_lines() -> None:
    copyright_line = f"© 2026 {FAKE_NAME}. All rights reserved."
    author_line = f'    {{ name = "{FAKE_NAME}", email = "{ALLOWED_EMAIL}" }}'
    assert name_allowed_on("README.md", copyright_line)
    assert name_allowed_on("pyproject.toml", author_line)
    assert not name_allowed_on("docs/privacy.md", copyright_line)
    assert not name_allowed_on("README.md", f"Written by {FAKE_NAME}.")
    assert _lines(copyright_line, "README.md", (FAKE_NAME,)) == []
    assert _lines(copyright_line, "docs/x.md", (FAKE_NAME,)) != []


def test_binary_content_checks_denylist() -> None:
    raw = b"\xff\xfe" + FAKE_NAME.encode()
    assert check_content("x.bin", raw, (FAKE_NAME,)) == [
        "personal value from the local denylist (Z**** Q****)"
    ]


# --- entry points --------------------------------------------------------------------


def test_main_masks_and_uses_local_denylist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / DENYLIST_FILE).write_text(FAKE_NAME + "\n")
    (tmp_path / "ok.md").write_text("nothing personal\n")
    (tmp_path / "bad.md").write_text(f"by {FAKE_NAME}\n")
    assert main(["ok.md"]) == 0
    assert main(["ok.md", "bad.md"]) == 1
    out = capsys.readouterr().out
    assert "Z**** Q****" in out
    assert FAKE_NAME not in out


def test_hook_wrapper_script_runs(tmp_path: Path) -> None:
    clean = tmp_path / "clean.md"
    clean.write_text("fine\n")
    dirty = tmp_path / "dirty.md"
    dirty.write_text(f"{LINUX_HOME}\n")
    script = str(REPO_ROOT / "scripts" / "privacy_guard.py")
    ok = subprocess.run(
        [sys.executable, script, str(clean)], capture_output=True, check=False, cwd=tmp_path
    )
    bad = subprocess.run(
        [sys.executable, script, str(dirty)], capture_output=True, check=False, cwd=tmp_path
    )
    assert (ok.returncode, bad.returncode) == (0, 1)
