"""Byte-identical re-run check: a SHA-256 manifest of the pipeline outputs.

Covers ``reports/``, ``models/`` and the demo JSON in ``data/demo/``. Every byte counts,
with one exception (ADR 0024 item 7): the ``git_commit`` value in a model's ``model.json``
records HEAD by design, so it is replaced by a fixed placeholder before hashing. The
manifest holds repository-relative paths and hashes only.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOTS = ("reports", "models")
DEMO_GLOB = "data/demo/*.json"
# Committed manifests live in reports/ but are the reference, not an output.
MANIFEST_GLOB = "manifest_*.json"
_COMMIT = re.compile(rb'"git_commit": "(?:[0-9a-f]{40}|unknown)"')
_PLACEHOLDER = b'"git_commit": "<ignored>"'


def digest(path: Path) -> str:
    """SHA-256 of a file; for ``model.json`` with exactly one ``git_commit`` neutralised."""
    data = path.read_bytes()
    if path.name == "model.json":
        data, n = _COMMIT.subn(_PLACEHOLDER, data)
        if n > 1:
            raise ValueError(f"{path.name}: {n} git_commit fields, expected at most 1")
    return hashlib.sha256(data).hexdigest()


def output_files(root: Path) -> list[Path]:
    """All output files, sorted, as paths under ``root``."""
    files = [p for r in ROOTS for p in (root / r).rglob("*") if p.is_file()]
    files += list(root.glob(DEMO_GLOB))
    return sorted(
        p
        for p in files
        if "__pycache__" not in p.parts
        and p.name != ".DS_Store"
        and not (p.parent == root / "reports" and p.match(MANIFEST_GLOB))
    )


def manifest(root: Path) -> dict[str, str]:
    """Repository-relative path -> SHA-256."""
    return {p.relative_to(root).as_posix(): digest(p) for p in output_files(root)}


def compare(old: dict[str, str], new: dict[str, str]) -> dict[str, list[str]]:
    """Paths that changed, disappeared or appeared."""
    return {
        "changed": sorted(k for k in old.keys() & new.keys() if old[k] != new[k]),
        "missing": sorted(old.keys() - new.keys()),
        "added": sorted(new.keys() - old.keys()),
    }


def main(argv: list[str]) -> int:
    """``--write FILE`` saves the manifest; ``--compare FILE`` exits 1 on any difference."""
    if len(argv) != 2 or argv[0] not in ("--write", "--compare"):
        print("usage: byte_check.py --write FILE | --compare FILE")
        return 2
    root = Path.cwd()
    path = Path(argv[1])
    now = manifest(root)
    if argv[0] == "--write":
        path.write_text(json.dumps(now, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {len(now)} hashes")
        return 0
    diff = compare(json.loads(path.read_text(encoding="utf-8")), now)
    for kind, paths in diff.items():
        for p in paths:
            print(f"{kind}: {p}")
    bad = sum(len(v) for v in diff.values())
    print(f"{len(now)} files, {bad} differences" + (" (identical)" if not bad else ""))
    return 1 if bad else 0
