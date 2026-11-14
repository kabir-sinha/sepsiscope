"""Byte-identical re-run check (logic in ``sepsiscope.repro``).

Run from the repository's top folder:
``uv run python scripts/byte_check.py --write MANIFEST`` before a re-run, then
``uv run python scripts/byte_check.py --compare MANIFEST`` after it (exit 1 on any
difference). Only ``git_commit`` in ``model.json`` is ignored (ADR 0024 item 7).
"""

from __future__ import annotations

import sys

from sepsiscope.repro import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
