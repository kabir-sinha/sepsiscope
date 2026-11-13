"""Remove personal paths from log records and CLI error output (plan B6).

Inside the repository a path is rewritten relative to the repository root; any other path
under the home directory starts with ``~``. Installed once by the CLI.
"""

from __future__ import annotations

import logging
import sys
import traceback
from pathlib import Path
from types import TracebackType

from sepsiscope.config import REPO_ROOT


def scrub(text: str, home: Path | None = None, repo: Path = REPO_ROOT) -> str:
    """Repository paths become relative, then the home directory becomes ``~``."""
    home_s = str(home if home is not None else Path.home())
    repo_s = str(repo)
    text = text.replace(repo_s + "/", "").replace(repo_s, ".")
    if home_s not in ("", "/"):
        text = text.replace(home_s, "~")
    return text


class ScrubFilter(logging.Filter):
    """Rewrites the final message (and any traceback) of every record it sees."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = scrub(record.getMessage())
        record.args = None
        if record.exc_info:
            record.exc_text = scrub("".join(traceback.format_exception(*record.exc_info)))
            record.exc_info = None
        return True


def _excepthook(kind: type[BaseException], value: BaseException, tb: TracebackType | None) -> None:
    sys.stderr.write(scrub("".join(traceback.format_exception(kind, value, tb))))


def install() -> None:
    """Filter on every root handler (adding a stderr handler if none) and on tracebacks."""
    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(logging.StreamHandler())
    for handler in root.handlers:
        if not any(isinstance(f, ScrubFilter) for f in handler.filters):
            handler.addFilter(ScrubFilter())
    sys.excepthook = _excepthook
