"""Notebooks must be committed output-free and without environment metadata."""

from __future__ import annotations

import json
from typing import Any

ALLOWED_TOP_METADATA = {"kernelspec", "language_info"}
# `version` would record the local interpreter version.
ALLOWED_LANGUAGE_INFO = {
    "name",
    "codemirror_mode",
    "file_extension",
    "mimetype",
    "nbconvert_exporter",
    "pygments_lexer",
}


def check_notebook(raw: bytes) -> list[str]:
    """Problems with a notebook's outputs or metadata (empty list = clean)."""
    try:
        nb: dict[str, Any] = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ["notebook is not valid JSON"]
    problems = []
    metadata = nb.get("metadata", {})
    extra = sorted(set(metadata) - ALLOWED_TOP_METADATA)
    if extra:
        problems.append(f"notebook metadata keys not allowed: {extra}")
    extra_lang = sorted(set(metadata.get("language_info", {})) - ALLOWED_LANGUAGE_INFO)
    if extra_lang:
        problems.append(f"notebook language_info keys not allowed: {extra_lang}")
    for index, cell in enumerate(nb.get("cells", []), start=1):
        if cell.get("outputs"):
            problems.append(f"cell {index} has outputs")
        if cell.get("execution_count") is not None:
            problems.append(f"cell {index} has an execution count")
        if cell.get("metadata"):
            problems.append(f"cell {index} has metadata {sorted(cell['metadata'])}")
    return problems
