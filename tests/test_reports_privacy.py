"""Tracked result files hold no patient IDs and nothing personal (plan P3)."""

from __future__ import annotations

import getpass
import re
import socket
from pathlib import Path

from sepsiscope.audit.denylist import ALLOWED_EMAIL
from sepsiscope.config import REPO_ROOT

PATIENT_ID = re.compile(r"\bp\d{6}\b")
GITHUB_ACCOUNT = ALLOWED_EMAIL.split("+", 1)[1].split("@", 1)[0]


def test_report_json_files_hold_no_ids_or_personal_values() -> None:
    files = sorted((REPO_ROOT / "reports").rglob("*.json"))
    assert files, "expected tracked result files"
    personal = [str(Path.home()), getpass.getuser(), socket.gethostname(), GITHUB_ACCOUNT]
    for path in files:
        text = path.read_text(encoding="utf-8")
        name = path.relative_to(REPO_ROOT).as_posix()
        assert not PATIENT_ID.search(text), f"{name}: patient ID"
        for value in personal:
            assert value.lower() not in text.lower(), f"{name}: personal value"
