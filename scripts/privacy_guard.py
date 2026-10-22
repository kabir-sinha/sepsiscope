"""pre-commit hook: block personal data in staged files.

Usage (pre-commit passes the staged file names): ``python scripts/privacy_guard.py FILE...``
Exit code 1 (commit blocked) if any file violates a rule. The rules live in
``sepsiscope.audit.rules`` so the hook, CI and ``sepsiscope privacy-audit`` share them.
"""

from __future__ import annotations

import sys

from sepsiscope.audit.rules import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
